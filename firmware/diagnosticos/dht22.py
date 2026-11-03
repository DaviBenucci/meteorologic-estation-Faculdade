from machine import Pin
import dht
import time

sensor = dht.DHT22(Pin(4))

while True:
    try:
        sensor.measure()
        print(f"A Temperatura é de {sensor.temperature():.2f} °C")
        print(f"A humidade é de {sensor.humidity():.2f}")
        time.sleep(5)
    except OSError as erro:
        print(f"houve um erro de comunicação:{erro}, por favor aguarde 5s e tentaremos novamente.")
        time.sleep(5)
    except ValueError as erro:
        print(f"o dispositivo retornou um valor incongruente {erro}, por favor aguar 5s e tentaremos novamente.")
        time.sleep(5)
    except TypeError as erro:
        print(f"o dispositivo retornou um Tipo desconhecido {erro}, por favor aguar 5s e tentaremos novamente.")
        time.sleep(5)
