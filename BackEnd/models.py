from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Medicao(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    temperatura_DHT: float | None = None
    umidade: float | None = Field(default=None, ge=0, le=100)
    temperatura_BMP: float | None = None
    pressao_BMP: float | None = None
    luminosidade: int | None = Field(default=None, ge=0, le=1)
    gas: int | None = Field(
        default=None, ge=-(2**63), le=2**63 - 1,
        description="Leitura analógica bruta, sem unidade de concentração; inteiro SQLite de 64 bits.",
    )


class MedicaoHistorico(Medicao):
    id: int
    recebida_em: datetime


PeriodoHistorico = Literal["5m", "10m", "15m", "1h", "6h", "24h"]


class ResumoEstatistico(BaseModel):
    minima: float | None = None
    maxima: float | None = None
    media: float | None = None


class EstatisticasHistorico(BaseModel):
    periodo: PeriodoHistorico | None
    quantidade: int
    temperatura_DHT: ResumoEstatistico
    temperatura_BMP: ResumoEstatistico
    umidade: ResumoEstatistico
    pressao_BMP: ResumoEstatistico


class MedicaoConsulta(Medicao):
    recebida_em: datetime
    idade_segundos: float
    desatualizada: bool


class SemMedicoes(BaseModel):
    status: Literal["sem_medicoes"] = "sem_medicoes"
