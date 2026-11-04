from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .alertas import avaliar_alertas
from .mq135 import analisar_medicao
from .models import EstatisticasHistorico, Medicao, MedicaoConsulta, MedicaoHistorico, PeriodoHistorico, SemMedicoes
from .storage import (
    LIMITE_HISTORICO,
    LIMITE_HISTORICO_MAXIMO,
    consultar_estatisticas,
    consultar_historico,
    consultar_ultima_medicao,
    inicializar_banco,
    salvar_medicao,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    inicializar_banco()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Non-finite input cannot be serialized back into a JSON error response.
    errors = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.post("/medicoes")
def receber_medicao(dados: Medicao) -> dict[str, str]:
    salvar_medicao(dados)
    return {"status": "recebido"}


@app.get("/medicoes/ultima")
def consultar_medicao() -> MedicaoConsulta | SemMedicoes:
    medicao = consultar_ultima_medicao()
    return medicao if medicao is not None else SemMedicoes()


@app.get("/medicoes/historico")
def consultar_medicoes(
    periodo: PeriodoHistorico | None = Query(default=None),
    limite: Annotated[int, Query(ge=1, le=LIMITE_HISTORICO_MAXIMO)] = LIMITE_HISTORICO,
) -> list[MedicaoHistorico]:
    return consultar_historico(limite, periodo)


@app.get("/medicoes/estatisticas")
def consultar_resumo(periodo: PeriodoHistorico | None = Query(default=None)) -> EstatisticasHistorico:
    return consultar_estatisticas(periodo)


@app.get("/alertas/atuais")
def consultar_alertas() -> dict:
    return avaliar_alertas(consultar_ultima_medicao())


@app.get("/mq135/analise")
def consultar_analise_mq135() -> dict:
    return analisar_medicao(consultar_ultima_medicao())


frontend_dir = Path(__file__).resolve().parent.parent / "FrontEnd"
app.mount("/dashboard", StaticFiles(directory=frontend_dir, html=True), name="dashboard")
