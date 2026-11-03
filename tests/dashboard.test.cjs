const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const frontend = join(__dirname, "..", "FrontEnd");
const source = readFileSync(join(frontend, "script.js"), "utf8");
const html = readFileSync(join(frontend, "index.html"), "utf8");
const readings = {
  temperatura_DHT: 23.9, umidade: 83.8, temperatura_BMP: 25.57,
  pressao_BMP: 923.28, luminosidade: 0, gas: null,
};
const recentReadings = {
  ...readings, recebida_em: "2026-11-03T01:00:00Z", idade_segundos: 0, desatualizada: false,
};
const reply = (data, ok = true) => ({ ok, json: async () => data });
const settle = () => new Promise(resolve => setImmediate(resolve));

async function dashboard(fetchResponse) {
  const elements = new Map();
  const calls = [];
  const timers = new Map();
  let interval;
  const context = vm.createContext({
    document: {
      getElementById(id) {
        assert.ok(html.includes(`id="${id}"`), `Elemento ausente no HTML: ${id}`);
        if (!elements.has(id)) {
          const classes = new Set();
          elements.set(id, {
            textContent: "", innerHTML: "", value: id === "history-period" ? "5m" : "", hidden: false, dataset: {},
            classList: {
              toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
              contains(name) { return classes.has(name); },
            },
            addEventListener() {},
          });
        }
        return elements.get(id);
      },
    },
    AbortController,
    fetch: async (url, options) => { calls.push({ url, options }); return fetchResponse(options, url); },
    setTimeout(callback, delay) { const id = Symbol(); timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(callback, delay) { interval = { callback, delay }; },
  });
  vm.runInContext(source, context);
  await settle();
  return {
    elements, calls, timers, interval,
    query: () => vm.runInContext("queryReadings()", context),
    history: () => vm.runInContext("queryHistory()", context),
    value: field => elements.get(field).textContent,
    state: () => elements.get("api-status").dataset.state,
  };
}

test("alertas mostram múltiplas condições, indisponibilidade e recuperação", async () => {
  let alerts = { estado: "ATENCAO", mensagem: "Condições ambientais requerem atenção.",
    recebida_em: recentReadings.recebida_em, alertas: [{ mensagem: "Temperatura elevada" }, { mensagem: "Umidade baixa" }] };
  const page = await dashboard((_, url) => reply(url.includes("alertas") ? alerts : recentReadings));
  assert.equal(page.elements.get("alerts").dataset.state, "ATENCAO");
  assert.match(page.elements.get("alerts-list").textContent, /Temperatura elevada\nUmidade baixa/);
  alerts = { estado: "INDISPONIVEL", mensagem: "Estação sem atualizações recentes.", recebida_em: recentReadings.recebida_em, alertas: [] };
  await page.interval.callback();
  assert.equal(page.elements.get("alerts").dataset.state, "INDISPONIVEL");
  alerts = { estado: "NORMAL", mensagem: "Monitoramento normal", recebida_em: recentReadings.recebida_em, alertas: [] };
  await page.interval.callback();
  assert.equal(page.elements.get("alerts").dataset.state, "NORMAL");
  assert.equal(page.elements.get("alerts-list").textContent, "");
});

test("falha na API de alertas não mantém alerta antigo", async () => {
  let ok = true;
  const page = await dashboard((_, url) => url.includes("alertas")
    ? reply({ estado: "ATENCAO", mensagem: "Atenção", alertas: [{ mensagem: "Temperatura elevada" }] }, ok)
    : reply(recentReadings));
  ok = false;
  await page.interval.callback();
  assert.equal(page.elements.get("alerts").dataset.state, "INDISPONIVEL");
  assert.match(page.elements.get("alerts-message").textContent, /Não foi possível/);
  assert.equal(page.elements.get("alerts-list").textContent, "");
});

test("histórico usa tempo real, mostra ponto isolado e preserva lacunas", async () => {
  const rows = [
    { ...readings, recebida_em: "2026-11-03T01:00:00Z", temperatura_DHT: 10 },
    { ...readings, recebida_em: "2026-11-03T01:15:00Z", temperatura_DHT: null },
    { ...readings, recebida_em: "2026-11-03T02:00:00Z", temperatura_DHT: 20 },
  ];
  const summary = { minima: 10, media: 15, maxima: 20 };
  const page = await dashboard((_, url) => reply(url.includes("historico") ? rows : url.includes("estatisticas")
    ? { quantidade: 3, temperatura_DHT: summary, temperatura_BMP: summary, umidade: summary, pressao_BMP: summary }
    : recentReadings));
  const chart = page.elements.get("temperature-chart").innerHTML;
  assert.match(chart, /chart-point dht.*cx="48\.0"/);
  assert.match(chart, /chart-point dht.*cx="624\.0"/);
  assert.match(chart, /chart-line bmp/);
  assert.match(page.elements.get("history-status").textContent, /3 medição/);
  assert.match(page.elements.get("statistics").innerHTML, /15 °C/);
  assert.ok(page.calls.some(call => call.url.includes("periodo=5m")));
});

test("formata os seis indicadores e usa URL relativa, sem cache", async () => {
  const page = await dashboard(() => reply(recentReadings));
  assert.equal(page.value("temperatura_DHT"), "23,9");
  assert.equal(page.value("umidade"), "83,8");
  assert.equal(page.value("temperatura_BMP"), "25,57");
  assert.equal(page.value("pressao_BMP"), "923,28");
  assert.equal(page.value("luminosidade"), "Ambiente claro");
  assert.equal(page.value("gas"), "Indisponível");
  assert.equal(page.elements.get("gas-unit").hidden, true);
  assert.equal(page.state(), "success");
  assert.equal(page.calls[0].url, "/medicoes/ultima");
  assert.equal(page.calls[0].options.cache, "no-store");
  assert.ok(page.elements.get("last-query").dateTime);
  assert.equal(page.elements.get("last-received").dateTime, "2026-11-03T01:00:00.000Z");
});

test("consulta a cada cinco segundos e atualiza sem recarregar", async () => {
  let data = recentReadings;
  const page = await dashboard(() => reply(data));
  assert.equal(page.interval.delay, 5000);
  data = { ...recentReadings, temperatura_DHT: 24.2, luminosidade: 1, gas: 169 };
  await page.interval.callback();
  assert.equal(page.calls.length, 8);
  assert.equal(page.value("temperatura_DHT"), "24,2");
  assert.equal(page.value("luminosidade"), "Ambiente escuro");
  assert.equal(page.value("gas"), "169");
});

test("campos nulos ou omitidos não viram zero, mas zero real é válido", async () => {
  const page = await dashboard(() => reply({ temperatura_DHT: 0, gas: 0, umidade: null }));
  assert.equal(page.value("temperatura_DHT"), "0,0");
  assert.equal(page.value("gas"), "0");
  for (const field of ["umidade", "temperatura_BMP", "pressao_BMP", "luminosidade"]) {
    assert.equal(page.value(field), "Indisponível");
    assert.equal(page.elements.get(`${field}-unit`).hidden, true);
  }
});

test("não interpreta strings, booleanos ou luminosidade desconhecida como medições", async () => {
  const page = await dashboard(() => reply({ ...readings, luminosidade: 2, gas: "42", umidade: false }));
  for (const field of ["luminosidade", "gas", "umidade"]) assert.equal(page.value(field), "Indisponível");
});

test("sem medições mostra aviso e se recupera ao receber dados", async () => {
  let data = { status: "sem_medicoes" };
  const page = await dashboard(() => reply(data));
  assert.equal(page.state(), "empty");
  assert.match(page.elements.get("notice").textContent, /ainda não enviou dados/);
  for (const field of Object.keys(readings)) assert.equal(page.value(field), "Indisponível");
  data = recentReadings;
  await page.query();
  assert.equal(page.state(), "success");
  assert.equal(page.elements.get("notice").hidden, true);
});

test("falhas de rede, HTTP, JSON e respostas inválidas têm estado de erro e recuperação", async () => {
  const failures = [
    () => { throw new Error("offline"); },
    () => reply({}, false),
    () => ({ ok: true, json: async () => { throw new SyntaxError("JSON"); } }),
    ...[null, [], {}, { status: "inesperado" }].map(data => () => reply(data)),
  ];
  for (const failure of failures) {
    let respond = () => reply(recentReadings);
    const page = await dashboard(() => respond());
    const lastSuccess = page.elements.get("last-query").dateTime;
    respond = failure;
    await page.query();
    assert.equal(page.state(), "error");
    assert.equal(page.elements.get("notice").hidden, false);
    assert.equal(page.value("temperatura_DHT"), "Indisponível");
    assert.equal(page.elements.get("last-query").dateTime, lastSuccess);
    respond = () => reply(recentReadings);
    await page.query();
    assert.equal(page.state(), "success");
    assert.equal(page.timers.size, 0);
  }
});

test("marca leituras antigas e recupera após novo POST sem depender do relógio local", async () => {
  let data = recentReadings;
  const page = await dashboard(() => reply(data));
  data = { ...recentReadings, idade_segundos: 91, desatualizada: true };
  await page.interval.callback();
  assert.equal(page.state(), "stale");
  assert.equal(page.elements.get("readings").dataset.stale, "true");
  assert.match(page.elements.get("notice").textContent, /91 segundos/);
  assert.equal(page.value("temperatura_DHT"), "23,9");
  assert.equal(page.value("gas"), "Indisponível");
  data = { ...recentReadings, recebida_em: "2026-11-03T01:02:00Z" };
  await page.interval.callback();
  assert.equal(page.state(), "success");
  assert.equal(page.elements.get("readings").dataset.stale, "false");
  assert.equal(page.elements.get("notice").hidden, true);
  assert.equal(page.elements.get("last-received").dateTime, "2026-11-03T01:02:00.000Z");
});

test("API antiga ou metadados inválidos não confirmam comunicação recente", async () => {
  for (const metadata of [
    {}, { recebida_em: null }, { recebida_em: "inválida" },
    { idade_segundos: -1 }, { idade_segundos: "0" }, { desatualizada: "false" },
  ]) {
    const data = Object.keys(metadata).length ? { ...recentReadings, ...metadata } : readings;
    const page = await dashboard(() => reply(data));
    assert.equal(page.state(), "unknown");
    assert.equal(page.elements.get("last-received").dateTime, "");
    assert.match(page.elements.get("notice").textContent, /Não é possível confirmar/);
    assert.equal(page.value("temperatura_DHT"), "23,9");
  }
});

test("limita consultas a quatro segundos e impede requisições sobrepostas", async () => {
  const page = await dashboard(({ signal }) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(new Error("timeout")));
  }));
  await page.query();
  assert.equal(page.calls.length, 4);
  const timeout = [...page.timers.values()][0];
  assert.equal(timeout.delay, 4000);
  for (const timer of [...page.timers.values()]) timer.callback();
  await settle();
  assert.equal(page.state(), "error");
  assert.equal(page.timers.size, 0);
});
