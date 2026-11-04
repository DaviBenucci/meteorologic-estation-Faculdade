"""Conversão calibrada e modelo acadêmico nominal do roteiro MQ-135."""

import math
import json
from pathlib import Path
from .config import LIMITE_ATUALIZACAO_SEGUNDOS

CAMINHO_CALIBRACAO = Path(__file__).resolve().parent / "data" / "mq135-calibracao.json"
CAMINHO_ROTEIRO = CAMINHO_CALIBRACAO.with_name("mq135-roteiro.json")
RL_ROTEIRO_OHMS = 10000.0
RELACAO_REFERENCIA_ROTEIRO = 3.6
COEFICIENTES = {"co2": (-0.42, 1.89), "amonia": (-0.42, 1.15),
                "alcool": (-0.40, 1.34), "benzeno": (-0.38, 1.23)}


def _positivo(valor: float) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        raise ValueError("O parâmetro deve ser finito e positivo")
    return valor


def resistencia_sensor(tensao_adc: float, tensao_circuito: float, carga: float,
                       divisor_superior: float, divisor_inferior: float) -> float:
    """Rs no circuito resistivo simples, considerando o divisor como carga adicional."""
    adc, circuito, rl, superior, inferior = map(
        _positivo, (tensao_adc, tensao_circuito, carga, divisor_superior, divisor_inferior)
    )
    tensao_ao = adc * (superior + inferior) / inferior
    if not math.isfinite(tensao_ao) or tensao_ao >= circuito:
        raise ValueError("Tensão AO fora do intervalo do circuito")
    carga_efetiva = 1 / (1 / rl + 1 / (superior + inferior))
    resultado = carga_efetiva * (circuito / tensao_ao - 1)
    return _positivo(resultado)


def relacao_resistencias(rs: float, r0: float) -> float:
    return _positivo(_positivo(rs) / _positivo(r0))


def referencia_calibracao(amostras_rs: list[float], relacao_referencia: float) -> float:
    """Calcula R0 para uma relação Rs/R0 conhecida, fornecida pelo operador."""
    if not amostras_rs:
        raise ValueError("São necessárias amostras de resistência")
    razao = _positivo(relacao_referencia)
    media = math.fsum(_positivo(valor) / len(amostras_rs) for valor in amostras_rs)
    return _positivo(media / razao)


def tensao_adc(adc: int, pontos: list) -> float:
    """Interpolação entre pontos medidos da curva ADC; não extrapola."""
    if isinstance(adc, bool) or not isinstance(adc, int) or not 0 <= adc <= 4095:
        raise ValueError("ADC inválido")
    if not isinstance(pontos, list) or len(pontos) < 2:
        raise ValueError("São necessários pontos medidos do ADC")
    anteriores = None
    for ponto in pontos:
        if not isinstance(ponto, list) or len(ponto) != 2:
            raise ValueError("Ponto ADC inválido")
        codigo, tensao = ponto
        if isinstance(codigo, bool) or not isinstance(codigo, int) or not 0 <= codigo <= 4095:
            raise ValueError("Código ADC inválido")
        if isinstance(tensao, bool) or not isinstance(tensao, (float, int)) or not math.isfinite(tensao) or not 0 <= tensao <= 3.3:
            raise ValueError("Tensão ADC inválida")
        if anteriores and (codigo <= anteriores[0] or tensao <= anteriores[1]):
            raise ValueError("Pontos ADC devem ser estritamente crescentes")
        anteriores = (codigo, tensao)
    for (x1, y1), (x2, y2) in zip(pontos, pontos[1:]):
        if x1 <= adc <= x2:
            return y1 + (adc - x1) * (y2 - y1) / (x2 - x1)
    raise ValueError("ADC fora da faixa calibrada")


def estimativas(rs: float, r0: float, intervalo: list | None = None) -> dict:
    razao = relacao_resistencias(rs, r0)
    if intervalo is not None:
        if not isinstance(intervalo, list) or len(intervalo) != 2:
            raise ValueError("Faixa de aplicação ausente")
        minimo, maximo = map(_positivo, intervalo)
        if minimo >= maximo or not minimo <= razao <= maximo:
            raise ValueError("Razão fora da faixa de aplicação")
    resultado = {}
    for gas, (a, b) in COEFICIENTES.items():
        expoente = (math.log(razao) - b) / a
        if not math.isfinite(expoente) or abs(expoente) > 70:
            raise ValueError("Resultado fora da faixa matemática")
        resultado[gas] = _positivo(math.exp(expoente))
    return resultado


