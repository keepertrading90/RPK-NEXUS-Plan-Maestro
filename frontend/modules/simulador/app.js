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

    document.getElementById('current-scenario-name').innerHTML = 'Cargando<br>datos...';
    setLoading(true);

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        currentData = await response.json();
        if (scenarioId === 'base') baseData = currentData;

        currentScenarioId = scenarioId;
        const baseName = isModeActual ? 'Escenario<br>Actual (ERP)' : 'Escenario<br>Base';
        const scName = scenarios.find(s => s.id == scenarioId)?.name || 'Escenario';
        const sName = scenarioId === 'base' ? baseName : `Escenario<br>${scName}`;
        document.getElementById('current-scenario-name').innerHTML = sName;

        if (scenarioId !== 'base' && currentData.meta) {
            document.getElementById('work-days').value = currentData.meta.dias_laborales || 238;
            document.getElementById('work-shifts').value = currentData.meta.horas_turno_global || 16;
            centerConfigs = currentData.meta.center_configs || {};
            // DO NOT pre-populate localOverrides with saved overrides.
            // localOverrides should only contain NEW edits made in the current session.
            localOverrides = [];
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
        document.getElementById('current-scenario-name').innerHTML = 'Error de<br>conexión';
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
                <td class="text-center" style="white-space: nowrap;">
                    <button class="secondary-btn btn-simular" 
                        style="padding: 0.3rem 0.6rem; font-size: 0.7rem;"
                        data-articulo="${d.Articulo}" 
                        data-centro="${d.Centro}">Ajustar</button>
                    <button class="secondary-btn btn-delete-art" 
                        style="padding: 0.3rem 0.4rem; font-size: 0.8rem; background: transparent; border: 1px solid #555; color: #888; cursor: pointer; margin-left: 4px;"
                        data-articulo="${d.Articulo}" 
                        data-centro="${d.Centro}"
                        title="Eliminar artículo">🗑️</button>
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
        // Resolve original values: use stored originals, or look up from baseData/comparisonData
        let origOee = ov.original_oee;
        let origPpm = ov.original_ppm;
        let origDem = ov.original_demanda;
        let origShifts = ov.original_shifts;
        let origSetup = ov.original_setup;
        let origMod = ov.original_mod;

        if (origOee === undefined || origOee === null) {
            const src = baseData?.detail?.find(d => String(d.Articulo) === String(ov.articulo) && String(d.Centro) === String(ov.centro));
            if (src) {
                origOee = src['%OEE'] || 0;
                origPpm = src['Piezas por minuto'] || 0;
                origDem = src['Volumen anual'] || 0;
                origShifts = src['horas_turno'] || 16;
                origSetup = src['Setup (h)'] || 0;
                origMod = src['Ratio_MOD'] || 1.0;
            } else {
                origOee = 0; origPpm = 0; origDem = 0; origShifts = 16; origSetup = 0; origMod = 1.0;
            }
        }

        const showTraslado = ov.new_centro && String(ov.new_centro) !== String(ov.centro);

        return `
            <div class="override-item">
                <button class="btn-remove-ov" onclick="removeOverride(${idx})" title="Eliminar">&times;</button>
                <h4>${ov.articulo}</h4>
                <div class="override-info">
                    ${showTraslado ? `<span>➜ Traslado: <b class="val-changed">${ov.new_centro}</b></span>` : ''}
                    
                    ${ov.oee_override != null ? (() => {
                const orig = ((origOee || 0) * 100).toFixed(1);
                const newVal = (ov.oee_override * 100).toFixed(1);
                const changed = orig !== newVal;
                return `<div>OEE: ${changed ? `<span class="val-original">${orig}%</span><b class="val-changed">➜ ${newVal}%</b>` : `<span>${orig}%</span>`}</div>`;
            })() : ''}
                    
                    ${ov.ppm_override != null ? (() => {
                const orig = Math.round(origPpm || 0);
                const newVal = Math.round(ov.ppm_override);
                const changed = orig !== newVal;
                return `<div>PPM: ${changed ? `<span class="val-original">${orig}</span><b class="val-changed">➜ ${newVal}</b>` : `<span>${orig}</span>`}</div>`;
            })() : ''}
                    
                    ${ov.demanda_override != null ? (() => {
                const orig = Math.round(origDem || 0);
                const newVal = Math.round(ov.demanda_override);
                const changed = orig !== newVal;
                return `<div>Dem: ${changed ? `<span class="val-original">${orig.toLocaleString()}</span><b class="val-changed">➜ ${newVal.toLocaleString()}</b>` : `<span>${orig.toLocaleString()}</span>`}</div>`;
            })() : ''}
                    ${ov.horas_turno_override != null ? (() => {
                const orig = origShifts || 16;
                const newVal = ov.horas_turno_override;
                const changed = orig != newVal;
                return `<div>Turnos: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
            })() : ''}

                    ${ov.setup_time_override !== undefined && ov.setup_time_override !== null ? (() => {
                const orig = (origSetup || 0).toFixed(1);
                const newVal = (Number(ov.setup_time_override)).toFixed(1);
                const changed = Math.abs(origSetup - ov.setup_time_override) >= 0.1;
                return `<div>Setup: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
            })() : ''}

                    ${ov.personnel_ratio_override !== undefined && ov.personnel_ratio_override !== null ? (() => {
                const orig = (origMod || 1.0).toFixed(1);
                const newVal = (Number(ov.personnel_ratio_override)).toFixed(1);
                const changed = origMod !== ov.personnel_ratio_override;
                return `<div>MOD: ${changed ? `<span class="val-original">${orig}</span><b class="val-changed">➜ ${newVal}</b>` : `<span>${orig}</span>`}</div>`;
            })() : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function removeOverride(i) {
    localOverrides.splice(i, 1);
    if (isComparisonMode) {
        await triggerCompareRecalculation();
    } else {
        await updatePreviewSimulation();
    }
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

                        if (ov.horas_turno_override != null) {
                            const orig = baseItem ? baseItem['horas_turno'] : '?';
                            const newVal = ov.horas_turno_override;
                            const changed = orig != newVal;
                            detailItemsHtml += `<div>Turnos: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
                        }

                        if (ov.setup_time_override != null) {
                            const orig = baseItem ? Number(baseItem['Setup (h)'] || 0).toFixed(1) : '?';
                            const newVal = Number(ov.setup_time_override).toFixed(1);
                            const changed = orig !== newVal;
                            detailItemsHtml += `<div>Setup: ${changed ? `<span class="val-original">${orig}h</span><b class="val-changed">➜ ${newVal}h</b>` : `<span>${orig}h</span>`}</div>`;
                        }

                        if (ov.personnel_ratio_override != null) {
                            const orig = baseItem ? Number(baseItem['Ratio_MOD'] || 1.0).toFixed(1) : '?';
                            const newVal = Number(ov.personnel_ratio_override).toFixed(1);
                            const changed = orig !== newVal;
                            detailItemsHtml += `<div>MOD: ${changed ? `<span class="val-original">${orig}</span><b class="val-changed">➜ ${newVal}</b>` : `<span>${orig}</span>`}</div>`;
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
        <div class="checkbox-item" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
            <div style="display: flex; align-items: center;">
                <input type="checkbox" id="cb-all" onchange="toggleSelectAll()" ${selectedCenters.length === 0 || selectedCenters.includes('all') ? 'checked' : ''}>
                <span style="margin-left:8px;">-- Todos los Centros --</span>
            </div>
            <button onclick="resetCenterConfigs(event)" style="background:var(--dark-surface); border:1px solid var(--border-color); color:var(--text-muted); padding:2px 6px; border-radius:3px; font-size:0.65rem; cursor:pointer;" onmouseover="this.style.color='white'; this.style.borderColor='#888'" onmouseout="this.style.color='var(--text-muted)'; this.style.borderColor='var(--border-color)'">
                Reset MOD/Turnos
            </button>
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
                        oninput="this.nextElementSibling.value = parseFloat(this.value).toFixed(1)"
                        onchange="setCenterRatio('${c}', this.value, event)">
                    <input type="number" min="0.1" max="3.0" step="0.1" value="${(config.personnel_ratio || 1.0).toFixed(1)}"
                        style="width: 45px; background: var(--border-color); border: 1px solid #444; color: white; text-align: center; border-radius: 3px; font-size: 0.75rem; padding: 2px;"
                        onchange="this.previousElementSibling.value = this.value; setCenterRatio('${c}', this.value, event)"
                        onclick="event.stopPropagation()">
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

async function resetCenterConfigs(event) {
    if (event) event.stopPropagation();
    centerConfigs = {};
    populateWorkCenters(); // Rerender to show default values
    await updatePreviewSimulation();
}

function toggleDropdown() {
    const content = document.getElementById('work-center-options');
    content.classList.toggle('show');
}

// Close dropdown when clicking outside
window.addEventListener('click', function (event) {
    if (!event.target.matches('.dropdown-btn') && !event.target.matches('.dropdown-btn *') && !event.target.closest('.dropdown-content')) {
        closeDropdowns();
    }
});

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
            if (isComparisonMode) {
                alert("Para simular nuevos datos, debes salir del modo comparativa.");
                return;
            }
            openEditModal(e.target.getAttribute('data-articulo'), e.target.getAttribute('data-centro'));
        }
        if (e.target.classList.contains('btn-delete-art') || e.target.closest('.btn-delete-art')) {
            const btn = e.target.classList.contains('btn-delete-art') ? e.target : e.target.closest('.btn-delete-art');
            openDeleteConfirmModal(btn.getAttribute('data-articulo'), btn.getAttribute('data-centro'));
        }
    };

    document.getElementById('btn-base').onclick = () => {
        if (isComparisonMode) {
            alert("Debes salir del Modo Comparativa antes de cambiar de pestaña.");
            return;
        }
        isModeActual = false;
        localOverrides = [];
        centerConfigs = {};
        currentScenarioId = 'base';
        loadSimulation('base');
    };

    const btnActual = document.getElementById('btn-actual');
    if (btnActual) {
        btnActual.onclick = () => {
            if (isComparisonMode) {
                alert("Debes salir del Modo Comparativa antes de cambiar de pestaña.");
                return;
            }
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

            // Read form values
            const formOee = parseFloat(document.getElementById('edit-oee').value) / 100 || 0;
            const formPpm = parseFloat(document.getElementById('edit-ppm').value) || 0;
            const formDemanda = parseFloat(document.getElementById('edit-demanda').value) || 0;
            const formNewCentro = document.getElementById('edit-new-centro').value;
            const formShifts = document.getElementById('edit-shifts').value;
            const formMod = parseFloat(document.getElementById('edit-mod').value) || null;
            const formSetup = parseFloat(document.getElementById('edit-setup').value) || 0;

            // Source of truth: baseData originals
            const b = baseData?.detail?.find(item => String(item.Articulo) == String(articulo) && String(item.Centro) == String(centroBase));
            const origOee = b ? b['%OEE'] : 0;
            const origPpm = b ? (b['Piezas por minuto'] || 0) : 0;
            const origDem = b ? (b['Volumen anual'] || 0) : 0;
            const origShifts = b ? (b.horas_turno || 16) : 16;
            const origSetup = b ? (b['Setup (h)'] || 0) : 0;
            const origMod = b ? (b.Ratio_MOD || 1.0) : 1.0;

            // Only include fields that actually changed (smart diffing)
            const thresh = 0.001; // tolerance for float comparison
            const override = {
                articulo,
                centro: centroBase,
                oee_override: Math.abs(formOee - origOee) > thresh ? formOee : null,
                ppm_override: Math.abs(formPpm - origPpm) > thresh ? formPpm : null,
                demanda_override: Math.abs(formDemanda - origDem) > 0.5 ? formDemanda : null,
                new_centro: (formNewCentro && String(formNewCentro) !== String(centroBase)) ? formNewCentro : null,
                horas_turno_override: (formShifts && parseInt(formShifts) !== origShifts) ? parseInt(formShifts) : null,
                personnel_ratio_override: (formMod && Math.abs(formMod - origMod) > thresh) ? formMod : null,
                setup_time_override: Math.abs(formSetup - origSetup) > thresh ? formSetup : null,
                // Store originals for diff visualization
                original_oee: origOee,
                original_ppm: origPpm,
                original_demanda: origDem,
                original_shifts: origShifts,
                original_setup: origSetup,
                original_mod: origMod
            };

            // Only save if at least one field actually changed
            const hasChanges = override.oee_override !== null || override.ppm_override !== null ||
                override.demanda_override !== null || override.new_centro !== null ||
                override.horas_turno_override !== null || override.personnel_ratio_override !== null ||
                override.setup_time_override !== null;

            if (!hasChanges) {
                document.getElementById('edit-modal').style.display = 'none';
                return; // No real changes, skip
            }

            const idx = localOverrides.findIndex(o => String(o.articulo) == String(articulo) && String(o.centro) == String(centroBase));
            if (idx >= 0) localOverrides[idx] = override;
            else localOverrides.push(override);

            document.getElementById('edit-modal').style.display = 'none';

            if (isComparisonMode) {
                await triggerCompareRecalculation();
                openDrillDown(centroBase);
            } else {
                await updatePreviewSimulation();
            }
        };
    }

    document.getElementById('cancel-edit').onclick = () => {
        document.getElementById('edit-modal').style.display = 'none';
    };

    document.getElementById('btn-new').onclick = () => {
        if (isComparisonMode) {
            alert("Debes salir del Modo Comparativa antes de crear un escenario.");
            return;
        }
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

    document.getElementById('btn-compare').onclick = () => {
        if (isComparisonMode) {
            alert("Ya estás en Modo Comparativa. Para iniciar una nueva, sal primero.");
            return;
        }
        document.getElementById('compare-modal').style.display = 'flex';
    };
    document.getElementById('run-compare').onclick = runCompare;
    document.getElementById('btn-exit-compare').onclick = exitComparisonMode;
    document.getElementById('btn-toggle-delta').onclick = () => {
        comparisonViewMode = (comparisonViewMode === 'absolute' ? 'delta' : 'absolute');
        document.getElementById('btn-toggle-delta').innerText = (comparisonViewMode === 'absolute' ? 'Ver Variación (%)' : 'Ver Valores Absolutos');
        renderComparisonDashboard();
    };
    document.getElementById('btn-manage').onclick = () => {
        if (isComparisonMode) {
            alert("Debes salir del Modo Comparativa antes de ir a Gestionar.");
            return;
        }
        renderManageList();
        document.getElementById('manage-modal').style.display = 'flex';
    };

    const closeHandlers = document.querySelectorAll('.close, .close-manage');
    closeHandlers.forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
        };
    });

    // Se usa un document.addEventListener para no pisar el de dropdowns
    document.addEventListener('click', (event) => {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });
}

