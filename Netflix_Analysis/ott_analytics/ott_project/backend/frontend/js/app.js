/* app.js — Main application logic */

// ── State ──────────────────────────────────────────────────────────────────
let statsData = null;
let chartInstances = {};
let currentPage = 1;
let currentFilters = { type: "", country: "" };

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(pageId) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));

  const page = document.getElementById("page-" + pageId);
  if (page) page.classList.add("active");

  const navItem = document.querySelector(`[data-page="${pageId}"]`);
  if (navItem) navItem.classList.add("active");

  if (pageId === "dashboard" && !statsData) loadDashboard();
  if (pageId === "browse") loadBrowse(1);
  if (pageId === "search") document.getElementById("search-input")?.focus();
}

// ── Helpers ────────────────────────────────────────────────────────────────
function showLoading(id) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="loading-state"><div class="spinner"></div>Loading...</div>`;
}

function showError(id, msg) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div class="alert alert-error">⚠️ ${msg}</div>`;
}

function fmtNum(n) {
  return typeof n === "number" ? n.toLocaleString() : n;
}

// ── Dashboard ──────────────────────────────────────────────────────────────
async function loadDashboard() {
  showLoading("stat-movies");
  try {
    const res = await api.stats();
    statsData = res.data;
    renderStats(statsData);
    renderCharts(statsData);
  } catch (e) {
    showError("stat-movies", "Cannot reach backend. Is app.py running?");
    console.error(e);
  }
}

function renderStats(d) {
  document.getElementById("stat-movies").textContent  = fmtNum(d.total_movies);
  document.getElementById("stat-tvshows").textContent = fmtNum(d.total_tvshows);
  document.getElementById("stat-countries").textContent = fmtNum(d.total_countries);
  document.getElementById("stat-genres").textContent  = fmtNum(d.total_genres);
}

function renderCharts(d) {
  // Destroy previous charts
  Object.values(chartInstances).forEach((c) => c?.destroy?.());
  chartInstances = {};

  // 1. Content-type doughnut
  chartInstances.typePie = makeDoughnutChart(
    "chart-type",
    ["Movies", "TV Shows"],
    [d.total_movies, d.total_tvshows],
    ["#e50914", "#00a8e0"]
  );

  // 2. Yearly growth line
  const years = Object.keys(d.yearly_growth).sort();
  const counts = years.map((y) => d.yearly_growth[y]);
  chartInstances.yearly = makeLineChart("chart-yearly", years, [
    {
      label: "Titles Added",
      data: counts,
      borderColor: "#e50914",
      backgroundColor: "rgba(229,9,20,0.08)",
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointBackgroundColor: "#e50914",
    },
  ]);

  // 3. Top genres horizontal bar
  const genreEntries = Object.entries(d.top_genres).sort((a, b) => b[1] - a[1]).slice(0, 8);
  chartInstances.genres = makeBarChart(
    "chart-genres",
    genreEntries.map((e) => e[0]),
    genreEntries.map((e) => e[1]),
    null,
    true
  );

  // 4. Top countries bar
  const countryEntries = Object.entries(d.top_countries).sort((a, b) => b[1] - a[1]).slice(0, 8);
  chartInstances.countries = makeBarChart(
    "chart-countries",
    countryEntries.map((e) => e[0]),
    countryEntries.map((e) => e[1])
  );

  // 5. Ratings doughnut
  const ratingEntries = Object.entries(d.top_ratings).slice(0, 6);
  chartInstances.ratings = makeDoughnutChart(
    "chart-ratings",
    ratingEntries.map((e) => e[0]),
    ratingEntries.map((e) => e[1])
  );
}

// ── Recommend ──────────────────────────────────────────────────────────────
async function runRecommend() {
  const title = document.getElementById("rec-title").value.trim();
  const n     = parseInt(document.getElementById("rec-n").value) || 10;
  const ctype = document.getElementById("rec-type").value || null;
  const out   = document.getElementById("rec-results");

  if (!title) { out.innerHTML = `<div class="alert alert-error">Please enter a title.</div>`; return; }

  out.innerHTML = `<div class="loading-state"><div class="spinner"></div>Finding similar content...</div>`;

  try {
    const res = await api.recommend(title, n, ctype);
    if (!res.success) {
      out.innerHTML = `<div class="alert alert-error">No content found matching "${title}"</div>`; return;
    }
    out.innerHTML = `<div class="alert alert-info">📽 Found ${res.count} recommendations for <strong>${res.query}</strong></div>
      <div class="result-grid">${res.recommendations.map(renderRecCard).join("")}</div>`;
  } catch (e) {
    out.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
  }
}

