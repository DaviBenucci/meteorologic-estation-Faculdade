from .config import LIMITE_ATUALIZACAO_SEGUNDOS, TEMPERATURA_ELEVADA, UMIDADE_BAIXA, UMIDADE_ELEVADA
from .models import MedicaoConsulta


def avaliar_alertas(medicao: MedicaoConsulta | None) -> dict:
    if medicao is None:
        return {"estado": "INDISPONIVEL", "alertas": [], "recebida_em": None,
                "mensagem": "Nenhuma medição recebida."}
    if medicao.desatualizada:
        return {"estado": "INDISPONIVEL", "recebida_em": medicao.recebida_em,
                "mensagem": "Estação sem atualizações recentes.", "alertas": [{
                    "id": "estacao_desatualizada", "variavel": "idade_segundos",
                    "valor": medicao.idade_segundos, "limite": LIMITE_ATUALIZACAO_SEGUNDOS,
                    "unidade": "s", "mensagem": f"Estação sem atualizações há mais de {LIMITE_ATUALIZACAO_SEGUNDOS} segundos."
                }]}

    alertas = []
    for identificador, variavel, valor, limite, unidade, atingido, descricao in (
        ("temperatura_elevada", "temperatura_DHT", medicao.temperatura_DHT, TEMPERATURA_ELEVADA, "°C", lambda v, l: v >= l, "Temperatura elevada"),
        ("umidade_baixa", "umidade", medicao.umidade, UMIDADE_BAIXA, "%", lambda v, l: v < l, "Umidade baixa"),
        ("umidade_elevada", "umidade", medicao.umidade, UMIDADE_ELEVADA, "%", lambda v, l: v >= l, "Umidade elevada"),
    ):
        if valor is not None and atingido(valor, limite):
            observado = f"{valor:g}".replace(".", ",")
            alertas.append({"id": identificador, "variavel": variavel, "valor": valor,
                            "limite": limite, "unidade": unidade,
                            "mensagem": f"{descricao}: {observado} {unidade}. Limite configurado: {limite:g} {unidade}."})
    faltantes = [nome for nome, valor in (("temperatura DHT22", medicao.temperatura_DHT), ("umidade", medicao.umidade)) if valor is None]
    if alertas:
        estado, mensagem = "ATENCAO", "Condições ambientais requerem atenção."
    elif faltantes:
        estado, mensagem = "INDISPONIVEL", "Dados insuficientes para avaliar todas as condições."
    else:
        estado, mensagem = "NORMAL", "Monitoramento normal: nenhuma condição configurada foi ultrapassada."
    if faltantes:
        mensagem += " Sem leitura de " + " e ".join(faltantes) + "."
    return {"estado": estado, "alertas": alertas, "recebida_em": medicao.recebida_em, "mensagem": mensagem}
