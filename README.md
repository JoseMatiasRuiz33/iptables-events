# iptables-events

**Trabajo 2 — Gestión y Administración de Redes**
*Jose Matías Ruiz Valero*

Sistema de captura de eventos sobre el cortafuegos del [Trabajo 1](https://github.com/) (cortafuegos perimetral con IPTables). El proyecto añade al firewall una capa de observabilidad: identifica eventos concretos del tráfico de red, los señaliza desde el espacio del kernel y dispara una notificación por correo electrónico al administrador.

**Vídeo de la demostración:** *(añadir aquí el enlace antes de la entrega)*

**Memoria completa:** [`Memoria_Def_Gestión y Administración de Redes Trabajo 2.pdf`](./Memoria_Def_Gesti%C3%B3n%20y%20Administraci%C3%B3n%20de%20Redes%20Trabajo%202.pdf)

---

## Idea general

IPTables vive en el kernel (ring 0), así que no se le pueden enganchar hooks directamente. Para reaccionar a sus eventos desde el espacio de usuario el proyecto implementa **dos enfoques complementarios**:

| Método | Cómo detecta el evento | Latencia | Detalle |
| --- | --- | --- | --- |
| **`log_monitor.py`** | Sigue `/var/log/kern.log` con `tail -F` y busca el prefijo de la regla `-j LOG` | Casi inmediata | Alto (SRC, DST, puerto, protocolo) |
| **`poll_monitor.py`** | Cada 5 s ejecuta `iptables -vnL` y compara los contadores con la lectura anterior | Hasta el periodo de polling | Bajo (solo nº de impactos) |

Cuando alguno detecta un evento, envía un correo SMTP con STARTTLS contra Gmail.

## Eventos monitorizados

| Evento | Cadena | Condición | Prefijo de log |
| --- | --- | --- | --- |
| **E1 — SSH bloqueado** | `INPUT` | TCP dport 22 desde 192.168.2.0/24 | `[EVT_SSH_DROP]` |
| **E2 — HTTP por NAT** | `FORWARD` | TCP dport 80 hacia 192.168.0.2 | `[EVT_HTTP_NAT]` |
| **E3 — Descarte por defecto** | `INPUT` | Cualquier paquete desde 192.168.2.0/24 | `[EVT_DROP_DEFAULT]` |

## Maqueta de red

```
   Red WAN 192.168.2.0/24          Red LAN 192.168.0.0/24
                                                            
   ┌─────────┐    ┌────────────────────┐    ┌──────────┐    
   │ Cliente │────│      Router        │────│ Servidor │    
   │ Debian  │    │ Debian + IPTables  │    │ Debian   │    
   │         │    │  + monitor.py      │    │          │    
   └─────────┘    └─────────┬──────────┘    └──────────┘    
                            │ STARTTLS                       
                            ▼                                
                      Servidor SMTP (Gmail)                  
                            │                                
                            ▼                                
                       Buzón admin                           
```

---

## Estructura del repositorio

```
iptables-events/
├── README.md                              # este fichero
├── Memoria_…Trabajo 2.pdf                 # memoria completa con diagramas
├── firewall.sh                            # reglas con LOG --log-prefix
├── config/
│   └── config.env.ejemplo                 # plantilla SMTP (sin secretos)
├── monitors/
│   ├── log_monitor.py                     # método 1: análisis de logs
│   └── poll_monitor.py                    # método 2: polling de contadores
└── systemd/
    ├── iptables-log-monitor.service       # unidad para log_monitor
    └── iptables-poll-monitor.service      # unidad para poll_monitor
```

---

## Requisitos previos

En el router (Debian):

```bash
sudo apt update
sudo apt install -y iptables python3 rsyslog
sudo systemctl enable --now rsyslog
```

> **`rsyslog` es imprescindible** para el método 1. Algunas instalaciones modernas de Debian no lo traen por defecto y, sin él, el fichero `/var/log/kern.log` no se crea y `log_monitor.py` no tendría nada que leer.

Además necesitas una **cuenta de Gmail con contraseña de aplicación** (no se puede usar la contraseña normal del correo):

1. En la cuenta emisora, activar la **verificación en dos pasos**.
2. Acceder a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Crear una contraseña de aplicación con cualquier nombre identificativo (p. ej. `router-iptables`).
4. Copiar la cadena de 16 caracteres **sin los espacios**.

---

## Instalación paso a paso

### 1. Clonar y desplegar

```bash
git clone <url-del-repo> iptables-events
cd iptables-events

# Scripts de monitor
sudo mkdir -p /opt/iptables-monitor
sudo cp monitors/log_monitor.py  /opt/iptables-monitor/
sudo cp monitors/poll_monitor.py /opt/iptables-monitor/
sudo chmod 755 /opt/iptables-monitor/*.py
```

### 2. Configurar las credenciales SMTP

```bash
sudo mkdir -p /etc/iptables-monitor
sudo cp config/config.env.ejemplo /etc/iptables-monitor/config.env
sudo nano /etc/iptables-monitor/config.env
```

Sustituir los valores de ejemplo por los reales. Importante:

- **Sin comillas** alrededor de los valores.
- **Sin espacios** alrededor del signo `=`.
- La contraseña de aplicación va **sin los espacios** que muestra Google.

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-cuenta@gmail.com
SMTP_PASS=abcdefghijklmnop
EMAIL_FROM=tu-cuenta@gmail.com
EMAIL_TO=tu-correo-personal@gmail.com
```

Proteger el fichero (contiene una contraseña en claro):

```bash
sudo chmod 600 /etc/iptables-monitor/config.env
sudo chown root:root /etc/iptables-monitor/config.env
```

### 3. Cargar las reglas de IPTables

El script `firewall.sh` añade las reglas `LOG` con prefijo sobre tu firewall del Trabajo 1. Ejecutarlo como root:

```bash
sudo bash firewall.sh
sudo iptables -L -nv --line-numbers   # verificar
```

### 4. Permitir la salida que el monitor necesita

**Punto crítico.** Con política `OUTPUT DROP` por defecto, el router se bloquea a sí mismo y no puede ni resolver DNS ni enviar el correo. Hay que abrir explícitamente:

```bash
# Loopback (DNS local y servicios internos)
sudo iptables -A OUTPUT -o lo -j ACCEPT
sudo iptables -A INPUT  -i lo -j ACCEPT

# Respuestas a conexiones iniciadas por el router
sudo iptables -A INPUT  -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# DNS saliente
sudo iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# SMTP saliente para el envío del correo
sudo iptables -A OUTPUT -p tcp --dport 587 -j ACCEPT
```

### 5. Probar el envío antes de seguir

Conviene confirmar que las credenciales y la salida funcionan antes de montar nada como servicio. Cargar el entorno y enviar un correo de prueba:

```bash
set -a
source /etc/iptables-monitor/config.env
set +a
python3 - <<'PY'
import os, smtplib, ssl
from email.message import EmailMessage
msg = EmailMessage()
msg["From"]    = os.environ["EMAIL_FROM"]
msg["To"]      = os.environ["EMAIL_TO"]
msg["Subject"] = "Prueba desde el router"
msg.set_content("Si lees esto, el SMTP funciona correctamente.")
with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=10) as s:
    s.starttls(context=ssl.create_default_context())
    s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
    s.send_message(msg)