def resistencia_roteiro(adc: int) -> float:
    # read() é 12 bits; no PDF read_u16() é normalizado por 65535.
    if isinstance(adc, bool) or not isinstance(adc, int) or not 0 < adc < 4095:
        raise ValueError("ADC nulo ou saturado")
    return _positivo((4095 / adc - 1) * RL_ROTEIRO_OHMS)


def referencia_roteiro(amostras: list) -> dict:
    from datetime import datetime, timezone

    if len(amostras) != 5:
        raise ValueError("São necessárias cinco medições reais recentes")
    if len({amostra.id for amostra in amostras}) != 5:
        raise ValueError("Medições de referência repetidas")
    agora = datetime.now(timezone.utc)
    if any(not 0 <= (agora - item.recebida_em).total_seconds() <= LIMITE_ATUALIZACAO_SEGUNDOS for item in amostras):
        raise ValueError("Medições de referência antigas")
    resistencias = [resistencia_roteiro(item.gas) for item in amostras]
    return {"modelo": "roteiro_olavo_nominal_v1", "criada_em_utc": agora.isoformat(),
            "r0_ohms": referencia_calibracao(resistencias, RELACAO_REFERENCIA_ROTEIRO),
            "rl_nominal_ohms": RL_ROTEIRO_OHMS, "relacao_referencia": RELACAO_REFERENCIA_ROTEIRO,
            "validacao_fisica": False, "ar_limpo_confirmado": False,
            "amostras": [{"id": item.id, "recebida_em": item.recebida_em.isoformat(), "adc": item.gas} for item in amostras]}


def avaliar_roteiro(adc: int, config: dict) -> dict:
    if not isinstance(config, dict) or config.get("modelo") != "roteiro_olavo_nominal_v1":
        raise ValueError("Referência do roteiro inválida")
    rs = resistencia_roteiro(adc)
    return {"modelo": config["modelo"], "validacao_fisica": False, "ar_limpo_confirmado": False,
            "referencia_criada_em_utc": config["criada_em_utc"],
            "rs_ohms": rs, "r0_ohms": _positivo(config["r0_ohms"]),
            "razao_rs_r0": relacao_resistencias(rs, config["r0_ohms"]),
            "estimativas_ppm": estimativas(rs, config["r0_ohms"])}


def avaliar_adc(adc: int, config: dict) -> dict:
    if not isinstance(config, dict) or config.get("validacao_fisica") is not True or config.get("versao_modelo") != "olavo-1":
        raise ValueError("Calibração não validada")
    if not isinstance(config.get("identificacao"), str) or not config["identificacao"].strip():
        raise ValueError("Identificação da calibração ausente")
    if config.get("intervalo_razao_validado") is None:
        raise ValueError("Faixa de aplicação ausente")
    volts = tensao_adc(adc, config["pontos_adc"])
    rs = resistencia_sensor(volts, config["tensao_circuito_v"], config["rl_ohms"],
                            config["divisor_superior_ohms"], config["divisor_inferior_ohms"])
    return {"identificacao_calibracao": config["identificacao"], "rs_ohms": rs,
            "razao_rs_r0": relacao_resistencias(rs, config["r0_ohms"]),
            "estimativas_ppm": estimativas(rs, config["r0_ohms"], config["intervalo_razao_validado"])}


def analisar_medicao(medicao) -> dict:
    resposta = {"estado": "PENDENTE", "mensagem": "Calibração pendente — estimativas indisponíveis.",
                "recebida_em": medicao.recebida_em if medicao else None}
    if medicao is None or medicao.gas is None or medicao.desatualizada:
        return resposta
    try:
        if CAMINHO_CALIBRACAO.exists():
            config = json.loads(CAMINHO_CALIBRACAO.read_text(encoding="utf-8"))
            resultado = avaliar_adc(medicao.gas, config)
            estado = "EXPERIMENTAL"
            mensagem = "Estimativas experimentais; não são medições independentes."
        else:
            config = json.loads(CAMINHO_ROTEIRO.read_text(encoding="utf-8"))
            resultado = avaliar_roteiro(medicao.gas, config)
            estado = "EXPERIMENTAL_ROTEIRO"
            mensagem = "Modelo acadêmico do roteiro — parâmetros nominais e referência do ambiente atual, sem validação física."
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return resposta
    return {**resposta, "estado": estado, "mensagem": mensagem, **resultado,
            "gas": resultado["estimativas_ppm"], "unidade": "ppm_estimados", "identifica_tipo_gas": False}
