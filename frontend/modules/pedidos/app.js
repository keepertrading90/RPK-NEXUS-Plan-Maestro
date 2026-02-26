/**
 * RPK NEXUS - Pedidos Module Logic (Refactored V5.5)
 */

let chartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

async function initDashboard() {
    console.log("Iniciando Dashboard de Pedidos (V5.5)...");
    const loaderBtn = document.getElementById('btn-refresh');
    try {
        if (loaderBtn) {
            loaderBtn.innerHTML = `<i data-lucide="loader" class="icon-spin"></i><span>Cargando...</span>`;
            lucide.createIcons();
        }

        await Promise.all([
            fetchSummary(),
            fetchTopArticulos()
        ]);

    } catch (err) {
        console.error("Error al cargar el dashboard:", err);
    } finally {
        if (loaderBtn) {
            loaderBtn.innerHTML = `<i data-lucide="rotate-cw"></i><span>Actualizar</span>`;
            lucide.createIcons();
        }
    }
}

async function fetchSummary() {
    const res = await fetch('/api/pedidos/summary');
    const data = await res.json();

    if (data.kpis) {
        document.getElementById('totalImporte').innerText = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(data.kpis.total_importe);
        document.getElementById('totalPiezas').innerText = new Intl.NumberFormat('es-ES').format(data.kpis.total_piezas);
        document.getElementById('totalRefs').innerText = data.kpis.num_referencias;
        document.getElementById('currentSnapshotDate').innerText = `Snapshot Base de Datos: ${data.ultima_fecha}`;
        document.getElementById('system-status').style.boxShadow = '0 0 8px #10b981';
        document.getElementById('system-status').style.backgroundColor = '#10b981';
        document.getElementById('status-text').innerText = 'Sistema Online';
    }

    if (data.evolucion) {
        renderChart(data.evolucion);
    }
}

async function fetchTopArticulos() {
    const res = await fetch('/api/pedidos/articulos');
    const data = await res.json();

    const tbody = document.getElementById('topPedidosTableBody');
    tbody.innerHTML = '';

    data.articulos.forEach(art => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <div style="font-weight:700; color: var(--text-primary);">${art.articulo}</div>
                <div style="font-size:0.75rem; color:var(--text-muted);">${art.referencia || ''}</div>
            </td>
            <td>${new Intl.NumberFormat('es-ES').format(art.cantidad)} uds.</td>
            <td class="text-right" style="font-weight:700; color:var(--rpk-red)">
                ${new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(art.importe)}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderChart(evol) {
    const ctx = document.getElementById('evolucionChart').getContext('2d');

    if (chartInstance) {
        chartInstance.destroy();
    }

    // Gradient styling for the area
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(227, 6, 19, 0.4)');
    gradient.addColorStop(1, 'rgba(227, 6, 19, 0)');

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: evol.fechas,
            datasets: [{
                label: 'Importe Cartera (€)',
                data: evol.importes,
                borderColor: '#E30613',
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#E30613',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(18, 18, 23, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#a0a0b0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function (context) {
                            return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#63636e',
                        callback: function (value) {
                            if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M€';
                            if (value >= 1000) return (value / 1000).toFixed(0) + 'k€';
                            return value + '€';
                        }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#63636e', maxRotation: 45, minRotation: 45 }
                }
            }
        }
    });

    // Handle CSS animation class definition if missing in UI for loader spinner
    if (!document.getElementById('spin-style')) {
        let style = document.createElement('style');
        style.id = 'spin-style';
        style.innerHTML = `@keyframes spin { 100% { transform: rotate(360deg); } } .icon-spin { animation: spin 2s linear infinite; }`;
        document.head.appendChild(style);
    }
}
