// --- Global Variables ---
const socket = io('/ws/demo');
let totalViolators = 0;
let totalSOS = 0;
let totalRecords = 0;
let currentIndex = 0;

// Chart instances
let locationChart = null;
let temperatureChart = null;
let alertsChart = null;

// --- DOM Elements ---
const statusIndicator = document.getElementById('status-indicator');
const currentTimeDisplay = document.getElementById('current-time');
const groundCounter = document.getElementById('ground-counter');
const nusukCounter = document.getElementById('nusuk-counter');
const timeCounter = document.getElementById('time-counter');
const tempCounter = document.getElementById('temp-counter');

// Stat cards
const redStat = document.getElementById('red-stat');
const orangeStat = document.getElementById('orange-stat');
const yellowStat = document.getElementById('yellow-stat');
const blueStat = document.getElementById('blue-stat');
const braceletCountElem = document.getElementById('bracelet-count');
const braceletContainer = document.getElementById('bracelet-container');

// Action log
const actionLog = document.getElementById('action-log');

// Telemetry display
const telemetryId = document.getElementById('telemetry-id');
const telemetryTemp = document.getElementById('telemetry-temp');
const telemetryGround = document.getElementById('telemetry-ground');
const telemetryNusuk = document.getElementById('telemetry-nusuk');
const telemetrySos = document.getElementById('telemetry-sos');
const telemetryAlert = document.getElementById('telemetry-alert');

// Temperature stats
const minTemp = document.getElementById('min-temp');
const maxTemp = document.getElementById('max-temp');
const avgTemp = document.getElementById('avg-temp');

// Controls
const startBtn = document.getElementById('start-btn');
const pauseBtn = document.getElementById('pause-btn');
const resetBtn = document.getElementById('reset-btn');
const nextStepBtn = document.getElementById('next-step-btn');
const speedSelect = document.getElementById('speed-select');
const simulationInfo = document.getElementById('simulation-info');
const lostPersonModal = document.getElementById('lost-person-modal');
const lostIdDisplay = document.getElementById('lost-id-display');
const closeBtn = document.querySelector('.close-btn');

// --- Utility Functions ---
function updateSimulationInfo(running, current, total) {
    const statusText = running ? 'قيد التشغيل' : 'متوقف';
    simulationInfo.textContent = `الحالة: ${statusText}. السجل: ${current} / ${total}`;
    currentIndex = current;
    totalRecords = total;
}

function updateControlButtons(running) {
    startBtn.disabled = running;
    pauseBtn.disabled = !running;
    nextStepBtn.disabled = running;
}

function logAction(icon, action, alertClass) {
    const li = document.createElement('li');
    li.className = `alert-${alertClass}`;
    li.innerHTML = `<strong>${icon} ${action}</strong> - ${new Date().toLocaleTimeString('ar-EG')}`;
    
    if (actionLog.firstChild) {
        actionLog.insertBefore(li, actionLog.firstChild);
    } else {
        actionLog.appendChild(li);
    }
    
    if (actionLog.children.length > 50) {
        actionLog.removeChild(actionLog.lastChild);
    }
}

// Bracelet simulation store
const bracelets = {}; // { pilgrim_id: { alert, temp, ts } }
let lastUpdatedBracelet = null;

function renderBracelets() {
    if (!braceletContainer) return;
    // Limit to recent 100 bracelets for display
    const ids = Object.keys(bracelets).slice(-100);
    braceletContainer.innerHTML = '';

    ids.forEach(id => {
        const info = bracelets[id];
        const dot = document.createElement('div');
        dot.className = 'bracelet-dot';
        dot.title = `${id} — ${info.alert} — ${info.temp}°C`;
        dot.dataset.pilgrim = id;
        // color by alert
        const color = getAlertColor(info.alert) || '#6c757d';
        dot.style.boxShadow = `0 0 0 2px ${color}55`;
        dot.style.backgroundColor = color;
        // small label inside for accessibility (hidden visually)
        const sr = document.createElement('span');
        sr.className = 'sr-only';
        sr.textContent = id;
        dot.appendChild(sr);
        braceletContainer.appendChild(dot);
        // pulse the most recently updated bracelet
        if (lastUpdatedBracelet && id === lastUpdatedBracelet) {
            dot.classList.add('pulse');
            setTimeout(() => dot.classList.remove('pulse'), 900);
        }
    });

    braceletCountElem.textContent = Object.keys(bracelets).length;
}

