#!/usr/bin/env python3
# "RUTA DE NEUSTRO ARCHIVO", por ejemplo: /opt/iptables-monitor/poll_monitor.py
import os, ssl, smtplib, subprocess, time
from email.message import EmailMessage

import os, ssl, smtplib, subprocess, time
from email.message import EmailMessage

SMTP_HOST  = os.environ["SMTP_HOST"]
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER  = os.environ["SMTP_USER"]
SMTP_PASS  = os.environ["SMTP_PASS"]
EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO   = os.environ["EMAIL_TO"]
INTERVAL   = 5  # segundos

EVENTS = {
  "EVT_SSH_DROP": "[ALERTA] Intento SSH bloqueado (x{n})",
  "EVT_HTTP_NAT": "[INFO] Acceso HTTP por NAT (x{n})",
  "EVT_DROP_DEFAULT": "[ALERTA] Paquete descartado por defecto (x{n})",
}

def read_counters():
    out = subprocess.run(["iptables", "-vnL"],
                         capture_output=True, text=True).stdout
    counters = {}
    for line in out.splitlines():
        for key in EVENTS:
            if f"/* {key} */" in line:
                counters[key] = int(line.split()[0])
    return counters

def notify(subject):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = EMAIL_FROM, EMAIL_TO, subject
    msg.set_content(f"Detectado por polling de contadores.\n{subject}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

previous = read_counters()
while True:
    time.sleep(INTERVAL)
    current = read_counters()
    for key, template in EVENTS.items():
        delta = current.get(key, 0) - previous.get(key, 0)
        if delta > 0:
            notify(template.format(n=delta))
    previous = current
