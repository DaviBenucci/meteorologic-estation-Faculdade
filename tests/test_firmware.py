import importlib.util
import json
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from BackEnd.models import Medicao


class StopMain(Exception):
    pass


class Ticks:
    period = 1 << 30

    def __init__(self):
        self.now = 0
        self.stop_at = 0

    def ticks_ms(self):
        return self.now % self.period

    def ticks_diff(self, first, second):
        return (first - second + self.period // 2) % self.period - self.period // 2

    def sleep_ms(self, duration):
        if not 0 <= duration <= 100:
            raise AssertionError("Pausa longa no laço principal")
        self.now += duration
        if self.now >= self.stop_at:
            raise StopMain()


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.clock = Ticks()
        self.ldr = Mock()
        self.ldr.value.return_value = 0
        self.pin = Mock(side_effect=lambda number, *args: self.ldr if number == 27 else number)
        self.pin.IN = 0
        self.i2c = Mock()
        self.adc = Mock()
        self.adc.read.return_value = 169
        self.adc_constructor = Mock(return_value=self.adc)
        self.adc_constructor.ATTN_11DB = 3
        self.bmp = Mock()
        self.bmp.read.return_value = (25.57, 923.28)
        self.bmp_constructor = Mock(return_value=self.bmp)
        self.dht = Mock()
        self.dht.temperature.return_value = 23.9
        self.dht.humidity.return_value = 83.8
        self.dht_constructor = Mock(return_value=self.dht)
        self.wlan = Mock()
        self.wlan.isconnected.return_value = True
        self.wlan.ifconfig.return_value = ("192.0.2.2", "255.255.255.0", "192.0.2.1", "192.0.2.1")
        self.posts = []
        self.responses = []
        self.requests = SimpleNamespace(post=Mock(side_effect=self.post))
        self.config = SimpleNamespace(
            WIFI_SSID="rede-de-teste", WIFI_SENHA="senha-de-teste",
            URL_MEDICOES="http://192.0.2.1:8000/medicoes",
        )
        modules = {
            "config": self.config,
            "machine": SimpleNamespace(Pin=self.pin, I2C=self.i2c, ADC=self.adc_constructor),
            "bmp280": SimpleNamespace(BMP280=self.bmp_constructor),
            "network": SimpleNamespace(STA_IF=0, WLAN=Mock(return_value=self.wlan)),
            "dht": SimpleNamespace(DHT22=self.dht_constructor),
            "requests": self.requests,
            "time": self.clock,
        }
        path = Path(__file__).resolve().parents[1] / "firmware" / "estacao.py"
        spec = importlib.util.spec_from_file_location("estacao_em_teste", path)
        self.firmware = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", modules):
            spec.loader.exec_module(self.firmware)
        self.firmware.print = Mock()

    def post(self, url, *, data, headers, timeout):
        self.posts.append((self.clock.now, json.loads(data)))
        self.assertEqual(url, self.config.URL_MEDICOES)
        self.assertEqual(headers, {"Content-Type": "application/json"})
        self.assertEqual(timeout, 3)
        response = SimpleNamespace(status_code=200, close=Mock())
        self.responses.append(response)
        return response

    def run_main(self, duration=61000, start=0):
        self.clock.now = start
        self.clock.stop_at = start + duration
        with self.assertRaises(StopMain):
            self.firmware.main()

    def test_importacao_nao_inicia_hardware_ou_rede(self):
        self.pin.assert_not_called()
        self.i2c.assert_not_called()
        self.adc_constructor.assert_not_called()
        self.firmware.network.WLAN.assert_not_called()

    def test_conectar_wifi_retorna_ip_da_rede_atual(self):
        self.assertEqual(self.firmware.conectar_wifi(self.wlan, 0), ("192.0.2.2", None))
        self.wlan.ifconfig.assert_called_once_with()
        self.wlan.connect.assert_not_called()

    def test_conectar_wifi_sem_ip_preserva_intervalo_de_tentativas(self):
        self.wlan.isconnected.return_value = False
        self.assertEqual(self.firmware.conectar_wifi(self.wlan, None), (None, 0))
        self.clock.now = 1000
        self.assertEqual(self.firmware.conectar_wifi(self.wlan, 0), (None, 0))
        self.wlan.ifconfig.assert_not_called()
        self.wlan.connect.assert_called_once_with(self.config.WIFI_SSID, self.config.WIFI_SENHA)

    def test_conectar_wifi_retorna_ip_se_conectar_imediatamente(self):
        self.wlan.isconnected.side_effect = [False, True]
        self.assertEqual(self.firmware.conectar_wifi(self.wlan, None), ("192.0.2.2", 0))
        self.wlan.ifconfig.assert_called_once_with()

    def test_main_informa_ip_sem_repetir_e_atualiza_apos_reconexao(self):
        self.wlan.isconnected.side_effect = lambda: not 1000 <= self.clock.now < 2000
        self.wlan.ifconfig.side_effect = lambda: (
            "192.0.2.2" if self.clock.now < 3000 else "192.0.2.3",
            "255.255.255.0", "192.0.2.1", "192.0.2.1",
        )
        self.run_main(duration=4000)
        mensagens = [
            call.args for call in self.firmware.print.call_args_list
            if call.args[0] == "[Wi-Fi] Conectado. IP do ESP32:"
        ]
        self.assertEqual(mensagens, [
            ("[Wi-Fi] Conectado. IP do ESP32:", "192.0.2.2"),
            ("[Wi-Fi] Conectado. IP do ESP32:", "192.0.2.2"),
            ("[Wi-Fi] Conectado. IP do ESP32:", "192.0.2.3"),
        ])
        self.assertEqual([instant for instant, _ in self.posts], [0, 2000])

    def test_leitura_5s_envio_7s_primeiro_imediato_e_pinos_preservados(self):
        reads = []
        self.bmp.read.side_effect = lambda: (reads.append(self.clock.now) or 25.57, 923.28)
        self.run_main()
        self.assertEqual(reads, list(range(0, 61000, 5000)))
        self.assertEqual([instant for instant, _ in self.posts], list(range(0, 61000, 7000)))
        self.assertEqual(self.dht.measure.call_count, 13)
        self.assertEqual(self.ldr.value.call_count, 13)
        self.i2c.assert_called_once_with(0, sda=21, scl=22, freq=100000)
        self.bmp_constructor.assert_called_once_with(self.i2c.return_value, address=0x76)
        self.dht_constructor.assert_called_once_with(4)
        self.pin.assert_any_call(27, self.pin.IN)
        self.adc_constructor.assert_called_once_with(34)
        self.adc.atten.assert_called_once_with(self.adc_constructor.ATTN_11DB)
        for _, data in self.posts:
            self.assertEqual(data["gas"], 169)
            self.assertEqual(Medicao.model_validate(data).model_dump(), data)
        for response in self.responses:
            response.close.assert_called_once()

    def test_intervalos_funcionam_na_virada_do_contador(self):
        start = self.clock.period - 2000
        self.run_main(start=start)
        self.assertEqual([instant - start for instant, _ in self.posts], list(range(0, 61000, 7000)))
        self.assertEqual(self.bmp.read.call_count, 13)

    def test_log_leitura_mostra_duracao_em_vez_do_contador(self):
        def read():
            self.clock.now += 137
            return 25.57, 923.28
        self.bmp.read.side_effect = read
        for start in (2500000, self.clock.period - 50):
            with self.subTest(start=start):
                self.clock.now = start
                data = self.firmware.ler_sensores({})
                self.firmware.print.assert_called_with(
                    "[Sensores] Leitura concluída. Duração: 137 ms:", data,
                )

    def test_log_http_mostra_duracao_ate_resposta_inclusive_na_virada(self):
        for status in (200, 503):
            for start in (2500000, self.clock.period - 50):
                with self.subTest(status=status, start=start):
                    response = SimpleNamespace(status_code=status, close=Mock())
                    def post(*args, **kwargs):
                        self.clock.now += 250
                        return response
                    self.requests.post.side_effect = post
                    self.clock.now = start
                    self.assertEqual(self.firmware.enviar_medicoes(self.wlan, {}), status == 200)
                    message = (
                        "[HTTP] Medição aceita (HTTP 200). Duração do POST: 250 ms."
                        if status == 200 else
                        "[HTTP] Envio recusado (HTTP 503). Duração do POST: 250 ms."
                    )
                    self.firmware.print.assert_called_with(message)
                    response.close.assert_called_once()

    def test_log_timeout_mostra_tempo_decorrido_e_preserva_erro(self):
        error = OSError("ETIMEDOUT")
        def fail(*args, **kwargs):
            self.clock.now += 3000
            raise error
        self.requests.post.side_effect = fail
        self.clock.now = self.clock.period - 50
        self.assertFalse(self.firmware.enviar_medicoes(self.wlan, {}))
        self.firmware.print.assert_called_with("[HTTP] Falha no envio após 3000 ms:", error)

    def test_falhas_individuais_nao_reutilizam_valores_e_recuperam(self):
        sensors = {}
        previous = self.firmware.ler_sensores(sensors)
        self.assertEqual(previous["umidade"], 83.8)
        self.bmp.read.side_effect = OSError("sensor ausente")
        self.dht.humidity.side_effect = ValueError("leitura inválida")
        data = self.firmware.ler_sensores(sensors)
        for field in ("temperatura_DHT", "umidade", "temperatura_BMP", "pressao_BMP"):
            self.assertIsNone(data[field])
        self.assertEqual(data["luminosidade"], 0)
        self.assertEqual(json.loads(self.firmware.preparar_dados(data))["gas"], 169)
        self.assertEqual(previous["umidade"], 83.8)
        self.bmp.read.side_effect = None
        self.dht.humidity.side_effect = None
        self.assertEqual(self.firmware.ler_sensores(sensors), previous)

    def test_falha_na_inicializacao_bmp_nao_interrompe_demais_sensores(self):
        self.bmp_constructor.side_effect = [OSError("I2C indisponível"), self.bmp]
        sensors = {}
        first = self.firmware.ler_sensores(sensors)
        self.assertIsNone(first["temperatura_BMP"])
        self.assertIsNone(first["pressao_BMP"])
        self.assertEqual(first["temperatura_DHT"], 23.9)
        self.assertEqual(self.firmware.ler_sensores(sensors)["pressao_BMP"], 923.28)

    def test_envio_usa_a_leitura_atual_mesmo_quando_sensor_falha_no_instante_do_post(self):
        def measure():
            if 35000 <= self.clock.now < 40000:
                raise OSError("DHT22 indisponível")
        self.dht.measure.side_effect = measure
        self.run_main()
        self.assertEqual(self.posts[0][1]["temperatura_DHT"], 23.9)
        self.assertEqual(self.posts[5][0], 35000)
        self.assertIsNone(self.posts[5][1]["temperatura_DHT"])
        self.assertIsNone(self.posts[5][1]["umidade"])
        self.assertEqual(self.posts[5][1]["pressao_BMP"], 923.28)
        self.assertEqual(self.posts[6][1]["temperatura_DHT"], 23.9)

    def test_ldr_falho_vira_null_sem_afetar_outros_campos(self):
        sensors = {}
        self.firmware.ler_sensores(sensors)
        self.ldr.value.side_effect = TypeError("leitura inválida")
        data = self.firmware.ler_sensores(sensors)
        self.assertIsNone(data["luminosidade"])
        self.assertEqual(data["umidade"], 83.8)

    def test_mq135_habilitado_preserva_adc_e_falha_vira_null(self):
        self.firmware.MQ135_HABILITADO = True
        sensors = {}
        self.assertEqual(self.firmware.ler_sensores(sensors)["gas"], 169)
        self.adc_constructor.assert_called_once_with(34)
        self.adc.atten.assert_called_once_with(self.adc_constructor.ATTN_11DB)
        self.adc.read.side_effect = OSError("falha ADC")
        self.assertIsNone(self.firmware.ler_sensores(sensors)["gas"])
        self.adc.read.side_effect = None
        self.assertEqual(self.firmware.ler_sensores(sensors)["gas"], 169)
        self.firmware.MQ135_HABILITADO = False
        count = self.adc.read.call_count
        self.assertIsNone(self.firmware.ler_sensores(sensors)["gas"])
        self.assertEqual(self.adc.read.call_count, count)

    def test_primeiro_envio_ocorre_assim_que_wifi_conecta(self):
        self.wlan.isconnected.side_effect = lambda: self.clock.now >= 1200
        self.run_main(duration=2000)
        self.assertEqual([instant for instant, _ in self.posts], [1200])
        self.wlan.connect.assert_called_once_with(self.config.WIFI_SSID, self.config.WIFI_SENHA)
        self.wlan.config.assert_called_once_with(reconnects=0)

    def test_wifi_sem_rede_mantem_leituras_e_reconecta_sem_reenviar_fila_antiga(self):
        attempts = []
        self.wlan.isconnected.side_effect = lambda: self.clock.now >= 85000
        self.wlan.connect.side_effect = lambda *args: attempts.append(self.clock.now)
        self.bmp.read.side_effect = lambda: (self.clock.now / 1000, 923.28)
        self.run_main(duration=91000)
        self.assertEqual(attempts, list(range(0, 85000, 10000)))
        self.assertEqual(self.bmp.read.call_count, 19)
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.posts[0][0], 85000)
        self.assertEqual(self.posts[0][1]["temperatura_BMP"], 85.0)

    def test_excecao_wifi_nao_encerra_monitoramento(self):
        self.wlan.isconnected.return_value = False
        self.wlan.connect.side_effect = OSError("rede indisponível")
        self.run_main()
        self.assertEqual(self.wlan.connect.call_count, 7)
        self.assertEqual(self.bmp.read.call_count, 13)
        self.requests.post.assert_not_called()

    def test_wifi_retorna_apos_longa_queda_com_contador_circular(self):
        self.clock.period = 1 << 16
        self.wlan.isconnected.side_effect = lambda: self.clock.now < 1000 or self.clock.now >= 80000
        self.run_main(duration=81000)
        self.assertEqual([instant for instant, _ in self.posts], [0, 80000])
        self.assertEqual(self.bmp.read.call_count, 17)

    def test_http_com_falha_nao_gera_tentativas_excessivas_nem_interrompe_leituras(self):
        attempts = []
        reads = []
        self.bmp.read.side_effect = lambda: (reads.append(self.clock.now) or 25.57, 923.28)
        def fail(*args, **kwargs):
            attempts.append(self.clock.now)
            self.clock.now += 3000
            raise OSError("timeout")
        self.requests.post.side_effect = fail
        self.run_main()
        self.assertEqual(attempts, list(range(0, 61000, 7000)))
        self.assertGreaterEqual(reads[-1], 56000)
        self.assertTrue(all(5000 <= later - earlier <= 8000 for earlier, later in zip(reads, reads[1:])))

    def test_http_recusado_fecha_resposta_e_permite_proximo_envio(self):
        response = SimpleNamespace(status_code=503, close=Mock(side_effect=OSError("falha no fechamento")))
        self.requests.post.side_effect = [response]
        data = self.firmware.ler_sensores({})
        self.assertFalse(self.firmware.enviar_medicoes(self.wlan, data))
        response.close.assert_called_once()
        self.requests.post.side_effect = self.post
        self.assertTrue(self.firmware.enviar_medicoes(self.wlan, data))
        self.responses[-1].close.assert_called_once()

    def test_http_sem_wifi_ou_requests_sem_timeout_nao_trava(self):
        data = self.firmware.ler_sensores({})
        self.wlan.isconnected.return_value = False
        self.assertFalse(self.firmware.enviar_medicoes(self.wlan, data))
        self.requests.post.assert_not_called()
        self.wlan.isconnected.return_value = True
        self.requests.post.side_effect = TypeError("timeout não suportado")
        self.assertFalse(self.firmware.enviar_medicoes(self.wlan, data))

    def test_configuracao_exemplo_possui_somente_valores_de_exemplo(self):
        path = Path(__file__).resolve().parents[1] / "firmware" / "config_example.py"
        config = runpy.run_path(str(path))
        self.assertEqual(config["WIFI_SSID"], "SEU_SSID")
        self.assertEqual(config["WIFI_SENHA"], "SUA_SENHA")
        self.assertEqual(config["URL_MEDICOES"], "http://192.0.2.1:8000/medicoes")

    def test_diagnosticos_wifi_e_http_usam_configuracao_compartilhada(self):
        path = Path(__file__).resolve().parents[1] / "firmware" / "diagnosticos"
        response = SimpleNamespace(status_code=200, text="{}", close=Mock())
        get = Mock(return_value=response)
        modules = {
            "config": self.config,
            "network": SimpleNamespace(STA_IF=0, WLAN=Mock(return_value=self.wlan)),
            "requests": SimpleNamespace(get=get),
        }
        with patch.dict("sys.modules", modules), patch("builtins.print"):
            runpy.run_path(str(path / "test_wifi.py"))
            runpy.run_path(str(path / "consultar_medicoes.py"))
        self.wlan.connect.assert_called_once_with(self.config.WIFI_SSID, self.config.WIFI_SENHA)
        get.assert_called_once_with(self.config.URL_MEDICOES + "/ultima")
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
