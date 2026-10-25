(function () {
  "use strict";

  const menuBtn = document.getElementById("menuBtn");
  const sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));
  }

  const palette = ["#47d7ac", "#5aa9ff", "#f3b44b", "#c084fc", "#ff8a95"];

  function chartAvailable() {
    return typeof window.Chart !== "undefined";
  }

  async function loadResults() {
    const canvas = document.getElementById("resultChart");
    if (!canvas) return;
    if (!chartAvailable()) {
      canvas.insertAdjacentHTML("afterend", "<p class='small'>Chart library unavailable; use the tables below.</p>");
      canvas.style.display = "none";
      return;
    }
    let payload;
    try {
      const response = await fetch("/api/v1/research/results");
      payload = await response.json();
    } catch (err) {
      return;
    }
    if (!payload || !payload.available || !payload.chart) return;
    const select = document.getElementById("metricSelect");
    const chart = new Chart(canvas, {
      type: "bar",
      data: buildData(payload.chart, "energy_per_served_request_j"),
      options: baseOptions("Energy / served request (J)")
    });
    if (select) {
      select.addEventListener("change", () => {
        chart.data = buildData(payload.chart, select.value);
        chart.options.plugins.title.text = payload.chart.metric_labels[select.value] || select.value;
        chart.update();
      });
    }
  }

  function buildData(chart, metric) {
    const datasets = chart.strategy_labels.map((label, index) => ({
      label: label,
      data: chart.labels.map((workload) => {
        const value = chart.metrics[metric][workload][index];
        return value === null ? null : value;
      }),
      backgroundColor: palette[index % palette.length] + "cc",
      borderColor: palette[index % palette.length],
      borderWidth: 1
    }));
    return { labels: chart.labels, datasets: datasets };
  }

  function baseOptions(title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#c9d7ec", boxWidth: 12 } },
        title: { display: true, text: title, color: "#e7edf7", font: { size: 13 } }
      },
      scales: {
        x: { ticks: { color: "#9fb0c9" }, grid: { color: "rgba(38,54,80,.55)" } },
        y: { beginAtZero: true, ticks: { color: "#9fb0c9" }, grid: { color: "rgba(38,54,80,.55)" } }
      }
    };
  }

  async function loadDiagnostic() {
    const canvas = document.getElementById("diagnosticChart");
    if (!canvas || !chartAvailable()) return;
    let payload;
    try {
      const response = await fetch("/api/v1/research/diagnostic");
      payload = await response.json();
    } catch (err) {
      return;
    }
    if (!payload || !payload.available || !payload.comparisons) return;
    const labels = payload.comparisons.map((row) => row.workload);
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "EAES J/served",
            data: payload.comparisons.map((row) => row.e_es),
            backgroundColor: "#47d7accc",
            borderColor: "#47d7ac",
            borderWidth: 1
          },
          {
            label: "HPA formula J/served",
            data: payload.comparisons.map((row) => row.h_es),
            backgroundColor: "#5aa9ffcc",
            borderColor: "#5aa9ff",
            borderWidth: 1
          }
        ]
      },
      options: baseOptions("Energy per served request (modelled, J)")
    });
  }

  loadResults();
  loadDiagnostic();
})();