function flashStat(alertType) {
    const map = {
        'RED': '.stat-red',
        'ORANGE': '.stat-orange',
        'YELLOW': '.stat-yellow',
        'BLUE': '.stat-blue',
        'GREEN': '#bracelet-card'
    };
    const selector = map[alertType];
    if (!selector) return;
    const card = document.querySelector(selector);
    if (!card) return;
    const icon = card.querySelector('.stat-icon');
    if (!icon) return;
    icon.classList.add('flash');
    setTimeout(() => icon.classList.remove('flash'), 1200);
}

function showLostPersonModal(lostId) {
    lostIdDisplay.textContent = lostId;
    lostPersonModal.style.display = 'block';
}

function hideLostPersonModal() {
    lostPersonModal.style.display = 'none';
}

function updateCurrentTime() {
    const now = new Date();
    currentTimeDisplay.textContent = now.toLocaleTimeString('ar-EG');
}

// Update time every second
setInterval(updateCurrentTime, 1000);
updateCurrentTime();

// --- Chart Initialization ---
function initLocationChart() {
    const ctx = document.getElementById('locationChart').getContext('2d');
    locationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['الحرم', 'منى', 'عرفات', 'مزدلفة', 'الجمرات'],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    '#007bff',
                    '#28a745',
                    '#ffc107',
                    '#fd7e14',
                    '#17a2b8'
                ],
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { family: "'Cairo', sans-serif", size: 12 },
                        padding: 15
                    }
                }
            }
        }
    });
}

function initTemperatureChart() {
    const ctx = document.getElementById('temperatureChart').getContext('2d');
    temperatureChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'المتوسط',
                    data: [],
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'الحد الأقصى',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'الحد الأدنى',
                    data: [],
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        font: { family: "'Cairo', sans-serif", size: 11 },
                        padding: 10
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        font: { family: "'Cairo', sans-serif" }
                    }
                },
                x: {
                    ticks: {
                        font: { family: "'Cairo', sans-serif" }
                    }
                }
            }
        }
    });
}

function initAlertsChart() {
    const ctx = document.getElementById('alertsChart').getContext('2d');
    alertsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'مخالفات المسار',
                    data: [],
                    backgroundColor: '#dc3545'
                },
                {
                    label: 'نداءات استغاثة',
                    data: [],
                    backgroundColor: '#fd7e14'
                },
                {
                    label: 'إجهاد حراري',
                    data: [],
                    backgroundColor: '#ffc107'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        font: { family: "'Cairo', sans-serif", size: 11 },
                        padding: 10
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        font: { family: "'Cairo', sans-serif" }
                    }
                },
                x: {
                    ticks: {
                        font: { family: "'Cairo', sans-serif" }
                    }
                }
            }
        }
    });
}

// --- Update Charts ---
function updateLocationChart(locations) {
    if (!locationChart) return;
    
    const locationNames = ['Haram', 'Mina', 'Arafat', 'Muzdalifah', 'Jamarat'];
    const counts = locationNames.map(loc => locations[loc] || 0);
    
    locationChart.data.datasets[0].data = counts;
    locationChart.update();
}

function updateTemperatureChart(data) {
    if (!temperatureChart) return;
    
    const labels = data.timestamps.map(ts => new Date(ts).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }));
    
    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = data.avg_temps;
    temperatureChart.data.datasets[1].data = data.max_temps;
    temperatureChart.data.datasets[2].data = data.min_temps;
    temperatureChart.update();
}

