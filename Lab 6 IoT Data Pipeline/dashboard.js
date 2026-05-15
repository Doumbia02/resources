/**
 * Smart GreenHouse Dashboard
 * Real-time IoT sensor visualization
 */

// ============================================
// CONFIGURATION - UPDATE THIS WITH YOUR API URL
// ============================================
const API_BASE_URL =
  "https://yymtb109s5.execute-api.us-east-1.amazonaws.com/prod";
// Example: 'https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod'

// ============================================
// Global State
// ============================================
let sensorChart = null;
let currentGreenhouseId = "greenhouse-01";
let refreshInterval = null;

// Alert thresholds (match Lambda settings)
const THRESHOLDS = {
  temperature: { min: 15, max: 35 },
  humidity: { min: 40, max: 85 },
  soil_moisture: { min: 30, max: 80 },
  light_intensity: { min: 100, max: 1000 },
};

// ============================================
// API Functions
// ============================================
async function apiCall(endpoint, params = {}) {
  const url = new URL(`${API_BASE_URL}${endpoint}`);
  Object.keys(params).forEach((key) =>
    url.searchParams.append(key, params[key])
  );

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error);
    updateConnectionStatus(false);
    throw error;
  }
}

async function getLatestReading() {
  return apiCall("/latest", { greenhouse_id: currentGreenhouseId });
}

async function getHistory(hours = 6) {
  return apiCall("/history", { greenhouse_id: currentGreenhouseId, hours });
}

async function getStats(hours = 24) {
  return apiCall("/stats", { greenhouse_id: currentGreenhouseId, hours });
}

async function getAlerts(limit = 10) {
  return apiCall("/alerts", { greenhouse_id: currentGreenhouseId, limit });
}

async function getGreenhouses() {
  return apiCall("/greenhouses");
}

// ============================================
// UI Update Functions
// ============================================
function updateCurrentReadings(data) {
  if (!data || !data.sensors) return;

  const sensors = data.sensors;

  // Temperature
  updateCard("temp", sensors.temperature?.value, "°C", THRESHOLDS.temperature);

  // Humidity
  updateCard("humidity", sensors.humidity?.value, "%", THRESHOLDS.humidity);

  // Soil Moisture
  updateCard(
    "soil",
    sensors.soil_moisture?.value,
    "%",
    THRESHOLDS.soil_moisture
  );

  // Light Intensity
  updateCard(
    "light",
    sensors.light_intensity?.value,
    " lux",
    THRESHOLDS.light_intensity
  );

  // Update timestamp
  const timestamp = new Date(data.timestamp);
  document.getElementById(
    "last-updated"
  ).textContent = `Last updated: ${timestamp.toLocaleTimeString()}`;
}

function updateCard(sensorId, value, unit, thresholds) {
  const valueEl = document.getElementById(`current-${sensorId}`);
  const statusEl = document.getElementById(`${sensorId}-status`);

  if (value === undefined || value === null) {
    valueEl.textContent = "--";
    return;
  }

  valueEl.textContent = value.toFixed(1);

  // Update status indicator
  statusEl.className = "card-status";
  if (value < thresholds.min || value > thresholds.max) {
    statusEl.classList.add("danger");
  } else if (value < thresholds.min * 1.1 || value > thresholds.max * 0.9) {
    statusEl.classList.add("warning");
  }
}

function updateStats(data) {
  if (!data) return;

  document.getElementById("stat-readings").textContent =
    data.summary?.total_readings || "--";
  document.getElementById("stat-alerts").textContent =
    data.summary?.total_alerts || "0";
  document.getElementById("stat-avg-temp").textContent = data.temperature
    ? `${data.temperature.avg}°C`
    : "--°C";
  document.getElementById("stat-avg-humidity").textContent = data.humidity
    ? `${data.humidity.avg}%`
    : "--%";

  // Update range displays
  if (data.temperature) {
    document.getElementById(
      "temp-range"
    ).textContent = `Min: ${data.temperature.min}°C | Max: ${data.temperature.max}°C`;
  }
  if (data.humidity) {
    document.getElementById(
      "humidity-range"
    ).textContent = `Min: ${data.humidity.min}% | Max: ${data.humidity.max}%`;
  }
  if (data.soil_moisture) {
    document.getElementById(
      "soil-range"
    ).textContent = `Min: ${data.soil_moisture.min}% | Max: ${data.soil_moisture.max}%`;
  }
  if (data.light_intensity) {
    document.getElementById(
      "light-range"
    ).textContent = `Min: ${data.light_intensity.min} | Max: ${data.light_intensity.max} lux`;
  }
}

