/**
 * RPK NEXUS - Pedidos Module Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

async function initDashboard() {
    console.log("Iniciando Dashboard de Pedidos...");
    try {
        await Promise.all([
            fetchSummary(),
            fetchTopArticulos()
        ]);
    } catch (err) {
        console.error("Error al cargar el dashboard:", err);
    }
}

async function fetchSummary() {
    const res = await fetch('/api/pedidos/summary');
    const data = await res.json();

    if (data.kpis) {
        document.getElementById('totalImporte').innerText = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(data.kpis.total_importe);
        document.getElementById('totalPiezas').innerText = new Intl.NumberFormat('es-ES').format(data.kpis.total_piezas);
        document.getElementById('totalRefs').innerText = data.kpis.num_references || data.kpis.num_referencias;
        document.getElementById('currentSnapshotDate').innerText = `Snapshot: ${data.ultima_fecha}`;
    }

    if (data.evolucion) {
        renderChart(data.evolucion);
    }
}

async function fetchTopArticulos() {
    const res = await fetch('/api/pedidos/articulos');
    const data = await res.json();

    const tbody = document.querySelector('#topPedidosTable tbody');
    tbody.innerHTML = '';

    data.articulos.forEach(art => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <div style="font-weight:600">${art.articulo}</div>
                <div style="font-size:0.75rem; color:var(--text-dim)">${art.referencia || ''}</div>
            </td>
            <td>${new Intl.NumberFormat('es-ES').format(art.cantidad)}</td>
            <td style="font-weight:600; color:var(--rpk-red)">${new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(art.importe)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderChart(evol) {
    const ctx = document.getElementById('evolucionChart').getContext('2d');

    // Gradiente para el área
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(227, 6, 19, 0.4)');
    gradient.addColorStop(1, 'rgba(227, 6, 19, 0)');

    new Chart(ctx, {
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
                    backgroundColor: '#1a1a20',
                    titleColor: '#fff',
                    bodyColor: '#a0a0b0',
                    borderColor: '#2d2d3a',
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
                        color: '#a0a0b0',
                        callback: function (value) {
                            if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M€';
                            if (value >= 1000) return (value / 1000).toFixed(0) + 'k€';
                            return value + '€';
                        }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#a0a0b0', maxRotation: 45, minRotation: 45 }
                }
            }
        }
    });
}