function updateAlertsChart(data) {
    if (!alertsChart) return;
    
    const labels = data.timestamps.map(ts => new Date(ts).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }));
    
    alertsChart.data.labels = labels;
    alertsChart.data.datasets[0].data = data.red;
    alertsChart.data.datasets[1].data = data.orange;
    alertsChart.data.datasets[2].data = data.yellow;
    alertsChart.update();
}

// --- Fetch and Update Statistics ---
function fetchAndUpdateStatistics() {
    fetch('/api/statistics')
        .then(res => res.json())
        .then(data => {
            redStat.textContent = data.alerts.red;
            orangeStat.textContent = data.alerts.orange;
            yellowStat.textContent = data.alerts.yellow;
            blueStat.textContent = data.alerts.blue;
            
            minTemp.textContent = data.temperature.min.toFixed(1) + '°C';
            maxTemp.textContent = data.temperature.max.toFixed(1) + '°C';
            avgTemp.textContent = data.temperature.avg.toFixed(1) + '°C';
            
            updateLocationChart(data.locations);
        })
        .catch(err => console.error('Error fetching statistics:', err));
}

function fetchAndUpdateCharts() {
    fetch('/api/temperature-timeline')
        .then(res => res.json())
        .then(data => updateTemperatureChart(data))
        .catch(err => console.error('Error fetching temperature timeline:', err));
    
    fetch('/api/alerts-timeline')
        .then(res => res.json())
        .then(data => updateAlertsChart(data))
        .catch(err => console.error('Error fetching alerts timeline:', err));
}

// --- WebSocket Handlers ---

socket.on('connect', () => {
    console.log('Connected to WebSocket');
    statusIndicator.textContent = 'متصل';
    statusIndicator.className = 'status-green';
    
    // Initialize charts
    initLocationChart();
    initTemperatureChart();
    initAlertsChart();
    
    // Fetch initial data
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            updateControlButtons(data.running);
            updateSimulationInfo(data.running, data.current_index, data.total_records);
            speedSelect.value = data.speed;
        });
    
    // Update statistics and charts
    fetchAndUpdateStatistics();
    fetchAndUpdateCharts();
});

socket.on('disconnect', () => {
    console.log('Disconnected from WebSocket');
    statusIndicator.textContent = 'غير متصل';
    statusIndicator.className = 'status-red';
    updateControlButtons(false);
});

socket.on('realtime_event', (data) => {
    console.log('New Event:', data);
    
    // Update telemetry display
    telemetryId.textContent = data.event.pilgrim_id;
    telemetryTemp.textContent = data.event.temp.toFixed(1) + '°C';
    telemetryGround.textContent = data.event.ground;
    telemetryNusuk.textContent = data.event.nusuk;
    telemetrySos.textContent = data.event.sos ? 'نعم ⚠️' : 'لا ✅';
    
    // Update alert display with color
    telemetryAlert.textContent = data.action;
    telemetryAlert.style.backgroundColor = getAlertColor(data.alert);
    telemetryAlert.style.color = 'white';
    
    // Update action log
    logAction(data.icon, data.action, data.alert);
    
    // Handle specific alerts
    if (data.alert === 'RED') {
        totalViolators++;
        // optimistic UI increment
        redStat.textContent = parseInt(redStat.textContent || '0') + 1;
    } else if (data.alert === 'ORANGE') {
        totalSOS++;
        orangeStat.textContent = parseInt(orangeStat.textContent || '0') + 1;
    } else if (data.alert === 'BLUE' && data.event.lost_id) {
        showLostPersonModal(data.event.lost_id);
        blueStat.textContent = parseInt(blueStat.textContent || '0') + 1;
    }

    // Update bracelet simulation
    bracelets[data.event.pilgrim_id] = {
        alert: data.alert,
        temp: data.event.temp,
        ts: data.event.timestamp
    };
    lastUpdatedBracelet = data.event.pilgrim_id;
    renderBracelets();

    // Flash the stat icon for visual feedback
    flashStat(data.alert);
    
    // Update simulation info
    updateSimulationInfo(true, currentIndex + 1, totalRecords);
    
    // Update statistics periodically
    if (currentIndex % 10 === 0) {
        fetchAndUpdateStatistics();
        fetchAndUpdateCharts();
    }
});

