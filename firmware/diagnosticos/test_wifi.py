from config import WIFI_SSID, WIFI_SENHA

import network
import time

ssid = WIFI_SSID
senha = WIFI_SENHA

wlan = network.WLAN(network.STA_IF)

wlan.active(True)

print("Tentando conectar ao Wi-Fi...")

wlan.connect(ssid, senha)

tentativas = 0

while not wlan.isconnected() and tentativas < 10:
    print("Aguardando conexão...")
    time.sleep(1)
    tentativas += 1

if wlan.isconnected():
    print("Conectado ao Wi-Fi!")
    print("IP:", wlan.ifconfig()[0])
else:
    print("Não foi possível conectar.")