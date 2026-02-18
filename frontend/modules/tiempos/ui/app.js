/**
 * RPK Time Analysis Dashboard - App Logic
 * @version 2.0.0 Refactor
 */

const API_BASE = '/api';

// Global State
const state = {
    currentTab: 'dashboard',
    fechas: [],
    centros: [],
    selectedCentros: [],
    charts: {},
    filters: {
        from: '',
        to: ''
    }
};

// Colors for Chart.js
const CHART_COLORS = [
    '#E30613', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#ec4899', '#71717a', '#facc15', '#4ade80'
];

/**
 * Initialization
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 RPK Dashboard Initializing...');

    // 1. Initial Data Load
    await initializeSystem();

    // 2. Event Listeners
    setupEventListeners();

    // 3. Render Initial Dashboard
    renderDashboard();

    lucide.createIcons();
});

async function initializeSystem() {
    try {
        // Fetch base data
        const [fechasRes, centrosRes, statusRes] = await Promise.all([
            fetch(`${API_BASE}/fechas`),
            fetch(`${API_BASE}/centros`),
            fetch(`${API_BASE}/status`)
        ]);

        const fechasData = await fechasRes.json();
        const centrosData = await centrosRes.json();
        const statusData = await statusRes.json();

        state.fechas = fechasData.fechas || [];
        state.centros = centrosData.centros || [];

        // Setup initial date filters (last 30 days if available)
        if (state.fechas.length > 0) {
            state.filters.to = state.fechas[state.fechas.length - 1];
            state.filters.from = state.fechas[Math.max(0, state.fechas.length - 30)];

            document.getElementById('date-from').value = state.filters.from;
            document.getElementById('date-to').value = state.filters.to;
        }

        // Update status indicator
        const statusDot = document.getElementById('system-status');
        if (statusData.status === 'online') {
            statusDot.style.background = '#10b981';
            statusDot.style.boxShadow = '0 0 8px #10b981';
        } else {
            statusDot.style.background = '#f59e0b';
            statusDot.style.boxShadow = '0 0 8px #f59e0b';
        }

    } catch (error) {
        console.error('System initialization failed:', error);
    }
}

function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = link.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // Date Filters
    document.getElementById('date-from').addEventListener('change', (e) => {
        state.filters.from = e.target.value;
        refreshCurrentTab();
    });

    document.getElementById('date-to').addEventListener('change', (e) => {
        state.filters.to = e.target.value;
        refreshCurrentTab();
    });

    // Refresh Button
    document.getElementById('btn-refresh').addEventListener('click', () => refreshCurrentTab());

    // Modal Close
    const overlay = document.getElementById('drilldown-overlay');
    document.getElementById('close-modal').addEventListener('click', () => overlay.style.display = 'none');
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.style.display = 'none';
    });
}

function switchTab(tabId) {
    if (tabId === state.currentTab) return;

    // Update UI active states
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector(`.nav-link[data-tab="${tabId}"]`).classList.add('active');

    // Update visibility
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    const activeTab = document.getElementById(`tab-${tabId}`);
    if (activeTab) activeTab.style.display = 'block';

    state.currentTab = tabId;

    // Refresh the new tab
    refreshCurrentTab();
}

async function refreshCurrentTab() {
    const main = document.querySelector('.main-content');
    main.classList.add('loading');

    try {
        if (state.currentTab === 'dashboard') {
            await renderDashboard();
        } else if (state.currentTab === 'evolution') {
            await renderEvolution();
        } else if (state.currentTab === 'ranking') {
            await renderRanking();
        }
    } finally {
        main.classList.remove('loading');
    }
}

/**
 * DASHBOARD VIEW
 */
