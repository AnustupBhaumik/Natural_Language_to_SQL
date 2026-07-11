// ---------- Tabs ----------
const tabButtons = document.querySelectorAll(".tab-btn");
tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "schema") loadSchema();
    if (btn.dataset.tab === "history") loadHistory();
  });
});

// ---------- Ask ----------
const questionInput = document.getElementById("question-input");
const askBtn = document.getElementById("ask-btn");
const errorBox = document.getElementById("error-box");
const resultBox = document.getElementById("result");

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    questionInput.value = chip.dataset.q;
    questionInput.focus();
  });
});

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) runQuery();
});
askBtn.addEventListener("click", runQuery);

async function runQuery() {
  const question = questionInput.value.trim();
  if (!question) return;

  setLoading(true);
  errorBox.classList.add("hidden");
  resultBox.classList.add("hidden");

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong.");
      return;
    }
    renderResult(data);
  } catch (err) {
    showError("Network error: " + err.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  askBtn.disabled = isLoading;
  askBtn.querySelector(".btn-label").textContent = isLoading ? "Generating…" : "Generate";
  askBtn.querySelector(".spinner").classList.toggle("hidden", !isLoading);
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function renderResult(data) {
  document.getElementById("sql-output").textContent = data.sql;
  document.getElementById("elapsed").textContent = `${data.elapsed_ms} ms`;
  document.getElementById("row-count").textContent = `${data.row_count} row${data.row_count === 1 ? "" : "s"}`;

  // Results table
  const wrap = document.getElementById("table-wrap");
  wrap.innerHTML = "";
  if (data.rows.length === 0) {
    wrap.innerHTML = `<div class="empty-note">Query ran successfully but returned no rows.</div>`;
  } else {
    const table = document.createElement("table");
    table.className = "results-table";
    const thead = document.createElement("thead");
    thead.innerHTML = `<tr>${data.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr>`;
    const tbody = document.createElement("tbody");
    tbody.innerHTML = data.rows
      .map((row) => `<tr>${row.map((v) => `<td>${escapeHtml(v)}</td>`).join("")}</tr>`)
      .join("");
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
  }

  // Tables used
  const tagList = document.getElementById("tables-used");
  tagList.innerHTML = data.tables_used
    .map(
      (t) =>
        `<div class="tag-item"><span class="tag-name">${escapeHtml(t.table)}</span><span class="tag-score">${t.relevance}</span></div>`
    )
    .join("");

  // Similar past queries
  const simList = document.getElementById("similar-queries");
  simList.innerHTML =
    data.similar_past_queries.length === 0
      ? `<div class="empty-note">No closely related past queries yet.</div>`
      : data.similar_past_queries
          .map(
            (e) => `<div class="similar-item">
                <div class="similar-q">${escapeHtml(e.question)}</div>
                <div class="similar-sql">${escapeHtml(e.sql)}</div>
              </div>`
          )
          .join("");

  resultBox.classList.remove("hidden");
}

function escapeHtml(v) {
  if (v === null || v === undefined) return "<span style='color:var(--text-dim)'>NULL</span>";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---------- Schema tab ----------
let schemaLoaded = false;
async function loadSchema() {
  if (schemaLoaded) return;
  const res = await fetch("/api/schema");
  const schema = await res.json();
  const container = document.getElementById("schema-container");
  container.innerHTML = Object.values(schema)
    .map(
      (t) => `
      <div class="schema-card">
        <h3>${escapeHtml(t.name)}</h3>
        <div class="schema-desc">${escapeHtml(t.description || "")}</div>
        ${t.columns
          .map(
            (c) => `<div class="col-row"><span class="col-name">${escapeHtml(c.name)}</span><span class="col-type">${escapeHtml(c.type)}</span></div>`
          )
          .join("")}
      </div>`
    )
    .join("");
  schemaLoaded = true;
}

// ---------- History tab ----------
async function loadHistory() {
  const res = await fetch("/api/history");
  const history = await res.json();
  const container = document.getElementById("history-container");
  container.innerHTML =
    history.length === 0
      ? `<div class="empty-note">No queries yet — ask something in the Ask tab.</div>`
      : history
          .map(
            (e) => `
      <div class="history-item">
        <div class="history-q">${escapeHtml(e.question)}</div>
        <div class="history-sql">${escapeHtml(e.sql)}</div>
        <div class="history-meta">${escapeHtml(e.timestamp || "")} · tables: ${escapeHtml((e.tables_used || []).join(", "))}</div>
      </div>`
          )
          .join("");
}
