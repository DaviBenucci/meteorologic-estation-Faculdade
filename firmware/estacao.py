from machine import Pin, I2C, ADC
from bmp280 import BMP280
import network
import requests
import dht
import time
import json

from config import WIFI_SSID, WIFI_SENHA, URL_MEDICOES

INTERVALO_LEITURA_MS = 5000
INTERVALO_ENVIO_MS = 7000
INTERVALO_WIFI_MS = 10000
TIMEOUT_HTTP_S = 3
MQ135_HABILITADO = True


def conectar_wifi(wlan, ultima_tentativa):
    """Retorna (IP ou None, ticks da última tentativa de conexão)."""
    agora = time.ticks_ms()
    tentar = ultima_tentativa is None or time.ticks_diff(agora, ultima_tentativa) >= INTERVALO_WIFI_MS
    try:
        if wlan.isconnected():
            return wlan.ifconfig()[0], None
        if not tentar:
            return None, ultima_tentativa

        wlan.active(True)
        wlan.config(reconnects=0)
        wlan.disconnect()
        wlan.connect(WIFI_SSID, WIFI_SENHA)
        print("[Wi-Fi] Tentativa de conexão iniciada.")
        ip = wlan.ifconfig()[0] if wlan.isconnected() else None
        return ip, agora
    except (OSError, ValueError) as erro:
        if tentar:
            print("[Wi-Fi] Falha na conexão:", erro)
        return None, agora if tentar else ultima_tentativa


def ler_sensores(sensores):
    inicio = time.ticks_ms()
    leituras = {
        "temperatura_DHT": None,
        "umidade": None,
        "temperatura_BMP": None,
        "pressao_BMP": None,
        "luminosidade": None,
        "gas": None,
    }

    try:
        if "bmp" not in sensores:
            i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)
            sensores["bmp"] = BMP280(i2c, address=0x76)
        temperatura, pressao = sensores["bmp"].read()
        leituras["temperatura_BMP"], leituras["pressao_BMP"] = temperatura, pressao
    except (OSError, ValueError, TypeError) as erro:
        sensores.pop("bmp", None)
        print("[BMP280] Falha na leitura:", erro)

    try:
        if "dht" not in sensores:
            sensores["dht"] = dht.DHT22(Pin(4))
        sensor = sensores["dht"]
        sensor.measure()
        temperatura = sensor.temperature()
        umidade = sensor.humidity()
        leituras["temperatura_DHT"], leituras["umidade"] = temperatura, umidade
    except (OSError, ValueError, TypeError) as erro:
        sensores.pop("dht", None)
        print("[DHT22] Falha na leitura:", erro)

    try:
        if "ldr" not in sensores:
            sensores["ldr"] = Pin(27, Pin.IN)
        leituras["luminosidade"] = sensores["ldr"].value()
    except (OSError, ValueError, TypeError) as erro:
        sensores.pop("ldr", None)
        print("[LDR] Falha na leitura:", erro)

    if MQ135_HABILITADO:
        try:
            if "mq135" not in sensores:
                mq135 = ADC(Pin(34))
                mq135.atten(ADC.ATTN_11DB)
                sensores["mq135"] = mq135
            leituras["gas"] = sensores["mq135"].read()
        except (OSError, ValueError, TypeError) as erro:
            sensores.pop("mq135", None)
            print("[MQ-135] Falha na leitura:", erro)

    duracao = time.ticks_diff(time.ticks_ms(), inicio)
    print("[Sensores] Leitura concluída. Duração: %d ms:" % duracao, leituras)
    return leituras


def preparar_dados(leituras):
    return json.dumps(leituras)


def enviar_medicoes(wlan, leituras):
    inicio = time.ticks_ms()
    resposta = None
    try:
        if not wlan.isconnected():
            print("[HTTP] Wi-Fi desconectado. Dados não enviados.")
            return False
        # ponytail: HTTP síncrono pode atrasar leituras; usar I/O assíncrono se precisar cadência rígida.
        resposta = requests.post(
            URL_MEDICOES,
            data=preparar_dados(leituras),
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_HTTP_S,
        )
        duracao = time.ticks_diff(time.ticks_ms(), inicio)
        if resposta.status_code == 200:
            print("[HTTP] Medição aceita (HTTP 200). Duração do POST: %d ms." % duracao)
            return True
        print("[HTTP] Envio recusado (HTTP %d). Duração do POST: %d ms." % (resposta.status_code, duracao))
    except (OSError, ValueError, TypeError) as erro:
        duracao = time.ticks_diff(time.ticks_ms(), inicio)
        print("[HTTP] Falha no envio após %d ms:" % duracao, erro)
    finally:
        if resposta is not None:
            try:
                resposta.close()
            except OSError as erro:
                print("[HTTP] Falha ao fechar a resposta:", erro)
    return False


def main():
    wlan = network.WLAN(network.STA_IF)
    sensores = {}
    ultima_tentativa_wifi = None
    ip_anterior = None
    ultima_leitura = None
    ultimo_envio = None
    leituras = None

    while True:
        ip_esp32, ultima_tentativa_wifi = conectar_wifi(wlan, ultima_tentativa_wifi)
        if ip_esp32 and ip_esp32 != ip_anterior:
            print("[Wi-Fi] Conectado. IP do ESP32:", ip_esp32)
        ip_anterior = ip_esp32
        agora = time.ticks_ms()
        if ultima_leitura is None or time.ticks_diff(agora, ultima_leitura) >= INTERVALO_LEITURA_MS:
            ultima_leitura = agora
            leituras = ler_sensores(sensores)

        agora = time.ticks_ms()
        if not ip_esp32:
            ultimo_envio = None
        elif ultimo_envio is None or time.ticks_diff(agora, ultimo_envio) >= INTERVALO_ENVIO_MS:
            ultimo_envio = agora
            enviar_medicoes(wlan, leituras)

        time.sleep_ms(100)


if __name__ == "__main__":
    main()