print("OK")
PY
```

Si llega el correo a la bandeja de `EMAIL_TO`, todo está listo para activar los monitores.

### 6. Instalar los servicios systemd

Antes de copiar las unidades, hay que editar la línea `ExecStart=` y poner la ruta real de cada script (en los ficheros pone `nuestra_ruta_del_script_log` y `nuestra_ruta_del_script_poll` como placeholder):

```bash
sudo nano systemd/iptables-log-monitor.service
# Cambiar:
#   ExecStart=/usr/bin/python3 nuestra_ruta_del_script_log
# Por:
#   ExecStart=/usr/bin/python3 /opt/iptables-monitor/log_monitor.py

sudo nano systemd/iptables-poll-monitor.service
# Cambiar:
#   ExecStart=/usr/bin/python3 nuestra_ruta_del_script_poll
# Por:
#   ExecStart=/usr/bin/python3 /opt/iptables-monitor/poll_monitor.py
```

Copiar y activar las unidades:

```bash
sudo cp systemd/iptables-log-monitor.service  /etc/systemd/system/
sudo cp systemd/iptables-poll-monitor.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now iptables-log-monitor.service
sudo systemctl enable --now iptables-poll-monitor.service

# Comprobación
sudo systemctl status iptables-log-monitor.service
sudo systemctl status iptables-poll-monitor.service
```

---

## Uso y demostración

Con los dos monitores corriendo, desde el **Cliente** (192.168.2.2) se disparan los tres eventos:

| Evento | Comando desde el cliente | Correo esperado |
| --- | --- | --- |
| **E1** | `ssh root@192.168.2.1` | `[ALERTA] Intento SSH bloqueado` |
| **E2** | `curl http://192.168.2.1/` | `[INFO] Acceso HTTP por NAT` |
| **E3** | `ping 192.168.2.1` | `[ALERTA] Paquete descartado por defecto` |

Hay multiplicidad de ejemplos, a mí se me ha ocurrido utilizar estos

Para ver en directo lo que va detectando cada monitor:

```bash
sudo journalctl -fu iptables-log-monitor.service
sudo journalctl -fu iptables-poll-monitor.service
sudo tail -F /var/log/kern.log         # las líneas crudas que produce IPTables
```

Con el método 1 el correo llega casi al instante. Con el método 2 puede tardar hasta 5 segundos (el periodo del bucle de polling) y el asunto incluye el contador de impactos: `(x3)`, `(x7)`, etc.

---

## Resolución de problemas

**`Connection timed out` al enviar el correo.**
Las reglas de OUTPUT están bloqueando la salida al puerto 587. Aplica el bloque del paso 4 (DNS + SMTP + loopback + estado).

**`Communication error to X.X.X.X#53 timeout` al resolver DNS.**
El resolver `X.X.X.X` es el de la red NAT de VirtualBox y no es alcanzable desde la interfaz del router. Apunta a un DNS público:

```bash
echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf
```

**`535 Authentication failed` desde Gmail.**
- La contraseña de `config.env` es la **normal** de la cuenta, no la de aplicación.
- La verificación en dos pasos no está activada en la cuenta emisora.
- Se ha copiado la contraseña con los espacios intermedios que muestra Google.

**El servicio dice "Unit could not be found".**
La unidad systemd no está creada o no se hizo `daemon-reload`. Repite el paso 6.

---

## Notas de diseño

- Las reglas `LOG` deben ir siempre **antes** de la regla `DROP` correspondiente. Si va al revés, IPTables descarta el paquete antes de pasarlo a `LOG` y no queda traza, esto lo comentábamos en el anterior trabajo.
- El espacio al final del prefijo (`"[EVT_SSH_DROP] "`) es deliberado: separa el identificador del resto de campos (`IN=`, `OUT=`, `SRC=`, etc.) que vuelca el kernel.
- Para el método 2 las reglas se identifican por comentario con `-m comment --comment "EVT_..."`, lo que permite reconocerlas en `iptables -vnL` sin depender de su orden.
- Los servicios systemd tienen `Restart=on-failure` con `RestartSec=3`, así que se reinician solos si el script peta por una pérdida momentánea de red SMTP.

