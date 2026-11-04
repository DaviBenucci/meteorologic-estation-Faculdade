"use strict";

const fields = {
  temperatura_DHT: 1,
  umidade: 1,
  temperatura_BMP: 2,
  pressao_BMP: 2,
  luminosidade: 0,
  gas: 0,
};
const statusElement = document.getElementById("api-status");
const statusText = document.getElementById("status-text");
const notice = document.getElementById("notice");
const lastQuery = document.getElementById("last-query");
const lastReceived = document.getElementById("last-received");
const readingsElement = document.getElementById("readings");
const historyPeriod = document.getElementById("history-period");
const historyStatus = document.getElementById("history-status");
const statisticsElement = document.getElementById("statistics");
let querying = false;
let historyQuerying = false;
let alertsQuerying = false;
let gasQuerying = false;

function renderReadings(data) {
  readingsElement.dataset.stale = "false";
  for (const [field, decimals] of Object.entries(fields)) {
    if (field === "gas") continue;
    const value = data[field];
    const available = typeof value === "number" && Number.isFinite(value)
      && (field !== "luminosidade" || value === 0 || value === 1);
    const element = document.getElementById(field);

    element.classList.toggle("is-unavailable", !available);
    document.getElementById(`${field}-unit`).hidden = !available;
    if (!available) {
      element.textContent = "Indisponível";
    } else if (field === "luminosidade") {
      element.textContent = value === 0 ? "Ambiente claro" : "Ambiente escuro";
    } else {
      element.textContent = value.toLocaleString("pt-BR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    }
  }
}

async function queryGasAnalysis() {
  if (gasQuerying) return;
  gasQuerying = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  const status = document.getElementById("gas-analysis-status");
  const estimates = document.getElementById("gas-estimates");
  const gas = document.getElementById("gas");
  const unit = document.getElementById("gas-unit");
  let available = false;
  try {
    const response = await fetch("/mq135/analise", { cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error("API indisponível");
    const data = await response.json();
    if (["EXPERIMENTAL", "EXPERIMENTAL_ROTEIRO"].includes(data.estado) && data.estimativas_ppm
      && ["co2", "amonia", "alcool", "benzeno"].every(key => validNumber(data.estimativas_ppm[key]) && data.estimativas_ppm[key] > 0)) {
      status.textContent = data.estado === "EXPERIMENTAL_ROTEIRO"
        ? "Modelo do roteiro — parâmetros nominais, sem validação física"
        : "Estimativas experimentais — não são medições independentes";
      gas.textContent = data.estimativas_ppm.co2.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
      gas.classList.toggle("is-unavailable", false);
      unit.hidden = false;
      available = true;
      estimates.textContent = [["CO₂", "co2"], ["NH₃", "amonia"], ["Álcool", "alcool"], ["Benzeno", "benzeno"]]
        .map(([label, key]) => `${label}: ${data.estimativas_ppm[key].toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ppm`).join(" · ");
    } else {
      status.textContent = "Calibração pendente — estimativas indisponíveis.";
      estimates.textContent = "Estimativas de CO₂, NH₃, álcool e benzeno indisponíveis.";
    }
  } catch {
    status.textContent = "Análise experimental indisponível — falha na API.";
    estimates.textContent = "";
  } finally {
    if (!available) {
      gas.textContent = "Indisponível";
      gas.classList.toggle("is-unavailable", true);
      unit.hidden = true;
    }
    clearTimeout(timeout);
    gasQuerying = false;
  }
}

function setStatus(state, text, message = "") {
  statusElement.dataset.state = state;
  statusText.textContent = text;
  notice.textContent = message;
  notice.hidden = !message;
}

function renderCommunication(data) {
  const receivedAt = typeof data.recebida_em === "string" ? new Date(data.recebida_em) : null;
  const known = receivedAt !== null && Number.isFinite(receivedAt.getTime())
    && typeof data.idade_segundos === "number" && Number.isFinite(data.idade_segundos)
    && data.idade_segundos >= 0 && typeof data.desatualizada === "boolean";

  if (!known) {
    lastReceived.textContent = "Não informado";
    lastReceived.dateTime = "";
    setStatus("unknown", "API acessível · idade da medição desconhecida",
      "A API não informou a última comunicação. Não é possível confirmar se estas medições são recentes.");
    return;
  }

  lastReceived.textContent = receivedAt.toLocaleString("pt-BR");
  lastReceived.dateTime = receivedAt.toISOString();
  readingsElement.dataset.stale = String(data.desatualizada);
  if (data.desatualizada) {
    setStatus("stale", "API acessível · medições desatualizadas",
      `Sem atualizações da estação há ${Math.floor(data.idade_segundos)} segundos. Os valores exibidos são da última medição recebida.`);
  } else {
    setStatus("success", "API acessível · comunicação recente da estação");
  }
}

async function queryAlerts() {
  if (alertsQuerying) return;
  alertsQuerying = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  const box = document.getElementById("alerts");
  const state = document.getElementById("alerts-state");
  const message = document.getElementById("alerts-message");
  const list = document.getElementById("alerts-list");
  const received = document.getElementById("alerts-received");
  try {
    const response = await fetch("/alertas/atuais", { cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error("API indisponível");
    const data = await response.json();
    if (!data || !["NORMAL", "ATENCAO", "INDISPONIVEL"].includes(data.estado)
      || !Array.isArray(data.alertas) || typeof data.mensagem !== "string"
      || data.alertas.some(alert => typeof alert.mensagem !== "string")) throw new Error("Resposta inválida");
    box.dataset.state = data.estado;
    state.textContent = { NORMAL: "✓ Normal", ATENCAO: "⚠ Atenção", INDISPONIVEL: "● Indisponível" }[data.estado];
    message.textContent = data.mensagem;
    list.textContent = data.alertas.map(alert => alert.mensagem).join("\n");
    const date = data.recebida_em ? new Date(data.recebida_em) : null;
    received.textContent = date && Number.isFinite(date.getTime()) ? date.toLocaleString("pt-BR") : "Nenhuma";
    received.dateTime = date && Number.isFinite(date.getTime()) ? date.toISOString() : "";
  } catch {
    box.dataset.state = "INDISPONIVEL";
    state.textContent = "● Indisponível";
    message.textContent = "Não foi possível consultar os alertas na API.";
    list.textContent = "";
    received.textContent = "Indisponível";
    received.dateTime = "";
  } finally {
    clearTimeout(timeout);
    alertsQuerying = false;
  }
}

async function queryReadings() {
  if (querying) return;
  querying = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);

  try {
    const response = await fetch("/medicoes/ultima", {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Falha na resposta da API");
    const data = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)
      || (data.status !== "sem_medicoes" && !Object.keys(fields).some(field => field in data))) {
      throw new Error("Resposta da API inválida");
    }

    const now = new Date();
    lastQuery.textContent = now.toLocaleTimeString("pt-BR");
    lastQuery.dateTime = now.toISOString();

    if (data.status === "sem_medicoes") {
      renderReadings({});
      lastReceived.textContent = "Nenhum";
      lastReceived.dateTime = "";
      setStatus("empty", "API acessível · aguardando medições",
        "A estação ainda não enviou dados. A consulta será repetida automaticamente a cada 5 segundos.");
    } else {
      renderReadings(data);
      renderCommunication(data);
    }
  } catch {
    renderReadings({});
    lastReceived.textContent = "Indisponível";
    lastReceived.dateTime = "";
    setStatus("error", "Falha na consulta à API",
      "Não foi possível obter as medições. Verifique se o servidor está acessível. Uma nova tentativa será feita automaticamente a cada 5 segundos.");
  } finally {
    clearTimeout(timeout);
    querying = false;
  }
}

const chartDefinitions = [
  { id: "temperature-chart", series: [
    { field: "temperatura_DHT", label: "DHT22", className: "dht" },
    { field: "temperatura_BMP", label: "BMP280", className: "bmp" },
  ]},
  { id: "humidity-chart", series: [{ field: "umidade", label: "DHT22", className: "humidity" }] },
  { id: "pressure-chart", series: [{ field: "pressao_BMP", label: "BMP280", className: "pressure" }] },
];

function validNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function chartPath(history, field, width, height, min, max, start, end) {
  const points = history.map(item => {
    const value = item[field];
    const time = Date.parse(item.recebida_em);
    if (!validNumber(value) || !Number.isFinite(time)) return null;
    const x = 48 + ((time - start) / Math.max(end - start, 1)) * (width - 64);
    const y = height - 32 - (max === min ? 0.5 : (value - min) / (max - min)) * (height - 72);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const paths = [];
  let segment = [];
  for (const point of points) {
    if (point) segment.push(point);
    else if (segment.length) { paths.push(segment.join(" ")); segment = []; }
  }
  if (segment.length) paths.push(segment.join(" "));
  return paths;
}

function renderChart(definition, history) {
  const chart = document.getElementById(definition.id);
  const width = 640;
  const height = 260;
  const values = definition.series.flatMap(series => history.map(item => item[series.field]).filter(validNumber));
  if (!values.length) {
    chart.innerHTML = '<text class="chart-empty" x="320" y="130" text-anchor="middle">Sem medições neste período</text>';
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const grid = [0, 0.5, 1].map(ratio => {
    const y = height - 32 - ratio * (height - 72);
    const value = min + ratio * (max - min);
    return `<line class="chart-grid" x1="48" x2="624" y1="${y}" y2="${y}"/><text class="chart-label" x="42" y="${y + 4}" text-anchor="end">${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}</text>`;
  }).join("");
  const first = history[0]?.recebida_em ? new Date(history[0].recebida_em) : null;
  const last = history.at(-1)?.recebida_em ? new Date(history.at(-1).recebida_em) : null;
  const lines = definition.series.map(series => chartPath(
    history, series.field, width, height, min, max, first?.getTime(), last?.getTime(),
  ).map(path => path.includes(" ")
    ? `<polyline class="chart-line ${series.className}" points="${path}"/>`
    : `<circle class="chart-point ${series.className}" cx="${path.split(",")[0]}" cy="${path.split(",")[1]}" r="4"/>`).join("")).join("");
  const labels = [first, last].filter(date => date && Number.isFinite(date.getTime())).map((date, index) =>
    `<text class="chart-label" x="${index ? 624 : 48}" y="248" text-anchor="${index ? "end" : "start"}">${date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</text>`,
  ).join("");
  const legend = definition.series.map((series, index) =>
    `<text class="chart-legend" x="${48 + index * 90}" y="18">${series.label}</text>`,
  ).join("");
  chart.innerHTML = `${grid}${lines}${labels}${legend}`;
}

function renderStatistics(stats) {
  const fields = [
    ["temperatura_DHT", "Temperatura DHT22", "°C"],
    ["temperatura_BMP", "Temperatura BMP280", "°C"],
    ["umidade", "Umidade", "%"],
    ["pressao_BMP", "Pressão", "hPa"],
  ];
  if (!stats?.quantidade) {
    statisticsElement.innerHTML = '<p class="stat-empty">Sem medições reais suficientes para calcular estatísticas neste período.</p>';
    return;
  }
  statisticsElement.innerHTML = fields.map(([field, label, unit]) => {
    const summary = stats[field];
    const format = value => validNumber(value) ? `${value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ${unit}` : "—";
    return `<article class="stat-card"><h3>${label}</h3><div class="stat-row"><div><span>Mínima</span><strong>${format(summary.minima)}</strong></div><div><span>Média</span><strong>${format(summary.media)}</strong></div><div><span>Máxima</span><strong>${format(summary.maxima)}</strong></div></div></article>`;
  }).join("");
}

async function queryHistory() {
  if (historyQuerying) return;
  historyQuerying = true;
  const periodo = historyPeriod.value;
  try {
    const query = `?periodo=${encodeURIComponent(periodo)}&limite=500`;
    const [historyResponse, statsResponse] = await Promise.all([
      fetch(`/medicoes/historico${query}`, { cache: "no-store" }),
      fetch(`/medicoes/estatisticas?periodo=${encodeURIComponent(periodo)}`, { cache: "no-store" }),
    ]);
    if (!historyResponse.ok || !statsResponse.ok) throw new Error("Falha na resposta do histórico");
    const history = await historyResponse.json();
    const stats = await statsResponse.json();
    if (periodo !== historyPeriod.value) return;
    if (!Array.isArray(history) || !stats || typeof stats !== "object") throw new Error("Histórico inválido");
    chartDefinitions.forEach(definition => renderChart(definition, history));
    renderStatistics(stats);
    historyStatus.dataset.state = "success";
    historyStatus.textContent = history.length
      ? `${history.length} medição(ões) reais no período selecionado.`
      : "Histórico vazio para o período selecionado.";
  } catch {
    historyStatus.dataset.state = "error";
    historyStatus.textContent = "Histórico indisponível: a API não respondeu.";
    statisticsElement.innerHTML = "";
    chartDefinitions.forEach(definition => renderChart(definition, []));
  } finally {
    historyQuerying = false;
    if (periodo !== historyPeriod.value) queryHistory();
  }
}

historyPeriod.addEventListener("change", queryHistory);
queryReadings();
queryHistory();
queryAlerts();
queryGasAnalysis();
setInterval(async () => {
  await Promise.all([queryReadings(), queryHistory(), queryAlerts(), queryGasAnalysis()]);
}, 5000);
