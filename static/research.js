(function () {
  "use strict";

  const menuBtn = document.getElementById("menuBtn");
  const sidebar = document.getElementById("sidebar");
  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));
  }

  const palette = ["#47d7ac", "#5aa9ff", "#f3b44b", "#c084fc", "#ff8a95"];
  const charts = {};

  function chartAvailable() {
    return typeof window.Chart !== "undefined";
  }

  if (chartAvailable()) {
    Chart.defaults.color = "#9fb0c9";
    Chart.defaults.borderColor = "rgba(38,54,80,.65)";
    Chart.defaults.font.family = '"Segoe UI", system-ui, Arial, sans-serif';
  }

  function unavailable(canvas, message) {
    if (!canvas) return;
    canvas.style.display = "none";
    if (!canvas.nextElementSibling || !canvas.nextElementSibling.classList.contains("chart-fallback")) {
      canvas.insertAdjacentHTML("afterend", `<p class="small chart-fallback">${message}</p>`);
    }
  }

  function destroyChart(id) {
    if (charts[id]) {
      charts[id].destroy();
      delete charts[id];
    }
  }

  function makeChart(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    if (!chartAvailable()) {
      unavailable(canvas, "Chart library unavailable; use the generated tables and CSV downloads.");
      return null;
    }
    destroyChart(id);
    charts[id] = new Chart(canvas, config);
    return charts[id];
  }

  function baseOptions(title, yTitle) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#c9d7ec", boxWidth: 12, usePointStyle: true } },
        title: { display: Boolean(title), text: title || "", color: "#e7edf7", font: { size: 13 } },
        tooltip: { backgroundColor: "#0e1829", borderColor: "#263650", borderWidth: 1 }
      },
      scales: {
        x: { ticks: { color: "#9fb0c9", maxRotation: 0 }, grid: { color: "rgba(38,54,80,.45)" } },
        y: {
          beginAtZero: true,
          title: { display: Boolean(yTitle), text: yTitle || "", color: "#9fb0c9", font: { size: 11 } },
          ticks: { color: "#9fb0c9" },
          grid: { color: "rgba(38,54,80,.45)" }
        }
      }
    };
  }

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
    return Number(value).toFixed(digits === undefined ? 3 : digits);
  }

  function pct(value, digits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
    return (Number(value) * 100).toFixed(digits === undefined ? 2 : digits) + "%";
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function lastValue(values) {
    if (!Array.isArray(values)) return null;
    for (let i = values.length - 1; i >= 0; i -= 1) {
      if (values[i] !== null && values[i] !== undefined) return values[i];
    }
    return null;
  }

  function hasValues(values) {
    return Array.isArray(values) && values.some((v) => v !== null && v !== undefined);
  }

  function buildMetricChart(chart, metric) {
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

  async function fetchJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    let payload = null;
    try {
      payload = await response.json();
    } catch (err) {
      return { ok: false, payload: null, status: response.status };
    }
    return { ok: response.ok, payload: payload, status: response.status };
  }

  async function loadResults() {
    const canvas = document.getElementById("resultChart");
    if (!canvas) return;
    const result = await fetchJson("/api/v1/research/results");
    if (!result.ok || !result.payload || !result.payload.available || !result.payload.chart) {
      unavailable(canvas, "Results data unavailable; check the run manifest.");
      return;
    }
    const payload = result.payload;
    const select = document.getElementById("metricSelect");
    const initial = select ? select.value : "energy_per_served_request_j";
    makeChart("resultChart", {
      type: "bar",
      data: buildMetricChart(payload.chart, initial),
      options: baseOptions("", "Mean value across ten seeds")
    });
    if (select) {
      select.addEventListener("change", () => {
        const chart = charts.resultChart;
        if (!chart) return;
        chart.data = buildMetricChart(payload.chart, select.value);
        chart.options.plugins.title.text = payload.chart.metric_labels[select.value] || select.value;
        chart.update();
      });
    }
    buildEnergyDropChart(payload.chart);
  }

  function buildEnergyDropChart(chartData) {
    const metric = "energy_per_offered_request_j";
    const dropMetric = "drop_rate";
    const datasets = chartData.strategy_labels.map((label, index) => ({
      label: label,
      data: chartData.labels.map((workload) => ({
        x: chartData.metrics[metric][workload][index],
        y: chartData.metrics[dropMetric][workload][index] === null
          ? null
          : chartData.metrics[dropMetric][workload][index] * 100,
        workload: workload
      })).filter((point) => point.x !== null && point.y !== null),
      backgroundColor: palette[index % palette.length] + "cc",
      borderColor: palette[index % palette.length],
      borderWidth: 1.5,
      pointRadius: 6,
      pointHoverRadius: 8
    }));
    makeChart("energyDropChart", {
      type: "scatter",
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#c9d7ec", usePointStyle: true } },
          tooltip: {
            backgroundColor: "#0e1829",
            borderColor: "#263650",
            borderWidth: 1,
            callbacks: {
              label: (context) => {
                const p = context.raw;
                return `${context.dataset.label} · ${p.workload}: ${fmt(p.x, 2)} J/offered, ${fmt(p.y, 2)}% drop`;
              }
            }
          }
        },
        scales: {
          x: {
            title: { display: true, text: "Estimated energy per offered request (J)", color: "#9fb0c9", font: { size: 11 } },
            ticks: { color: "#9fb0c9" },
            grid: { color: "rgba(38,54,80,.45)" }
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: "Request drop rate (%)", color: "#9fb0c9", font: { size: 11 } },
            ticks: { color: "#9fb0c9", callback: (v) => v + "%" },
            grid: { color: "rgba(38,54,80,.45)" }
          }
        }
      }
    });
  }

  function chartXY(series, key, color, label, dashed) {
    return {
      label: label,
      data: series.time_s.map((t, i) => ({ x: t, y: series[key][i] })),
      borderColor: color,
      backgroundColor: color + "22",
      borderWidth: 2,
      borderDash: dashed ? [6, 4] : [],
      pointRadius: 0,
      tension: 0.18,
      spanGaps: true
    };
  }

  function updateSelectionKpis(payload) {
    const summary = payload.summary || {};
    const series = payload.series || {};
    const finalOffered = lastValue(series.offered_rps);
    const finalCpu = lastValue(series.cpu_percent);
    const finalReady = lastValue(series.ready_replicas);
    setText("selWorkload", payload.workload + " (simulated)");
    setText("selStrategy", payload.strategy_label || payload.strategy);
    setText("selCurrentRps", finalOffered === null ? "n/a" : fmt(finalOffered, 2) + " req/s");
    setText("selCpu", finalCpu === null ? "n/a" : fmt(finalCpu, 1) + "%");
    setText("selReplicas", finalReady === null ? "n/a" : fmt(finalReady, 1));
    setText("selAvgReplicas", summary.avg_ready_replicas === null ? "n/a" : fmt(summary.avg_ready_replicas, 2));
    setText("selTotalEnergy", summary.measurement_energy_j === null ? "n/a" : fmt(summary.measurement_energy_j, 0) + " J");
    setText("selEnergyServed", summary.energy_per_served_request_j === null ? "n/a" : fmt(summary.energy_per_served_request_j, 2) + " J");
    setText("selEnergyOffered", summary.energy_per_offered_request_j === null ? "n/a" : fmt(summary.energy_per_offered_request_j, 2) + " J");
    setText("selDrop", pct(summary.drop_rate));
    setText("selSla", pct(summary.sla_violation_rate));
    setText("selP95", summary.p95_latency_ms === null ? "n/a" : fmt(summary.p95_latency_ms, 1) + " ms");
    setText("selReplicaHours", summary.replica_hours === null ? "n/a" : fmt(summary.replica_hours, 3));
    setText("selScaling", summary.scaling_events === null ? "n/a" : fmt(summary.scaling_events, 1));
    setText("selectionStatus", `${payload.seeds_used.length} seed${payload.seeds_used.length === 1 ? "" : "s"} · ${series.time_s.length} ticks · backend data`);
    setText(
      "selectionNote",
      "The final-tick values are the last 5 s interval, not a live cluster reading. Energy is modelled from node CPU and the configured power assumptions."
    );
  }

  function renderSelectionCharts(payload) {
    const series = payload.series;
    const datasets = [
      chartXY(series, "offered_rps", "#5aa9ff", "Offered req/s"),
    ];
    if (hasValues(series.forecast_rps)) {
      datasets.push(chartXY(series, "forecast_rps", "#f3b44b", "Forecast req/s", true));
      datasets.push(chartXY(series, "actual_forward_rps", "#47d7ac", "Actual at t+2", true));
    }
    makeChart("tsWorkloadChart", {
      type: "line",
      data: { datasets: datasets },
      options: baseOptions("", "Requests per second")
    });
    makeChart("tsCpuChart", {
      type: "line",
      data: { datasets: [chartXY(series, "cpu_percent", "#c084fc", "CPU utilisation (%)")] },
      options: baseOptions("", "CPU %")
    });
    makeChart("tsReplicaChart", {
      type: "line",
      data: {
        datasets: [
          chartXY(series, "ready_replicas", "#47d7ac", "Ready replicas"),
          chartXY(series, "desired_replicas", "#5aa9ff", "Desired replicas", true),
          chartXY(series, "pending_replicas", "#f3b44b", "Pending replicas", true)
        ]
      },
      options: baseOptions("", "Replicas")
    });
  }

  async function loadSelection() {
    const workloadEl = document.getElementById("filterWorkload");
    const strategyEl = document.getElementById("filterStrategy");
    const seedEl = document.getElementById("filterSeed");
    if (!workloadEl || !strategyEl || !seedEl) return;
    const params = new URLSearchParams({
      workload: workloadEl.value,
      strategy: strategyEl.value,
      seed: seedEl.value
    });
    setText("selectionStatus", "Loading backend series…");
    const result = await fetchJson("/api/v1/research/timeseries?" + params.toString());
    if (!result.ok || !result.payload || !result.payload.available) {
      setText("selectionStatus", (result.payload && result.payload.error) || "Series unavailable.");
      return;
    }
    updateSelectionKpis(result.payload);
    renderSelectionCharts(result.payload);
  }

  async function loadDiagnostic() {
    const canvas = document.getElementById("diagnosticChart");
    if (canvas) {
      const result = await fetchJson("/api/v1/research/diagnostic");
      if (result.ok && result.payload && result.payload.available && result.payload.comparisons) {
        const payload = result.payload;
        const labels = payload.comparisons.map((row) => row.workload);
        makeChart("diagnosticChart", {
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
          options: baseOptions("Energy per served request (modelled, J)", "J per served request")
        });
      } else {
        unavailable(canvas, "Diagnostic chart unavailable; use the tables below.");
      }
    }
    await loadControllerTrace();
    bindTraceControls();
  }

  function bindTraceControls() {
    ["traceWorkload", "traceStrategy", "traceSeed"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", loadControllerTrace);
    });
  }

  async function loadControllerTrace() {
    const workloadEl = document.getElementById("traceWorkload");
    const strategyEl = document.getElementById("traceStrategy");
    const seedEl = document.getElementById("traceSeed");
    if (!workloadEl || !strategyEl || !seedEl) return;
    const params = new URLSearchParams({
      workload: workloadEl.value,
      strategy: strategyEl.value,
      seed: seedEl.value
    });
    setText("traceStatus", "Loading raw trace…");
    const result = await fetchJson("/api/v1/research/controller-trace?" + params.toString());
    if (!result.ok || !result.payload || !result.payload.available) {
      setText("traceStatus", (result.payload && result.payload.error) || "Trace unavailable.");
      return;
    }
    const payload = result.payload;
    const latest = payload.latest || {};
    setText("traceStatus", `${payload.strategy_label} · seed ${payload.seed} · ${payload.behavior.ticks} ticks`);
    setText("trWorkload", `${payload.workload} @ t=${fmt(latest.time_s, 0)} s${latest.warmup ? " (warm-up)" : ""}`);
    setText("trRate", latest.observed_rps === null ? "n/a" : fmt(latest.observed_rps, 2) + " req/s");
    setText("trCpu", fmt(latest.cpu_percent, 1) + "%");
    setText("trReplicas", `${fmt(latest.ready_replicas, 0)} / ${fmt(latest.desired_replicas, 0)}`);
    setText("trAction", latest.scaling_action || "hold");
    setText("trRule", latest.rule_fired || "n/a");
    setText("trCooldown", latest.cooldown_status || "n/a");
    setText("trMargin", latest.sla_margin === null ? "n/a" : fmt(latest.sla_margin, 3));
    setText("trForecast", latest.forecast_rps === null ? "not applicable" : fmt(latest.forecast_rps, 2) + " req/s");
    setText("trEnergy", latest.energy_per_tick_j === null ? "n/a" : fmt(latest.energy_per_tick_j, 1) + " J");
    setText("trReason", latest.decision_reason || "No decision reason recorded.");
    const detailsEl = document.getElementById("trDetails");
    if (detailsEl) detailsEl.textContent = JSON.stringify(latest.decision_details || {}, null, 2);

    const body = document.getElementById("traceHistoryBody");
    if (body) {
      body.textContent = "";
      if (!payload.history || payload.history.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.className = "small";
        cell.textContent = "No scale-up or scale-down action in this run (holds only).";
        row.appendChild(cell);
        body.appendChild(row);
      } else {
        payload.history.forEach((item) => {
          const row = document.createElement("tr");
          const values = [
            fmt(item.time_s, 1),
            item.action,
            `${fmt(item.from_replicas, 0)} → ${fmt(item.to_replicas, 0)}`,
            item.rule || "n/a",
            item.reason || "n/a",
            fmt(item.observed_rps, 2)
          ];
          values.forEach((value) => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
          });
          body.appendChild(row);
        });
      }
    }
    const behavior = payload.behavior || {};
    const rules = Object.entries(behavior.rule_counts || {})
      .map(([rule, count]) => `${rule} (${count})`)
      .join(" · ");
    setText("traceBehavior", `Scaling events: ${behavior.scaling_events || 0}. Rule counts: ${rules || "n/a"}.`);

    const series = payload.series || {};
    const datasets = [chartXY(series, "observed_rps", "#5aa9ff", "Observed req/s")];
    if (hasValues(series.forecast_rps)) {
      datasets.push(chartXY(series, "forecast_rps", "#f3b44b", "Forecast at decision time", true));
      datasets.push(chartXY(series, "actual_forward_rps", "#47d7ac", "Actual at t+2", true));
    }
    makeChart("traceForecastChart", {
      type: "line",
      data: { datasets: datasets },
      options: baseOptions("", "Requests per second")
    });
  }

  loadResults();
  loadSelection();
  loadDiagnostic();

  ["filterWorkload", "filterStrategy", "filterSeed"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", loadSelection);
  });
})();