async function renderDashboard() {
    const params = new URLSearchParams({
        fecha_inicio: state.filters.from,
        fecha_fin: state.filters.to
    });

    const res = await fetch(`${API_BASE}/summary?${params}`);
    const data = await res.json();

    if (data.error) {
        console.error('Dashboard data error:', data.error);
        return;
    }

    // 1. Update KPIs
    document.getElementById('kpi-total-carga').innerText = data.kpis.total_carga.toLocaleString();
    document.getElementById('kpi-media-carga').innerText = data.kpis.media_carga.toLocaleString();
    document.getElementById('kpi-centros').innerText = data.kpis.num_centros;

    // 2. Render Main Chart
    renderMainChart(data);

    // 3. Render Mini Ranking
    renderMiniRanking(data.rankings);
}

function renderMainChart(data) {
    const ctx = document.getElementById('mainChart').getContext('2d');

    if (state.charts.main) state.charts.main.destroy();

    const datasets = [
        {
            label: 'Carga Total',
            data: data.evolucion_total.cargas,
            borderColor: '#E30613',
            backgroundColor: 'rgba(227, 6, 19, 0.1)',
            fill: true,
            tension: 0.4,
            borderWidth: 3,
            pointRadius: 0,
            pointHoverRadius: 6,
            yAxisID: 'y'
        }
    ];

    // Add Top 5 centers
    let colorIdx = 1;
    Object.entries(data.evolucion_centros).forEach(([centro, cData]) => {
        datasets.push({
            label: `Centro ${centro}`,
            data: cData.cargas,
            borderColor: CHART_COLORS[colorIdx++ % CHART_COLORS.length],
            borderWidth: 1.5,
            borderDash: [5, 5],
            fill: false,
            tension: 0.4,
            pointRadius: 0,
            yAxisID: 'y'
        });
    });

    state.charts.main = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.evolucion_total.fechas,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: false // We use custom legends if needed
                },
                tooltip: {
                    backgroundColor: 'rgba(18, 18, 23, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#a0a0ab',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    usePointStyle: true,
                    callbacks: {
                        label: (context) => ` ${context.dataset.label}: ${context.parsed.y.toFixed(1)}h`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#63636e', maxRotation: 0, autoSkip: true }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#63636e' }
                }
            }
        }
    });

    // Update Custom Legend Container
    renderCustomLegend('chart-legend-container', datasets);
}

function renderCustomLegend(containerId, datasets) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = datasets.slice(0, 6).map(ds => `
        <div class="status-indicator" style="margin-right: 1.5rem; display: inline-flex;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background: ${ds.borderColor}; margin-right: 6px;"></div>
            <span style="font-size: 0.75rem;">${ds.label}</span>
        </div>
    `).join('');
}