function cleanOverridesForSave(overrides) {
    return (overrides || []).map(o => ({
        articulo: String(o.articulo),
        centro: String(o.centro),
        oee_override: o.oee_override ?? null,
        ppm_override: o.ppm_override ?? null,
        demanda_override: o.demanda_override ?? null,
        new_centro: o.new_centro ?? null,
        horas_turno_override: o.horas_turno_override ?? null,
        setup_time_override: o.setup_time_override ?? null,
        personnel_ratio_override: o.personnel_ratio_override ?? null
    }));
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
                overrides: cleanOverridesForSave(localOverrides)
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
        alert('Error de red al guardar: ' + e.message);
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
    const dataSource = (isComparisonMode && comparisonData?.dataB) ? comparisonData.dataB : currentData;
    const d = dataSource?.detail?.find(item => item.Articulo == articulo && item.Centro == centro);
    if (!d) return;

    document.getElementById('edit-articulo').value = articulo;
    document.getElementById('edit-centro').value = centro;
    document.getElementById('display-articulo').innerText = articulo;
    document.getElementById('edit-oee').value = (d['%OEE'] * 100).toFixed(2);
    document.getElementById('edit-ppm').value = Math.round(d['Piezas por minuto'] || d['PPM'] || 0);
    document.getElementById('edit-demanda').value = Math.round(d['Volumen anual'] || d['Demanda'] || 0);

    const existingOverride = localOverrides.find(o => o.articulo == articulo && o.centro == centro);
    document.getElementById('edit-shifts').value = (existingOverride && existingOverride.horas_turno_override) ? existingOverride.horas_turno_override : "";
    document.getElementById('edit-setup').value = (existingOverride && existingOverride.setup_time_override !== undefined) ? existingOverride.setup_time_override : (d['Setup (h)'] || d['Setup'] || 0);
    document.getElementById('edit-mod').value = (existingOverride && existingOverride.personnel_ratio_override) ? existingOverride.personnel_ratio_override : (d.Ratio_MOD || d.Ratio_Personas_Maquina || 1.0);

    const centers = [...new Set(currentData.detail.map(item => item.Centro))].sort();
    document.getElementById('edit-new-centro').innerHTML = centers.map(c => `<option value="${c}" ${c == centro ? 'selected' : ''}>${c}</option>`).join('');
    document.getElementById('edit-modal').style.display = 'flex';
}

