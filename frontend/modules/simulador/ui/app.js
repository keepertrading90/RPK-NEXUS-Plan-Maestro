const API_BASE = '/api';
let currentData = null;
let baseData = null;
let chartInstance = null;
let scenarios = [];
let currentScenarioId = 'base';
let selectedCenters = [];
let localOverrides = [];
let centerConfigs = {};
let updateTimeout;
let isComparisonMode = false;
let comparisonData = null;
let comparisonViewMode = 'absolute'; // 'absolute' or 'delta'

function debounce(func, wait) {
    return function (...args) {
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function setLoading(isLoading) {
    const main = document.querySelector('main');
    if (!main) return;
    if (isLoading) {
        main.classList.add('loading');
    } else {
        main.classList.remove('loading');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("App iniciada. Configurando listeners...");
    setupEventListeners();
    initApp();
});

async function initApp() {
    isComparisonMode = false;
    const compBox = document.getElementById('comparison-controls');
    if (compBox) compBox.style.display = 'none';
    await loadScenarios();
    await loadSimulation('base');
}

async function loadScenarios() {
    try {
        const response = await fetch(`${API_BASE}/scenarios`);
        scenarios = await response.json();
        const compareA = document.getElementById('compare-a');
        const compareB = document.getElementById('compare-b');
        if (compareA && compareB) {
            const options = ['<option value="base">Base</option>', ...scenarios.map(s => `<option value="${s.id}">${s.name}</option>`)];
            compareA.innerHTML = options.join('');
            compareB.innerHTML = options.join('');
        }
    } catch (error) {
        console.error('Error loading scenarios:', error);
    }
}

async function loadSimulation(scenarioId) {
    const days = document.getElementById('work-days').value || 238;
    const shifts = document.getElementById('work-shifts').value || 16;

    if (scenarioId !== 'base') {
        centerConfigs = {};
    }

    const url = scenarioId === 'base'
        ? `${API_BASE}/simulate/base?dias_laborales=${days}&horas_turno=${shifts}`
        : `${API_BASE}/simulate/${scenarioId}?dias_laborales=${days}&horas_turno=${shifts}`;

    document.getElementById('current-scenario-name').innerText = 'Cargando datos...';
    setLoading(true);

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        currentData = await response.json();
        if (scenarioId === 'base') baseData = currentData;

        currentScenarioId = scenarioId;
        const sName = scenarioId === 'base' ? 'Escenario Base' : scenarios.find(s => s.id == scenarioId)?.name || 'Escenario';
        document.getElementById('current-scenario-name').innerText = sName;

        if (scenarioId !== 'base' && currentData.meta) {
            document.getElementById('work-days').value = currentData.meta.dias_laborales || 238;
            document.getElementById('work-shifts').value = currentData.meta.horas_turno_global || 16;
            centerConfigs = currentData.meta.center_configs || {};
            localOverrides = currentData.meta.applied_overrides || [];

            // Map original values from baseData for diff visualization
            localOverrides.forEach(ov => {
                const baseItem = baseData?.detail.find(d => d.Articulo == ov.articulo && d.Centro == ov.centro);
                if (baseItem) {
                    ov.original_oee = baseItem['%OEE'];
                    ov.original_ppm = baseItem['Piezas por minuto'];
                    ov.original_demanda = baseItem['Volumen anual'];
                    ov.original_shifts = baseItem['horas_turno'] || 16;
                    ov.original_mod = baseItem['Ratio_MOD'] || 1.0;
                }
            });
        }

        // Cargar paneles laterales
        renderLocalOverrides();
        if (scenarioId !== 'base') {
            loadScenarioHistory(scenarioId);
        } else {
            const historyContainer = document.getElementById('history-list');
            if (historyContainer) historyContainer.innerHTML = '<p class="empty-msg">No hay histórico para Base</p>';
        }

        populateWorkCenters();
        updateNavItemActive(scenarioId);
        updateUI();
    } catch (error) {
        console.error('Error loading simulation:', error);
        document.getElementById('current-scenario-name').innerText = 'Error de conexión';
    } finally {
        setLoading(false);
    }
}

function updateNavItemActive(id) {
    document.querySelectorAll('.nav-tab').forEach(item => {
        item.classList.remove('active');
    });
    if (isComparisonMode) {
        document.getElementById('btn-compare')?.classList.add('active');
    } else if (id === 'base') {
        document.getElementById('btn-base')?.classList.add('active');
    } else {
        document.getElementById('btn-manage')?.classList.add('active');
    }
}

function updateUI() {
    if (isComparisonMode) {
        // If we are comparing and currentData was updated (e.g. from an adjustment)
        // sync it back to dataB if it's the active comparison target
        if (currentData && comparisonData) {
            comparisonData.dataB = currentData;
        }
        renderComparisonDashboard();
        renderComparisonTable();
        renderExecutiveInsights();
        return;
    }
    if (!currentData || !currentData.summary || currentData.summary.length === 0) {
        document.getElementById('summary-stats').innerHTML = '<div class="stat-item">No hay datos</div>';
        return;
    }
    let filteredSummary = [...currentData.summary];
    let filteredDetail = [...currentData.detail];

    const isFiltered = selectedCenters.length > 0 && !selectedCenters.includes('all');
    if (isFiltered) {
        const selectedSet = new Set(selectedCenters.map(val => String(val).trim()));
        filteredSummary = currentData.summary.filter(s => selectedSet.has(String(s.Centro).trim()));
        filteredDetail = currentData.detail.filter(d => selectedSet.has(String(d.Centro).trim()));
    }

    renderChart(filteredSummary);
    renderSummary(filteredSummary, isFiltered);
    renderTable(filteredDetail);
}

function renderChart(summary) {
    const ctx = document.getElementById('saturationChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: summary.map(s => s.Centro),
            datasets: [{
                label: '% Saturación Media',
                data: summary.map(s => (s.Saturacion * 100).toFixed(1)),
                backgroundColor: summary.map(s => s.Saturacion > 0.85 ? '#dc3545' : (s.Saturacion > 0.7 ? '#ffc107' : '#28a745')),
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: '#2d2d35' }, ticks: { color: '#a0a0a0' } },
                x: { grid: { display: false }, ticks: { color: '#a0a0a0' } }
            },
            plugins: { legend: { display: false } },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const label = chartInstance.data.labels[index];

                    // Update filter state
                    selectedCenters = [label];

                    // Update dropdown UI to reflect selection
                    populateWorkCenters(); // Re-render checkboxes
                    updateUI(); // Refresh dashboard

                    // Smooth scroll to table for better UX
                    const tableCard = document.querySelector('.table-card');
                    if (tableCard) {
                        tableCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            },
            onHover: (e, elements) => {
                e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
            }
        }
    });
}