function renderRecCard(item) {
  const pct = Math.round(item.similarity * 100);
  return `
    <div class="result-card">
      <div class="result-card-title">${item.title}</div>
      <div class="result-card-meta">
        <span class="badge-type ${item.type === 'Movie' ? 'badge-movie' : 'badge-show'}">${item.type}</span>
        <span class="badge-type badge-rating">${item.rating}</span>
        <span>${item.release_year}</span>
      </div>
      <div class="result-card-genre">${item.genre}</div>
      <div class="sim-bar"><div class="sim-fill" style="width:${pct}%"></div></div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px;font-family:var(--font-mono)">${pct}% match</div>
    </div>`;
}

// ── Predict Type ───────────────────────────────────────────────────────────
async function runPredictType() {
  const country  = document.getElementById("pt-country").value.trim();
  const rating   = document.getElementById("pt-rating").value;
  const genre    = document.getElementById("pt-genre").value.trim();
  const year     = document.getElementById("pt-year").value;
  const duration = document.getElementById("pt-duration").value;
  const out      = document.getElementById("pt-result");

  if (!country || !genre || !year) {
    out.innerHTML = `<div class="alert alert-error">Fill in all required fields.</div>`; return;
  }

  out.innerHTML = `<div class="loading-state"><div class="spinner"></div>Predicting...</div>`;
  try {
    const res = await api.predictType({ country, rating, genre, release_year: +year, duration_num: +duration });
    const r   = res.result;
    out.innerHTML = `
      <div class="prediction-box">
        <div class="pred-label">PREDICTED CONTENT TYPE</div>
        <div class="pred-value">${r.prediction}</div>
        <div class="pred-confidence">Confidence: ${(r.confidence * 100).toFixed(1)}%</div>
        <div class="top3-list" style="margin-top:12px">
          <div class="top3-item"><div class="top3-rating">Movie</div><div class="top3-prob">${(r.movie_prob*100).toFixed(1)}%</div></div>
          <div class="top3-item"><div class="top3-rating">TV Show</div><div class="top3-prob">${(r.tvshow_prob*100).toFixed(1)}%</div></div>
        </div>
      </div>`;
  } catch (e) {
    out.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
  }
}

// ── Predict Rating ─────────────────────────────────────────────────────────
async function runPredictRating() {
  const description  = document.getElementById("pr-desc").value.trim();
  const content_type = document.getElementById("pr-type").value;
  const country      = document.getElementById("pr-country").value.trim();
  const genre        = document.getElementById("pr-genre").value.trim();
  const release_year = document.getElementById("pr-year").value;
  const out          = document.getElementById("pr-result");

  if (!description || !country || !genre || !release_year) {
    out.innerHTML = `<div class="alert alert-error">Fill in all required fields.</div>`; return;
  }

  out.innerHTML = `<div class="loading-state"><div class="spinner"></div>Predicting...</div>`;
  try {
    const res = await api.predictRating({ description, content_type, country, genre, release_year: +release_year });
    const r   = res.result;
    out.innerHTML = `
      <div class="prediction-box">
        <div class="pred-label">PREDICTED MATURITY RATING</div>
        <div class="pred-value">${r.predicted_rating}</div>
        <div class="pred-confidence">Confidence: ${(r.confidence * 100).toFixed(1)}%</div>
        <div class="top3-list">
          ${r.top3.map(t => `<div class="top3-item">
            <div class="top3-rating">${t.rating}</div>
            <div class="top3-prob">${(t.probability*100).toFixed(1)}%</div>
          </div>`).join("")}
        </div>
      </div>`;
  } catch (e) {
    out.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
  }
}

// ── Predict Genre ──────────────────────────────────────────────────────────
async function runPredictGenre() {
  const title       = document.getElementById("pg-title").value.trim();
  const description = document.getElementById("pg-desc").value.trim();
  const threshold   = parseFloat(document.getElementById("pg-threshold").value) || 0.25;
  const out         = document.getElementById("pg-result");

  if (!description) {
    out.innerHTML = `<div class="alert alert-error">Description is required.</div>`; return;
  }

  out.innerHTML = `<div class="loading-state"><div class="spinner"></div>Predicting...</div>`;
  try {
    const res = await api.predictGenre({ title, description, threshold });
    const genres = res.result.predicted_genres;
    if (!genres.length) {
      out.innerHTML = `<div class="alert alert-info">No genres predicted above threshold ${threshold}. Try lowering it.</div>`;
      return;
    }
    out.innerHTML = `
      <div style="margin-top:16px">
        <div style="font-size:12px;color:var(--muted);font-family:var(--font-mono);margin-bottom:12px">PREDICTED GENRES</div>
        <div class="bar-chart">${genres.map(g => `
          <div class="bar-row">
            <div class="bar-label">${g.genre}</div>
            <div class="bar-track">
              <div class="bar-fill generic" data-pct="${Math.round(g.probability*100)}" style="width:${Math.round(g.probability*100)}%">
                ${Math.round(g.probability*100)}%
              </div>
            </div>
          </div>`).join("")}
        </div>
      </div>`;
  } catch (e) {
    out.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
  }
}