async function renderManageList() {
    // Refrescar la lista de escenarios desde el servidor antes de renderizar
    await loadScenarios();
    const container = document.getElementById('manage-list-container');
    if (!scenarios || scenarios.length === 0) {
        container.innerHTML = '<p class="empty-state" style="padding: 2rem; text-align: center; opacity: 0.6;">No hay escenarios guardados.</p>';
        return;
    }
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

window.loadAndClose = async (id) => {
    document.getElementById('manage-modal').style.display = 'none';
    await loadSimulation(id);
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
            idA: scA,
            idB: scB,
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
let currentDrillDownCenter = null;

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
            <div style="display: flex; gap: 0.5rem;">
                <button id="btn-download-compare-pdf" class="action-btn small" onclick="downloadComparePDF()" style="background: rgba(227,6,19,0.1); color: var(--rpk-red); border: 1px solid var(--rpk-red); font-size: 0.75rem;">📥 Informe PDF</button>
                <button id="btn-exit-compare" class="action-btn small" onclick="attemptExitComparison()" style="background:transparent; color:var(--text-muted); border:1px solid var(--border-color); font-size:0.75rem;">✕ Salir</button>
            </div>
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
                <div class="panel-title" style="margin-right:1rem">Filtros:</div>
                <div id="compare-center-dropdown" class="custom-dropdown">
                    <div class="dropdown-btn" onclick="toggleCompareDropdown()">
                        <span id="compare-dropdown-text">-- Top 15 Centros --</span>
                        <span class="arrow">▼</span>
                    </div>
                    <div id="compare-center-options" class="dropdown-content"></div>
                </div>
                <button onclick="resetCompareFilter()" class="action-btn secondary" style="margin-left:10px">Restablecer Ranking</button>
            </div>

            <!-- Row 3: Impact Analysis -->
            <div class="rec-bar" id="impact-bar" style="margin-bottom: 5px;"></div>

            <!-- Row 4: Chart + Drill-down container -->
            <div class="compare-body" id="compare-body">
                <div class="chart-panel dash-card" style="height: 400px; padding: 1.5rem;">
                    <div class="panel-title" id="compare-chart-title" style="margin-bottom:1rem">Cargando gráfica...</div>
                    <div class="chart-wrap" style="flex: 1; height:100%"><canvas id="compareChart"></canvas></div>
                </div>
                <!-- Drill-down se insertará debajo via JS -->
            </div>
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

function toggleCompareDropdown() {
    document.getElementById("compare-center-options").classList.toggle("show");
}

function populateCompareFilters() {
    if (!comparisonData?.dataB) return;
    const sB = comparisonData.dataB.summary || [];
    const allCenters = sB.map(s => String(s.Centro)).sort();

    const list = document.getElementById('compare-center-options');
    if (!list) return;

    list.innerHTML = '';
    allCenters.forEach(c => {
        const isChecked = comparisonSelectedCenters.includes(c);
        const label = document.createElement('label');
        label.className = 'checkbox-item';
        label.innerHTML = `<input type="checkbox" value="${c}" ${isChecked ? 'checked' : ''}><span>${c}</span>`;
        list.appendChild(label);
    });

    const checkboxes = list.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', onCompareFilterChange);
    });

    updateCompareDropdownText();
}

