/**
 * Log-Guard Dashboard - Real-time WebSocket Client
 *
 * WebSocket을 통해 백엔드로부터 실시간 통계와 이상 탐지 알림을 수신하고,
 * Chart.js를 사용하여 트래픽, 레이턴시, 에러율 그래프를 업데이트합니다.
 */

// ─── Configuration ───────────────────────────────────────
const WS_URL = `ws://${window.location.host}/ws`;
const MAX_DATA_POINTS = 120; // 차트에 표시할 최대 데이터 포인트 수
const MAX_ALERTS = 50;

// ─── State ───────────────────────────────────────────────
let ws = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let prevStats = null;
let alertCount = 0;

// ─── DOM References ──────────────────────────────────────
const dom = {
    connectionStatus: document.getElementById('connection-status'),
    statusText: document.querySelector('.status-text'),
    currentTime: document.getElementById('current-time'),
    totalLogs: document.getElementById('total-logs'),
    totalLogsTrend: document.getElementById('total-logs-trend'),
    logsPerSec: document.getElementById('logs-per-sec'),
    logsPerSecTrend: document.getElementById('logs-per-sec-trend'),
    avgLatency: document.getElementById('avg-latency'),
    avgLatencyTrend: document.getElementById('avg-latency-trend'),
    errorRate: document.getElementById('error-rate'),
    errorRateTrend: document.getElementById('error-rate-trend'),
    anomalyCount: document.getElementById('anomaly-count'),
    anomalyTrend: document.getElementById('anomaly-trend'),
    alertsFeed: document.getElementById('alerts-feed'),
    clearAlertsBtn: document.getElementById('clear-alerts-btn'),
    cardAnomalies: document.getElementById('card-anomalies'),
};

// ─── Chart.js Configuration ─────────────────────────────

const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    interaction: { mode: 'index', intersect: false },
    plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(26, 32, 53, 0.95)',
            titleColor: '#f1f5f9',
            bodyColor: '#94a3b8',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            titleFont: { family: "'Inter', sans-serif", weight: '600' },
            bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
        },
    },
    scales: {
        x: {
            type: 'time',
            time: { unit: 'second', displayFormats: { second: 'HH:mm:ss' } },
            grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
            ticks: { color: '#64748b', font: { size: 10, family: "'JetBrains Mono', monospace" }, maxTicksLimit: 8 },
            border: { display: false },
        },
        y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
            ticks: { color: '#64748b', font: { size: 10, family: "'JetBrains Mono', monospace" }, maxTicksLimit: 6 },
            border: { display: false },
        },
    },
};

// Traffic Chart
const trafficChart = new Chart(document.getElementById('traffic-chart'), {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Logs Processed',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.08)',
                fill: true,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
            },
            {
                label: 'Anomalies',
                data: [],
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.3)',
                borderWidth: 0,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointStyle: 'triangle',
                showLine: false,
            },
        ],
    },
    options: { ...chartDefaults },
});

// Latency Chart
const latencyChart = new Chart(document.getElementById('latency-chart'), {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Avg Latency (ms)',
                data: [],
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.08)',
                fill: true,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
            },
        ],
    },
    options: {
        ...chartDefaults,
        scales: {
            ...chartDefaults.scales,
            y: {
                ...chartDefaults.scales.y,
                ticks: {
                    ...chartDefaults.scales.y.ticks,
                    callback: (value) => value + 'ms',
                },
            },
        },
    },
});

// Error Rate Chart
const errorChart = new Chart(document.getElementById('error-chart'), {
    type: 'line',
    data: {
        datasets: [
            {
                label: 'Error Rate (%)',
                data: [],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.08)',
                fill: true,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
            },
        ],
    },
    options: {
        ...chartDefaults,
        scales: {
            ...chartDefaults.scales,
            y: {
                ...chartDefaults.scales.y,
                suggestedMax: 20,
                ticks: {
                    ...chartDefaults.scales.y.ticks,
                    callback: (value) => value + '%',
                },
            },
        },
    },
});

// ─── WebSocket Connection ────────────────────────────────

