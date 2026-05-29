# Ejemplo 1: SSH desde fuera de la red de confianza
iptables -A INPUT -p tcp --dport 22 -s 192.168.2.0/24 -j LOG --log-prefix "[EVT_SSH_DROP] " --log-level info
iptables -A INPUT -p tcp --dport 22 -s 192.168.2.0/24 -j DROP

# Ejemplo 2: HTTP que cruza el NAT al servidor interno
iptables -A FORWARD -p tcp -d 192.168.0.2 --dport 80 -j LOG --log-prefix "[EVT_HTTP_NAT] " --log-level info
iptables -A FORWARD -p tcp -d 192.168.0.2 --dport 80 -j ACCEPT

# Ejemplo 3: cualquier paquete que llega al final de INPUT de una red que no es de confianza y se descarta
iptables -A INPUT -s 192.168.2.0/24 -j LOG --log-prefix "[EVT_DROP_DEFAULT] " --log-level info
iptables -A INPUT -s 192.168.2.0/24 -j DROP