function renderSummary(summary, isFiltered) {
    const container = document.getElementById('summary-stats');
    if (!summary || summary.length === 0) {
        container.innerHTML = '<div class="stat-item">No hay datos</div>';
        return;
    }
    const avgSat = (summary.reduce((acc, current) => acc + (current.Saturacion || 0), 0) / summary.length * 100).toFixed(1);
    const totalDemanda = summary.reduce((acc, current) => acc + (current['Volumen anual'] || 0), 0).toLocaleString();

    container.innerHTML = `
        <div class="stat-item">
            <div class="stat-val ${avgSat > 85 ? 'rpk-red-text' : ''}">${avgSat}%</div>
            <div class="stat-label">Saturación Media ${isFiltered ? '(Sectores)' : ''}</div>
        </div>
        <div class="stat-item">
            <div class="stat-val" style="color: #4facfe;">${(summary.reduce((acc, c) => acc + (c.Horas_Hombre || 0), 0) / (currentData.meta.dias_laborales * 8)).toFixed(1)}</div>
            <div class="stat-label">Operarios Necesarios (FTE)</div>
        </div>
        <div class="stat-item">
            <div class="stat-val">${totalDemanda}</div>
            <div class="stat-label">Demanda Total (pzs)</div>
        </div>
    `;
}

function renderTable(detail) {
    const body = document.getElementById('table-body');
    const search = document.getElementById('table-search').value.toLowerCase();
    const totalGroupDemand = detail.reduce((acc, d) => acc + (d['Volumen anual'] || 0), 0);

    let filtered = detail;
    if (search) filtered = filtered.filter(d => d.Articulo.toString().toLowerCase().includes(search));

    body.innerHTML = filtered.slice(0, 100).map(d => {
        const sat = (d.Saturacion * 100).toFixed(1);
        const satClass = sat > 85 ? 'pill-high' : (sat > 70 ? 'pill-mid' : 'pill-low');
        const impact = totalGroupDemand > 0 ? ((d['Volumen anual'] / totalGroupDemand) * 100).toFixed(1) : 0;
        const shifts = d.horas_turno || 16;

        let shiftLabel = `${shifts}h`;
        if (shifts == 8) shiftLabel = "1 Turno (8h)";
        else if (shifts == 16) shiftLabel = "2 Turnos (16h)";
        else if (shifts == 24) shiftLabel = "3 Turnos (24h)";

        return `
            <tr>
                <td><strong>${d.Articulo}</strong></td>
                <td class="text-center">
                    <span class="center-tag">${d.Centro}</span>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">${shiftLabel}</div>
                </td>
                <td class="text-right">${d['Volumen anual'].toLocaleString()}</td>
                <td class="text-right">${Math.round(d['Piezas por minuto'])}</td>
                <td class="text-right">${(d['%OEE'] * 100).toFixed(1)}%</td>
                <td class="text-center">
                    <span class="saturation-pill ${satClass}">${sat}%</span>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">
                        ${(d.Horas_Totales || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}h
                    </div>
                </td>
                <td class="text-right">
                    <span class="mod-value">${(d.Ratio_MOD || 1).toFixed(1)}</span>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">
                        ${(d.Horas_Hombre || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}h/h
                    </div>
                </td>
                <td class="text-right">
                    <div class="impact-bar-container"><div class="impact-bar" style="width: ${impact}%"></div></div>
                    <span style="font-size:0.75rem; color:var(--text-muted)">${impact}%</span>
                </td>
                <td class="text-center">
                    <button class="secondary-btn btn-simular" 
                        style="padding: 0.3rem 0.6rem; font-size: 0.7rem;"
                        data-articulo="${d.Articulo}" 
                        data-centro="${d.Centro}">Ajustar</button>
                </td>
            </tr>
        `;
    }).join('');
}

/* --- LOGICA PANELES LATERALES (CAMBIOS Y HISTORIAL) --- */
function renderLocalOverrides() {
    const container = document.getElementById('overrides-list');
    if (!container) return;

    if (localOverrides.length === 0) {
        container.innerHTML = '<p class="empty-msg">No hay cambios aplicados</p>';
        return;
    }

    container.innerHTML = localOverrides.map((ov, idx) => {
        return `
            <div class="override-item">
                <button class="btn-remove-ov" onclick="removeOverride(${idx})" title="Eliminar">&times;</button>
                <h4>${ov.articulo}</h4>
                <div class="override-info">
                    ${ov.new_centro ? `<span>➜ Traslado: <b class="val-changed">${ov.new_centro}</b></span>` : ''}
                    
                    ${ov.oee_override ? (() => {
                const orig = (ov.original_oee * 100).toFixed(1);
                const newVal = (ov.oee_override * 100).toFixed(1);
                const changed = orig !== newVal;
                return `<div>OEE: ${changed ? `<span class="val-original">${orig}%</span><b class="val-changed">➜ ${newVal}%</b>` : `<span>${orig}%</span>`}</div>`;
            })() : ''}
                    
                    ${ov.ppm_override ? (() => {
                const orig = Math.round(ov.original_ppm);
                const newVal = Math.round(ov.ppm_override);
                const changed = orig !== newVal;
                return `<div>PPM: ${changed ? `<span class="val-original">${orig}</span><b class="val-changed">➜ ${newVal}</b>` : `<span>${orig}</span>`}</div>`;
            })() : ''}
                    
                    ${ov.demanda_override ? (() => {
                const orig = Math.round(ov.original_demanda);
                const newVal = Math.round(ov.demanda_override);
                const changed = orig !== newVal;
                return `<div>Dem: ${changed ? `<span class="val-original">${orig.toLocaleString()}</span><b class="val-changed">➜ ${newVal.toLocaleString()}</b>` : `<span>${orig.toLocaleString()}</span>`}</div>`;
            })() : ''}
                    ${ov.horas_turno_override ? (() => {
                const orig = ov.original_shifts;
                const newVal = ov.horas_turno_override;
                const changed = orig != newVal;
                return `<div>Turnos: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
            })() : ''}

                    ${ov.setup_time_override !== undefined && ov.setup_time_override !== null ? (() => {
                const orig = (ov.original_setup || 0).toFixed(1);
                const newVal = (ov.setup_time_override).toFixed(1);
                const changed = Math.abs(orig - newVal) > 0.1;
                return `<div>Setup: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
            })() : ''}
                </div>
            </div>
        `;
    }).join('');
}

function removeOverride(i) {
    localOverrides.splice(i, 1);
    updatePreviewSimulation();
}