function renderMiniRanking(rankings) {
    const tbody = document.getElementById('mini-ranking-body');
    if (!tbody) return;

    if (!rankings || rankings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center">No hay datos disponibles.</td></tr>';
        return;
    }

    tbody.innerHTML = rankings.slice(0, 10).map(r => {
        const centroId = r.Centro || 'N/A';
        const media = r.Media_Diaria || 0;

        return `
            <tr style="cursor: pointer" onclick="showDrilldown('${centroId}')">
                <td><span class="center-tag">${centroId}</span></td>
                <td class="font-bold">${r.Carga_Total.toFixed(1)}h</td>
                <td class="text-right">
                    <span class="rpk-red-text font-bold">${media.toFixed(1)}h/día</span>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * RANKING VIEW (FULL)
 */
async function renderRanking() {
    const params = new URLSearchParams({
        fecha_inicio: state.filters.from,
        fecha_fin: state.filters.to
    });

    const res = await fetch(`${API_BASE}/summary?${params}`);
    const data = await res.json();

    const tbody = document.getElementById('full-ranking-body');
    if (!tbody) return;

    if (!data.rankings || data.rankings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No hay datos de ranking disponibles para este periodo.</td></tr>';
        return;
    }

    tbody.innerHTML = data.rankings.map(r => {
        const centroId = r.Centro || 'N/A';
        const media = r.Media_Diaria || 0;

        return `
            <tr style="cursor: pointer" onclick="showDrilldown('${centroId}')">
                <td><span class="center-tag">${centroId}</span></td>
                <td class="font-bold">${r.Carga_Total.toFixed(1)}h</td>
                <td class="font-bold rpk-red-text">${media.toFixed(2)}h</td>
                <td class="text-muted">${data.kpis.num_dias} días</td>
                <td class="text-muted">-</td>
            </tr>
        `;
    }).join('');
}

/**
 * DRILLDOWN MODAL
 */
window.showDrilldown = async (centro) => {
    const overlay = document.getElementById('drilldown-overlay');
    const tableBody = document.getElementById('drilldown-body');
    const title = document.getElementById('drilldown-title');

    title.innerText = `Centro ${centro} | Análisis Artículos`;
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center">Cargando desglose...</td></tr>';
    overlay.style.display = 'flex';

    try {
        // We use the month from the "to" filter for the breakdown
        const mes = state.filters.to.substring(0, 7);
        const res = await fetch(`${API_BASE}/centro/${centro}/articulos/mes/${mes}`);
        const data = await res.json();

        if (!data.articulos || data.articulos.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center">No hay datos para este periodo.</td></tr>';
            return;
        }

        tableBody.innerHTML = data.articulos.map(art => `
            <tr>
                <td class="font-bold">${art.articulo}</td>
                <td style="color: var(--text-muted)">${art.of || '-'}</td>
                <td class="rpk-red-text">${art.horas.toFixed(1)}h</td>
                <td class="text-center">${art.dias}</td>
                <td>
                    <div class="progress-bar-container" style="margin-top:0">
                        <div class="progress-fill" style="width: ${art.porcentaje}%"></div>
                    </div>
                    <span style="font-size: 0.7rem; color: var(--text-muted)">${art.porcentaje}% de carga</span>
                </td>
            </tr>
        `).join('');

    } catch (e) {
        console.error(e);
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center">Error al cargar datos.</td></tr>';
    }
};

/**
 * EVOLUTION VIEW
 */
async function renderEvolution() {
    const container = document.getElementById('centro-chips-container');
    if (!container) return;

    // Render chips if empty
    if (container.children.length === 0) {
        container.innerHTML = state.centros.map(c => `
            <div class="filter-pill centro-chip" data-id="${c.id}" onclick="toggleCentroSelection('${c.id}')">
                <span>${c.id}</span>
            </div>
        `).join('');
    }

    await updateComparisonChart();
}

window.toggleCentroSelection = (id) => {
    const chip = document.querySelector(`.centro-chip[data-id="${id}"]`);
    if (state.selectedCentros.includes(id)) {
        state.selectedCentros = state.selectedCentros.filter(sid => sid !== id);
        chip.style.background = 'var(--surface-dark)';
        chip.style.borderColor = 'var(--border-glass)';
    } else {
        if (state.selectedCentros.length >= 8) return; // Limit
        state.selectedCentros.push(id);
        chip.style.background = 'var(--accent-red)';
        chip.style.borderColor = 'var(--rpk-red)';
    }
    updateComparisonChart();
};

async function updateComparisonChart() {
    if (state.selectedCentros.length === 0) {
        // Clear chart or show message
        return;
    }

    const params = new URLSearchParams({
        fecha_inicio: state.filters.from,
        fecha_fin: state.filters.to
    });

    const res = await fetch(`${API_BASE}/centro/${state.selectedCentros.join(',')}?${params}`);
    const data = await res.json();

    const ctx = document.getElementById('comparisonChart').getContext('2d');
    if (state.charts.evolution) state.charts.evolution.destroy();

    const datasets = Object.entries(data.centros).map(([id, cData], idx) => ({
        label: `C${id}`,
        data: cData.cargas,
        borderColor: CHART_COLORS[idx % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] + '20',
        fill: false,
        tension: 0.3,
        borderWidth: 2
    }));

    state.charts.evolution = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.fechas,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { color: '#fff', boxWidth: 10, padding: 20 } }
            },
            scales: {
                x: { ticks: { color: '#63636e' } },
                y: { ticks: { color: '#63636e' } }
            }
        }
    });
}
