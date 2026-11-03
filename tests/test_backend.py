from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from BackEnd import storage
from BackEnd.main import app


SAMPLE = {
    "temperatura_DHT": 23.9,
    "umidade": 83.8,
    "temperatura_BMP": 25.57,
    "pressao_BMP": 923.28,
    "luminosidade": 0,
    "gas": None,
}


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.default_database = storage.CAMINHO_BANCO
        cls.database = Path(cls.temporary.name) / "data" / "estacao.db"
        cls.database_patch = patch.object(storage, "CAMINHO_BANCO", cls.database)
        cls.database_patch.start()
        cls.start_server()

    @classmethod
    def start_server(cls):
        cls.socket = socket.socket()
        cls.socket.bind(("127.0.0.1", 0))
        cls.base_url = f"http://127.0.0.1:{cls.socket.getsockname()[1]}"
        cls.server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_config=None, lifespan="on"))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={"sockets": [cls.socket]}, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 5
        while not cls.server.started:
            if time.monotonic() > deadline or not cls.thread.is_alive():
                raise RuntimeError("O servidor de teste não iniciou")
            time.sleep(0.01)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.database_patch.stop()
        cls.temporary.cleanup()

    @classmethod
    def stop_server(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise RuntimeError("O servidor de teste não encerrou")
        cls.socket.close()

    def setUp(self):
        self.assertEqual(storage.CAMINHO_BANCO, self.database)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM medicoes")

    def request(self, method, path, payload=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base_url + path, data=body, method=method,
                          headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            return response.status, json.loads(body) if "application/json" in content_type else body

    def test_sem_medicoes(self):
        self.assertEqual(self.request("GET", "/medicoes/ultima"), (200, {"status": "sem_medicoes"}))

    def test_alertas_limites_nulos_e_multiplos(self):
        self.assertEqual(self.request("GET", "/alertas/atuais")[1]["estado"], "INDISPONIVEL")
        for temperatura, umidade, estado, ids in (
            (29.9, 30, "NORMAL", []),
            (30, 50, "ATENCAO", ["temperatura_elevada"]),
            (31, 29.9, "ATENCAO", ["temperatura_elevada", "umidade_baixa"]),
            (20, 80, "ATENCAO", ["umidade_elevada"]),
            (20, 81, "ATENCAO", ["umidade_elevada"]),
            (None, 50, "INDISPONIVEL", []),
            (31, None, "ATENCAO", ["temperatura_elevada"]),
            (None, None, "INDISPONIVEL", []),
        ):
            with self.subTest(temperatura=temperatura, umidade=umidade):
                self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": temperatura, "umidade": umidade})
                status, data = self.request("GET", "/alertas/atuais")
                self.assertEqual(status, 200)
                self.assertEqual(data["estado"], estado)
                self.assertEqual([item["id"] for item in data["alertas"]], ids)
                self.assertIsNotNone(data["recebida_em"])
                if ids:
                    self.assertTrue({"variavel", "valor", "limite", "unidade", "mensagem"} <= data["alertas"][0].keys())

    def test_alertas_desatualizacao_e_recuperacao(self):
        now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            utc.now.return_value = now
            self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": 35})
            utc.now.return_value = now + timedelta(seconds=90)
            self.assertEqual(self.request("GET", "/alertas/atuais")[1]["estado"], "ATENCAO")
            utc.now.return_value = now + timedelta(seconds=91)
            stale = self.request("GET", "/alertas/atuais")[1]
            self.assertEqual(stale["estado"], "INDISPONIVEL")
            self.assertEqual([a["id"] for a in stale["alertas"]], ["estacao_desatualizada"])
            self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": 25, "umidade": 50})
            self.assertEqual(self.request("GET", "/alertas/atuais")[1]["estado"], "NORMAL")

    def test_post_get_preserva_campos_e_null(self):
        self.assertEqual(self.request("POST", "/medicoes", SAMPLE), (200, {"status": "recebido"}))
        status, data = self.request("GET", "/medicoes/ultima")
        self.assertEqual(status, 200)
        self.assertEqual({field: data[field] for field in SAMPLE}, SAMPLE)
        self.assertEqual(set(data), set(SAMPLE) | {"recebida_em", "idade_segundos", "desatualizada"})
        self.assertIsNone(data["gas"])
        received = datetime.fromisoformat(data["recebida_em"].replace("Z", "+00:00"))
        self.assertEqual(received.utcoffset(), timedelta(0))
        self.assertLess(abs((datetime.now(timezone.utc) - received).total_seconds()), 5)
        self.assertGreaterEqual(data["idade_segundos"], 0)
        self.assertFalse(data["desatualizada"])

    def test_limites_null_omitidos_e_zeros(self):
        for payload in ({}, dict.fromkeys(SAMPLE), dict.fromkeys(SAMPLE, 0), {"umidade": 100, "luminosidade": 1, "gas": 4095}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request("POST", "/medicoes", payload)[0], 200)
                data = self.request("GET", "/medicoes/ultima")[1]
                self.assertEqual({field: data[field] for field in SAMPLE}, {field: payload.get(field) for field in SAMPLE})

    def test_dados_invalidos_nao_substituem_medicao(self):
        self.request("POST", "/medicoes", SAMPLE)
        previous = self.request("GET", "/medicoes/ultima")[1]
        invalid = [
            {"umidade": -0.1}, {"umidade": 100.1}, {"umidade": "83.8"}, {"umidade": True},
            {"luminosidade": -1}, {"luminosidade": 2}, {"luminosidade": 0.5},
            {"luminosidade": "1"}, {"luminosidade": False},
            {"gas": "123"}, {"gas": 1.5}, {"gas": True},
            {"gas": 2**63}, {"gas": -(2**63) - 1},
            {"temperatura_DHT": "quente"}, {"temperatura_BMP": False},
            {"pressao_BMP": []}, [],
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                status, data = self.request("POST", "/medicoes", payload)
                self.assertEqual(status, 422)
                self.assertTrue(data["detail"])
                current = self.request("GET", "/medicoes/ultima")[1]
                self.assertEqual(current["recebida_em"], previous["recebida_em"])
                self.assertEqual({field: current[field] for field in SAMPLE}, SAMPLE)
        for raw in (b'{', b'null'):
            with self.subTest(raw=raw):
                self.assertEqual(self.request("POST", "/medicoes", raw=raw)[0], 422)

    def test_numeros_nao_finitos_recebem_422(self):
        for number in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(number=number):
                status, data = self.request("POST", "/medicoes", raw=f'{{"temperatura_DHT":{number}}}'.encode())
                self.assertEqual(status, 422)
                self.assertTrue(data["detail"])
                self.assertEqual(self.request("GET", "/medicoes/ultima")[1], {"status": "sem_medicoes"})

    def test_limite_de_90_segundos_e_retorno_da_estacao(self):
        received = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            utc.now.return_value = received
            self.request("POST", "/medicoes", SAMPLE)
            for age, stale in ((0, False), (89.999, False), (90, False), (90.001, True), (150, True)):
                with self.subTest(age=age):
                    utc.now.return_value = received + timedelta(seconds=age)
                    status, data = self.request("GET", "/medicoes/ultima")
                    self.assertEqual(status, 200)
                    self.assertAlmostEqual(data["idade_segundos"], age)
                    self.assertEqual(data["desatualizada"], stale)
                    self.assertEqual({field: data[field] for field in SAMPLE}, SAMPLE)
            utc.now.return_value = received + timedelta(seconds=150)
            self.request("POST", "/medicoes", SAMPLE)
            data = self.request("GET", "/medicoes/ultima")[1]
            self.assertFalse(data["desatualizada"])
            self.assertEqual(data["idade_segundos"], 0)
            self.assertEqual(datetime.fromisoformat(data["recebida_em"].replace("Z", "+00:00")), received + timedelta(seconds=150))

    def test_envios_a_cada_30_segundos_renovam_a_comunicacao(self):
        received = datetime(2026, 11, 3, tzinfo=timezone.utc)
        payload = {**SAMPLE, "gas": None}
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            for elapsed in (0, 30, 60, 90):
                utc.now.return_value = received + timedelta(seconds=elapsed)
                self.assertEqual(self.request("POST", "/medicoes", payload), (200, {"status": "recebido"}))
                data = self.request("GET", "/medicoes/ultima")[1]
                self.assertEqual(datetime.fromisoformat(data["recebida_em"].replace("Z", "+00:00")), received + timedelta(seconds=elapsed))
                self.assertEqual(data["idade_segundos"], 0)
                self.assertFalse(data["desatualizada"])
                self.assertIsNone(data["gas"])
            utc.now.return_value += timedelta(seconds=91)
            self.assertTrue(self.request("GET", "/medicoes/ultima")[1]["desatualizada"])

    def test_get_nao_renova_comunicacao_e_cliente_nao_define_metadados(self):
        received = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            utc.now.return_value = received
            self.request("POST", "/medicoes", {**SAMPLE, "recebida_em": "2000-01-01T00:00:00Z", "desatualizada": False})
            utc.now.return_value = received + timedelta(seconds=91)
            for _ in range(2):
                data = self.request("GET", "/medicoes/ultima")[1]
                self.assertEqual(datetime.fromisoformat(data["recebida_em"].replace("Z", "+00:00")), received)
                self.assertEqual(data["idade_segundos"], 91)
                self.assertTrue(data["desatualizada"])
            self.assertEqual(len(self.request("GET", "/medicoes/historico")[1]), 1)

    def test_caminho_absoluto_schema_e_indice_criados_automaticamente(self):
        expected = Path(storage.__file__).resolve().parent / "data" / "estacao.db"
        self.assertEqual(self.default_database, expected)
        self.assertTrue(self.database.is_file())
        with closing(sqlite3.connect(self.database)) as connection:
            columns = {row[1]: row for row in connection.execute("PRAGMA table_info(medicoes)")}
            self.assertEqual(columns["id"][2], "INTEGER")
            self.assertEqual(columns["id"][5], 1)
            for field in ("temperatura_DHT", "umidade", "temperatura_BMP", "pressao_BMP"):
                self.assertEqual(columns[field][2], "REAL")
            for field in ("luminosidade", "gas"):
                self.assertEqual(columns[field][2], "INTEGER")
                self.assertEqual(columns[field][3], 0)
            self.assertEqual(columns["recebida_em"][2], "TEXT")
            plan = connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM medicoes ORDER BY recebida_em DESC, id DESC LIMIT ?", (10,)
            ).fetchall()
            self.assertTrue(any("idx_medicoes_recebida_em" in row[3] for row in plan))

    def test_historico_vazio(self):
        self.assertEqual(self.request("GET", "/medicoes/historico"), (200, []))

    def test_historico_limite_ordem_cronologica_e_desempate_por_id(self):
        received = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            for seconds, temperature in ((30, 23.9), (0, 24.1), (30, 24.3)):
                utc.now.return_value = received + timedelta(seconds=seconds)
                self.assertEqual(self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": temperature})[0], 200)
        status, data = self.request("GET", "/medicoes/historico?limite=2")
        self.assertEqual(status, 200)
        self.assertEqual([item["temperatura_DHT"] for item in data], [23.9, 24.3])
        self.assertLess(data[0]["id"], data[1]["id"])
        self.assertIsNone(data[0]["gas"])
        self.assertEqual(set(data[0]), set(SAMPLE) | {"id", "recebida_em"})

    def test_historico_limites_padrao_e_maximo(self):
        for _ in range(103):
            storage.salvar_medicao(storage.Medicao(**SAMPLE))
        self.assertEqual(len(self.request("GET", "/medicoes/historico")[1]), 100)
        self.assertEqual(len(self.request("GET", "/medicoes/historico?limite=1")[1]), 1)
        self.assertEqual(len(self.request("GET", "/medicoes/historico?limite=1000")[1]), 103)

    def test_historico_rejeita_limites_invalidos_e_injecao_sql(self):
        self.request("POST", "/medicoes", SAMPLE)
        for value in ("0", "-1", "1001", "abc", "1.5", "", "1%3BDROP%20TABLE%20medicoes"):
            with self.subTest(value=value):
                status, data = self.request("GET", "/medicoes/historico?limite=" + value)
                self.assertEqual(status, 422)
                self.assertTrue(data["detail"])
        self.assertEqual(len(self.request("GET", "/medicoes/historico")[1]), 1)

    def test_historico_filtra_periodo_em_ordem_cronologica(self):
        received = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            for elapsed, temperature in ((-7200, 20.0), (-1800, 21.0), (0, 22.0)):
                utc.now.return_value = received + timedelta(seconds=elapsed)
                self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": temperature})
            utc.now.return_value = received
            status, data = self.request("GET", "/medicoes/historico?periodo=1h")
            for period in ("6h", "24h"):
                self.assertEqual(len(self.request("GET", "/medicoes/historico?periodo=" + period)[1]), 3)
                self.assertEqual(self.request("GET", "/medicoes/estatisticas?periodo=" + period)[1]["quantidade"], 3)
        self.assertEqual(status, 200)
        self.assertEqual([item["temperatura_DHT"] for item in data], [21.0, 22.0])
        self.assertTrue(data[0]["recebida_em"] < data[1]["recebida_em"])
        self.assertEqual(self.request("GET", "/medicoes/historico?periodo=2h")[0], 422)

    def test_periodos_em_minutos_no_historico_e_estatisticas(self):
        now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            for minutes in (0, 7, 12, 20):
                utc.now.return_value = now - timedelta(minutes=minutes)
                storage.salvar_medicao(storage.Medicao(**SAMPLE))
            utc.now.return_value = now
            for period, expected in (("5m", 1), ("10m", 2), ("15m", 3)):
                with self.subTest(period=period):
                    history = self.request("GET", "/medicoes/historico?periodo=" + period)[1]
                    stats = self.request("GET", "/medicoes/estatisticas?periodo=" + period)[1]
                    self.assertEqual(len(history), expected)
                    self.assertEqual(stats["quantidade"], expected)

    def test_historico_limitado_cobre_inicio_e_fim_do_periodo(self):
        received = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            for minutes in range(10):
                utc.now.return_value = received + timedelta(minutes=minutes)
                storage.salvar_medicao(storage.Medicao(**{**SAMPLE, "temperatura_DHT": 20 + minutes}))
            utc.now.return_value = received + timedelta(minutes=10)
            data = self.request("GET", "/medicoes/historico?periodo=1h&limite=3")[1]
        self.assertEqual(len(data), 3)
        self.assertEqual([data[0]["temperatura_DHT"], data[-1]["temperatura_DHT"]], [20, 29])

    def test_estatisticas_ignoram_null_e_retorna_estado_vazio(self):
        status, empty = self.request("GET", "/medicoes/estatisticas?periodo=1h")
        self.assertEqual(status, 200)
        self.assertEqual(empty["quantidade"], 0)
        self.assertIsNone(empty["temperatura_DHT"]["media"])
        self.request("POST", "/medicoes", {
            **SAMPLE, "temperatura_DHT": 20.0, "temperatura_BMP": None,
            "umidade": None, "pressao_BMP": 1000.0,
        })
        self.request("POST", "/medicoes", {
            **SAMPLE, "temperatura_DHT": 24.0, "temperatura_BMP": 26.0,
            "umidade": 60.0, "pressao_BMP": 1010.0,
        })
        stats = self.request("GET", "/medicoes/estatisticas")[1]
        self.assertEqual(stats["quantidade"], 2)
        self.assertEqual(stats["temperatura_DHT"], {"minima": 20.0, "maxima": 24.0, "media": 22.0})
        self.assertEqual(stats["temperatura_BMP"], {"minima": 26.0, "maxima": 26.0, "media": 26.0})
        self.assertEqual(stats["umidade"], {"minima": 60.0, "maxima": 60.0, "media": 60.0})
        self.assertEqual(stats["pressao_BMP"], {"minima": 1000.0, "maxima": 1010.0, "media": 1005.0})

    def test_ultima_e_a_ultima_inserida_mesmo_se_relogio_retroceder(self):
        received = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            utc.now.return_value = received
            self.request("POST", "/medicoes", SAMPLE)
            utc.now.return_value -= timedelta(seconds=30)
            self.request("POST", "/medicoes", {**SAMPLE, "temperatura_DHT": 24.2})
            data = self.request("GET", "/medicoes/ultima")[1]
            self.assertEqual(data["temperatura_DHT"], 24.2)
            self.assertEqual(data["idade_segundos"], 0)
            utc.now.return_value -= timedelta(seconds=30)
            self.assertEqual(self.request("GET", "/medicoes/ultima")[1]["idade_segundos"], 0)

    def test_inicializacao_repetida_preserva_dados(self):
        self.request("POST", "/medicoes", SAMPLE)
        previous = self.request("GET", "/medicoes/historico")[1]
        storage.inicializar_banco()
        storage.inicializar_banco()
        self.assertEqual(self.request("GET", "/medicoes/historico")[1], previous)

    def test_persistencia_apos_reiniciar_servidor_http(self):
        self.request("POST", "/medicoes", SAMPLE)
        previous = self.request("GET", "/medicoes/historico")[1]
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", "/medicoes/historico")[1], previous)
        data = self.request("GET", "/medicoes/ultima")[1]
        self.assertEqual({key: data[key] for key in SAMPLE}, SAMPLE)

    def test_persistencia_e_idade_em_novo_processo_fora_da_raiz(self):
        with patch("BackEnd.storage.datetime", wraps=datetime) as utc:
            utc.now.return_value = datetime.now(timezone.utc) - timedelta(seconds=120)
            self.request("POST", "/medicoes", SAMPLE)
        code = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "from BackEnd import storage; storage.CAMINHO_BANCO = Path(sys.argv[2]); "
            "storage.inicializar_banco(); print(storage.consultar_ultima_medicao().model_dump_json())"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(Path(__file__).resolve().parents[1]), str(self.database)],
            cwd=self.temporary.name, capture_output=True, text=True, check=True, timeout=10,
        )
        data = json.loads(result.stdout)
        self.assertEqual({key: data[key] for key in SAMPLE}, SAMPLE)
        self.assertTrue(data["desatualizada"])
        self.assertGreaterEqual(data["idade_segundos"], 120)

    def test_falha_de_insercao_nao_apaga_historico_e_permite_recuperacao(self):
        self.request("POST", "/medicoes", SAMPLE)
        previous = self.request("GET", "/medicoes/historico")[1]
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TRIGGER falha_teste BEFORE INSERT ON medicoes BEGIN SELECT RAISE(ABORT, 'falha simulada'); END")
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                storage.salvar_medicao(storage.Medicao(**SAMPLE))
            self.assertEqual(self.request("GET", "/medicoes/historico")[1], previous)
        finally:
            with closing(sqlite3.connect(self.database)) as connection, connection:
                connection.execute("DROP TRIGGER falha_teste")
        self.assertEqual(self.request("POST", "/medicoes", SAMPLE)[0], 200)
        self.assertEqual(len(self.request("GET", "/medicoes/historico")[1]), 2)

    def test_dashboard_swagger_e_schema(self):
        for path in ("/dashboard", "/dashboard/style.css", "/dashboard/script.js", "/docs"):
            with self.subTest(path=path):
                status, content = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(content)
        schema = self.request("GET", "/openapi.json")[1]
        models = schema["components"]["schemas"]
        self.assertEqual(models["Medicao"]["properties"]["umidade"]["anyOf"][0]["maximum"], 100)
        self.assertIn("recebida_em", models["MedicaoConsulta"]["properties"])


if __name__ == "__main__":
    unittest.main()
