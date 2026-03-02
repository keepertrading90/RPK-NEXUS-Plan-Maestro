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

function enterComparisonMode() {
    const banner = document.getElementById('comparison-controls');
    if (banner) {
        banner.style.display = 'flex';
        banner.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span class="pill-info" style="background:#000; color:#ffc107; border-color:#ffc107">MODO COMPARATIVA KPI</span>
                <span style="font-size: 0.9rem;">${comparisonData.nameA} <span style="opacity:0.6">vs</span> <strong>${comparisonData.nameB}</strong></span>
            </div>
            <button id="btn-exit-compare" class="action-btn small" onclick="exitComparisonMode()" style="background:#000; color:#fff; border:1px solid #444">Cerrar Comparativa</button>
        `;
    }

    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'none';

    const dashboardGrid = document.querySelector('.dashboard-grid');
    if (dashboardGrid) {
        dashboardGrid.className = 'bento-pro';
        dashboardGrid.innerHTML = `
            <!-- Tile 1: Radar Multi-KPI -->
            <div class="tile-radar">
                <div class="kpi-header">Radar Multi-KPI — 5 Dimensiones</div>
                <div class="radar-container">
                    <div class="radar-chart-wrap"><canvas id="radarChart"></canvas></div>
                    <div class="radar-legend" id="radar-legend"></div>
                </div>
            </div>

            <!-- Tile 2: Gauge Eficiencia + Riesgo -->
            <div class="tile-gauge">
                <div class="kpi-header">Eficiencia Global de Planta</div>
                <div class="gauge-container" id="gauge-container"></div>
                <div style="margin-top: 16px;">
                    <div class="kpi-header">Riesgo Operativo</div>
                    <div id="risk-score-container"></div>
                </div>
            </div>

            <!-- Tile 3: Heatmap Variación -->
            <div class="tile-heatmap">
                <div class="kpi-header">Heatmap — Variación Saturación por Centro</div>
                <div class="heatmap-grid" id="heatmap-grid"></div>
            </div>

            <!-- Tile 4: Waterfall Capacidad -->
            <div class="tile-waterfall">
                <div class="kpi-header">Waterfall — Delta Capacidad (horas)</div>
                <div class="waterfall-container"><canvas id="waterfallChart"></canvas></div>
            </div>

            <!-- Tile 5: Decisiones + Recomendaciones -->
            <div class="tile-decisions">
                <div class="kpi-header">Semáforo de Decisión</div>
                <div class="semaphore-list" id="semaphore-list"></div>
                <div id="recommendation-container" style="margin-top: 12px;"></div>
            </div>
        `;
    }

    const tableCard = document.querySelector('.table-card');
    if (tableCard) tableCard.classList.add('glass-table');

    comparisonViewMode = 'absolute';
    document.getElementById('table-search').value = '';

    updateNavItemActive();
    renderExecutiveInsights();
    renderComparisonTable();
}

let radarChartInstance = null;
let waterfallChartInstance = null;

function renderExecutiveInsights() {
    if (!comparisonData || !comparisonData.dataA || !comparisonData.dataB) return;

    const summaryA = comparisonData.dataA.summary || [];
    const summaryB = comparisonData.dataB.summary || [];
    const detailA = comparisonData.dataA.detail || [];
    const detailB = comparisonData.dataB.detail || [];
    const daysA = comparisonData.dataA.meta.dias_laborales || 238;
    const daysB = comparisonData.dataB.meta.dias_laborales || 238;

    // ===== CALCULATIONS =====
    const avgSatA = summaryA.length > 0 ? (summaryA.reduce((a, s) => a + (s.Saturacion || 0), 0) / summaryA.length) * 100 : 0;
    const avgSatB = summaryB.length > 0 ? (summaryB.reduce((a, s) => a + (s.Saturacion || 0), 0) / summaryB.length) * 100 : 0;

    const oeeA = detailA.length > 0 ? (detailA.reduce((a, d) => a + (d['%OEE'] || 0), 0) / detailA.length) * 100 : 0;
    const oeeB = detailB.length > 0 ? (detailB.reduce((a, d) => a + (d['%OEE'] || 0), 0) / detailB.length) * 100 : 0;

    const totalHoursA = detailA.reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);
    const totalHoursB = detailB.reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);

    const setupA = detailA.reduce((a, d) => a + (d['Tiempo_Setup'] || 0), 0);
    const setupB = detailB.reduce((a, d) => a + (d['Tiempo_Setup'] || 0), 0);

    const sumHHA = detailA.reduce((a, d) => a + (d.Horas_Hombre || 0), 0);
    const sumHHB = detailB.reduce((a, d) => a + (d.Horas_Hombre || 0), 0);
    const fteA = sumHHA / (daysA * 8);
    const fteB = sumHHB / (daysB * 8);

    // Normalize for radar (scale 0-100)
    const maxHours = Math.max(totalHoursA, totalHoursB, 1);
    const maxSetup = Math.max(setupA, setupB, 1);
    const maxFTE = Math.max(fteA, fteB, 1);

    // ===== 1. RADAR CHART =====
    const radarCtx = document.getElementById('radarChart');
    if (radarCtx) {
        if (radarChartInstance) radarChartInstance.destroy();
        radarChartInstance = new Chart(radarCtx.getContext('2d'), {
            type: 'radar',
            data: {
                labels: ['Saturación', 'OEE', 'Carga (h)', 'Setup (h)', 'FTE'],
                datasets: [
                    {
                        label: comparisonData.nameA,
                        data: [avgSatA, oeeA, (totalHoursA / maxHours) * 100, (setupA / maxSetup) * 100, (fteA / maxFTE) * 100],
                        backgroundColor: 'rgba(100, 100, 100, 0.15)',
                        borderColor: '#666',
                        borderWidth: 2,
                        pointBackgroundColor: '#888'
                    },
                    {
                        label: comparisonData.nameB,
                        data: [avgSatB, oeeB, (totalHoursB / maxHours) * 100, (setupB / maxSetup) * 100, (fteB / maxFTE) * 100],
                        backgroundColor: 'rgba(227, 6, 19, 0.15)',
                        borderColor: '#E30613',
                        borderWidth: 2,
                        pointBackgroundColor: '#E30613'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 120,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        angleLines: { color: 'rgba(255,255,255,0.05)' },
                        pointLabels: { color: '#a0a0a0', font: { size: 11, weight: '600' } },
                        ticks: { display: false }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });

        // Radar Legend
        const legend = document.getElementById('radar-legend');
        if (legend) {
            const dims = [
                { name: 'Saturación', valA: avgSatA.toFixed(1) + '%', valB: avgSatB.toFixed(1) + '%' },
                { name: 'OEE', valA: oeeA.toFixed(1) + '%', valB: oeeB.toFixed(1) + '%' },
                { name: 'Carga', valA: totalHoursA.toFixed(0) + 'h', valB: totalHoursB.toFixed(0) + 'h' },
                { name: 'Setup', valA: setupA.toFixed(0) + 'h', valB: setupB.toFixed(0) + 'h' },
                { name: 'FTE', valA: fteA.toFixed(1), valB: fteB.toFixed(1) }
            ];
            legend.innerHTML = dims.map(d => `
                <div class="radar-legend-item">
                    <span style="font-size:0.7rem; color:var(--text-muted)">${d.name}</span>
                    <span class="leg-val" style="color:#888">${d.valA}</span>
                    <span style="color:#444">→</span>
                    <span class="leg-val" style="color:var(--rpk-red)">${d.valB}</span>
                </div>
            `).join('');
        }
    }

    // ===== 2. EFFICIENCY GAUGE =====
    const gaugeEl = document.getElementById('gauge-container');
    if (gaugeEl) {
        const efficiency = Math.min(100, Math.max(0, 100 - avgSatB + oeeB * 0.5));
        const efficiencyA = Math.min(100, Math.max(0, 100 - avgSatA + oeeA * 0.5));
        const delta = efficiency - efficiencyA;
        const deltaClass = delta > 1 ? 'positive' : delta < -1 ? 'negative' : 'neutral';
        const deltaSign = delta > 0 ? '+' : '';
        const rotation = -90 + (efficiency / 100) * 180;

        gaugeEl.innerHTML = `
            <div class="gauge-ring">
                <div class="gauge-fill" style="transform: rotate(${rotation}deg)"></div>
                <div class="gauge-value">${efficiency.toFixed(1)}%</div>
            </div>
            <div class="gauge-label">Índice compuesto: (100 - Sat) + OEE×0.5</div>
            <div class="gauge-delta ${deltaClass}">${deltaSign}${delta.toFixed(1)} pts vs ${comparisonData.nameA}</div>
        `;
    }

    // ===== 3. RISK SCORE =====
    const riskEl = document.getElementById('risk-score-container');
    if (riskEl) {
        const criticalCenters = summaryB.filter(s => s.Saturacion > 0.85).length;
        const overloadedCenters = summaryB.filter(s => s.Saturacion > 1.0).length;
        const riskScore = Math.min(100, Math.round(
            (criticalCenters / Math.max(summaryB.length, 1)) * 40 +
            (overloadedCenters / Math.max(summaryB.length, 1)) * 40 +
            (avgSatB > 80 ? 20 : avgSatB > 60 ? 10 : 0)
        ));
        const riskColor = riskScore > 70 ? '#ff4d4d' : riskScore > 40 ? '#f5a623' : '#4cd137';
        const riskLabel = riskScore > 70 ? 'ALTO' : riskScore > 40 ? 'MEDIO' : 'BAJO';

        riskEl.innerHTML = `
            <div class="risk-container">
                <div class="risk-bar-bg">
                    <div class="risk-bar-fill" style="width:${riskScore}%; background:${riskColor}"></div>
                </div>
                <div class="risk-value" style="color:${riskColor}">${riskScore}</div>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:4px;">
                <span style="font-size:0.65rem; color:var(--text-muted)">Centros críticos: ${criticalCenters} | Sobrecarga: ${overloadedCenters}</span>
                <span style="font-size:0.7rem; font-weight:800; color:${riskColor}">${riskLabel}</span>
            </div>
        `;
    }

    // ===== 4. HEATMAP =====
    const heatmapEl = document.getElementById('heatmap-grid');
    if (heatmapEl) {
        const labels = [...new Set([...summaryA.map(s => String(s.Centro)), ...summaryB.map(s => String(s.Centro))])].sort();
        heatmapEl.innerHTML = labels.map(centro => {
            const itemA = summaryA.find(s => String(s.Centro) === centro) || { Saturacion: 0 };
            const itemB = summaryB.find(s => String(s.Centro) === centro) || { Saturacion: 0 };
            const diff = ((itemB.Saturacion - itemA.Saturacion) * 100);
            const absDiff = Math.abs(diff);
            const intensity = Math.min(absDiff / 30, 1);
            const bg = diff > 0.5
                ? `rgba(255, 77, 77, ${0.1 + intensity * 0.4})`
                : diff < -0.5
                    ? `rgba(76, 209, 55, ${0.1 + intensity * 0.4})`
                    : 'rgba(255,255,255,0.03)';
            const barColor = diff > 0.5 ? '#ff4d4d' : diff < -0.5 ? '#4cd137' : '#555';
            return `
                <div class="heatmap-cell" style="background:${bg};" title="Centro ${centro}: ${diff > 0 ? '+' : ''}${diff.toFixed(1)}% saturación">
                    <div class="cell-id">${centro}</div>
                    <div class="cell-val">${diff > 0 ? '+' : ''}${diff.toFixed(1)}%</div>
                    <div class="cell-bar" style="background:${barColor}"></div>
                </div>
            `;
        }).join('');
    }

    // ===== 5. WATERFALL CHART =====
    const wfCtx = document.getElementById('waterfallChart');
    if (wfCtx) {
        if (waterfallChartInstance) waterfallChartInstance.destroy();
        const labels = [...new Set([...summaryA.map(s => String(s.Centro)), ...summaryB.map(s => String(s.Centro))])].sort();
        const deltas = labels.map(centro => {
            const hA = detailA.filter(d => String(d.Centro) === centro).reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);
            const hB = detailB.filter(d => String(d.Centro) === centro).reduce((a, d) => a + (d['Horas_Totales'] || 0), 0);
            return { centro, delta: hB - hA };
        }).filter(d => Math.abs(d.delta) > 0.1).sort((a, b) => b.delta - a.delta);

        waterfallChartInstance = new Chart(wfCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: deltas.map(d => d.centro),
                datasets: [{
                    label: 'Δ Horas',
                    data: deltas.map(d => d.delta.toFixed(1)),
                    backgroundColor: deltas.map(d => d.delta > 0 ? 'rgba(255,77,77,0.7)' : 'rgba(76,209,55,0.7)'),
                    borderColor: deltas.map(d => d.delta > 0 ? '#ff4d4d' : '#4cd137'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: '#2d2d35' }, ticks: { color: '#a0a0a0' } },
                    x: { grid: { display: false }, ticks: { color: '#a0a0a0', font: { size: 10 } } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${parseFloat(ctx.raw) > 0 ? '+' : ''}${ctx.raw}h`
                        }
                    }
                }
            }
        });
    }

    // ===== 6. DECISION SEMAPHORE =====
    const semEl = document.getElementById('semaphore-list');
    if (semEl) {
        const deltaSat = avgSatB - avgSatA;
        const deltaOEE = oeeB - oeeA;
        const deltaFTE = fteB - fteA;
        const deltaHours = totalHoursB - totalHoursA;
        const critCount = summaryB.filter(s => s.Saturacion > 0.85).length;

        const items = [
            {
                dot: deltaSat > 5 ? 'red' : deltaSat > 2 ? 'yellow' : 'green',
                text: 'Saturación Media',
                value: `${deltaSat > 0 ? '+' : ''}${deltaSat.toFixed(1)}%`,
                valueColor: deltaSat > 5 ? '#ff4d4d' : deltaSat > 2 ? '#f5a623' : '#4cd137'
            },
            {
                dot: deltaOEE < -2 ? 'red' : deltaOEE < 0 ? 'yellow' : 'green',
                text: 'Eficiencia OEE',
                value: `${deltaOEE > 0 ? '+' : ''}${deltaOEE.toFixed(1)}%`,
                valueColor: deltaOEE < -2 ? '#ff4d4d' : deltaOEE < 0 ? '#f5a623' : '#4cd137'
            },
            {
                dot: deltaFTE > 5 ? 'red' : deltaFTE > 1 ? 'yellow' : 'green',
                text: 'Personal (FTE)',
                value: `${deltaFTE > 0 ? '+' : ''}${deltaFTE.toFixed(1)} personas`,
                valueColor: deltaFTE > 5 ? '#ff4d4d' : deltaFTE > 1 ? '#f5a623' : '#4cd137'
            },
            {
                dot: deltaHours > 100 ? 'red' : deltaHours > 10 ? 'yellow' : 'green',
                text: 'Carga Total',
                value: `${deltaHours > 0 ? '+' : ''}${deltaHours.toFixed(0)}h`,
                valueColor: deltaHours > 100 ? '#ff4d4d' : deltaHours > 10 ? '#f5a623' : '#4cd137'
            },
            {
                dot: critCount > 3 ? 'red' : critCount > 0 ? 'yellow' : 'green',
                text: 'Centros Críticos (>85%)',
                value: `${critCount} centros`,
                valueColor: critCount > 3 ? '#ff4d4d' : critCount > 0 ? '#f5a623' : '#4cd137'
            }
        ];

        semEl.innerHTML = items.map(item => `
            <div class="semaphore-item">
                <div class="semaphore-dot ${item.dot}"></div>
                <div class="semaphore-text">${item.text}</div>
                <div class="semaphore-value" style="color:${item.valueColor}">${item.value}</div>
            </div>
        `).join('');
    }

    // ===== 7. SMART RECOMMENDATIONS =====
    const recEl = document.getElementById('recommendation-container');
    if (recEl) {
        const recommendations = [];
        const criticalCenters = summaryB.filter(s => s.Saturacion > 0.85).map(s => String(s.Centro));
        const freeCenters = summaryB.filter(s => s.Saturacion < 0.5).map(s => String(s.Centro));

        if (criticalCenters.length > 0 && freeCenters.length > 0) {
            recommendations.push(`Redistribuir carga de centros saturados (${criticalCenters.slice(0, 2).join(', ')}) hacia centros con capacidad libre (${freeCenters.slice(0, 2).join(', ')}).`);
        }
        if (criticalCenters.length > 0 && freeCenters.length === 0) {
            recommendations.push(`⚠️ ${criticalCenters.length} centros en estado crítico sin alternativa libre. Considerar turno adicional o subcontratación.`);
        }
        if (oeeB < oeeA && (oeeA - oeeB) > 2) {
            recommendations.push(`El OEE ha caído ${(oeeA - oeeB).toFixed(1)}%. Revisar cambios en cadencias o condiciones de máquina antes de aplicar este escenario.`);
        }
        if ((fteB - fteA) > 3) {
            recommendations.push(`Se necesitan +${(fteB - fteA).toFixed(0)} operarios (FTE). Solicitar provisión al dept. de RRHH con ${Math.ceil((fteB - fteA) * 1.1)} posiciones netas (10% rotación).`);
        }
        if (recommendations.length === 0) {
            recommendations.push('El escenario es viable sin cambios estructurales. Proceder con la planificación estándar.');
        }

        recEl.innerHTML = `
            <div class="recommendation-box">
                <div class="rec-title">💡 Recomendación del Sistema</div>
                <div class="rec-text">${recommendations.join('<br><br>')}</div>
            </div>
        `;
    }
}

function exitComparisonMode() {
    isComparisonMode = false;
    document.getElementById('comparison-controls').style.display = 'none';

    // Destroy KPI chart instances
    if (radarChartInstance) { radarChartInstance.destroy(); radarChartInstance = null; }
    if (waterfallChartInstance) { waterfallChartInstance.destroy(); waterfallChartInstance = null; }

    // Restore control bar
    const controlBar = document.querySelector('.control-bar');
    if (controlBar) controlBar.style.display = 'flex';

    // Restore standard Grid (check both old and new class names)
    const dashboardGrid = document.querySelector('.bento-pro') || document.querySelector('.bento-grid');
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
