import network
import requests
from config import URL_MEDICOES

wlan = network.WLAN(network.STA_IF)

print("Wi-Fi conectado:", wlan.isconnected())
print("IP do ESP32:", wlan.ifconfig()[0])

url = URL_MEDICOES.rstrip("/") + "/ultima"

resposta = None

try:
    resposta = requests.get(url)

    print("Status HTTP:", resposta.status_code)
    print("Dados recebidos:", resposta.text)

except OSError as erro:
    print("Erro de comunicação:", erro)

finally:
    if resposta is not None:
        resposta.close()
