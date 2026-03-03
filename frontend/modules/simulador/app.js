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
let isModeActual = false;

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
        ? `${API_BASE}/simulate/base?dias_laborales=${days}&horas_turno=${shifts}&use_actual=${isModeActual}`
        : `${API_BASE}/simulate/${scenarioId}?dias_laborales=${days}&horas_turno=${shifts}&use_actual=${isModeActual}`;

    document.getElementById('current-scenario-name').innerText = 'Cargando datos...';
    setLoading(true);

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        currentData = await response.json();
        if (scenarioId === 'base') baseData = currentData;

        currentScenarioId = scenarioId;
        const baseName = isModeActual ? 'Escenario Actual (ERP)' : 'Escenario Base';
        const sName = scenarioId === 'base' ? baseName : scenarios.find(s => s.id == scenarioId)?.name || 'Escenario';
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
        if (isModeActual) {
            document.getElementById('btn-actual')?.classList.add('active');
        } else {
            document.getElementById('btn-base')?.classList.add('active');
        }
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
        isModeActual = false;
        localOverrides = [];
        centerConfigs = {};
        currentScenarioId = 'base';
        loadSimulation('base');
    };

    const btnActual = document.getElementById('btn-actual');
    if (btnActual) {
        btnActual.onclick = () => {
            isModeActual = true;
            localOverrides = [];
            centerConfigs = {};
            currentScenarioId = 'base';
            loadSimulation('base');
        };
    }

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
        const res = await fetch(`${API_BASE}/simulate/preview?use_actual=${isModeActual}`, {
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

let comparisonViewMetric = 'Saturacion'; // 'Saturacion', 'OEE', 'Carga', 'FTE'
let comparisonSelectedCenters = [];
let compareHasEdits = false;

function enterComparisonMode() {
    document.body.classList.add('compare-mode');
    comparisonViewMetric = 'Saturacion';
    comparisonSelectedCenters = [];
    compareHasEdits = false;
    localOverrides = [];

    document.querySelector('.right-panel').style.display = 'none';

    const banner = document.getElementById('comparison-controls');
    if (banner) {
        banner.style.display = 'flex';
        banner.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span class="pill-info" style="background:rgba(227,6,19,0.15); color:var(--rpk-red); border-color:var(--rpk-red)">⚡ MODO COMPARATIVA</span>
                <span style="font-size: 0.85rem; color: var(--text-muted);">${comparisonData.nameA} <span style="opacity:0.5">VS</span> <strong style="color:#fff">${comparisonData.nameB}</strong></span>
            </div>
            <button id="btn-exit-compare" class="action-btn small" onclick="attemptExitComparison()" style="background:transparent; color:var(--text-muted); border:1px solid var(--border-color); font-size:0.75rem;">✕ Salir</button>
        `;
    }

    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'none';

    const dashboardGrid = document.querySelector('.dashboard-grid') || document.querySelector('.compare-layout');
    if (dashboardGrid) {
        dashboardGrid.className = 'compare-layout';
        dashboardGrid.innerHTML = `
            <!-- Row 1: KPI Cards -->
            <div class="kpi-row" id="kpi-row"></div>

            <!-- Row 2: Filter Bar -->
            <div class="compare-filter-bar" id="compare-filter-bar">
                <div class="panel-title">Filtro de Centros:</div>
                <select id="compare-center-select" multiple size="1" style="height:32px" onchange="onCompareFilterChange()">
                    <!-- options -->
                </select>
                <button onclick="resetCompareFilter()">Restablecer Top 15</button>
            </div>

            <!-- Row 3: Chart + Drill-down -->
            <div class="compare-body" id="compare-body">
                <div class="chart-panel">
                    <div class="panel-title" id="compare-chart-title">Saturación por Centro — Base vs Escenario</div>
                    <div class="chart-wrap"><canvas id="compareChart"></canvas></div>
                </div>
                <!-- Drilldown se insertará si hay un centro seleccionado -->
            </div>

            <!-- Row 4: Impact Analysis -->
            <div class="rec-bar" id="impact-bar"></div>
        `;
    }

    const tableCard = document.querySelector('.table-card');
    if (tableCard) tableCard.style.display = 'none';

    populateCompareFilters();
    renderCompareAll();
}

function renderCompareAll() {
    renderKPICards();
    renderCompareChart();
    renderImpactAnalysis();
}

let compareChartInstance = null;

function setCompareMetric(metric) {
    comparisonViewMetric = metric;
    renderCompareAll();
}

function renderKPICards() {
    if (!comparisonData?.dataA || !comparisonData?.dataB) return;
    const sA = comparisonData.dataA.summary || [];
    const sB = comparisonData.dataB.summary || [];
    const dA = comparisonData.dataA.detail || [];
    const dB = comparisonData.dataB.detail || [];
    const daysA = comparisonData.dataA.meta?.dias_laborales || 238;
    const daysB = comparisonData.dataB.meta?.dias_laborales || 238;

    const avgSatA = sA.length ? (sA.reduce((a, s) => a + (s.Saturacion || 0), 0) / sA.length) * 100 : 0;
    const avgSatB = sB.length ? (sB.reduce((a, s) => a + (s.Saturacion || 0), 0) / sB.length) * 100 : 0;
    const oeeA = dA.length ? (dA.reduce((a, d) => a + (d['%OEE'] || 0), 0) / dA.length) * 100 : 0;
    const oeeB = dB.length ? (dB.reduce((a, d) => a + (d['%OEE'] || 0), 0) / dB.length) * 100 : 0;
    const hoursA = dA.reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);
    const hoursB = dB.reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);
    const hhA = dA.reduce((a, d) => a + (d.Horas_Hombre || 0), 0);
    const hhB = dB.reduce((a, d) => a + (d.Horas_Hombre || 0), 0);
    const fteA = hhA / (daysA * 8);
    const fteB = hhB / (daysB * 8);

    const kpis = [
        { id: 'Saturacion', label: 'Saturación', value: avgSatB.toFixed(1) + '%', delta: avgSatB - avgSatA, fmt: v => (v > 0 ? '+' : '') + v.toFixed(1) + '%', inv: true },
        { id: 'OEE', label: 'OEE Medio', value: oeeB.toFixed(1) + '%', delta: oeeB - oeeA, fmt: v => (v > 0 ? '+' : '') + v.toFixed(1) + '%', inv: false },
        { id: 'Carga', label: 'Carga Total', value: hoursB.toLocaleString('es-ES', { maximumFractionDigits: 0 }) + 'h', delta: hoursB - hoursA, fmt: v => (v > 0 ? '+' : '') + v.toFixed(0) + 'h', inv: true },
        { id: 'FTE', label: 'Personal (FTE)', value: fteB.toFixed(1), delta: fteB - fteA, fmt: v => (v > 0 ? '+' : '') + v.toFixed(1), inv: true }
    ];

    const row = document.getElementById('kpi-row');
    if (!row) return;
    row.innerHTML = kpis.map(k => {
        const abs = Math.abs(k.delta);
        let cls = 'flat';
        if (abs > 0.05) cls = (k.inv ? k.delta > 0 : k.delta < 0) ? 'up' : 'down';
        const arrow = cls === 'up' ? '▲' : cls === 'down' ? '▼' : '●';
        const activeCls = comparisonViewMetric === k.id ? 'active' : '';
        return `
            <div class="kpi-card ${activeCls}" onclick="setCompareMetric('${k.id}')">
                <div class="kpi-label">${k.label}</div>
                <div class="kpi-value">${k.value}</div>
                <div class="kpi-delta ${cls}">${arrow} ${k.fmt(k.delta)}</div>
                <div class="kpi-sub">vs ${comparisonData.nameA}</div>
            </div>
        `;
    }).join('');
}

function populateCompareFilters() {
    if (!comparisonData?.dataB) return;
    const sB = comparisonData.dataB.summary || [];
    const allCenters = sB.map(s => String(s.Centro)).sort();
    
    const sel = document.getElementById('compare-center-select');
    if (!sel) return;
    sel.innerHTML = `<option value="">-- Filtrar Centros Específicos --</option>` + 
        allCenters.map(c => `<option value="${c}">${c}</option>`).join('');
}

function onCompareFilterChange() {
    const sel = document.getElementById('compare-center-select');
    const opts = Array.from(sel.selectedOptions).map(o => o.value).filter(v => v);
    comparisonSelectedCenters = opts;
    renderCompareChart();
}

function resetCompareFilter() {
    comparisonSelectedCenters = [];
    const sel = document.getElementById('compare-center-select');
    if (sel) sel.value = '';
    renderCompareChart();
}

function getCompareMetricValue(centroId, dataObj) {
    const s = (dataObj.summary || []).find(x => String(x.Centro) === String(centroId));
    const dArts = (dataObj.detail || []).filter(x => String(x.Centro) === String(centroId));
    
    if (comparisonViewMetric === 'Saturacion') return s ? s.Saturacion * 100 : 0;
    if (comparisonViewMetric === 'Carga') return dArts.reduce((acc, a) => acc + (a.Horas_Totales || 0), 0);
    if (comparisonViewMetric === 'OEE') {
        if (!dArts.length) return 0;
        return (dArts.reduce((acc, a) => acc + (a['%OEE'] || 0), 0) / dArts.length) * 100;
    }
    if (comparisonViewMetric === 'FTE') {
        const hh = dArts.reduce((acc, a) => acc + (a.Horas_Hombre || 0), 0);
        const days = dataObj.meta?.dias_laborales || 238;
        return hh / (days * 8);
    }
    return 0;
}

function renderCompareChart() {
    if (!comparisonData?.dataA || !comparisonData?.dataB) return;
    
    const sA = comparisonData.dataA.summary || [];
    const sB = comparisonData.dataB.summary || [];
    const allCenters = [...new Set([...sA.map(s => String(s.Centro)), ...sB.map(s => String(s.Centro))])].sort();

    let targetCenters = allCenters;
    
    if (comparisonSelectedCenters.length > 0) {
        targetCenters = comparisonSelectedCenters;
    } else {
        // Top 15 by Saturation in B
        targetCenters = [...allCenters].sort((a,b) => {
            const satA = sB.find(s => String(s.Centro) === a)?.Saturacion || 0;
            const satB = sB.find(s => String(s.Centro) === b)?.Saturacion || 0;
            return satB - satA;
        }).slice(0, 15);
    }

    const labels = targetCenters;
    const valsA = labels.map(c => getCompareMetricValue(c, comparisonData.dataA));
    const valsB = labels.map(c => getCompareMetricValue(c, comparisonData.dataB));

    const ctx = document.getElementById('compareChart');
    if (!ctx) return;
    
    document.getElementById('compare-chart-title').innerText = `${comparisonViewMetric} por Centro — ${comparisonData.nameA} vs ${comparisonData.nameB}`;

    if (compareChartInstance) compareChartInstance.destroy();

    compareChartInstance = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: comparisonData.nameA,
                    data: valsA,
                    backgroundColor: 'rgba(100,100,100,0.5)',
                    borderColor: '#666',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: comparisonData.nameB,
                    data: valsB,
                    backgroundColor: valsB.map(v => {
                        if (comparisonViewMetric === 'Saturacion' && v > 85) return 'rgba(255,77,77,0.7)';
                        return 'rgba(227,6,19,0.85)';
                    }),
                    borderColor: valsB.map(v => {
                        if (comparisonViewMetric === 'Saturacion' && v > 85) return '#ff4d4d';
                        return 'var(--rpk-red)';
                    }),
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    openDrillDown(labels[idx]);
                }
            },
            onHover: (e, elements) => {
                e.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#a0a0a0' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#a0a0a0', font: { size: 11, weight: '600' } }
                }
            },
            plugins: {
                legend: { display: true, position: 'top', labels: { color: '#a0a0a0', boxWidth: 12 } }
            }
        }
    });

    // Cierra el drill down si estaba abierto pero la barra no clica
    const body = document.getElementById('compare-body');
    if (body) {
        body.classList.remove('has-drill');
        const existingDrill = document.querySelector('.drilldown-panel');
        if (existingDrill) existingDrill.remove();
    }
}

function openDrillDown(centro) {
    const dB = comparisonData.dataB.detail || [];
    const artsB = dB.filter(d => String(d.Centro) === String(centro));
    
    // Preparar el HTML del drilldown
    const body = document.getElementById('compare-body');
    if (!body) return;
    
    body.classList.add('has-drill');
    
    // Eliminar el actual si existe
    const existing = document.querySelector('.drilldown-panel');
    if (existing) existing.remove();

    const turnosVal = centerConfigs[centro] || 'auto';

    const panel = document.createElement('div');
    panel.className = 'drilldown-panel';
    panel.innerHTML = `
        <div class="drill-header">
            <div class="drill-title">Centro ${centro}</div>
            <button class="drill-back" onclick="renderCompareChart()">✕ Cerrar</button>
        </div>
        <div style="margin-bottom: 15px; display:flex; gap:10px; align-items:center;">
            <label style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Turnos:</label>
            <select class="dark-input" style="padding: 3px 6px; font-size:0.75rem; min-width:80px;" onchange="applyCompareCenterEdit('${centro}', this.value)">
                <option value="auto" ${turnosVal === 'auto' ? 'selected' : ''}>Auto</option>
                <option value="8" ${turnosVal === 8 ? 'selected' : ''}>1 (8h)</option>
                <option value="16" ${turnosVal === 16 ? 'selected' : ''}>2 (16h)</option>
                <option value="24" ${turnosVal === 24 ? 'selected' : ''}>3 (24h)</option>
            </select>
        </div>
        <table class="drill-table">
            <thead>
                <tr>
                    <th>Art.</th>
                    <th title="S={Setup} / T={Traslado}">Conf</th>
                    <th title="Demanda Neta Anual">DMD</th>
                    <th title="OEE (%)">OEE</th>
                    <th title="Ratio Persona/Máquina">MOD</th>
                    <th title="Piezas Por Minuto">PPM</th>
                </tr>
            </thead>
            <tbody>
                ${artsB.map(r => `
                    <tr>
                        <td style="font-weight:600">${r.Articulo}</td>
                        <td style="display:flex;flex-direction:column;gap:3px">
                            <input title="Setup (Hrs)" type="number" class="dark-input" style="width:36px; padding:2px; font-size:0.7rem;" value="${(r.Setup || 0)}" onblur="applyCompareEdit('${r.Articulo}','Setup', this.value)">
                            <select title="Traslado" class="dark-input" style="width:36px; padding:2px; font-size:0.7rem;" onchange="applyCompareEdit('${r.Articulo}','Requiere_Traslado', this.value)">
                                <option value="1" ${r.Requiere_Traslado ? 'selected':''}>Si</option>
                                <option value="0" ${!r.Requiere_Traslado ? 'selected':''}>No</option>
                            </select>
                        </td>
                        <td><input type="number" class="dark-input" style="width:55px; padding:2px; font-size:0.7rem;" value="${Math.round(r.Demanda_Neta || r.Demanda || 0)}" onblur="applyCompareEdit('${r.Articulo}', 'Demanda', this.value)"></td>
                        <td><input type="number" class="dark-input" style="width:40px; padding:2px; font-size:0.7rem;" value="${(r['%OEE']*100).toFixed(1)}" onblur="applyCompareEdit('${r.Articulo}', 'OEE', this.value)"></td>
                        <td><input type="number" class="dark-input" style="width:32px; padding:2px; font-size:0.7rem;" value="${(r.Ratio_Personas_Maquina || 1.0)}" onblur="applyCompareEdit('${r.Articulo}', 'Ratio_Personas_Maquina', this.value)"></td>
                        <td><input type="number" class="dark-input" style="width:44px; padding:2px; font-size:0.7rem;" value="${r.PPM || 0}" onblur="applyCompareEdit('${r.Articulo}', 'PPM', this.value)"></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <div style="font-size: 0.65rem; color: var(--rpk-red); margin-top: 10px;">★ Los cambios recalculan el Escenario B en vivo.</div>
    `;
    
    body.appendChild(panel);
    compareChartInstance.resize();
}

async function applyCompareCenterEdit(centro, value) {
    if (value === 'auto') delete centerConfigs[centro];
    else centerConfigs[centro] = parseInt(value, 10);
    await triggerCompareRecalculation();
    openDrillDown(centro);
}

async function applyCompareEdit(articulo, field, value) {
    let override = localOverrides.find(o => o.Articulo === articulo);
    if (!override) {
        override = { Articulo: articulo };
        localOverrides.push(override);
    }
    
    let floatVal = parseFloat(value);
    if (field === 'OEE') {
        override['%OEE'] = floatVal / 100.0;
    } else {
        override[field] = floatVal;
    }

    const centro = comparisonData.dataB.detail.find(d => String(d.Articulo) === String(articulo))?.Centro;
    await triggerCompareRecalculation();
    if(centro) openDrillDown(centro);
}

async function triggerCompareRecalculation() {
    setLoading(true);
    compareHasEdits = true;
    try {
        const payload = {
            base_scenario_id: comparisonData.idB,
            overrides: localOverrides,
            center_configs: centerConfigs,
            config: {
                dias_laborales: parseInt(document.getElementById('work-days').value) || 238,
                turno_general: parseInt(document.getElementById('work-shifts').value) || 16,
                use_actual: false 
            }
        };

        const res = await fetch(`${API_BASE}/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error('Error al recalcular escenario B');
        const newData = await res.json();
        
        comparisonData.dataB = newData;
        renderCompareAll();
        renderLocalOverrides();
    } catch (e) {
        alert(e.message);
    } finally {
        setLoading(false);
    }
}

function renderImpactAnalysis() {
    if (!comparisonData?.dataA || !comparisonData?.dataB) return;
    const sA = comparisonData.dataA.summary || [];
    const sB = comparisonData.dataB.summary || [];
    const dA = comparisonData.dataA.detail || [];
    const dB = comparisonData.dataB.detail || [];
    
    const critA = sA.filter(s => s.Saturacion > 0.85).length;
    const critB = sB.filter(s => s.Saturacion > 0.85).length;
    
    const daysA = comparisonData.dataA.meta?.dias_laborales || 238;
    const daysB = comparisonData.dataB.meta?.dias_laborales || 238;
    const fteA = dA.reduce((acc, d) => acc + (d.Horas_Hombre || 0), 0) / (daysA * 8);
    const fteB = dB.reduce((acc, d) => acc + (d.Horas_Hombre || 0), 0) / (daysB * 8);
    const deltaFTE = fteB - fteA;

    // Centros modificados
    const modifiedCenters = [];
    sB.forEach(sbItem => {
        const saItem = sA.find(s => String(s.Centro) === String(sbItem.Centro));
        if (!saItem || Math.abs(sbItem.Saturacion - saItem.Saturacion) > 0.02) {
            modifiedCenters.push(sbItem.Centro);
        }
    });

    const bar = document.getElementById('impact-bar');
    if (!bar) return;
    bar.innerHTML = `
        <div class="rec-section">
            <div class="rec-title">Cambios Identificados</div>
            <div class="rec-item">
                <div class="rec-dot ${modifiedCenters.length > 0 ? 'yellow' : 'flat'}"></div>
                <div>${modifiedCenters.length} centros con variaciones respecto al base.</div>
            </div>
            ${modifiedCenters.length > 0 ? `<div style="font-size:0.7rem; color:var(--text-muted); margin-left:12px;">${modifiedCenters.slice(0,5).join(', ')}${modifiedCenters.length > 5 ? '...' : ''}</div>` : ''}
        </div>
        <div class="rec-section">
            <div class="rec-title">Nivel de Criticidad (>85%)</div>
            <div class="rec-item">
                <div class="rec-dot ${critB > critA ? 'red' : critB < critA ? 'green' : 'yellow'}"></div>
                <div>${critB} centros críticos críticos. ${critB > critA ? `(+ ${critB - critA} vs Base)` : critB < critA ? `(- ${critA - critB} vs Base)`:''}</div>
            </div>
        </div>
        <div class="rec-section">
            <div class="rec-title">Previsión de RRHH</div>
            <div class="rec-item">
                <div class="rec-dot ${deltaFTE > 5 ? 'red' : deltaFTE < -5 ? 'green' : 'yellow'}"></div>
                <div>Necesidad calculada: ${deltaFTE > 0 ? '+' : ''}${deltaFTE.toFixed(1)} FTE vs Base.</div>
            </div>
        </div>
    `;
}

function attemptExitComparison() {
    if (compareHasEdits) {
        document.getElementById('overwrite-section').style.display = 'block';
        document.getElementById('btn-overwrite-confirm').onclick = () => confirmExitComparison('overwrite');
        document.getElementById('btn-save-new-confirm').onclick = () => confirmExitComparison('new');
        document.getElementById('save-modal').style.display = 'flex';
    } else {
        exitComparisonMode();
    }
}

async function confirmExitComparison(action) {
    let savePayload = {
        overrides: localOverrides,
        center_configs: centerConfigs,
        config: comparisonData.dataB.meta || { dias_laborales: 238, turno_general: 16 }
    };

    if (action === 'overwrite') {
        if (comparisonData.idB === 'base' || comparisonData.idB === 'actual') {
            alert('Atención: NO ES POSIBLE sobreescribir los escenarios fijos (Base/Actual). Guardalo como nuevo.');
            return;
        }
        setLoading(true);
        try {
            savePayload.name = comparisonData.nameB;
            await fetch(`${API_BASE}/scenarios/${comparisonData.idB}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(savePayload)
            });
            alert('Escenario sobreescrito correctamente.');
        } catch (e) {
            alert('No se pudo guardar: ' + e.message);
        } finally {
            setLoading(false);
        }
    } else if (action === 'new') {
        const name = document.getElementById('new-scenario-name').value;
        if (!name) return alert('Por favor, ingresa un nombre para el nuevo escenario');
        setLoading(true);
        savePayload.name = name;
        try {
            await fetch(`${API_BASE}/scenarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(savePayload)
            });
            alert('Nuevo escenario generado.');
        } catch (e) {
            alert('Error al guardar: ' + e.message);
        } finally {
            setLoading(false);
        }
    }
    
    document.getElementById('save-modal').style.display = 'none';
    
    // Clear and exit
    localOverrides = [];
    centerConfigs = {};
    renderLocalOverrides();
    exitComparisonMode();
}

function exitComparisonMode() {
    isComparisonMode = false;
    document.body.classList.remove('compare-mode');
    document.getElementById('comparison-controls').style.display = 'none';
    document.querySelector('.right-panel').style.display = '';

    if (compareChartInstance) { compareChartInstance.destroy(); compareChartInstance = null; }

    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'flex';

    const dashboardGrid = document.querySelector('.compare-layout');
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

    const tableCard = document.querySelector('.table-card');
    if (tableCard) {
        tableCard.style.display = '';
    }

    if (currentScenarioId) loadSimulation(currentScenarioId);
    else updateUI();
}
