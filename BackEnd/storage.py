from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .models import (
    EstatisticasHistorico,
    Medicao,
    MedicaoConsulta,
    MedicaoHistorico,
    PeriodoHistorico,
    ResumoEstatistico,
)
from .config import LIMITE_ATUALIZACAO_SEGUNDOS

LIMITE_HISTORICO = 100
LIMITE_HISTORICO_MAXIMO = 1000
MAXIMO_PONTOS_GRAFICO = 500
PERIODOS_SEGUNDOS = {"5m": 300, "10m": 600, "15m": 900, "1h": 3600, "6h": 21600, "24h": 86400}
CAMINHO_BANCO = Path(__file__).resolve().parent / "data" / "estacao.db"


def _conectar() -> sqlite3.Connection:
    conexao = sqlite3.connect(CAMINHO_BANCO, timeout=5)
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar_banco() -> None:
    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    with closing(_conectar()) as conexao:
        conexao.executescript(Path(__file__).with_name("schema.sql").read_text())


def salvar_medicao(dados: Medicao) -> None:
    valores = dados.model_dump()
    valores["recebida_em"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    with closing(_conectar()) as conexao, conexao:
        conexao.execute(
            """INSERT INTO medicoes (
                temperatura_DHT, umidade, temperatura_BMP, pressao_BMP,
                luminosidade, gas, recebida_em
            ) VALUES (
                :temperatura_DHT, :umidade, :temperatura_BMP, :pressao_BMP,
                :luminosidade, :gas, :recebida_em
            )""",
            valores,
        )


def _converter_medicao(linha: sqlite3.Row) -> MedicaoHistorico:
    valores = dict(linha)
    valores["recebida_em"] = datetime.fromisoformat(valores["recebida_em"])
    return MedicaoHistorico(**valores)


def consultar_ultima_medicao() -> MedicaoConsulta | None:
    with closing(_conectar()) as conexao:
        linha = conexao.execute("SELECT * FROM medicoes ORDER BY id DESC LIMIT 1").fetchone()
    if linha is None:
        return None

    registro = _converter_medicao(linha)
    idade = max(0.0, (datetime.now(timezone.utc) - registro.recebida_em).total_seconds())
    return MedicaoConsulta(
        **registro.model_dump(exclude={"id"}),
        idade_segundos=idade,
        desatualizada=idade > LIMITE_ATUALIZACAO_SEGUNDOS,
    )


def _inicio_periodo(periodo: PeriodoHistorico | None) -> str | None:
    if periodo is None:
        return None
    return (datetime.now(timezone.utc) - timedelta(seconds=PERIODOS_SEGUNDOS[periodo])).isoformat(
        timespec="microseconds"
    )


def consultar_historico(
    limite: int = LIMITE_HISTORICO,
    periodo: PeriodoHistorico | None = None,
) -> list[MedicaoHistorico]:
    inicio = _inicio_periodo(periodo)
    where = "WHERE recebida_em >= ?" if inicio is not None else ""
    parametros: tuple[object, ...] = (inicio,) if inicio is not None else ()
    with closing(_conectar()) as conexao:
        if periodo is None or limite == 1:
            linhas = conexao.execute(
                f"SELECT * FROM (SELECT * FROM medicoes {where} ORDER BY recebida_em DESC, id DESC LIMIT ?) ORDER BY recebida_em ASC, id ASC",
                (*parametros, min(limite, MAXIMO_PONTOS_GRAFICO)),
            ).fetchall()
        else:
            linhas = conexao.execute(
                """WITH ordenadas AS (
                    SELECT *, ROW_NUMBER() OVER (ORDER BY recebida_em, id) AS pos,
                    COUNT(*) OVER () AS total FROM medicoes WHERE recebida_em >= ?
                ) SELECT id, temperatura_DHT, umidade, temperatura_BMP, pressao_BMP,
                    luminosidade, gas, recebida_em FROM ordenadas
                WHERE total <= ? OR pos = 1 OR pos = total OR
                    CAST((pos - 1) * 1.0 * (? - 1) / (total - 1) AS INTEGER) >
                    CAST((pos - 2) * 1.0 * (? - 1) / (total - 1) AS INTEGER)
                ORDER BY pos""",
                (inicio, min(limite, MAXIMO_PONTOS_GRAFICO), min(limite, MAXIMO_PONTOS_GRAFICO), min(limite, MAXIMO_PONTOS_GRAFICO)),
            ).fetchall()
    return [_converter_medicao(linha) for linha in linhas]


def consultar_estatisticas(periodo: PeriodoHistorico | None = None) -> EstatisticasHistorico:
    inicio = _inicio_periodo(periodo)
    where = "WHERE recebida_em >= ?" if inicio is not None else ""
    parametros: tuple[object, ...] = (inicio,) if inicio is not None else ()
    campos = ("temperatura_DHT", "temperatura_BMP", "umidade", "pressao_BMP")
    with closing(_conectar()) as conexao:
        linha = conexao.execute(
            f"""SELECT COUNT(*) AS quantidade,
                {", ".join(
                    f"MIN({campo}) AS {campo}_min, MAX({campo}) AS {campo}_max, AVG({campo}) AS {campo}_avg"
                    for campo in campos
                )}
                FROM medicoes {where}""",
            parametros,
        ).fetchone()

    def resumo(campo: str) -> ResumoEstatistico:
        return ResumoEstatistico(
            minima=linha[f"{campo}_min"],
            maxima=linha[f"{campo}_max"],
            media=linha[f"{campo}_avg"],
        )

    return EstatisticasHistorico(
        periodo=periodo,
        quantidade=linha["quantidade"],
        **{campo: resumo(campo) for campo in campos},
    )