socket.on('counters_update', (data) => {
    groundCounter.textContent = data.ground;
    nusukCounter.textContent = data.nusuk;
    timeCounter.textContent = data.time;
});

socket.on('simulation_status', (data) => {
    console.log('Simulation Status:', data);
    
    if (data.status === 'start') {
        updateControlButtons(true);
    } else if (data.status === 'pause' || data.status === 'reset' || data.status === 'finished') {
        updateControlButtons(false);
    }
    
    if (data.status === 'reset' || data.status === 'finished') {
        currentIndex = 0;
        totalViolators = 0;
        totalSOS = 0;
        
        redStat.textContent = 0;
        orangeStat.textContent = 0;
        yellowStat.textContent = 0;
        blueStat.textContent = 0;
        
        actionLog.innerHTML = '';
        
        groundCounter.textContent = '---';
        nusukCounter.textContent = '---';
        timeCounter.textContent = '---';
        tempCounter.textContent = '---';
        
        telemetryId.textContent = '---';
        telemetryTemp.textContent = '---';
        telemetryGround.textContent = '---';
        telemetryNusuk.textContent = '---';
        telemetrySos.textContent = '---';
        telemetryAlert.textContent = '---';
        
        hideLostPersonModal();
        
        // Refresh charts
        fetchAndUpdateStatistics();
        fetchAndUpdateCharts();
    }
    
    if (data.running !== undefined) {
        updateSimulationInfo(data.running, currentIndex, totalRecords);
    }
});

// --- Control Handlers ---

function sendControlAction(action, value = null) {
    fetch('/api/control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action, value }),
    })
    .then(res => res.json())
    .then(data => {
        console.log('Control Response:', data);
    })
    .catch(error => console.error('Error sending control action:', error));
}

startBtn.addEventListener('click', () => sendControlAction('START'));
pauseBtn.addEventListener('click', () => sendControlAction('PAUSE'));
resetBtn.addEventListener('click', () => sendControlAction('RESET'));
nextStepBtn.addEventListener('click', () => sendControlAction('NEXT_STEP'));
function applySpeedUI(speed) {
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach(c => {
        if (parseInt(speed) > 1) c.classList.add('fast'); else c.classList.remove('fast');
    });
    // show in simulation info
    simulationInfo.textContent = `الحالة: ${simulationInfo.textContent.includes('قيد التشغيل') ? 'قيد التشغيل' : 'متوقف'}. السجل: ${currentIndex} / ${totalRecords}  •  سرعة: ${speed}x`;
}

speedSelect.addEventListener('change', (e) => {
    const v = e.target.value;
    applySpeedUI(v);
    sendControlAction('SPEED', v);
});

// --- Modal Close Handlers ---
closeBtn.addEventListener('click', hideLostPersonModal);
window.addEventListener('click', (event) => {
    if (event.target === lostPersonModal) {
        hideLostPersonModal();
    }
});

// --- Helper Functions ---
function getAlertColor(alertType) {
    const colors = {
        'RED': '#dc3545',
        'ORANGE': '#fd7e14',
        'YELLOW': '#ffc107',
        'BLUE': '#17a2b8',
        'GREEN': '#28a745'
    };
    return colors[alertType] || '#6c757d';
}

// --- PWA Service Worker Registration ---
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/service-worker.js').then(registration => {
            console.log('SW registered: ', registration);
        }).catch(registrationError => {
            console.log('SW registration failed: ', registrationError);
        });
    });
}
