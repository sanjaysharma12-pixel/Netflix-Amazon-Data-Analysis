/* charts.js — Chart.js wrappers */

const COLORS = {
  netflix: "#e50914",
  amazon:  "#00a8e0",
  accent:  "#f5c518",
  green:   "#22c55e",
  purple:  "#6366f1",
  muted:   "#6b6b80",
  border:  "#2a2a38",
  text:    "#f0f0f5",
  palette: ["#e50914","#00a8e0","#f5c518","#22c55e","#6366f1","#f97316","#ec4899","#14b8a6","#a855f7","#fb923c"],
};

Chart.defaults.color = COLORS.muted;
Chart.defaults.borderColor = COLORS.border;
Chart.defaults.font.family = "'DM Sans', sans-serif";

function makeLineChart(canvasId, labels, datasets, options = {}) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: datasets.length > 1 } },
      scales: {
        x: { grid: { color: COLORS.border }, ticks: { maxTicksLimit: 10 } },
        y: { grid: { color: COLORS.border }, beginAtZero: true },
      },
      ...options,
    },
  });
}

function makeBarChart(canvasId, labels, data, color = COLORS.netflix, horizontal = false) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: Array.isArray(color) ? color : labels.map((_, i) => COLORS.palette[i % COLORS.palette.length]),
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: horizontal ? "y" : "x",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: COLORS.border } },
        y: { grid: { color: COLORS.border } },
      },
    },
  });
}

function makeDoughnutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors || COLORS.palette,
        borderColor: "#0a0a0f",
        borderWidth: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: { boxWidth: 12, padding: 16, font: { size: 12 } },
        },
      },
      cutout: "65%",
    },
  });
}

function animateBars() {
  document.querySelectorAll(".bar-fill[data-pct]").forEach((el) => {
    setTimeout(() => {
      el.style.width = el.dataset.pct + "%";
    }, 100);
  });
}