function updateCompareDropdownText() {
    const textSpan = document.getElementById('compare-dropdown-text');
    if (comparisonSelectedCenters.length === 0) {
        textSpan.innerText = '-- Top 15 Centros --';
    } else {
        textSpan.innerText = `${comparisonSelectedCenters.length} centro(s) seleccionado(s)`;
    }
}

function onCompareFilterChange() {
    const list = document.getElementById('compare-center-options');
    const checked = Array.from(list.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
    comparisonSelectedCenters = checked;
    updateCompareDropdownText();
    renderCompareChart();
}

function resetCompareFilter() {
    comparisonSelectedCenters = [];
    populateCompareFilters(); // will re-render unchecked checkboxes and text
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
        targetCenters = [...allCenters].sort((a, b) => {
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
                        if (comparisonViewMetric === 'Saturacion') {
                            if (v > 85) return '#ff4d4d'; // Rojo
                            if (v > 70) return '#f5a623'; // Amarillo
                            return '#4cd137'; // Verde
                        }
                        return 'rgba(227,6,19,0.85)';
                    }),
                    borderColor: valsB.map(v => {
                        if (comparisonViewMetric === 'Saturacion') {
                            if (v > 85) return '#d00000';
                            if (v > 70) return '#e67e22';
                            return '#44bd32';
                        }
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
            plugins: {
                legend: { display: true, position: 'top', labels: { color: '#a0a0a0', boxWidth: 12 } }
            },
            onClick: (e, items) => {
                const elements = compareChartInstance.getElementsAtEventForMode(e, 'index', { intersect: false }, true);
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    openDrillDown(labels[idx]);
                }
            },
            onHover: (e, elements, chart) => {
                const points = chart.getElementsAtEventForMode(e, 'index', { intersect: false }, true);
                e.native.target.style.cursor = points.length > 0 ? 'pointer' : 'default';
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
            }
        }
    });
}