function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const demoTimeout = setTimeout(() => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log('[Log-Guard] Server connection delayed - switching to demo mode');
            runDemoMode();
        }
    }, 2000);

    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('[Log-Guard] WebSocket connected');
        clearTimeout(demoTimeout);
        reconnectAttempts = 0;
        setConnectionStatus(true);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'stats') {
                handleStats(msg.data);
            } else if (msg.type === 'anomaly') {
                handleAnomaly(msg.data);
            }
        } catch (e) {
            console.error('[Log-Guard] Parse error:', e);
        }
    };

    ws.onclose = () => {
        console.log('[Log-Guard] WebSocket disconnected');
        setConnectionStatus(false);
        runDemoMode();
        scheduleReconnect();
    };

    ws.onerror = (err) => {
        console.error('[Log-Guard] WebSocket error:', err);
        ws.close();
    };
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
    console.log(`[Log-Guard] Reconnecting in ${delay / 1000}s...`);
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
    }, delay);
}

function setConnectionStatus(connected) {
    dom.connectionStatus.className = `status-badge ${connected ? 'connected' : 'disconnected'}`;
    dom.statusText.textContent = connected ? 'Connected' : 'Disconnected';
}

// ─── Stats Handler ───────────────────────────────────────

function handleStats(stats) {
    const now = new Date();

    // Update stat cards
    animateValue(dom.totalLogs, stats.total_processed);
    dom.logsPerSec.textContent = calculateRate(stats.total_processed);
    dom.avgLatency.innerHTML = `${stats.avg_latency.toFixed(1)}<span class="stat-unit">ms</span>`;
    dom.errorRate.innerHTML = `${stats.error_rate.toFixed(1)}<span class="stat-unit">%</span>`;
    dom.anomalyCount.textContent = stats.total_anomalies;

    // Update trends
    if (prevStats) {
        const logDelta = stats.total_processed - prevStats.total_processed;
        dom.totalLogsTrend.textContent = `+${logDelta} since last update`;

        const latencyDiff = stats.avg_latency - prevStats.avg_latency;
        if (Math.abs(latencyDiff) > 0.1) {
            dom.avgLatencyTrend.textContent = `${latencyDiff > 0 ? '+' : ''}${latencyDiff.toFixed(1)}ms`;
            dom.avgLatencyTrend.className = `stat-trend ${latencyDiff > 0 ? 'up' : 'down'}`;
        }

        const errorDiff = stats.error_rate - prevStats.error_rate;
        if (Math.abs(errorDiff) > 0.01) {
            dom.errorRateTrend.textContent = `${errorDiff > 0 ? '+' : ''}${errorDiff.toFixed(1)}%`;
            dom.errorRateTrend.className = `stat-trend ${errorDiff > 0 ? 'up' : 'down'}`;
        }
    }

    // Anomaly card state
    if (stats.total_anomalies > 0) {
        dom.cardAnomalies.classList.add('has-anomalies');
        dom.anomalyTrend.textContent = `${stats.total_anomalies} detected`;
        dom.anomalyTrend.className = 'stat-trend up';
    }

    // Update charts
    addChartData(trafficChart, 0, now, stats.total_processed);
    addChartData(latencyChart, 0, now, stats.avg_latency);
    addChartData(errorChart, 0, now, stats.error_rate);

    prevStats = { ...stats };
}

function calculateRate(totalProcessed) {
    if (!prevStats) return '0';
    const rate = totalProcessed - prevStats.total_processed;
    return rate > 0 ? rate.toString() : '0';
}

function animateValue(element, newValue) {
    const currentText = element.textContent.replace(/[^0-9]/g, '');
    const current = parseInt(currentText) || 0;
    if (newValue === current) return;

    element.textContent = newValue.toLocaleString();
    element.closest('.stat-card')?.classList.add('flash');
    setTimeout(() => {
        element.closest('.stat-card')?.classList.remove('flash');
    }, 600);
}

// ─── Anomaly Handler ─────────────────────────────────────

function handleAnomaly(data) {
    alertCount++;
    dom.anomalyCount.textContent = alertCount;

    // Add marker to traffic chart
    const anomalyDataset = trafficChart.data.datasets[1];
    anomalyDataset.data.push({ x: new Date(data.detected_at), y: prevStats?.total_processed || 0 });
    if (anomalyDataset.data.length > MAX_DATA_POINTS) {
        anomalyDataset.data.shift();
    }
    trafficChart.update('none');

    // Flash effect on anomaly card
    dom.cardAnomalies.classList.add('has-anomalies');

    // Add alert to feed
    addAlertToFeed(data);
}