// ── Search ─────────────────────────────────────────────────────────────────
let searchTimer;
function onSearchInput() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 400);
}

async function runSearch() {
  const q   = document.getElementById("search-input").value.trim();
  const out = document.getElementById("search-results");
  if (!q) { out.innerHTML = ""; return; }

  out.innerHTML = `<div class="loading-state"><div class="spinner"></div></div>`;
  try {
    const res = await api.search(q, 20);
    if (!res.count) {
      out.innerHTML = `<div class="alert alert-info">No results for "${q}"</div>`; return;
    }
    out.innerHTML = `
      <div style="font-size:12px;color:var(--muted);font-family:var(--font-mono);margin-bottom:12px">${res.count} results for "${q}"</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Title</th><th>Type</th><th>Genre</th><th>Country</th><th>Year</th><th>Rating</th></tr></thead>
          <tbody>${res.results.map(r => `
            <tr>
              <td style="font-weight:600">${r.title}</td>
              <td><span class="badge-type ${r.type==='Movie'?'badge-movie':'badge-show'}">${r.type}</span></td>
              <td class="td-muted" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.listed_in}</td>
              <td class="td-muted">${r.country}</td>
              <td class="td-muted">${r.release_year}</td>
              <td><span class="badge-type badge-rating">${r.rating}</span></td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    out.innerHTML = `<div class="alert alert-error">Error: ${e.message}</div>`;
  }
}

// ── Browse ─────────────────────────────────────────────────────────────────
async function loadBrowse(page = 1) {
  currentPage = page;
  const out = document.getElementById("browse-results");
  showLoading("browse-results");
  try {
    const res = await api.titles(page, 20, currentFilters.type, currentFilters.country);
    document.getElementById("browse-total").textContent = `${fmtNum(res.total)} titles`;
    out.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Type</th><th>Genre</th><th>Country</th><th>Year</th><th>Rating</th><th>Duration</th></tr></thead>
          <tbody>${res.titles.map((r, i) => `
            <tr>
              <td class="td-muted" style="font-family:var(--font-mono)">${(page-1)*20+i+1}</td>
              <td style="font-weight:600">${r.title}</td>
              <td><span class="badge-type ${r.type==='Movie'?'badge-movie':'badge-show'}">${r.type}</span></td>
              <td class="td-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.listed_in}</td>
              <td class="td-muted">${r.country}</td>
              <td class="td-muted">${r.release_year}</td>
              <td><span class="badge-type badge-rating">${r.rating}</span></td>
              <td class="td-muted">${r.duration}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    renderPagination(page, res.pages);
  } catch (e) {
    showError("browse-results", e.message);
  }
}

function applyBrowseFilters() {
  currentFilters.type    = document.getElementById("browse-type-filter").value;
  currentFilters.country = document.getElementById("browse-country-filter").value.trim();
  loadBrowse(1);
}

function renderPagination(current, total) {
  const el = document.getElementById("pagination");
  if (!el || total <= 1) { if(el) el.innerHTML=""; return; }
  let html = "";
  const pages = Math.min(total, 200); // cap display

  if (current > 1) html += `<button class="page-btn" onclick="loadBrowse(${current-1})">‹</button>`;

  const range = [];
  range.push(1);
  if (current > 3) range.push("...");
  for (let p = Math.max(2, current-1); p <= Math.min(pages-1, current+1); p++) range.push(p);
  if (current < pages - 2) range.push("...");
  if (pages > 1) range.push(pages);

  range.forEach(p => {
    if (p === "...") html += `<span class="page-info">…</span>`;
    else html += `<button class="page-btn ${p===current?"active":""}" onclick="loadBrowse(${p})">${p}</button>`;
  });

  if (current < pages) html += `<button class="page-btn" onclick="loadBrowse(${current+1})">›</button>`;
  el.innerHTML = html;
}

// ── Tab switching ──────────────────────────────────────────────────────────
function switchTab(containerId, tabId) {
  const container = document.getElementById(containerId);
  container.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  container.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  container.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  document.getElementById(tabId).classList.add("active");
}

// ── Check backend health ───────────────────────────────────────────────────
async function checkHealth() {
  const dot  = document.querySelector(".status-dot");
  const text = document.querySelector(".status-text");
  try {
    await api.health();
    dot.style.background  = "#22c55e";
    text.textContent = "API Online";
  } catch {
    dot.style.background  = "#e50914";
    dot.style.animation   = "none";
    text.textContent = "API Offline";
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  navigate("dashboard");

  // Enter key for recommend
  document.getElementById("rec-title")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runRecommend();
  });
});
