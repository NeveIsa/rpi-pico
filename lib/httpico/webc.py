import network
from config import config
from socket import socket, SOCK_STREAM, AF_INET

# LOAD CONFIG
apconf = config["ACCESSPOINT"]

# INIT AP
ap = network.WLAN(network.AP_IF)
ap.active(False)
ap.config(ssid=apconf["ssid"], password=apconf["pass"])
ap.active(True)  # start AP

html = open("webconfig.html").read()


# create a web-server to get settings
def webconfig():
    sock = socket(AF_INET, SOCK_STREAM)
    sock.bind(("0.0.0.0", 80))
    sock.listen()
    conn, addr = sock.accept()
    conn.sendall(html)
    return
    while True:
        data = conn.recv(1024)
        if not data:
            break
        conn.sendall(data)
