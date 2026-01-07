const btn = document.getElementById("refreshBtn");
const lastUpdate = document.getElementById("lastUpdate");
const totalEstimatedMain = document.getElementById("totalEstimatedMain");
const fiisCount = document.getElementById("fiisCount");
const avgYield = document.getElementById("avgYield");
const lastMonth = document.getElementById("lastMonth");
const topYieldName = document.getElementById("topYieldName");
const topYieldValue = document.getElementById("topYieldValue");
const topPositionName = document.getElementById("topPositionName");
const topPositionValue = document.getElementById("topPositionValue");
const lastFetchLabel = document.getElementById("lastFetchLabel");
const lastFetchValue = document.getElementById("lastFetchValue");
const fiisTable = document.getElementById("fiisTable");
const fiisEmpty = document.getElementById("fiisEmpty");
const timeline = document.getElementById("timeline");
const tableMonth = document.getElementById("tableMonth");

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const number = new Intl.NumberFormat("pt-BR");

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function clearChildren(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function renderTable(rows) {
  clearChildren(fiisTable);
  if (!rows.length) {
    fiisEmpty.style.display = "block";
    return;
  }
  fiisEmpty.style.display = "none";

  const header = document.createElement("div");
  header.className = "table__row table__head";
  header.innerHTML =
    "<span>Fundo</span><span>Qtd</span><span>Ultimo rendimento</span><span>Total estimado</span>";
  fiisTable.appendChild(header);

  rows.forEach((row) => {
    const div = document.createElement("div");
    div.className = "table__row";
    const amount = row.has_dividend ? currency.format(row.amount_per_share) : "-";
    const total = row.has_dividend ? currency.format(row.total) : "-";
    div.innerHTML =
      `<span>${row.ticker}</span>` +
      `<span>${number.format(row.qty)}</span>` +
      `<span>${amount}</span>` +
      `<span>${total}</span>`;
    fiisTable.appendChild(div);
  });
}

function renderTimeline(items) {
  clearChildren(timeline);
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Sem historico ainda.";
    timeline.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const entry = document.createElement("div");
    entry.className = "timeline__item";
    entry.innerHTML =
      `<div class="dot"></div>` +
      `<div><strong>${item.month}</strong><p>${currency.format(item.total)}</p></div>`;
    timeline.appendChild(entry);
  });
}

async function loadData() {
  const [summaryResp, fiisResp, timelineResp] = await Promise.all([
    fetch("/api/summary"),
    fetch("/api/fiis"),
    fetch("/api/timeline?limit=3"),
  ]);

  const summary = await summaryResp.json();
  const fiis = await fiisResp.json();
  const timelineData = await timelineResp.json();

  totalEstimatedMain.textContent = currency.format(summary.total_estimated || 0);
  fiisCount.textContent = summary.fiis_count || 0;
  avgYield.textContent = currency.format(summary.avg_yield || 0);
  lastMonth.textContent = summary.month || "-";
  tableMonth.textContent = summary.month || "Mensal";

  if (summary.top_yield) {
    topYieldName.textContent = summary.top_yield.ticker;
    topYieldValue.textContent = currency.format(summary.top_yield.amount_per_share);
  } else {
    topYieldName.textContent = "-";
    topYieldValue.textContent = "-";
  }

  if (summary.top_position) {
    topPositionName.textContent = summary.top_position.ticker;
    topPositionValue.textContent = `${number.format(summary.top_position.qty)} cotas`;
  } else {
    topPositionName.textContent = "-";
    topPositionValue.textContent = "-";
  }

  lastUpdate.textContent = formatDate(summary.last_update);
  lastFetchLabel.textContent = summary.last_update ? "OK" : "-";
  lastFetchValue.textContent = formatDate(summary.last_update);

  renderTable(fiis.rows || []);
  renderTimeline(timelineData.items || []);
}

btn.addEventListener("click", async () => {
  btn.classList.add("loading");
  btn.querySelector("span").textContent = "Atualizando...";
  try {
    const response = await fetch("/api/fetch", { method: "POST" });
    if (!response.ok) {
      throw new Error("Falha na coleta");
    }
    await loadData();
  } catch (err) {
    lastUpdate.textContent = "Erro na coleta";
  } finally {
    btn.querySelector("span").textContent = "Atualizar";
    btn.classList.remove("loading");
  }
});

loadData().catch(() => {
  lastUpdate.textContent = "Servidor offline";
});
