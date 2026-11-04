import math
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from BackEnd.mq135 import referencia_calibracao, relacao_resistencias, resistencia_sensor, tensao_adc, estimativas, avaliar_adc
from BackEnd.calibrar_mq135 import calibrar, main
from BackEnd.mq135 import resistencia_roteiro, referencia_roteiro, avaliar_roteiro


class MQ135Tests(unittest.TestCase):
    def test_roteiro_reflete_cinco_amostras_e_normalizacao_12_bits(self):
        agora = datetime.now(timezone.utc)
        amostras = [SimpleNamespace(id=i, recebida_em=agora, gas=2000) for i in range(5)]
        referencia = referencia_roteiro(amostras)
        self.assertAlmostEqual(resistencia_roteiro(2000), 10475)
        self.assertAlmostEqual(referencia["r0_ohms"], 10475 / 3.6)
        resultado = avaliar_roteiro(2000, referencia)
        self.assertAlmostEqual(resultado["razao_rs_r0"], 3.6)
        self.assertFalse(resultado["validacao_fisica"])
        self.assertFalse(resultado["ar_limpo_confirmado"])
        self.assertEqual(len(referencia["amostras"]), 5)
        for valor in (None, 0, 4095, -1, 65535, float("nan"), True):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                resistencia_roteiro(valor)
        with self.assertRaises(ValueError):
            referencia_roteiro(amostras[:4])
        amostras[0].recebida_em = agora - timedelta(seconds=91)
        with self.assertRaises(ValueError):
            referencia_roteiro(amostras)

    def test_conversao_calibracao_e_equacoes(self):
        config = {"validacao_fisica": True, "versao_modelo": "olavo-1", "identificacao": "teste",
                  "pontos_adc": [[0, 0], [4000, 2]], "tensao_circuito_v": 5,
                  "rl_ohms": 20000, "divisor_superior_ohms": 10000, "divisor_inferior_ohms": 10000,
                  "relacao_referencia": 3.6, "amostras_adc": [2000] * 5,
                  "intervalo_razao_validado": [1, 10]}
        self.assertEqual(tensao_adc(2000, config["pontos_adc"]), 1)
        resultado = calibrar(config)
        self.assertAlmostEqual(resultado["r0_ohms"], 15000 / 3.6)
        analise = avaliar_adc(2000, resultado)
        self.assertAlmostEqual(analise["razao_rs_r0"], 3.6)
        for gas, (a, b) in {"co2": (-.42, 1.89), "amonia": (-.42, 1.15), "alcool": (-.40, 1.34), "benzeno": (-.38, 1.23)}.items():
            self.assertAlmostEqual(analise["estimativas_ppm"][gas], math.exp((math.log(3.6) - b) / a))
        with self.assertRaises(ValueError):
            avaliar_adc(2000, {**resultado, "validacao_fisica": False})
        with self.assertRaises(ValueError):
            tensao_adc(4095, config["pontos_adc"])
        with self.assertRaises(ValueError):
            estimativas(15000, resultado["r0_ohms"], [4, 5])
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / "entrada.json"
            destino = Path(pasta) / "calibracao.json"
            fonte.write_text(json.dumps(config), encoding="utf-8")
            with patch("BackEnd.calibrar_mq135.CAMINHO_CALIBRACAO", destino), patch.object(sys, "argv", ["calibrar", str(fonte)]):
                main()
                salvo = json.loads(destino.read_text(encoding="utf-8"))
                self.assertAlmostEqual(salvo["r0_ohms"], resultado["r0_ohms"])
                self.assertEqual(salvo["amostras_adc"], config["amostras_adc"])
                with self.assertRaises(FileExistsError):
                    main()
                self.assertEqual(json.loads(destino.read_text(encoding="utf-8")), salvo)

    def test_divisor_e_carga_em_paralelo(self):
        # Vadc=1 V implica AO=2 V; RL=20 kΩ em paralelo com o divisor de 20 kΩ.
        self.assertAlmostEqual(resistencia_sensor(1, 5, 20000, 10000, 10000), 15000)

    def test_referencia_e_relacao(self):
        r0 = referencia_calibracao([12000, 18000], 3)
        self.assertEqual(r0, 5000)
        self.assertEqual(relacao_resistencias(15000, r0), 3)

    def test_rejeita_parametros_invalidos(self):
        for valor in (0, -1, math.nan, math.inf, -math.inf, True, None):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    resistencia_sensor(valor, 5, 20000, 10000, 10000)
                with self.assertRaises(ValueError):
                    relacao_resistencias(1000, valor)
                with self.assertRaises(ValueError):
                    referencia_calibracao([1000], valor)
        for tensao in (2.5, 3):
            with self.assertRaises(ValueError):
                resistencia_sensor(tensao, 5, 20000, 10000, 10000)
        with self.assertRaises(ValueError):
            referencia_calibracao([], 3)
        with self.assertRaises(ValueError):
            referencia_calibracao([1000, math.nan], 3)
