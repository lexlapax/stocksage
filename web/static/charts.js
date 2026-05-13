(function () {
  const colors = {
    blue: "#2563eb",
    green: "#16a34a",
    rose: "#e11d48",
    slate: "#475569",
    line: "#dfe3ea",
  };

  function readData(id) {
    const node = document.getElementById(id);
    if (!node) {
      return [];
    }
    try {
      return JSON.parse(node.textContent || "[]");
    } catch {
      return [];
    }
  }

  function percentTick(value) {
    return `${value}%`;
  }

  function signedPercent(value) {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}%`;
  }

  function zeroGrid(context) {
    return context.tick.value === 0 ? colors.slate : colors.line;
  }

  function zeroGridWidth(context) {
    return context.tick.value === 0 ? 2 : 1;
  }

  function renderSystemAccuracy() {
    const canvas = document.getElementById("system-accuracy-chart");
    const data = readData("system-accuracy-data");
    if (!canvas || !data.length) {
      return;
    }

    new Chart(canvas, {
      type: "line",
      data: {
        labels: data.map((point) => point.date),
        datasets: [
          {
            label: "Rolling 30-day hit rate",
            data: data.map((point) => point.hit_rate),
            borderColor: colors.blue,
            backgroundColor: "rgba(37, 99, 235, 0.12)",
            borderWidth: 2,
            fill: true,
            tension: 0.25,
            pointRadius: 3,
          },
          {
            label: "50% reference",
            data: data.map(() => 50),
            borderColor: colors.slate,
            borderDash: [5, 5],
            borderWidth: 1,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
          },
          tooltip: {
            callbacks: {
              label: (context) => `${context.dataset.label}: ${percentTick(context.parsed.y)}`,
            },
          },
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              callback: percentTick,
            },
            title: {
              display: true,
              text: "Hit rate",
            },
          },
          x: {
            title: {
              display: true,
              text: "Analysis date",
            },
          },
        },
      },
    });
  }

  function renderTickerAlpha() {
    const canvas = document.getElementById("ticker-alpha-chart");
    const data = readData("ticker-alpha-data");
    if (!canvas || !data.length) {
      return;
    }

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.map((point) => point.date),
        datasets: [
          {
            label: "Alpha vs market",
            data: data.map((point) => point.alpha_return),
            backgroundColor: data.map((point) =>
              point.alpha_return >= 0 ? colors.green : colors.rose,
            ),
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: (context) => `Alpha: ${signedPercent(context.parsed.y)}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: signedPercent,
            },
            grid: {
              color: zeroGrid,
              lineWidth: zeroGridWidth,
            },
            title: {
              display: true,
              text: "Alpha",
            },
          },
          x: {
            title: {
              display: true,
              text: "Analysis date",
            },
          },
        },
      },
    });
  }

  function renderRatingCalibration() {
    const canvas = document.getElementById("rating-calibration-chart");
    const data = readData("rating-calibration-data");
    if (!canvas || !data.length) {
      return;
    }

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.map((point) => point.rating),
        datasets: [
          {
            label: "Average alpha",
            data: data.map((point) => point.avg_alpha_return),
            backgroundColor: data.map((point) =>
              point.avg_alpha_return >= 0 ? colors.green : colors.rose,
            ),
            borderWidth: 0,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: (context) => `Avg alpha: ${signedPercent(context.parsed.x)}`,
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: {
              callback: signedPercent,
            },
            grid: {
              color: zeroGrid,
              lineWidth: zeroGridWidth,
            },
            title: {
              display: true,
              text: "Average alpha",
            },
          },
          y: {
            title: {
              display: true,
              text: "Rating",
            },
          },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!window.Chart) {
      return;
    }
    renderSystemAccuracy();
    renderTickerAlpha();
    renderRatingCalibration();
  });
})();
