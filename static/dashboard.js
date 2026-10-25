/* Energy-Aware Autoscaling dashboard behaviour.
   Charts are optional: if the CDN library fails to load, tables remain usable. */
(function () {
  'use strict';

  var COLORS = {
    static: { bg: 'rgba(142,160,192,.75)', border: '#8ea0c0' },
    hpa: { bg: 'rgba(242,169,59,.75)', border: '#f2a93b' },
    energy_aware: { bg: 'rgba(55,201,139,.75)', border: '#37c98b' }
  };
  var GRID = 'rgba(36,48,74,.7)';
  var TICK = '#8ea0c0';

  function readChartData() {
    var el = document.getElementById('chartData');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function showFallback(message) {
    var el = document.getElementById('chartFallback');
    if (!el) return;
    if (message) el.textContent = message;
    el.hidden = false;
  }

  function chartsAvailable() {
    if (typeof window.Chart === 'undefined') {
      showFallback('Chart library could not be loaded (offline or blocked CDN). Tables and metrics remain fully usable.');
      return false;
    }
    return true;
  }

  function baseOptions(unit, title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: TICK, boxWidth: 12, boxHeight: 12 } },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              var v = ctx.parsed.y;
              if (v === null || v === undefined) return ctx.dataset.label + ': no data';
              return ctx.dataset.label + ': ' + v + (unit ? ' ' + unit : '');
            }
          }
        },
        title: title ? { display: true, text: title, color: '#e6ecf7', font: { size: 13 } } : { display: false }
      },
      scales: {
        x: { ticks: { color: TICK }, grid: { color: GRID } },
        y: { beginAtZero: true, ticks: { color: TICK }, grid: { color: GRID }, title: unit ? { display: true, text: unit, color: TICK } : { display: false } }
      }
    };
  }

  function datasetsFor(data, metric, workloads, type) {
    var strategies = data.strategies;
    return strategies.map(function (s, i) {
      return {
        label: data.labels[i],
        data: workloads.map(function (w) {
          var arr = data[metric] && data[metric][w];
          return arr ? arr[i] : null;
        }),
        backgroundColor: COLORS[s] ? COLORS[s].bg : '#888',
        borderColor: COLORS[s] ? COLORS[s].border : '#888',
        borderWidth: 1,
        borderRadius: type === 'bar' ? 6 : 0,
        tension: 0.3,
        fill: false
      };
    });
  }

  function buildGroupedChart(canvasId, data, metric, unit, label) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    var workloads = data.workloads;
    new window.Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: workloads.map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); }),
        datasets: datasetsFor(data, metric, workloads, 'bar')
      },
      options: baseOptions(unit, label)
    });
  }

  function initCharts(data) {
    if (!data) return;
    buildGroupedChart('energyChart', data, 'energy', 'J/request', 'Estimated energy per request');
    buildGroupedChart('replicaChart', data, 'replicas', 'replicas', 'Average replicas');
    buildGroupedChart('cpuChart', data, 'cpu', '%', 'Average CPU utilisation');
    buildGroupedChart('latencyChart', data, 'latency', 'ms', 'Average latency');
    buildGroupedChart('slaChart', data, 'sla', 'violations', 'SLA violations');
  }

  function initExplorer() {
    var table = document.getElementById('experimentTable');
    if (!table) return;

    var strategy = document.getElementById('filterStrategy');
    var workload = document.getElementById('filterWorkload');
    var repetition = document.getElementById('filterRepetition');
    var search = document.getElementById('searchBox');
    var exportBtn = document.getElementById('exportCsv');
    var counter = document.getElementById('visibleCount');
    var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));

    function apply() {
      var s = strategy ? strategy.value : '';
      var w = workload ? workload.value : '';
      var r = repetition ? repetition.value : '';
      var q = search ? search.value.trim().toLowerCase() : '';
      var visible = 0;
      rows.forEach(function (row) {
        var ok = true;
        if (s && row.getAttribute('data-strategy') !== s) ok = false;
        if (w && row.getAttribute('data-workload') !== w) ok = false;
        if (r && String(row.getAttribute('data-repetition')) !== String(r)) ok = false;
        if (q && (row.getAttribute('data-search') || '').indexOf(q) === -1) ok = false;
        row.style.display = ok ? '' : 'none';
        if (ok) visible += 1;
      });
      if (counter) counter.textContent = visible;
    }

    [strategy, workload, repetition].forEach(function (el) {
      if (el) el.addEventListener('change', apply);
    });
    if (search) search.addEventListener('input', apply);

    if (exportBtn) {
      exportBtn.addEventListener('click', function () {
        var lines = [];
        var headers = [];
        table.querySelectorAll('thead th').forEach(function (th) { headers.push(th.textContent.trim()); });
        lines.push(headers.join(','));
        rows.forEach(function (row) {
          if (row.style.display === 'none') return;
          var cells = [];
          row.querySelectorAll('td').forEach(function (td) {
            var text = td.textContent.trim().replace(/"/g, '""');
            cells.push('"' + text + '"');
          });
          lines.push(cells.join(','));
        });
        var blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'experiments_filtered.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }
  }

  function initShell() {
    var btn = document.getElementById('menuBtn');
    var sidebar = document.getElementById('sidebar');
    if (btn && sidebar) {
      btn.addEventListener('click', function () { sidebar.classList.toggle('open'); });
    }
    var clock = document.getElementById('liveClock');
    if (clock) {
      var render = function () {
        clock.textContent = new Date().toLocaleString();
      };
      render();
      setInterval(render, 1000);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initShell();
    initExplorer();
    var data = readChartData();
    if (data && chartsAvailable()) {
      initCharts(data);
    }
  });
})();