function updateAlertsList(data) {
  const container = document.getElementById("alerts-list");

  if (!data || !data.alerts || data.alerts.length === 0) {
    container.innerHTML =
      '<p class="no-alerts">✅ No recent alerts - all systems normal!</p>';
    return;
  }

  const alertsHtml = data.alerts
    .slice(0, 8)
    .map((alert) => {
      const isCritical = alert.severity === "CRITICAL";
      const icon = isCritical ? "🚨" : "⚠️";
      const time = new Date(alert.reading_timestamp).toLocaleTimeString();

      return `
            <div class="alert-item ${isCritical ? "" : "warning"}">
                <span class="alert-icon">${icon}</span>
                <span class="alert-text">
                    <strong>${alert.alert_type.replace(/_/g, " ")}</strong><br>
                    Value: ${alert.value}${alert.unit} (threshold: ${
        alert.threshold
      }${alert.unit})
                </span>
                <span class="alert-time">${time}</span>
            </div>
        `;
    })
    .join("");

  container.innerHTML = alertsHtml;
}

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById("connection-status");
  if (connected) {
    statusEl.textContent = "🟢 Connected";
    statusEl.style.color = "#28a745";
  } else {
    statusEl.textContent = "🔴 Connection Error";
    statusEl.style.color = "#dc3545";
  }
}

// ============================================
// Chart Functions
// ============================================
function initChart() {
  const ctx = document.getElementById("sensor-chart").getContext("2d");

  sensorChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Temperature (°C)",
          data: [],
          borderColor: "#ff6b6b",
          backgroundColor: "rgba(255, 107, 107, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y",
        },
        {
          label: "Humidity (%)",
          data: [],
          borderColor: "#4dabf7",
          backgroundColor: "rgba(77, 171, 247, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y1",
        },
        {
          label: "Soil Moisture (%)",
          data: [],
          borderColor: "#8b5a2b",
          backgroundColor: "rgba(139, 90, 43, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "y1",
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
          position: "top",
          labels: {
            usePointStyle: true,
            padding: 20,
          },
        },
        tooltip: {
          backgroundColor: "rgba(0, 0, 0, 0.8)",
          padding: 12,
          titleFont: { size: 14 },
          bodyFont: { size: 13 },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxTicksLimit: 10 },
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          title: { display: true, text: "Temperature (°C)" },
          grid: { color: "rgba(0, 0, 0, 0.05)" },
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          title: { display: true, text: "Percentage (%)" },
          grid: { drawOnChartArea: false },
          min: 0,
          max: 100,
        },
      },
    },
  });
}

function updateChartData(historyData) {
  if (!sensorChart || !historyData || !historyData.readings) return;

  const readings = historyData.readings;

  // Limit data points for performance
  const maxPoints = 100;
  const step = Math.max(1, Math.floor(readings.length / maxPoints));
  const sampledReadings = readings.filter((_, i) => i % step === 0);

  // Extract data
  const labels = sampledReadings.map((r) => {
    const date = new Date(r.timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  });

  const temperatures = sampledReadings.map(
    (r) => r.sensors?.temperature?.value
  );
  const humidities = sampledReadings.map((r) => r.sensors?.humidity?.value);
  const soilMoistures = sampledReadings.map(
    (r) => r.sensors?.soil_moisture?.value
  );

  // Update chart
  sensorChart.data.labels = labels;
  sensorChart.data.datasets[0].data = temperatures;
  sensorChart.data.datasets[1].data = humidities;
  sensorChart.data.datasets[2].data = soilMoistures;
  sensorChart.update("none");
}

async function updateCharts() {
  const hours = parseInt(document.getElementById("chart-hours").value);
  try {
    const historyData = await getHistory(hours);
    updateChartData(historyData);
  } catch (error) {
    console.error("Failed to update charts:", error);
  }
}

// ============================================
// Main Functions
// ============================================
async function refreshData() {
  const btn = document.getElementById("refresh-btn");
  btn.textContent = "⏳ Loading...";
  btn.disabled = true;

  try {
    // Fetch all data in parallel
    const [latest, stats, alerts] = await Promise.all([
      getLatestReading(),
      getStats(24),
      getAlerts(10),
    ]);

    updateCurrentReadings(latest);
    updateStats(stats);
    updateAlertsList(alerts);
    await updateCharts();

    updateConnectionStatus(true);
  } catch (error) {
    console.error("Refresh failed:", error);
  } finally {
    btn.textContent = "🔄 Refresh";
    btn.disabled = false;
  }
}

async function loadGreenhouses() {
  try {
    const data = await getGreenhouses();
    const select = document.getElementById("greenhouse-select");

    if (data.greenhouses && data.greenhouses.length > 0) {
      select.innerHTML = data.greenhouses
        .map((id) => `<option value="${id}">${id}</option>`)
        .join("");
    }

    select.addEventListener("change", (e) => {
      currentGreenhouseId = e.target.value;
      refreshData();
    });
  } catch (error) {
    console.error("Failed to load greenhouses:", error);
  }
}

// ============================================
// Initialization
// ============================================
document.addEventListener("DOMContentLoaded", async () => {
  console.log("🌱 Smart GreenHouse Dashboard initializing...");

  // Check API configuration
  if (API_BASE_URL === "YOUR_API_GATEWAY_URL_HERE") {
    alert(
      "⚠️ Please update API_BASE_URL in dashboard.js with your API Gateway URL!"
    );
    return;
  }

  // Initialize chart
  initChart();

  // Load greenhouses dropdown
  await loadGreenhouses();

  // Initial data load
  await refreshData();

  // Auto-refresh every 30 seconds
  refreshInterval = setInterval(refreshData, 30000);

  console.log("✅ Dashboard ready!");
});

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
  if (refreshInterval) clearInterval(refreshInterval);
});