async function loadScenarioHistory(id) {
    try {
        const res = await fetch(`${API_BASE}/scenarios/${id}/history`);
        const history = await res.json();
        const container = document.getElementById('history-list');
        if (!container) return;

        if (!history || history.length === 0) {
            container.innerHTML = '<p class="empty-msg">Sin registros previos</p>';
            return;
        }

        container.innerHTML = history.map(h => {
            let changesSummary = '';
            try {
                const details = JSON.parse(h.details_snapshot);
                if (details && details.length > 0) {
                    changesSummary = `<div class="history-details-list">`;
                    details.forEach(ov => {
                        const baseItem = baseData?.detail.find(d => d.Articulo == ov.articulo && d.Centro == (ov.centro_original || ov.centro));

                        let detailItemsHtml = '';

                        if (ov.new_centro) detailItemsHtml += `<span>➜ Traslado: <b class="val-changed">${ov.new_centro}</b></span>`;

                        if (ov.oee_override) {
                            const orig = baseItem ? (baseItem['%OEE'] * 100).toFixed(1) : '?';
                            const newVal = (ov.oee_override * 100).toFixed(1);
                            const changed = orig !== newVal;
                            detailItemsHtml += `<div>OEE: ${changed ? `<span class="val-original">${orig}%</span><b class="val-changed">➜ ${newVal}%</b>` : `<span>${orig}%</span>`}</div>`;
                        }

                        if (ov.ppm_override) {
                            const orig = baseItem ? Math.round(baseItem['Piezas por minuto']) : '?';
                            const newVal = Math.round(ov.ppm_override);
                            const changed = orig !== newVal;
                            detailItemsHtml += `<div>PPM: ${changed ? `<span class="val-original">${orig}</span><b class="val-changed">➜ ${newVal}</b>` : `<span>${orig}</span>`}</div>`;
                        }

                        if (ov.demanda_override) {
                            const orig = baseItem ? Math.round(baseItem['Volumen anual']) : '?';
                            const newVal = Math.round(ov.demanda_override);
                            const changed = orig !== newVal;
                            detailItemsHtml += `<div>Dem: ${changed ? `<span class="val-original">${orig.toLocaleString()}</span><b class="val-changed">➜ ${newVal.toLocaleString()}</b>` : `<span>${orig.toLocaleString()}</span>`}</div>`;
                        }

                        if (ov.horas_turno_override) {
                            const orig = baseItem ? baseItem['horas_turno'] : '?';
                            const newVal = ov.horas_turno_override;
                            const changed = orig != newVal;
                            detailItemsHtml += `<div>Turnos: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
                        }

                        changesSummary += `
                            <div class="history-article-row">
                                <div class="article-label">${ov.articulo}</div>
                                <div class="override-info">${detailItemsHtml}</div>
                            </div>`;
                    });
                    changesSummary += `</div>`;
                }
            } catch (err) { console.error("Err parsing snapshot", err); }

            return `
                <div class="history-item">
                    <div class="history-header">
                        <div class="history-info">
                            <div class="history-time">${h.timestamp}</div>
                            <div class="history-name">${h.name}</div>
                        </div>
                        <div class="history-badge">
                            ${h.changes_count} Cambios
                        </div>
                    </div>
                    ${changesSummary}
                </div>
            `;
        }).join('');
    } catch (e) { console.error("Error history", e); }
}

/* --- DROPDOWN LOGIC --- */
function populateWorkCenters() {
    const list = document.getElementById('work-center-options');
    if (!list || !currentData.detail) return;

    // Get unique centers and sort
    const centers = [...new Set(currentData.detail.map(d => d.Centro))].sort();

    // Create Checkboxes
    // Changed: Handlers moved to inputs. Text (span) has no click handler.
    let html = `
        <div class="checkbox-item">
            <input type="checkbox" id="cb-all" onchange="toggleSelectAll()" ${selectedCenters.length === 0 || selectedCenters.includes('all') ? 'checked' : ''}>
            <span style="margin-left:8px;">-- Todos los Centros --</span>
        </div>
        <div style="border-bottom: 1px solid var(--border-color); margin: 5px 0;"></div>
    `;

    centers.forEach(c => {
        const isChecked = selectedCenters.includes(String(c)) && !selectedCenters.includes('all');
        const config = centerConfigs[String(c)] || {};
        const activeShift = config.shifts || 16; // Default to 16h (2T) or similar

        html += `
            <div class="checkbox-item work-center-row">
                <div class="wc-check-part">
                    <input type="checkbox" id="cb-${c}" onchange="toggleOption('${c}')" ${isChecked ? 'checked' : ''}>
                    <span class="wc-label">${c}</span>
                </div>
                <div class="wc-shifts-part">
                    <button class="shift-btn ${activeShift == 8 ? 'active text-white' : ''}" onclick="setCenterShift('${c}', 8, event)">1T</button>
                    <button class="shift-btn ${activeShift == 16 ? 'active text-white' : ''}" onclick="setCenterShift('${c}', 16, event)">2T</button>
                    <button class="shift-btn ${activeShift == 24 ? 'active text-white' : ''}" onclick="setCenterShift('${c}', 24, event)">3T</button>
                </div>
                <div class="wc-ratio-part" style="margin-top: 5px; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 0.65rem; color: var(--text-muted)">MOD:</span>
                    <input type="range" min="0.1" max="3.0" step="0.1" value="${config.personnel_ratio || 1.0}" 
                        style="width: 60px; height: 4px;" 
                        oninput="this.nextElementSibling.innerText = parseFloat(this.value).toFixed(1)"
                        onchange="setCenterRatio('${c}', this.value, event)">
                    <span style="font-size: 0.7rem; min-width: 20px;">${(config.personnel_ratio || 1.0).toFixed(1)}</span>
                </div>
            </div>
        `;
    });

    list.innerHTML = html;
    updateDropdownText();
}

async function setCenterShift(centro, shifts, event) {
    if (event) event.stopPropagation();

    if (!centerConfigs[String(centro)]) {
        centerConfigs[String(centro)] = {};
    }

    centerConfigs[String(centro)].shifts = shifts;

    // Check if there are articles in this center that need their individual shift updated
    // or if we just let the global center config handle it in simulation_core.
    // The backend simulation_core already handles center_configs:
    // for centro, config in center_configs.items():
    //     df.loc[df['Centro'].astype(str) == str(centro), 'horas_turno'] = int(config['shifts'])

    populateWorkCenters(); // Update buttons state
    await updatePreviewSimulation();
}

async function setCenterRatio(centro, ratio, event) {
    if (event) event.stopPropagation();
    if (!centerConfigs[String(centro)]) centerConfigs[String(centro)] = {};
    centerConfigs[String(centro)].personnel_ratio = parseFloat(ratio);
    await updatePreviewSimulation();
}

function toggleDropdown() {
    const content = document.getElementById('work-center-options');
    content.classList.toggle('show');
}

// Close dropdown when clicking outside
window.onclick = function (event) {
    if (!event.target.matches('.dropdown-btn') && !event.target.matches('.dropdown-btn *') && !event.target.closest('.dropdown-content')) {
        closeDropdowns();
    }
    // Also handle modal closing here
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

function closeDropdowns() {
    const dropdowns = document.getElementsByClassName("dropdown-content");
    for (let i = 0; i < dropdowns.length; i++) {
        const openDropdown = dropdowns[i];
        if (openDropdown.classList.contains('show')) {
            openDropdown.classList.remove('show');
        }
    }
}

function toggleSelectAll() {
    const cbAll = document.getElementById('cb-all');
    // Input 'change' has already toggled the checked state
    const isChecked = cbAll.checked;

    if (isChecked) {
        selectedCenters = ['all'];
        // Uncheck others visually
        document.querySelectorAll('#work-center-options input[type="checkbox"]').forEach(cb => {
            if (cb.id !== 'cb-all') cb.checked = false;
        });
    } else {
        // If unchecking 'All', we technically have nothing selected, or maybe just clear 'all'.
        // Let's assume empty array.
        selectedCenters = [];
    }
    updateDropdownText();
}

function toggleOption(val) {
    const cb = document.getElementById(`cb-${val}`);
    // Input 'change' has already toggled the checked state
    const isChecked = cb.checked;

    // If we select a specific one, uncheck 'All'
    if (isChecked) {
        if (selectedCenters.includes('all')) selectedCenters = [];
        selectedCenters.push(String(val));
        document.getElementById('cb-all').checked = false;
    } else {
        selectedCenters = selectedCenters.filter(c => c !== String(val));
    }
    updateDropdownText();
}

function updateDropdownText() {
    const textSpan = document.getElementById('dropdown-text');
    if (selectedCenters.includes('all') || selectedCenters.length === 0) {
        textSpan.innerText = "-- Todos los Centros --";
        // If empty, logical state is 'all'
        // But UI logic above manages 'cb-all' state.
        if (selectedCenters.length === 0) {
            selectedCenters = ['all'];
            document.getElementById('cb-all').checked = true;
        }
    } else {
        textSpan.innerText = `${selectedCenters.length} Seleccionado(s)`;
    }
}

function setupEventListeners() {
    document.getElementById('table-body').onclick = (e) => {
        if (e.target.classList.contains('btn-simular')) {
            openEditModal(e.target.getAttribute('data-articulo'), e.target.getAttribute('data-centro'));
        }
    };

    document.getElementById('btn-base').onclick = () => {
        localOverrides = [];
        centerConfigs = {};
        currentScenarioId = 'base';
        loadSimulation('base');
    };

    document.getElementById('work-days').oninput = debounce(() => updatePreviewSimulation(), 500);
    document.getElementById('work-shifts').onchange = () => updatePreviewSimulation();

    document.getElementById('btn-apply-filter').onclick = () => {
        // State is already updated by checkboxes
        updateUI();
        closeDropdowns(); // Close dropdown immediately
    };

    document.getElementById('btn-clear-filter').onclick = () => {
        selectedCenters = ['all'];
        populateWorkCenters(); // Re-render to clear checks
        updateUI();
    };

    document.getElementById('table-search').oninput = () => updateUI();

    const editForm = document.getElementById('edit-form');
    if (editForm) {
        editForm.onsubmit = async (e) => {
            e.preventDefault();
            const articulo = document.getElementById('edit-articulo').value;
            const centroBase = document.getElementById('edit-centro').value;
            const oee = parseFloat(document.getElementById('edit-oee').value) / 100 || 0;
            const ppm = parseFloat(document.getElementById('edit-ppm').value) || 0;
            const demanda = parseFloat(document.getElementById('edit-demanda').value) || 0;
            const new_centro = document.getElementById('edit-new-centro').value;
            const shifts = document.getElementById('edit-shifts').value;

            const override = {
                articulo,
                centro: centroBase,
                oee_override: oee,
                ppm_override: ppm,
                demanda_override: demanda,
                new_centro: new_centro,
                horas_turno_override: shifts ? parseInt(shifts) : null,
                personnel_ratio_override: parseFloat(document.getElementById('edit-mod').value) || null,
                setup_time_override: parseFloat(document.getElementById('edit-setup').value) || 0
            };

            const idx = localOverrides.findIndex(o => o.articulo == articulo && o.centro == centroBase);

            // Capture original values from baseData (source of truth)
            const b = baseData?.detail.find(item => item.Articulo == articulo && item.Centro == centroBase);
            override.original_oee = b ? b['%OEE'] : 0;
            override.original_ppm = b ? b['Piezas por minuto'] : 0;
            override.original_demanda = b ? b['Volumen anual'] : 0;
            override.original_shifts = b ? (b.horas_turno || 16) : 16;
            override.original_setup = b ? (b['Setup (h)'] || 0) : 0;
            override.original_mod = b ? (b.Ratio_MOD || 1.0) : 1.0;

            if (idx >= 0) localOverrides[idx] = override;
            else localOverrides.push(override);

            document.getElementById('edit-modal').style.display = 'none';
            await updatePreviewSimulation();
        };
    }

    document.getElementById('cancel-edit').onclick = () => {
        document.getElementById('edit-modal').style.display = 'none';
    };

    document.getElementById('btn-new').onclick = () => {
        const modal = document.getElementById('save-modal');
        const overwriteSection = document.getElementById('overwrite-section');
        const nameInput = document.getElementById('new-scenario-name');

        nameInput.value = ''; // Reset input

        if (currentScenarioId && currentScenarioId !== 'base') {
            overwriteSection.style.display = 'block';
            const currentName = scenarios.find(s => s.id == currentScenarioId)?.name || 'Actual';
            nameInput.placeholder = `Nombre para copia de ${currentName}`;
        } else {
            overwriteSection.style.display = 'none';
            nameInput.placeholder = 'Nombre del escenario (Ej: Q1 2026)...';
        }

        modal.style.display = 'flex';
        setTimeout(() => nameInput.focus(), 100);
    };

    document.getElementById('btn-save-new-confirm').onclick = async () => {
        const name = document.getElementById('new-scenario-name').value;
        if (!name) {
            alert("Por favor inserta un nombre para el escenario.");
            return;
        }
        await performSaveScenario(name);
        document.getElementById('save-modal').style.display = 'none';
    };

    document.getElementById('btn-overwrite-confirm').onclick = async () => {
        const currentScenario = scenarios.find(s => s.id == currentScenarioId);
        if (!currentScenario) return;
        await performSaveScenario(currentScenario.name, currentScenarioId);
        document.getElementById('save-modal').style.display = 'none';
    };

    document.getElementById('btn-compare').onclick = () => document.getElementById('compare-modal').style.display = 'flex';
    document.getElementById('run-compare').onclick = runCompare;
    document.getElementById('btn-exit-compare').onclick = exitComparisonMode;
    document.getElementById('btn-toggle-delta').onclick = () => {
        comparisonViewMode = (comparisonViewMode === 'absolute' ? 'delta' : 'absolute');
        document.getElementById('btn-toggle-delta').innerText = (comparisonViewMode === 'absolute' ? 'Ver Variación (%)' : 'Ver Valores Absolutos');
        renderComparisonDashboard();
    };
    document.getElementById('btn-manage').onclick = () => { renderManageList(); document.getElementById('manage-modal').style.display = 'flex'; };

    const closeHandlers = document.querySelectorAll('.close, .close-manage');
    closeHandlers.forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
        };
    });

    window.onclick = (event) => {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    };
}

async function performSaveScenario(name, overwriteId = null) {
    const days = parseInt(document.getElementById('work-days').value);
    const shifts = parseInt(document.getElementById('work-shifts').value);

    try {
        setLoading(true);
        const url = overwriteId ? `${API_BASE}/scenarios/${overwriteId}/full` : `${API_BASE}/scenarios`;
        const method = overwriteId ? 'PUT' : 'POST';

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                dias_laborales: days,
                horas_turno_global: shifts,
                center_configs: centerConfigs,
                overrides: localOverrides
            })
        });

        if (res.ok) {
            const s = await res.json();
            await loadScenarios();
            loadSimulation(s.id);
        } else {
            const error = await res.json();
            console.error("Error al guardar escenario:", error);
            alert(error.detail || "Error al guardar el escenario.");
        }
    } catch (e) {
        console.error(e);
    } finally {
        setLoading(false);
    }
}

async function updatePreviewSimulation() {
    const days = document.getElementById('work-days').value || 238;
    const shifts = document.getElementById('work-shifts').value || 16;
    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/simulate/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                overrides: localOverrides,
                dias_laborales: parseInt(days),
                horas_turno: parseInt(shifts),
                center_configs: centerConfigs
            })
        });
        currentData = await res.json();

        // Actualizar panel de cambios tras simulación
        renderLocalOverrides();
        updateUI();
    } catch (e) { console.error(e); }
    finally {
        setLoading(false);
    }
}

function openEditModal(articulo, centro) {
    const d = currentData.detail.find(item => item.Articulo == articulo && item.Centro == centro);
    if (!d) return;
    document.getElementById('edit-articulo').value = articulo;
    document.getElementById('edit-centro').value = centro;
    document.getElementById('display-articulo').innerText = articulo;
    document.getElementById('edit-oee').value = (d['%OEE'] * 100).toFixed(2);
    document.getElementById('edit-ppm').value = Math.round(d['Piezas por minuto']);
    document.getElementById('edit-demanda').value = Math.round(d['Volumen anual']);
    const existingOverride = localOverrides.find(o => o.articulo == articulo && o.centro == centro);
    document.getElementById('edit-shifts').value = (existingOverride && existingOverride.horas_turno_override) ? existingOverride.horas_turno_override : "";
    document.getElementById('edit-setup').value = (existingOverride && existingOverride.setup_time_override !== undefined) ? existingOverride.setup_time_override : (d['Setup (h)'] || 0);
    document.getElementById('edit-mod').value = (existingOverride && existingOverride.personnel_ratio_override) ? existingOverride.personnel_ratio_override : (d.Ratio_MOD || 1.0);

    const centers = [...new Set(currentData.detail.map(item => item.Centro))].sort();
    document.getElementById('edit-new-centro').innerHTML = centers.map(c => `<option value="${c}" ${c == centro ? 'selected' : ''}>${c}</option>`).join('');
    document.getElementById('edit-modal').style.display = 'flex';
}

function renderManageList() {
    const container = document.getElementById('manage-list-container');
    container.innerHTML = scenarios.map(s => `
        <div class="card" style="margin-bottom: 0.5rem; padding: 1rem; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 600;">${s.name}</span>
            <div style="display: flex; gap: 8px;">
                <button class="primary-btn" onclick="loadAndClose(${s.id})" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">Cargar</button>
                <button class="secondary-btn" onclick="deleteScenarioInline(${s.id})" style="padding: 0.4rem 0.8rem; font-size: 0.8rem; color: #ff4444;">Borrar</button>
            </div>
        </div>
    `).join('');
}

window.deleteScenarioInline = async (id) => {
    if (!confirm("¿Borrar escenario?")) return;
    try {
        const res = await fetch(`${API_BASE}/scenarios/${id}`, { method: 'DELETE' });
        if (res.ok) {
            await loadScenarios();
            renderManageList();
            if (currentScenarioId == id) loadSimulation('base');
        }
    } catch (e) { alert("Error al eliminar"); }
};

window.loadAndClose = (id) => {
    loadSimulation(id);
    document.getElementById('manage-modal').style.display = 'none';
};

async function runCompare() {
    const scA = document.getElementById('compare-a').value;
    const scB = document.getElementById('compare-b').value;
    try {
        setLoading(true);
        const resA = await fetch(`${API_BASE}/simulate/${scA === 'base' ? 'base' : scA}`);
        const resB = await fetch(`${API_BASE}/simulate/${scB === 'base' ? 'base' : scB}`);

        if (!resA.ok || !resB.ok) {
            const err = !resA.ok ? await resA.json() : await resB.json();
            throw new Error(err.detail || "Error al cargar la simulación de comparación.");
        }

        comparisonData = {
            nameA: scA === 'base' ? 'Base' : scenarios.find(s => s.id == scA).name,
            nameB: scB === 'base' ? 'Base' : scenarios.find(s => s.id == scB).name,
            dataA: await resA.json(),
            dataB: await resB.json()
        };
        isComparisonMode = true;
        document.getElementById('compare-modal').style.display = 'none';
        enterComparisonMode();
    } catch (e) {
        console.error(e);
        alert("No se pudo iniciar la comparativa: " + e.message);
    } finally {
        setLoading(false);
    }
}

function enterComparisonMode() {
    const banner = document.getElementById('comparison-controls');
    if (banner) {
        banner.style.display = 'flex';
        banner.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span class="pill-info" style="background:#000; color:#ffc107; border-color:#ffc107">MODO COMPARATIVA</span>
                <span style="font-size: 0.9rem;">${comparisonData.nameA} <span style="opacity:0.6">vs</span> <strong>${comparisonData.nameB}</strong></span>
            </div>
            <button id="btn-exit-compare" class="action-btn small" onclick="exitComparisonMode()" style="background:#000; color:#fff; border:1px solid #444">Cerrar Comparativa</button>
        `;
    }

    // Hide standard control bar to maximize space
    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'none';

    // Restructure Dashboard to Bento
    const dashboardGrid = document.querySelector('.dashboard-grid');
    if (dashboardGrid) {
        dashboardGrid.className = 'bento-grid';
        dashboardGrid.innerHTML = `
            <!-- Large Tile: Chart -->
            <div class="bento-item bento-large chart-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h4 style="margin: 0; font-size: 1rem;">Comparativa de Carga por Centro</h4>
                    <button id="btn-toggle-delta" class="action-btn small secondary" onclick="toggleComparisonView()" style="padding: 0.2rem 0.5rem; font-size: 0.7rem;">Ver Variación (%)</button>
                </div>
                <div class="chart-container" style="height: 350px;">
                    <canvas id="saturationChart"></canvas>
                </div>
                <div class="ghost-bar-legend">
                    <div style="display: flex; align-items: center; gap: 5px;"><div class="legend-color" style="background: #666"></div> ${comparisonData.nameA}</div>
                    <div style="display: flex; align-items: center; gap: 5px;"><div class="legend-color" style="background: var(--rpk-red)"></div> ${comparisonData.nameB}</div>
                </div>
            </div>

            <!-- Tile: Net Impact -->
            <div class="bento-item bento-small" id="tile-impact">
                <div class="insight-header">Impacto Neto</div>
                <div class="insight-value" id="val-impact">--</div>
                <div class="insight-label">Capacidad vs ${comparisonData.nameA}</div>
                <div id="delta-impact-badge"></div>
            </div>

            <!-- Tile: OEE Evolution -->
            <div class="bento-item bento-small" id="tile-oee">
                <div class="insight-header">Evolución OEE</div>
                <div class="insight-value" id="val-oee">--</div>
                <div class="insight-label">Promedio ponderado</div>
                <div id="delta-oee-badge"></div>
            </div>

            <!-- Tile: Headcount (FTE) -->
            <div class="bento-item bento-small" id="tile-headcount">
                <div class="insight-header">Personal (FTE)</div>
                <div class="insight-value" id="val-headcount">--</div>
                <div class="insight-label">Basado en Ratio MOD</div>
                <div id="delta-headcount-badge"></div>
            </div>

            <!-- Tile: Top Changes -->
            <div class="bento-item bento-medium" id="tile-changes">
                <div class="insight-header">Cambios Críticos</div>
                <div id="top-changes-list" style="margin-top: 0.5rem;">
                    <!-- JS Generated -->
                </div>
            </div>
        `;
    }

    // Set table to glass style
    const tableCard = document.querySelector('.table-card');
    if (tableCard) tableCard.classList.add('glass-table');

    comparisonViewMode = 'absolute';
    document.getElementById('table-search').value = '';

    updateNavItemActive();
    renderComparisonDashboard();
    renderComparisonTable();
    renderExecutiveInsights();
    triggerDashboardAnimation();
}

function renderExecutiveInsights() {
    if (!comparisonData || !comparisonData.dataA || !comparisonData.dataB) {
        console.warn("Faltan datos para insights ejecutivos.");
        return;
    }

    const summaryA = comparisonData.dataA.summary || [];
    const summaryB = comparisonData.dataB.summary || [];
    const detailA = comparisonData.dataA.detail || [];
    const detailB = comparisonData.dataB.detail || [];

    // 1. Calculate Net Impact (Capacity)
    const avgA = summaryA.length > 0 ? (summaryA.reduce((acc, s) => acc + (s.Saturacion || 0), 0) / summaryA.length) : 0;
    const avgB = summaryB.length > 0 ? (summaryB.reduce((acc, s) => acc + (s.Saturacion || 0), 0) / summaryB.length) : 0;
    const deltaAvg = (avgB - avgA) * 100;

    // Total Hours Delta
    const totalHoursA = detailA.reduce((acc, d) => acc + (d['Horas_Totales'] || 0), 0);
    const totalHoursB = detailB.reduce((acc, d) => acc + (d['Horas_Totales'] || 0), 0);
    const hourDelta = totalHoursB - totalHoursA;

    const impactVal = document.getElementById('val-impact');
    if (impactVal) {
        impactVal.innerText = `${Math.abs(deltaAvg).toFixed(1)}%`;
        const badge = document.getElementById('delta-impact-badge');
        if (deltaAvg > 0.01) {
            impactVal.style.color = 'var(--rpk-red)';
            badge.innerHTML = `<span class="insight-delta delta-neg">▲ +${Math.abs(hourDelta).toFixed(0)}h req. extra</span>`;
        } else if (deltaAvg < -0.01) {
            impactVal.style.color = '#4cd137';
            badge.innerHTML = `<span class="insight-delta delta-pos">▼ -${Math.abs(hourDelta).toFixed(0)}h optimización</span>`;
        } else {
            impactVal.style.color = '#fff';
            badge.innerHTML = `<span class="insight-delta">● Sin variación neta</span>`;
        }
    }

    // 2. OEE Evolution
    const oeeA = detailA.length > 0 ? (detailA.reduce((acc, d) => acc + (d['%OEE'] || 0), 0) / detailA.length) : 0;
    const oeeB = detailB.length > 0 ? (detailB.reduce((acc, d) => acc + (d['%OEE'] || 0), 0) / detailB.length) : 0;
    const deltaOEE = (oeeB - oeeA) * 100;

    const oeeVal = document.getElementById('val-oee');
    if (oeeVal) {
        oeeVal.innerText = `${(oeeB * 100).toFixed(1)}%`;
        const badge = document.getElementById('delta-oee-badge');
        if (deltaOEE > 0.1) {
            badge.innerHTML = `<span class="insight-delta delta-pos">▲ +${deltaOEE.toFixed(1)}% vs ${comparisonData.nameA}</span>`;
        } else if (deltaOEE < -0.1) {
            badge.innerHTML = `<span class="insight-delta delta-neg">▼ ${deltaOEE.toFixed(1)}% vs ${comparisonData.nameA}</span>`;
        } else {
            badge.innerHTML = `<span class="insight-delta">● Estable</span>`;
        }
    }

    // 3. Headcount (FTE)
    const daysA = comparisonData.dataA.meta.dias_laborales || 238;
    const daysB = comparisonData.dataB.meta.dias_laborales || 238;

    // Sum Hombres/Horas
    const sumHHA = detailA.reduce((acc, d) => acc + (d.Horas_Hombre || 0), 0);
    const sumHHB = detailB.reduce((acc, d) => acc + (d.Horas_Hombre || 0), 0);

    // FTE theoretical (assuming 8h shift)
    const fteA = sumHHA / (daysA * 8);
    const fteB = sumHHB / (daysB * 8);
    const deltaFTE = fteB - fteA;

    const fteVal = document.getElementById('val-headcount');
    if (fteVal) {
        fteVal.innerText = fteB.toFixed(1);
        const fteBadge = document.getElementById('delta-headcount-badge');
        if (deltaFTE > 0.1) {
            fteBadge.innerHTML = `<span class="insight-delta delta-neg">▲ +${deltaFTE.toFixed(1)} FTE vs ${comparisonData.nameA}</span>`;
        } else if (deltaFTE < -0.1) {
            fteBadge.innerHTML = `<span class="insight-delta delta-pos">▼ ${deltaFTE.toFixed(1)} FTE vs ${comparisonData.nameA}</span>`;
        } else {
            fteBadge.innerHTML = `<span class="insight-delta">● Sin variación</span>`;
        }
    }

    // 3. Top 3 Changes
    const changes = [];
    const labels = [...new Set([...summaryA.map(s => String(s.Centro)), ...summaryB.map(s => String(s.Centro))])].sort();
    labels.forEach(label => {
        const itemA = summaryA.find(s => String(s.Centro) === label) || { Saturacion: 0 };
        const itemB = summaryB.find(s => String(s.Centro) === label) || { Saturacion: 0 };
        const diff = (itemB.Saturacion - itemA.Saturacion) * 100;
        if (Math.abs(diff) > 0.1) {
            changes.push({ center: label, diff: diff });
        }
    });

    changes.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff));
    const topList = document.getElementById('top-changes-list');
    if (topList) {
        topList.innerHTML = changes.slice(0, 3).map(c => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <span style="font-weight: 600; font-size: 0.85rem;">Centro ${c.center}</span>
                <span class="${c.diff > 0 ? 'delta-neg' : 'delta-pos'}" style="font-size: 0.8rem; font-weight: 800; padding: 2px 6px; border-radius: 4px;">
                    ${c.diff > 0 ? '+' : ''}${c.diff.toFixed(1)}%
                </span>
            </div>
        `).join('') || '<div style="font-size: 0.8rem; opacity: 0.5;">No hay cambios significativos</div>';
    }

    // 4. Recommendation Logic
    const criticalCenters = summaryB.filter(s => s.Saturacion > 0.85);
    const recommendationContainer = document.getElementById('tile-changes'); // Reusing or updating
    if (recommendationContainer && criticalCenters.length > 0) {
        const div = document.createElement('div');
        div.style.marginTop = '1rem';
        div.style.padding = '10px';
        div.style.background = 'rgba(227, 6, 19, 0.1)';
        div.style.borderRadius = '8px';
        div.style.borderLeft = '4px solid var(--rpk-red)';
        div.innerHTML = `
            <div style="font-size: 0.75rem; font-weight: 800; color: var(--rpk-red); margin-bottom: 4px;">RECOMENDACIÓN</div>
            <div style="font-size: 0.8rem;">Se detectan ${criticalCenters.length} centros con saturación crítica (>85%). Considerar redistribución de carga.</div>
        `;
        recommendationContainer.appendChild(div);
    }
}

function exitComparisonMode() {
    isComparisonMode = false;
    document.getElementById('comparison-controls').style.display = 'none';

    // Restore control bar
    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'flex';

    // Restore standard Grid
    const dashboardGrid = document.querySelector('.bento-grid');
    if (dashboardGrid) {
        dashboardGrid.className = 'dashboard-grid';
        dashboardGrid.innerHTML = `
            <div class="dash-card chart-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h4 style="margin: 0;">Saturación por Centro (%)</h4>
                    <button id="btn-toggle-delta" class="action-btn small secondary" style="display:none; padding: 0.2rem 0.5rem; font-size: 0.7rem;">Ver Variación (%)</button>
                </div>
                <div class="chart-container">
                    <canvas id="saturationChart"></canvas>
                </div>
            </div>
            <div class="dash-card summary-card">
                <h4>Resumen de Capacidad</h4>
                <div id="summary-stats" class="summary-content"></div>
            </div>
        `;
    }

    // Restore table
    const tableCard = document.querySelector('.table-card');
    if (tableCard) tableCard.classList.remove('glass-table');

    if (currentScenarioId) updateNavItemActive(currentScenarioId);
    updateUI();
}

function renderComparisonDashboard() {
    const ctx = document.getElementById('saturationChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    const summaryA = (comparisonData.dataA.summary || []);
    const summaryB = (comparisonData.dataB.summary || []);

    const centersA = summaryA.map(s => String(s.Centro));
    const centersB = summaryB.map(s => String(s.Centro));
    const labels = [...new Set([...centersA, ...centersB])].sort();

    const dataA_Abs = labels.map(label => {
        const item = summaryA.find(s => String(s.Centro) === label);
        return item ? (item.Saturacion * 100).toFixed(1) : "0.0";
    });
    const dataB_Abs = labels.map(label => {
        const item = summaryB.find(s => String(s.Centro) === label);
        return item ? (item.Saturacion * 100).toFixed(1) : "0.0";
    });

    const deltaData = labels.map((centro, i) => {
        const valA = parseFloat(dataA_Abs[i]);
        const valB = parseFloat(dataB_Abs[i]);
        return (valB - valA).toFixed(1);
    });

    const isDelta = comparisonViewMode === 'delta';
    const mainDataset = isDelta ? {
        label: `Variación (%)`,
        data: deltaData,
        backgroundColor: deltaData.map(d => parseFloat(d) > 0 ? '#ff4d4d' : '#4cd137'),
        borderColor: deltaData.map(d => Math.abs(parseFloat(d)) > 10 ? '#fff' : 'transparent'),
        borderWidth: deltaData.map(d => Math.abs(parseFloat(d)) > 10 ? 1 : 0)
    } : {
        label: comparisonData.nameB,
        data: dataB_Abs,
        backgroundColor: dataB_Abs.map(val => parseFloat(val) > 90 ? '#ff4d4d' : '#E30613'),
        borderColor: dataB_Abs.map(val => parseFloat(val) > 90 ? '#ffffff' : 'transparent'),
        borderWidth: dataB_Abs.map(val => parseFloat(val) > 90 ? 2 : 0)
    };

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: isDelta ? [mainDataset] : [
                {
                    label: comparisonData.nameA,
                    data: dataA_Abs,
                    backgroundColor: '#444'
                },
                mainDataset
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#2d2d35' },
                    ticks: { color: '#a0a0a0' },
                    max: Math.max(100, ...dataA_Abs, ...dataB_Abs) + 10
                },
                x: { grid: { display: false }, ticks: { color: '#a0a0a0' } }
            },
            plugins: {
                legend: {
                    labels: { color: '#fff' }
                }
            }
        }
    });

    // Only render standard summary if container exists
    if (document.getElementById('summary-stats')) {
        renderComparisonSummary();
    }
}

function renderComparisonSummary() {
    const container = document.getElementById('summary-stats');
    if (!container) return; // Silent return if not in standard mode

    const avgA = (comparisonData.dataA.summary.reduce((acc, s) => acc + s.Saturacion, 0) / comparisonData.dataA.summary.length * 100).toFixed(1);
    const avgB = (comparisonData.dataB.summary.reduce((acc, s) => acc + s.Saturacion, 0) / comparisonData.dataB.summary.length * 100).toFixed(1);

    const delta = (avgB - avgA).toFixed(1);
    const deltaClass = delta > 0 ? 'delta-up' : (delta < 0 ? 'delta-down' : 'delta-neutral');
    const deltaIcon = delta > 0 ? '▲' : (delta < 0 ? '▼' : '●');
    const deltaText = delta == 0 ? 'Sin cambios' : `${Math.abs(delta)}% ${delta > 0 ? 'incremento' : 'reducción'}`;

    container.innerHTML = `
        <div class="stat-item" style="border-left-color: #666">
            <div class="stat-val">${avgA}%</div>
            <div class="stat-label">Saturación Media</div>
            <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; margin-top: 5px; text-transform: uppercase; letter-spacing: 0.05em;">
                ${comparisonData.nameA}
            </div>
        </div>
        <div class="stat-item" style="border-left-color: var(--rpk-red)">
            <div class="stat-val">${avgB}%</div>
            <div class="stat-label">Saturación Media</div>
            <div style="font-size: 0.7rem; color: var(--rpk-red); font-weight: 700; margin-top: 5px; text-transform: uppercase; letter-spacing: 0.05em;">
                ${comparisonData.nameB}
            </div>
            <div class="delta-badge ${deltaClass}">
                ${deltaIcon} ${deltaText}
            </div>
        </div>
    `;
}

function renderComparisonTable() {
    const body = document.getElementById('table-body');
    if (!body) return;
    const search = document.getElementById('table-search').value.toLowerCase();

    // We compare B against A
    const detailA = comparisonData.dataA.detail;
    const detailB = comparisonData.dataB.detail;

    let filtered = detailB;
    if (search) filtered = filtered.filter(d => d.Articulo.toString().toLowerCase().includes(search));

    body.innerHTML = filtered.slice(0, 100).map(dB => {
        // Find matching item in A by Article AND centro_original
        const dA = detailA.find(item => item.Articulo == dB.Articulo && (item.centro_original == dB.centro_original || item.Centro == dB.centro_original)) || {};

        const sat = (dB.Saturacion * 100).toFixed(1);
        const satClass = sat > 85 ? 'pill-high' : (sat > 70 ? 'pill-mid' : 'pill-low');

        const hasDiffOEE = Math.abs((dB['%OEE'] || 0) - (dA['%OEE'] || 0)) > 0.001;
        const hasDiffPPM = Math.abs((dB['Piezas por minuto'] || 0) - (dA['Piezas por minuto'] || 0)) > 0.1;
        const hasDiffDem = Math.abs((dB['Volumen anual'] || 0) - (dA['Volumen anual'] || 0)) > 1;
        const hasDiffCen = (dB['Centro'] !== dA['Centro']);
        const hasDiffShifts = (dB['horas_turno'] !== dA['horas_turno']);
        const hasDiffSetup = Math.abs((dB['Setup (h)'] || 0) - (dA['Setup (h)'] || 0)) > 0.01;

        const anyDiff = hasDiffOEE || hasDiffPPM || hasDiffDem || hasDiffCen || hasDiffShifts || hasDiffSetup;

        return `
            <tr class="${anyDiff ? 'row-changed' : ''}">
                <td><strong>${dB.Articulo}</strong></td>
                <td class="text-center">
                    <span class="center-tag ${hasDiffCen ? 'val-changed font-bold' : ''}">${dB.Centro}</span>
                    <div style="font-size: 0.7rem; color: ${hasDiffShifts ? 'var(--rpk-red)' : 'var(--text-muted)'}; margin-top: 4px;">
                        ${dB.horas_turno}h ${hasDiffShifts ? `(vs ${dA.horas_turno || 0}h)` : ''}
                    </div>
                </td>
                <td class="text-right ${hasDiffDem ? 'val-changed font-bold' : ''}">${dB['Volumen anual']?.toLocaleString() || 0}</td>
                <td class="text-right ${hasDiffPPM ? 'val-changed font-bold' : ''}">${Math.round(dB['Piezas por minuto'] || 0)}</td>
                <td class="text-right ${hasDiffOEE ? 'val-changed font-bold' : ''}">${((dB['%OEE'] || 0) * 100).toFixed(1)}%</td>
                <td class="text-center">
                    <span class="saturation-pill ${satClass}">${sat}%</span>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">
                        ${(dB.Horas_Totales || 0).toFixed(1)}h
                    </div>
                </td>
                <td class="text-right">${(dB.Ratio_MOD || 1.0).toFixed(2)}</td>
                <td class="text-right">${((dB.Impacto || 0) * 100).toFixed(1)}%</td>
                <td class="text-center">
                    <button class="secondary-btn btn-simular" 
                        style="padding: 0.3rem 0.6rem; font-size: 0.7rem;"
                        data-articulo="${dB.Articulo}" 
                        data-centro="${dB.Centro}">Ajustar</button>
                </td>
            </tr>
        `;
    }).join('');
}

function toggleComparisonView() {
    comparisonViewMode = (comparisonViewMode === 'delta') ? 'absolute' : 'delta';
    const btn = document.getElementById('btn-toggle-delta');
    if (btn) {
        btn.innerText = (comparisonViewMode === 'delta') ? 'Ver Valores Absolutos' : 'Ver Variación (%)';
    }
    renderComparisonDashboard();
}

// Add simple micro-animation trigger
function triggerDashboardAnimation() {
    const items = document.querySelectorAll('.bento-item');
    items.forEach((item, i) => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(20px)';
        item.style.transition = `all 0.5s ease ${i * 0.1}s`;
        setTimeout(() => {
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, 10);
    });
}