function addAlertToFeed(data) {
    // Remove empty state
    const emptyState = dom.alertsFeed.querySelector('.alert-empty');
    if (emptyState) emptyState.remove();

    const time = new Date(data.detected_at);
    const timeStr = time.toLocaleTimeString('ko-KR', { hour12: false });

    const alertEl = document.createElement('div');
    alertEl.className = 'alert-item';
    alertEl.innerHTML = `
        <span class="alert-type-badge ${data.anomaly_type}">${data.anomaly_type}</span>
        <div>
            <div class="alert-message">${escapeHtml(data.message)}</div>
            <div class="alert-details">
                <span>Z=${data.z_score.toFixed(2)}</span>
                <span>val=${data.current_value}</span>
                <span>mean=${data.mean}</span>
                <span>std=${data.std}</span>
                <span>window=${data.window_size}</span>
            </div>
        </div>
        <span class="alert-time">${timeStr}</span>
    `;

    // Prepend (newest first)
    dom.alertsFeed.insertBefore(alertEl, dom.alertsFeed.firstChild);

    // Limit feed size
    while (dom.alertsFeed.children.length > MAX_ALERTS) {
        dom.alertsFeed.removeChild(dom.alertsFeed.lastChild);
    }
}

// ─── Chart Helpers ───────────────────────────────────────

function addChartData(chart, datasetIndex, time, value) {
    const dataset = chart.data.datasets[datasetIndex];
    dataset.data.push({ x: time, y: value });

    if (dataset.data.length > MAX_DATA_POINTS) {
        dataset.data.shift();
    }

    chart.update('none');
}

// ─── Utilities ───────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateClock() {
    const now = new Date();
    dom.currentTime.textContent = now.toLocaleTimeString('ko-KR', { hour12: false });
}

// ─── Event Listeners ─────────────────────────────────────

dom.clearAlertsBtn.addEventListener('click', () => {
    dom.alertsFeed.innerHTML = `
        <div class="alert-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <polyline points="9 12 12 15 16 10"/>
            </svg>
            <p>No anomalies detected yet. System is monitoring...</p>
        </div>
    `;
});

// ─── Init ────────────────────────────────────────────────
// ─── Demo Mode (Serverless Simulator) ───────────────────

let isDemoMode = false;
let demoInterval = null;

function runDemoMode() {
    if (isDemoMode) return;
    isDemoMode = true;

    console.log('[Log-Guard] Demo Mode Active - Simulating real-time data');
    setConnectionStatus(false);
    dom.statusText.textContent = 'Demo Mode';
    dom.connectionStatus.classList.add('demo');

    let totalProcessed = prevStats ? prevStats.total_processed : 0;
    let totalAnomalies = prevStats ? prevStats.total_anomalies : 0;
    
    demoInterval = setInterval(() => {
        const now = new Date();
        const isAnomalyHit = Math.random() > 0.96; 
        
        const addedLogs = Math.floor(Math.random() * 15) + 5;
        totalProcessed += addedLogs;
        
        const stats = {
            total_processed: totalProcessed,
            total_anomalies: totalAnomalies,
            avg_latency: isAnomalyHit ? 450 + Math.random() * 500 : 40 + Math.random() * 80,
            error_rate: isAnomalyHit ? 15 + Math.random() * 10 : 0.5 + Math.random() * 2,
        };
        
        handleStats(stats);

        if (isAnomalyHit) {
            totalAnomalies++;
            handleAnomaly({
                anomaly_type: Math.random() > 0.5 ? 'LATENCY_SPIKE' : 'ERROR_RATE_SPIKE',
                message: isAnomalyHit ? 'Sudden increase in response time' : 'Error rate exceeded threshold',
                detected_at: now.toISOString(),
                z_score: 3.0 + Math.random() * 2,
                current_value: stats.avg_latency.toFixed(1),
                mean: 55.4,
                std: 12.2,
                window_size: 60
            });
        }
    }, 1000);
}

function stopDemoMode() {
    if (!isDemoMode) return;
    isDemoMode = false;
    if (demoInterval) clearInterval(demoInterval);
    dom.connectionStatus.classList.remove('demo');
    console.log('[Log-Guard] Demo Mode Stopped - Switched to Live Data');
}

// ─── Init ────────────────────────────────────────────────

updateClock();
setInterval(updateClock, 1000);
connect();

// 주기적으로 연결 확인 및 유지
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
        stopDemoMode();
    }
}, 15000);

// Demo Mode 스타일 보조 루틴
const style = document.createElement('style');
style.textContent = `
    .status-badge.demo { background: rgba(59, 130, 246, 0.2) !important; color: #60a5fa !important; border: 1px solid rgba(96, 165, 250, 0.3) !important; }
    .status-badge.demo::before { background: #3b82f6 !important; box-shadow: 0 0 8px #3b82f6 !important; }
`;
document.head.appendChild(style);