function openDrillDown(centro) {
    currentDrillDownCenter = centro;
    const dB = comparisonData.dataB.detail || [];
    const artsB = dB.filter(d => String(d.Centro) === String(centro));

    const body = document.getElementById('compare-body');
    if (!body) return;

    // Eliminar el actual si existe
    const existing = document.querySelector('.drilldown-panel');
    if (existing) existing.remove();

    const turnosVal = centerConfigs[centro] || 'auto';

    const panel = document.createElement('div');
    panel.className = 'drilldown-panel dash-card table-card';
    panel.innerHTML = `
        <div class="card-header" style="padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <h3 style="margin:0; font-size:1.1rem; color:#fff">Detalle Centro: <span style="color:var(--rpk-red)">${centro}</span></h3>
                <div style="display:flex; align-items:center; gap:8px; margin-left:1.5rem; background:rgba(255,255,255,0.03); padding:4px 10px; border-radius:8px; border:1px solid var(--border-color);">
                    <label style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px">Turnos Centro:</label>
                    <select class="dark-input" style="padding: 2px 6px; font-size:0.8rem; min-width:120px; border:none; background:transparent;" onchange="applyCompareCenterEdit('${centro}', this.value)">
                        <option value="auto" ${turnosVal === 'auto' ? 'selected' : ''}>(Auto)</option>
                        <option value="8" ${turnosVal === 8 ? 'selected' : ''}>1 (8h)</option>
                        <option value="16" ${turnosVal === 16 ? 'selected' : ''}>2 (16h)</option>
                        <option value="24" ${turnosVal === 24 ? 'selected' : ''}>3 (24h)</option>
                    </select>
                </div>
            </div>
            <button class="action-btn small secondary" onclick="closeDrillDown()">✕ Cerrar Detalle</button>
        </div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Articulo</th>
                        <th class="text-right">Demanda</th>
                        <th class="text-right">PPM</th>
                        <th class="text-right">OEE (%)</th>
                        <th class="text-center">Saturación</th>
                        <th class="text-right">Ratio MOD</th>
                        <th class="text-center">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    ${artsB.map(r => {
        const sat = (r.Saturacion * 100).toFixed(1);
        const satClass = sat > 85 ? 'pill-high' : (sat > 70 ? 'pill-mid' : 'pill-low');

        const demanda = r.Demanda_Neta || r.Demanda || r['Volumen anual'] || 0;
        const ppm = r.PPM || r['Piezas por minuto'] || 0;

        return `
                            <tr>
                                <td><strong>${r.Articulo}</strong></td>
                                <td class="text-right">${Math.round(demanda).toLocaleString()}</td>
                                <td class="text-right">${Math.round(ppm)}</td>
                                <td class="text-right">${(r['%OEE'] * 100).toFixed(1)}%</td>
                                <td class="text-center">
                                    <span class="saturation-pill ${satClass}">${sat}%</span>
                                </td>
                                <td class="text-right">${(r.Ratio_Personas_Maquina || 1.0).toFixed(1)}</td>
                                <td class="text-center">
                                    <button class="secondary-btn" 
                                        style="padding: 0.3rem 0.6rem; font-size: 0.7rem;"
                                        onclick="openEditModal('${r.Articulo}', '${centro}')">Ajustar</button>
                                </td>
                            </tr>
                        `;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
    body.appendChild(panel);
    if (compareChartInstance) compareChartInstance.resize();

    // Auto-scroll suave al detalle
    setTimeout(() => {
        panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
}

function closeDrillDown() {
    const existing = document.querySelector('.drilldown-panel');
    if (existing) existing.remove();
    if (compareChartInstance) compareChartInstance.resize();
}

async function applyCompareCenterEdit(centro, value) {
    if (value === 'auto') delete centerConfigs[centro];
    else centerConfigs[centro] = parseInt(value, 10);
    await triggerCompareRecalculation();
    openDrillDown(centro);
}

async function applyCompareEdit(articulo, field, value) {
    // Find existing override or create one with correct lowercase keys
    let override = localOverrides.find(o => String(o.articulo) === String(articulo));
    if (!override) {
        // Find the centro from dataB detail
        const detailItem = comparisonData.dataB.detail.find(d => String(d.Articulo) === String(articulo));
        const centro = detailItem?.Centro || '';
        override = { articulo: String(articulo), centro: String(centro) };
        localOverrides.push(override);
    }

    let floatVal = parseFloat(value);
    // Map display field names to override field names
    switch (field) {
        case 'OEE': override.oee_override = floatVal / 100.0; break;
        case 'PPM': override.ppm_override = floatVal; break;
        case 'Demanda': override.demanda_override = floatVal; break;
        case 'Setup': override.setup_time_override = floatVal; break;
        case 'MOD': override.personnel_ratio_override = floatVal; break;
        default: override[field] = floatVal;
    }

    const centro = override.centro;
    await triggerCompareRecalculation();
    if (centro) openDrillDown(centro);
}

async function triggerCompareRecalculation() {
    setLoading(true);
    compareHasEdits = true;
    try {
        const cleanOverrides = localOverrides.map(o => ({
            articulo: String(o.articulo),
            centro: String(o.centro),
            oee_override: o.oee_override,
            ppm_override: o.ppm_override,
            demanda_override: o.demanda_override,
            new_centro: o.new_centro,
            horas_turno_override: o.horas_turno_override,
            setup_time_override: o.setup_time_override,
            personnel_ratio_override: o.personnel_ratio_override
        }));

        const payload = {
            base_scenario_id: comparisonData.idB,
            overrides: cleanOverrides,
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
        if (currentDrillDownCenter) openDrillDown(currentDrillDownCenter);
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

    // Centros modificados: Consideramos cualquier override local O una diferencia de saturación > 0.1%
    const modifiedCenters = [];
    const centersInOverrides = new Set(localOverrides.map(o => o.centro));

    sB.forEach(sbItem => {
        const saItem = sA.find(s => String(s.Centro) === String(sbItem.Centro));
        const hasOverride = centersInOverrides.has(String(sbItem.Centro));
        const hasSatDiff = saItem && Math.abs(sbItem.Saturacion - saItem.Saturacion) > 0.001;

        if (hasOverride || hasSatDiff) {
            modifiedCenters.push(sbItem.Centro);
        }
    });

    const bar = document.getElementById('impact-bar');
    if (!bar) return;
    bar.innerHTML = `
        <div class="rec-section" style="cursor:pointer" title="Ver estos centros en el gráfico">
            <div class="rec-title">Cambios Identificados</div>
            <div class="rec-item">
                <div class="rec-dot ${modifiedCenters.length > 0 ? 'yellow' : 'flat'}"></div>
                <div>${modifiedCenters.length} centros con variaciones respecto a ${comparisonData.nameA}.</div>
            </div>
            ${modifiedCenters.length > 0 ? `<div style="font-size:0.7rem; color:var(--text-muted); margin-left:12px;">${modifiedCenters.slice(0, 8).join(', ')}${modifiedCenters.length > 8 ? '...' : ''}</div>` : ''}
        </div>
        <div class="rec-section" style="cursor:pointer" title="Ver centros críticos en el gráfico">
            <div class="rec-title">Nivel de Criticidad (>85%)</div>
            <div class="rec-item">
                <div class="rec-dot ${critB > critA ? 'red' : critB < critA ? 'green' : 'yellow'}"></div>
                <div>${critB} centros críticos críticos. ${critB > critA ? `(+ ${critB - critA} vs ${comparisonData.nameA})` : critB < critA ? `(- ${critA - critB} vs ${comparisonData.nameA})` : ''}</div>
            </div>
        </div>
        <div class="rec-section" style="cursor:pointer" title="Ver impacto de personal en el gráfico">
            <div class="rec-title">Previsión de RRHH</div>
            <div class="rec-item">
                <div class="rec-dot ${Math.abs(deltaFTE) > 5 ? 'red' : Math.abs(deltaFTE) < 1 ? 'green' : 'yellow'}"></div>
                <div>Necesidad calculada: ${deltaFTE > 0 ? '+' : ''}${deltaFTE.toFixed(1)} FTE vs ${comparisonData.nameA}.</div>
            </div>
        </div>
    `;

    // Interactividad
    const sections = bar.querySelectorAll('.rec-section');
    sections[0].onclick = () => {
        comparisonSelectedCenters = modifiedCenters;
        renderCompareChart();
    };
    sections[1].onclick = () => {
        comparisonSelectedCenters = sB.filter(s => s.Saturacion > 0.85).map(s => String(s.Centro));
        renderCompareChart();
    };
    sections[2].onclick = () => {
        // Centros con mayor variacion de FTE
        comparisonSelectedCenters = sB.filter(sb => {
            const sa = sA.find(x => String(x.Centro) === String(sb.Centro));
            const delta = Math.abs((sb.Horas_Carga || 0) - (sa ? sa.Horas_Carga : 0));
            return delta > 40; // Mas de una semana de trabajo de diferencia
        }).map(s => String(s.Centro));
        renderCompareChart();
    };
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
    const meta = comparisonData.dataB.meta || {};
    const existingOverrides = meta.applied_overrides || [];

    // Merge existing scenario overrides with new session overrides
    // Session overrides take precedence for the same articulo & centro
    const mergedOverridesMap = new Map();

    // 1. Add existing overrides
    existingOverrides.forEach(ov => {
        if (!ov.articulo) return;
        const key = `${ov.articulo}_${ov.centro || ''}`;
        mergedOverridesMap.set(key, { ...ov });
    });

    // 2. Apply session overrides (localOverrides) on top
    localOverrides.forEach(ov => {
        if (!ov.articulo) return;
        // In comparison mode, 'centro' is the original center we are overriding
        const key = `${ov.articulo}_${ov.centro || ''}`;
        const existing = mergedOverridesMap.get(key) || {};
        // Merge changed fields
        const merged = { ...existing };
        merged.articulo = ov.articulo;
        merged.centro = ov.centro;
        if (ov.oee_override !== null && ov.oee_override !== undefined) merged.oee_override = ov.oee_override;
        if (ov.ppm_override !== null && ov.ppm_override !== undefined) merged.ppm_override = ov.ppm_override;
        if (ov.demanda_override !== null && ov.demanda_override !== undefined) merged.demanda_override = ov.demanda_override;
        if (ov.new_centro !== null && ov.new_centro !== undefined) merged.new_centro = ov.new_centro;
        if (ov.horas_turno_override !== null && ov.horas_turno_override !== undefined) merged.horas_turno_override = ov.horas_turno_override;
        if (ov.personnel_ratio_override !== null && ov.personnel_ratio_override !== undefined) merged.personnel_ratio_override = ov.personnel_ratio_override;
        if (ov.setup_time_override !== null && ov.setup_time_override !== undefined) merged.setup_time_override = ov.setup_time_override;
        mergedOverridesMap.set(key, merged);
    });

    const finalOverridesList = Array.from(mergedOverridesMap.values());

    const buildPayload = (name) => ({
        name,
        dias_laborales: meta.dias_laborales || parseInt(document.getElementById('work-days').value) || 238,
        horas_turno_global: meta.horas_turno_global || parseInt(document.getElementById('work-shifts').value) || 16,
        center_configs: centerConfigs,
        overrides: cleanOverridesForSave(finalOverridesList)
    });

    if (action === 'overwrite') {
        if (comparisonData.idB === 'base' || comparisonData.idB === 'actual') {
            alert('Atención: NO ES POSIBLE sobreescribir los escenarios fijos (Base/Actual). Guardalo como nuevo.');
            return;
        }
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/scenarios/${comparisonData.idB}/full`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(buildPayload(comparisonData.nameB))
            });
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error'); }
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
        try {
            const res = await fetch(`${API_BASE}/scenarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(buildPayload(name))
            });
            if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Error'); }
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
    await loadScenarios();
    exitComparisonMode();
}

function exitComparisonMode() {
    // Full state reset
    isComparisonMode = false;
    comparisonData = null;
    comparisonSelectedCenters = [];
    compareHasEdits = false;
    currentDrillDownCenter = null;

    document.body.classList.remove('compare-mode');
    document.getElementById('comparison-controls').style.display = 'none';
    const rightPanel = document.querySelector('.right-panel');
    if (rightPanel) rightPanel.style.display = '';

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
    if (tableCard) tableCard.style.display = '';

    // Remove any leftover drilldown panels
    document.querySelectorAll('.drilldown-panel').forEach(p => p.remove());

    if (currentScenarioId) loadSimulation(currentScenarioId);
    else loadSimulation('base');
}

async function downloadComparePDF() {
    if (!comparisonData?.dataA || !comparisonData?.dataB) return;
    try {
        setLoading(true);
        const sA = comparisonData.dataA.summary || [];
        const sB = comparisonData.dataB.summary || [];
        const dA = comparisonData.dataA.detail || [];
        const dB = comparisonData.dataB.detail || [];
        const daysA = comparisonData.dataA.meta?.dias_laborales || 238;
        const daysB = comparisonData.dataB.meta?.dias_laborales || 238;
        const paramShifts = parseInt(document.getElementById('work-shifts').value) || 16;

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
            { name: 'Saturación Media', valA: avgSatA, valB: avgSatB, unit: '%', higher_is_better: false },
            { name: 'OEE Global Medio', valA: oeeA, valB: oeeB, unit: '%', higher_is_better: true },
            { name: 'Carga Máquina Total', valA: hoursA, valB: hoursB, unit: 'h', higher_is_better: false },
            { name: 'Necesidad Personal (FTE)', valA: fteA, valB: fteB, unit: '', higher_is_better: false }
        ];

        const centros_impacto = [];
        sB.forEach(sb => {
            const sa = sA.find(x => String(x.Centro) === String(sb.Centro));
            if (sa && Math.abs(sb.Saturacion - sa.Saturacion) > 0.01) {
                centros_impacto.push({
                    centro: String(sb.Centro),
                    sat_a: sa.Saturacion * 100,
                    sat_b: sb.Saturacion * 100,
                    mod_a: sa.Ratio_Personas_Maquina || 1,
                    mod_b: sb.Ratio_Personas_Maquina || 1
                });
            }
        });

        centros_impacto.sort((a, b) => Math.abs(b.sat_b - b.sat_a) - Math.abs(a.sat_b - a.sat_a));

        const cambios_activos = localOverrides.map(ov => {
            let details = [];
            if (ov.demanda_override) details.push(`Demanda: ${ov.demanda_override}`);
            if (ov.ppm_override) details.push(`PPM: ${ov.ppm_override}`);
            if (ov.oee_override) details.push(`OEE: ${(ov.oee_override * 100).toFixed(1)}%`);
            if (ov.setup_time_override) details.push(`Setup: ${ov.setup_time_override}h`);
            if (ov.horas_turno_override) details.push(`Turnos: ${ov.horas_turno_override}h`);
            if (ov.personnel_ratio_override) details.push(`MOD: ${ov.personnel_ratio_override}`);
            return {
                tipo: `Ctro ${ov.centro} - Art. ${ov.articulo}`,
                detalle: details.join(" | ") || "Sobreescribir activo",
                a: "Base/Modelo A",
                b: "Ajuste Directo"
            };
        });

        const payload = {
            escenario_a: comparisonData.nameA,
            escenario_b: comparisonData.nameB,
            kpis: kpis,
            centros_impacto: centros_impacto.slice(0, 15),
            cambios_activos: cambios_activos,
            dias_laborales: daysB,
            turnos: paramShifts
        };

        const res = await fetch(`${API_BASE}/reports/comparativa-pdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Error al generar PDF');

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeName = comparisonData.nameB.replace(/ /g, '_');
        a.download = `Informe_Impacto_vs_${safeName}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

    } catch (e) {
        console.error(e);
        alert('Error descargando el informe: ' + e.message);
    } finally {
        setLoading(false);
    }
}

async function downloadScenarioPDF() {
    if (!currentData || !currentData.summary) return;
    try {
        setLoading(true);
        const s = currentData.summary || [];
        const d = currentData.detail || [];
        const days = currentData.meta?.dias_laborales || 238;
        const paramShifts = parseInt(document.getElementById('work-shifts').value) || 16;
        const name = document.getElementById('current-scenario-name').textContent || currentScenarioId;

        const avgSat = s.length ? (s.reduce((a, st) => a + (st.Saturacion || 0), 0) / s.length) * 100 : 0;
        const oee = d.length ? (d.reduce((a, dtl) => a + (dtl['%OEE'] || 0), 0) / d.length) * 100 : 0;
        const hours = d.reduce((a, dtl) => a + (dtl['Horas_Totales'] || 0), 0);
        const hh = d.reduce((a, dtl) => a + (dtl.Horas_Hombre || 0), 0);
        const fte = hh / (days * 8);

        const kpis = [
            { name: 'Saturación Media', value: avgSat, unit: '%' },
            { name: 'OEE Global Medio', value: oee, unit: '%' },
            { name: 'Carga Máquina Total', value: hours, unit: 'h' },
            { name: 'Necesidad Personal (FTE)', value: fte, unit: '' }
        ];

        const centros = s.map(st => ({
            centro: String(st.Centro),
            saturacion: st.Saturacion * 100,
            mod: st.Ratio_Personas_Maquina || 1
        })).sort((a, b) => b.saturacion - a.saturacion).slice(0, 15);

        const cambios_activos = localOverrides.map(ov => {
            let details = [];
            if (ov.demanda_override) details.push(`Demanda: ${ov.demanda_override}`);
            if (ov.ppm_override) details.push(`PPM: ${ov.ppm_override}`);
            if (ov.oee_override) details.push(`OEE: ${(ov.oee_override * 100).toFixed(1)}%`);
            if (ov.setup_time_override) details.push(`Setup: ${ov.setup_time_override}h`);
            if (ov.horas_turno_override) details.push(`Turnos: ${ov.horas_turno_override}h`);
            if (ov.personnel_ratio_override) details.push(`MOD: ${ov.personnel_ratio_override}`);
            return {
                tipo: `Ctro ${ov.centro} - Art. ${ov.articulo}`,
                detalle: details.join(" | ") || "Sobreescribir manual"
            };
        });

        const payload = {
            escenario_nombre: name,
            kpis: kpis,
            centros: centros,
            cambios_activos: cambios_activos,
            dias_laborales: days,
            turnos: paramShifts
        };

        const res = await fetch(`${API_BASE}/reports/escenario-pdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('Error al generar PDF individual');

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeName = name.replace(/ /g, '_');
        a.download = `Simulacion_Actual_${safeName}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

    } catch (e) {
        console.error(e);
        alert('Error descargando el informe individual: ' + e.message);
    } finally {
        setLoading(false);
    }
}

// ============================================================
// GESTIÓN DE ARTÍCULOS (CRUD - Persistencia en Excel Maestro)
// ============================================================

function openNewArticleModal() {
    // Populate centro dropdown with existing centers
    const centers = currentData?.detail
        ? [...new Set(currentData.detail.map(d => d.Centro))].sort()
        : [];
    const centroSelect = document.getElementById('new-art-centro');
    centroSelect.innerHTML = centers.map(c => `<option value="${c}">${c}</option>`).join('');

    // Reset form
    document.getElementById('new-art-code').value = '';
    document.getElementById('new-art-demanda').value = '0';
    document.getElementById('new-art-ppm').value = '0';
    document.getElementById('new-art-oee').value = '75';
    document.getElementById('new-art-dias').value = '238';

    document.getElementById('new-article-modal').style.display = 'flex';
}

async function submitNewArticle(e) {
    e.preventDefault();

    const articulo = document.getElementById('new-art-code').value.trim();
    const centro = document.getElementById('new-art-centro').value;
    const volumen_anual = parseFloat(document.getElementById('new-art-demanda').value) || 0;
    const piezas_por_minuto = parseFloat(document.getElementById('new-art-ppm').value) || 0;
    const oee = (parseFloat(document.getElementById('new-art-oee').value) || 75) / 100;
    const dias_laborales = parseFloat(document.getElementById('new-art-dias').value) || 238;

    if (!articulo) {
        alert('El código de artículo es obligatorio.');
        return;
    }

    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/articulos/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ articulo, centro, volumen_anual, piezas_por_minuto, oee, dias_laborales })
        });

        const result = await res.json();

        if (!res.ok) {
            alert('Error: ' + (result.detail || result.message || 'Error desconocido'));
            return;
        }

        if (result.status === 'warning') {
            alert('Aviso: ' + result.message);
        }

        document.getElementById('new-article-modal').style.display = 'none';

        // Reload simulation to reflect the new article
        localOverrides = [];
        await loadSimulation(currentScenarioId);

    } catch (error) {
        console.error('Error creando artículo:', error);
        alert('Error de conexión al crear el artículo.');
    } finally {
        setLoading(false);
    }
}

let pendingDeleteArticulo = null;
let pendingDeleteCentro = null;

function openDeleteConfirmModal(articulo, centro) {
    pendingDeleteArticulo = articulo;
    pendingDeleteCentro = centro;
    document.getElementById('delete-art-name').textContent = articulo;
    document.getElementById('delete-art-centro').textContent = centro;
    document.getElementById('delete-confirm-modal').style.display = 'flex';
}

async function confirmDeleteArticle() {
    if (!pendingDeleteArticulo || !pendingDeleteCentro) return;

    setLoading(true);
    try {
        const deleteUrl = `${API_BASE}/articulos/${encodeURIComponent(pendingDeleteArticulo)}?centro=${encodeURIComponent(pendingDeleteCentro)}`;
        const res = await fetch(deleteUrl, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await res.json();

        if (!res.ok) {
            alert('Error: ' + (result.detail || result.message || 'Error desconocido'));
            return;
        }

        if (result.status === 'warning') {
            alert('Aviso: ' + result.message);
        }

        document.getElementById('delete-confirm-modal').style.display = 'none';

        // Remove any local overrides for this article
        localOverrides = localOverrides.filter(
            o => !(String(o.articulo) === String(pendingDeleteArticulo) && String(o.centro) === String(pendingDeleteCentro))
        );

        // Reload simulation
        await loadSimulation(currentScenarioId);

    } catch (error) {
        console.error('Error eliminando artículo:', error);
        alert('Error de conexión al eliminar el artículo.');
    } finally {
        setLoading(false);
        pendingDeleteArticulo = null;
        pendingDeleteCentro = null;
    }
}

// Wire up the new-article form and delete-confirm button
document.addEventListener('DOMContentLoaded', () => {
    const newArtForm = document.getElementById('new-article-form');
    if (newArtForm) {
        newArtForm.addEventListener('submit', submitNewArticle);
    }
    const deleteBtn = document.getElementById('btn-confirm-delete');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', confirmDeleteArticle);
    }
});
