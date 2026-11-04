"""Registra uma calibração fornecida pelo operador, sem alterar medições."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .mq135 import CAMINHO_CALIBRACAO, CAMINHO_ROTEIRO, avaliar_adc, referencia_calibracao, referencia_roteiro, resistencia_sensor, tensao_adc


def calibrar(dados: dict) -> dict:
    amostras = dados["amostras_adc"]
    if not isinstance(amostras, list) or len(amostras) < 5:
        raise ValueError("Informe pelo menos cinco amostras ADC")
    rs = [resistencia_sensor(tensao_adc(adc, dados["pontos_adc"]), dados["tensao_circuito_v"],
                             dados["rl_ohms"], dados["divisor_superior_ohms"], dados["divisor_inferior_ohms"])
          for adc in amostras]
    resultado = {**dados, "r0_ohms": referencia_calibracao(rs, dados["relacao_referencia"]),
                 "criada_em_utc": datetime.now(timezone.utc).isoformat()}
    for adc in amostras:
        avaliar_adc(adc, resultado)
    return resultado


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python -m BackEnd.calibrar_mq135 dados-medidos.json | --roteiro")
    destino = CAMINHO_CALIBRACAO
    if sys.argv[1] == "--roteiro":
        from .storage import CAMINHO_BANCO, consultar_historico
        if not CAMINHO_BANCO.is_file():
            raise ValueError("Banco de medições inexistente")
        resultado = referencia_roteiro(consultar_historico(limite=5))
        destino = CAMINHO_ROTEIRO
    else:
        dados = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        resultado = calibrar(dados)
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteudo = json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False)
    with destino.open("x", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    print("Referência salva:", destino)


if __name__ == "__main__":
    main()
