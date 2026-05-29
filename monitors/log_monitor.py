#!/usr/bin/env python3
# “RUTA DE NUESTRO ARCHIVO” por ejemplo: /opt/iptables-monitor/log_monitor.py
import os, re, ssl, smtplib, subprocess
from email.message import EmailMessage

LOG_PATH   = "/var/log/kern.log"
SMTP_HOST  = os.environ["SMTP_HOST"]
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER  = os.environ["SMTP_USER"]
SMTP_PASS  = os.environ["SMTP_PASS"]
EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO   = os.environ["EMAIL_TO"]

EVENTS = {
  "EVT_SSH_DROP":     "[ALERTA] Intento SSH bloqueado",
  "EVT_HTTP_NAT":     "[INFO] Acceso HTTP por NAT",
  "EVT_DROP_DEFAULT": "[ALERTA] Paquete descartado por defecto",
}

FIELD_RE = re.compile(r"(SRC|DST|PROTO|SPT|DPT)=(\S+)")

def notify(subject, body):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = EMAIL_FROM, EMAIL_TO, subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

def handle(line):
    for key, subject in EVENTS.items():
        if f"[{key}]" in line:
            f = dict(FIELD_RE.findall(line))
            body = (f"Evento: {key}\n"
                    f"SRC:    {f.get('SRC','?')}\n"
                    f"DST:    {f.get('DST','?')}\n"
                    f"Proto:  {f.get('PROTO','?')} "
                    f"{f.get('SPT','?')} -> {f.get('DPT','?')}\n\n"
                    f"Línea original:\n{line}")
            notify(subject, body); return

with subprocess.Popen(["tail", "-F", "-n0", LOG_PATH],
                      stdout=subprocess.PIPE, text=True) as proc:
    for line in proc.stdout:
        handle(line.strip())
