const API_BASE = '/api';
let currentData = null;
let chartInstance = null;
let scenarios = [];
let currentScenarioId = 'base';
let selectedCenters = [];
let localOverrides = [];
let centerConfigs = {}; // Estructura: { "CentroID": { shifts: 8|16|24 } }
let updateTimeout;

let isComparisonMode = false;
let comparisonData = null;

function debounce(func, wait) {
    return function (...args) {
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function setLoading(isLoading) {
    const main = document.querySelector('main');
    const filterInputs = document.querySelectorAll('#filters input, #filters select, #filters button');

    if (isLoading) {
        main.classList.add('loading');
        filterInputs.forEach(el => el.disabled = true);
    } else {
        main.classList.remove('loading');
        filterInputs.forEach(el => el.disabled = false);
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

    // Al cargar un escenario específico (no 'base'), limpiamos los cambios locales 
    // para ver exactamente lo que hay guardado en la DB.
    if (scenarioId !== 'base') {
        localOverrides = [];
        centerConfigs = {};
    }

    const url = scenarioId === 'base'
        ? `${API_BASE}/simulate/base?dias_laborales=${days}&horas_turno=${shifts}`
        : `${API_BASE}/simulate/${scenarioId}?dias_laborales=${days}&horas_turno=${shifts}`;

    document.getElementById('current-scenario-name').innerText = 'Cargando datos...';
    setLoading(true);

    try {
        console.log(`Cargando simulación: ${url}`);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        currentData = await response.json();

        if (!currentData || !currentData.summary || !currentData.detail) {
            throw new Error("Formato de datos inválido del servidor");
        }

        // Actualizamos el ID del escenario cargado ANTES de renderizar
        currentScenarioId = scenarioId;

        const sName = scenarioId === 'base' ? 'Escenario Base' : scenarios.find(s => s.id == scenarioId)?.name || 'Escenario';
        document.getElementById('current-scenario-name').innerText = sName;

        // Si es un escenario guardado, sincronizar la UI con sus parámetros globales
        if (scenarioId !== 'base' && currentData.meta) {
            document.getElementById('work-days').value = currentData.meta.dias_laborales || 238;
            document.getElementById('work-shifts').value = currentData.meta.horas_turno_global || 16;
            centerConfigs = currentData.meta.center_configs || {};
            // Al cargar un escenario, sus overrides ya vienen aplicados en data.detail desde el backend,
            // pero si queremos que aparezcan en el panel de la izquierda, tendríamos que 
            // mapear currentData.meta.overrides (si existiera) a localOverrides.
            // Por ahora, mantenemos la lógica de que CARGAR limpia la vista previa local.
        }

        // Cargar histórico siempre si no es base
        const historyList = document.getElementById('history-list');
        if (scenarioId !== 'base') {
            loadScenarioHistory(scenarioId);
        } else if (historyList) {
            historyList.innerHTML = '<p class="empty-msg">No hay histórico para Base</p>';
        }

        renderLocalOverrides(); // Refrescar panel de cambios
        populateWorkCenters();
        updateNavItemActive(scenarioId);
        updateUI();
    } catch (error) {
        console.error('Error loading simulation:', error);
        document.getElementById('current-scenario-name').innerText = 'Error de conexión';
        alert("No se pudo conectar con el servidor.");
    } finally {
        setLoading(false);
    }
}

function updateNavItemActive(id) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    if (id === 'base') {
        document.getElementById('btn-base')?.classList.add('active');
    } else {
        // Para escenarios guardados, podemos marcar 'Gestionar' como activo o nada
        document.getElementById('btn-manage')?.classList.add('active');
    }
}

function updateUI() {
    if (isComparisonMode) {
        renderComparisonDashboard();
        return;
    }

    if (!currentData || !currentData.summary || currentData.summary.length === 0) {
        console.warn("No hay datos para mostrar en la simulación actual.");
        document.getElementById('summary-stats').innerHTML = '<div class="stat-item">No hay datos cargados</div>';
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
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const centro = summary[context.dataIndex].Centro;
                            const config = centerConfigs[centro] || { shifts: document.getElementById('work-shifts').value };
                            return `Sat: ${context.raw}% (Config: ${config.shifts}h)`;
                        }
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const centerName = summary[index].Centro;
                    handleCenterClick(centerName);
                }
            }
        }
    });
}

function handleCenterClick(centerName) {
    const select = document.getElementById('work-center');
    Array.from(select.options).forEach(opt => opt.selected = (opt.value == centerName));
    selectedCenters = [centerName];
    updateUI();
    document.getElementById('table-section').scrollIntoView({ behavior: 'smooth' });
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
            <div class="stat-val">${summary.length}</div>
            <div class="stat-label">Centros ${isFiltered ? 'Filtrados' : 'Totales'}</div>
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
        const days = document.getElementById('work-days').value || 238;

        // Prioridad de horas de turno: Override Individual > Config por Centro > Global
        const globalShifts = document.getElementById('work-shifts').value || 16;
        const centerSpecificShift = centerConfigs[d.Centro]?.shifts;
        const shifts = d.horas_turno_override || centerSpecificShift || globalShifts;

        const hours = (d.Saturacion * shifts * days).toFixed(1);

        return `
            <tr>
                <td><strong>${d.Articulo}</strong></td>
                <td class="text-center">
                    <div style="display:flex; flex-direction:column; align-items:center;">
                        <span class="center-tag">${d.Centro}</span>
                        <span style="font-size:0.6rem; color:var(--text-dim); margin-top:2px;">${shifts}h</span>
                    </div>
                </td>
                <td class="text-right">${d['Volumen anual'].toLocaleString()}</td>
                <td class="text-right">${Math.round(d['Piezas por minuto'])}</td>
                <td class="text-right">${(d['%OEE'] * 100).toFixed(1)}%</td>
                <td class="text-center">
                    <span class="saturation-pill ${satClass}">${sat}%</span>
                    <span class="hours-label" style="font-size: 0.7rem; color: var(--text-dim); display: block; margin-top: 2px;">${hours}h</span>
                </td>
                <td class="text-right"><div class="impact-bar-container"><div class="impact-bar" style="width: ${impact}%"></div><span>${impact}%</span></div></td>
                <td class="text-center">
                    <button class="btn btn-secondary btn-simular" 
                        style="padding: 0.3rem 0.6rem; font-size: 0.7rem;"
                        data-articulo="${d.Articulo}" 
                        data-centro="${d.Centro}">Ajustar</button>
                </td>
            </tr>
        `;
    }).join('');
}

function populateWorkCenters() {
    const select = document.getElementById('work-center');
    if (!select || !currentData.detail) return;

    const centers = [...new Set(currentData.detail.map(d => d.Centro))].sort();
    const options = [`<option value="all" ${selectedCenters.includes('all') ? 'selected' : ''}>-- Todos los Centros --</option>`];
    centers.forEach(c => {
        const isSelected = selectedCenters.includes(String(c));
        options.push(`<option value="${c}" ${isSelected ? 'selected' : ''}>${c}</option>`);
    });

    select.innerHTML = options.join('');
    renderCenterConfigsLink();
}

function renderCenterConfigsLink() {
    let configLink = document.getElementById('btn-config-shifts-centers');
    if (!configLink) {
        configLink = document.createElement('button');
        configLink.id = 'btn-config-shifts-centers';
        configLink.className = 'secondary-btn';
        configLink.style.marginLeft = '10px';
        configLink.innerHTML = '⚙️ Config. Turnos Centros';
        configLink.onclick = openCenterConfigModal;
        const actions = document.querySelector('.filter-actions');
        if (actions) actions.appendChild(configLink);
    }
}

function openCenterConfigModal() {
    const centers = [...new Set(currentData.detail.map(d => d.Centro))].sort();
    const globalShifts = document.getElementById('work-shifts').value;

    const modalHtml = `
        <div id="center-config-modal" class="modal" style="display:block">
            <div class="modal-content" style="width: 600px;">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                <h2>Configuración de Turnos por Centro</h2>
                <p style="font-size: 0.8rem; color: var(--text-dim); margin-bottom: 1rem;">
                    Define los turnos específicos para cada centro.
                </p>
                <div style="max-height: 400px; overflow-y: auto; margin-bottom: 1rem;">
                    <table style="width:100%">
                        <thead>
                            <tr>
                                <th style="text-align:left">Centro</th>
                                <th style="text-align:left">Turnos Actuales</th>
                                <th style="text-align:left">Cambiar a</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${centers.map(c => {
        const current = centerConfigs[c] ? centerConfigs[c].shifts : globalShifts;
        return `
                                <tr>
                                    <td><strong>${c}</strong></td>
                                    <td><span class="pill-low">${current}h</span></td>
                                    <td>
                                        <select onchange="window.updateCenterShiftConfig('${c}', this.value)" style="padding:2px 5px; font-size:0.8rem;">
                                            <option value="" ${!centerConfigs[c] ? 'selected' : ''}>Global (${globalShifts}h)</option>
                                            <option value="8" ${centerConfigs[c]?.shifts == 8 ? 'selected' : ''}>1 Turno (8h)</option>
                                            <option value="16" ${centerConfigs[c]?.shifts == 16 ? 'selected' : ''}>2 Turnos (16h)</option>
                                            <option value="24" ${centerConfigs[c]?.shifts == 24 ? 'selected' : ''}>3 Turnos (24h)</option>
                                        </select>
                                    </td>
                                </tr>`;
    }).join('')}
                        </tbody>
                    </table>
                </div>
                <div class="modal-actions">
                    <button class="primary-btn" onclick="window.applyCenterConfigs()">Aplicar y Recalcular</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

window.updateCenterShiftConfig = (center, value) => {
    if (!value) delete centerConfigs[center];
    else centerConfigs[center] = { shifts: parseInt(value) };
};

window.applyCenterConfigs = () => {
    const modal = document.getElementById('center-config-modal');
    if (modal) modal.remove();
    updatePreviewSimulation();
};

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
        renderLocalOverrides();
        loadSimulation('base');
    };

    document.getElementById('work-days').oninput = debounce(() => updatePreviewSimulation(), 500);

    document.getElementById('work-shifts').onchange = () => {
        // Al cambiar turnos globales, recalculamos todo
        updatePreviewSimulation();
    };

    document.getElementById('btn-apply-filter').onclick = () => {
        const select = document.getElementById('work-center');
        selectedCenters = Array.from(select.options).filter(o => o.selected).map(o => o.value);
        updateUI();
    };

    document.getElementById('btn-clear-filter').onclick = () => {
        const select = document.getElementById('work-center');
        Array.from(select.options).forEach(o => o.selected = false);
        selectedCenters = [];
        updateUI();
    };

    document.getElementById('table-search').oninput = () => updateUI();

    const liveUpdateSim = debounce(() => {
        const articulo = document.getElementById('edit-articulo').value;
        const centroBase = document.getElementById('edit-centro').value;
        const oee = parseFloat(document.getElementById('edit-oee').value) / 100 || 0;
        const ppm = parseFloat(document.getElementById('edit-ppm').value) || 0;
        const demanda = parseFloat(document.getElementById('edit-demanda').value) || 0;
        const new_centro = document.getElementById('edit-new-centro').value;
        const shifts = document.getElementById('edit-shifts').value;

        const currentItem = currentData?.detail.find(it => it.Articulo == articulo && (it.centro_original || it.Centro) == centroBase);

        const override = {
            articulo,
            centro: centroBase,
            centro_original: currentItem?.centro_original || centroBase,
            oee_override: oee,
            ppm_override: ppm,
            demanda_override: demanda,
            new_centro: new_centro,
            horas_turno_override: shifts ? parseInt(shifts) : null
        };

        const idx = localOverrides.findIndex(o => o.articulo == articulo && o.centro == centroBase);
        if (idx >= 0) localOverrides[idx] = override;
        else localOverrides.push(override);

        updatePreviewSimulation();
    }, 400);

    ['edit-oee', 'edit-ppm', 'edit-demanda', 'edit-new-centro', 'edit-shifts'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.oninput = liveUpdateSim;
    });

    const editForm = document.getElementById('edit-form');
    if (editForm) {
        editForm.onsubmit = (e) => {
            e.preventDefault();
            document.getElementById('edit-modal').style.display = 'none';
        };
    }

    document.getElementById('cancel-edit').onclick = () => {
        document.getElementById('edit-modal').style.display = 'none';
    };

    document.getElementById('btn-new').onclick = async () => {
        const days = parseInt(document.getElementById('work-days').value);
        const shifts = parseInt(document.getElementById('work-shifts').value);

        // Un cambio es válido si hay artículos simulados O los parámetros globales difieren de la base
        const hasGlobalChanges = days !== 238 || shifts !== 16 || Object.keys(centerConfigs).length > 0;
        const hasActiveChanges = localOverrides.length > 0;

        if (!hasGlobalChanges && !hasActiveChanges) {
            alert("No hay cambios para guardar. Modifica días, turnos o artículos.");
            return;
        }

        let name = "";
        let isUpdate = false;

        // Si tenemos un escenario cargado que no es el base, preguntamos si sobrescribir
        if (currentScenarioId && currentScenarioId !== 'base') {
            const currentName = scenarios.find(s => s.id == currentScenarioId)?.name || "Escenario Actual";
            const choice = confirm(`¿Deseas sobreescritos los cambios en "${currentName}" o crear un escenario NUEVO?\n\nAceptar = Sobrescribir "${currentName}"\nCancelar = Crear escenario NUEVO`);

            if (choice) {
                isUpdate = true;
                name = currentName;
            }
        }

        if (!isUpdate) {
            name = prompt("Nombre del nuevo escenario:");
            if (!name) return;
        }

        try {
            const url = isUpdate ? `${API_BASE}/scenarios/${currentScenarioId}/full` : `${API_BASE}/scenarios`;
            const method = isUpdate ? 'PUT' : 'POST';

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
                alert(isUpdate ? "Escenario actualizado correctamente" : "Nuevo escenario guardado!");
                await loadScenarios();
                const s = await res.json();
                loadSimulation(s.id);
            } else {
                const err = await res.json();
                alert("Error al guardar: " + (err.detail || "Error desconocido"));
            }
        } catch (e) {
            console.error(e);
            alert("Error de conexión al guardar");
        }
    };

    document.getElementById('btn-compare').onclick = () => document.getElementById('compare-modal').style.display = 'block';
    document.getElementById('run-compare').onclick = runCompare;
    document.getElementById('btn-exit-compare').onclick = exitComparisonMode;
    document.getElementById('btn-manage').onclick = () => { renderManageList(); document.getElementById('manage-modal').style.display = 'block'; };

    // Cerrar modales con la X
    const closeCompare = document.querySelector('#compare-modal .close');
    if (closeCompare) closeCompare.onclick = () => document.getElementById('compare-modal').style.display = 'none';

    const closeManage = document.querySelector('.close-manage');
    if (closeManage) closeManage.onclick = () => document.getElementById('manage-modal').style.display = 'none';

    // Cerrar al hacer click fuera del modal
    window.onclick = (event) => {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(m => {
            if (event.target == m) m.style.display = 'none';
        });
    };
}

async function updatePreviewSimulation() {
    const days = document.getElementById('work-days').value || 238;
    const shifts = document.getElementById('work-shifts').value || 16;
    document.getElementById('current-scenario-name').innerText = 'Simulando...';
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
        const data = await res.json();
        currentData = data;

        // Actualizar el nombre del escenario para reflejar cambios
        const nameEl = document.getElementById('current-scenario-name');
        if (currentScenarioId === 'base') {
            nameEl.innerText = 'Escenario Base (Modificado)';
        } else {
            const sc = scenarios.find(s => s.id == currentScenarioId);
            nameEl.innerText = `${sc?.name || 'Escenario'} (Modificado)`;
        }

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
    document.getElementById('edit-centro').value = d.centro_original || d.Centro;
    document.getElementById('display-articulo').innerText = articulo;
    document.getElementById('edit-oee').value = (d['%OEE'] * 100).toFixed(2);
    document.getElementById('edit-ppm').value = Math.round(d['Piezas por minuto']);
    document.getElementById('edit-demanda').value = Math.round(d['Volumen anual']);
    document.getElementById('edit-shifts').value = d.horas_turno_override || "";

    const centers = [...new Set(currentData.detail.map(item => item.Centro))].sort();
    document.getElementById('edit-new-centro').innerHTML = centers.map(c => `<option value="${c}" ${c == centro ? 'selected' : ''}>${c}</option>`).join('');
    document.getElementById('edit-modal').style.display = 'block';
}

function renderLocalOverrides() {
    const container = document.getElementById('overrides-list');
    if (!container) return; // Ya no existe en layout ejecutivo
    if (localOverrides.length === 0) {
        container.innerHTML = '<p class="empty-msg">No hay cambios aplicados</p>';
        return;
    }

    container.innerHTML = localOverrides.map((ov, idx) => {
        // Buscamos el dato en currentData
        // Intentamos encontrarlo por la identidad original del artículo
        const currentItem = currentData.detail.find(d => d.Articulo == ov.articulo && (d.centro_original || d.Centro) == (ov.centro_original || ov.centro));

        // El origen real es el centro_original que viene del Excel maestro
        const puntoOrigen = currentItem?.centro_original || ov.centro;
        const isCentroChanged = ov.new_centro && ov.new_centro !== puntoOrigen;
        const isOeeChanged = ov.oee_override !== undefined && Math.abs((currentItem?.['%OEE'] || 0) - ov.oee_override) > 0.001;
        const isPpmChanged = ov.ppm_override !== undefined && Math.round(currentItem?.['Piezas por minuto'] || 0) !== Math.round(ov.ppm_override);
        const isDemChanged = ov.demanda_override !== undefined && Math.round(currentItem?.['Volumen anual'] || 0) !== Math.round(ov.demanda_override);
        const isShiftChanged = ov.horas_turno_override && ov.horas_turno_override !== (currentItem?.horas_turno || 16);

        return `
            <div class="override-item">
                <button class="btn-remove-ov" onclick="removeOverride(${idx})" title="Eliminar">&times;</button>
                <h4>${ov.articulo}</h4>
                <div class="override-info">
                    ${isCentroChanged ? `<span>➜ Traslado: ${puntoOrigen} ➜ <b class="high-val">${ov.new_centro}</b></span>` : `<span>Centro: ${ov.new_centro || ov.centro}</span>`}
                    ${isOeeChanged ? `<span>OEE: ${(currentItem?.['%OEE'] * 100 || 0).toFixed(1)}% ➜ <b class="high-val">${(ov.oee_override * 100).toFixed(1)}%</b></span>` : `<span>OEE: ${(currentItem?.['%OEE'] * 100 || 0).toFixed(1)}%</span>`}
                    ${isPpmChanged ? `<span>PPM: ${Math.round(currentItem?.['Piezas por minuto'] || 0)} ➜ <b class="high-val">${Math.round(ov.ppm_override)}</b></span>` : `<span>PPM: ${Math.round(currentItem?.['Piezas por minuto'] || 0)}</span>`}
                    ${isDemChanged ? `<span>Demanda: ${Math.round(currentItem?.['Volumen anual'] || 0).toLocaleString()} ➜ <b class="high-val">${ov.demanda_override.toLocaleString()}</b></span>` : `<span>Demanda: ${Math.round(currentItem?.['Volumen anual'] || 0).toLocaleString()}</span>`}
                    ${isShiftChanged ? `<span>Turnos: ${currentItem?.horas_turno || 16}h ➜ <b class="high-val">${ov.horas_turno_override}h</b></span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function removeOverride(i) {
    localOverrides.splice(i, 1);
    if (localOverrides.length === 0) loadSimulation(currentScenarioId);
    else updatePreviewSimulation();
    renderLocalOverrides();
}

async function loadScenarioHistory(id) {
    try {
        const res = await fetch(`${API_BASE}/scenarios/${id}/history`);
        renderHistory(await res.json());
    } catch (e) { }
}

function renderHistory(history) {
    const container = document.getElementById('history-list');
    if (!container) return; // Ya no existe en layout ejecutivo
    if (!history || history.length === 0) {
        container.innerHTML = '<p class="empty-msg">Sin registros previos</p>';
        return;
    }

    container.innerHTML = history.map(h => {
        let detailsHtml = '';
        try {
            const overrides = JSON.parse(h.details_snapshot || '[]');
            detailsHtml = overrides.map(ov => {
                const base = currentData?.detail.find(d => d.Articulo == ov.articulo && (d.centro_original || d.Centro) == ov.centro);

                const isCentroChanged = ov.new_centro && ov.new_centro !== ov.centro;
                const isOeeChanged = ov.oee_override !== undefined && base && Math.abs(base['%OEE'] - ov.oee_override) > 0.001;
                const isPpmChanged = ov.ppm_override !== undefined && base && Math.round(base['Piezas por minuto']) !== Math.round(ov.ppm_override);
                const isDemChanged = ov.demanda_override !== undefined && base && Math.round(base['Volumen anual']) !== Math.round(ov.demanda_override);

                return `
                    <div class="history-detail-row">
                        <strong>${ov.articulo}</strong>: 
                        ${isCentroChanged ? `Centro: ${ov.centro} ➜ <span class="high-val">${ov.new_centro}</span>` : `Centro: ${ov.centro}`},
                        ${isOeeChanged ? `OEE: ${(base['%OEE'] * 100).toFixed(1)}% ➜ <span class="high-val">${(ov.oee_override * 100).toFixed(1)}%</span>` : `OEE: ${(base?.['%OEE'] * 100 || (ov.oee_override * 100)).toFixed(1)}%`},
                        ${isPpmChanged ? `PPM: ${Math.round(base['Piezas por minuto'])} ➜ <span class="high-val">${Math.round(ov.ppm_override)}</span>` : `PPM: ${Math.round(base?.['Piezas por minuto'] || ov.ppm_override)}`},
                        ${isDemChanged ? `Dem: ${Math.round(base['Volumen anual']).toLocaleString()} ➜ <span class="high-val">${ov.demanda_override.toLocaleString()}</span>` : `Dem: ${(base?.['Volumen anual'] || ov.demanda_override).toLocaleString()}`}
                    </div>
                `;
            }).join('');
        } catch (e) {
            detailsHtml = '<span>Error al cargar detalles</span>';
        }

        return `
            <div class="history-item">
                <span class="history-time">${h.timestamp}</span>
                <span class="history-name">${h.name}</span>
                <div class="history-meta">
                    ${detailsHtml}
                </div>
            </div>
        `;
    }).join('');
}

function renderManageList() {
    const container = document.getElementById('manage-list-container');
    container.innerHTML = scenarios.map(s => `
        <div class="manage-item">
            <span style="font-weight: 600;">${s.name}</span>
            <div class="manage-actions" style="display: flex; gap: 8px;">
                <button class="action-btn" onclick="loadAndClose(${s.id})" title="Cargar Escenario">Cargar</button>
                <button class="icon-btn" onclick="renameScenarioInline(${s.id}, '${s.name}')" title="Renombrar">✎</button>
                <button class="icon-btn" onclick="deleteScenarioInline(${s.id})" title="Borrar" style="color: var(--rpk-red); border-color: rgba(227, 6, 19, 0.2);">🗑</button>
            </div>
        </div>
    `).join('');
}

window.renameScenarioInline = async (id, currentName) => {
    const newName = prompt("Nuevo nombre para el escenario:", currentName);
    if (!newName || newName === currentName) return;

    try {
        const res = await fetch(`${API_BASE}/scenarios/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });
        if (res.ok) {
            await loadScenarios();
            renderManageList();
            if (currentScenarioId == id) {
                document.getElementById('current-scenario-name').innerText = newName;
            }
        }
    } catch (e) { alert("Error al renombrar"); }
};

window.deleteScenarioInline = async (id) => {
    if (!confirm("¿Estás seguro de que deseas eliminar este escenario? Esta acción no se puede deshacer.")) return;

    try {
        const res = await fetch(`${API_BASE}/scenarios/${id}`, { method: 'DELETE' });
        if (res.ok) {
            await loadScenarios();
            renderManageList();
            if (currentScenarioId == id) {
                loadSimulation('base');
            }
        }
    } catch (e) { alert("Error al eliminar"); }
};

function loadAndClose(id) { loadSimulation(id); document.getElementById('manage-modal').style.display = 'none'; }

async function runCompare() {
    const scA = document.getElementById('compare-a').value;
    const scB = document.getElementById('compare-b').value;
    try {
        const resA = await fetch(`${API_BASE}/simulate/${scA === 'base' ? 'base' : scA}`);
        const resB = await fetch(`${API_BASE}/simulate/${scB === 'base' ? 'base' : scB}`);
        comparisonData = { nameA: scA, nameB: scB, dataA: await resA.json(), dataB: await resB.json() };
        isComparisonMode = true;
        document.getElementById('compare-modal').style.display = 'none';
        enterComparisonMode();
    } catch (e) { }
}

function enterComparisonMode() {
    document.getElementById('comparison-controls').style.display = 'flex';
    document.getElementById('filters').style.display = 'none';
    renderComparisonDashboard();
}

function exitComparisonMode() { isComparisonMode = false; initApp(); }

function renderComparisonDashboard() {
    updateComparisonChart();
    renderComparisonSummary();
    renderComparisonTable();
}

function updateComparisonChart() {
    const ctx = document.getElementById('saturationChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: comparisonData.dataA.summary.map(s => s.Centro),
            datasets: [
                { label: comparisonData.nameA, data: comparisonData.dataA.summary.map(s => s.Saturacion * 100), backgroundColor: '#444' },
                { label: comparisonData.nameB, data: comparisonData.dataB.summary.map(s => s.Saturacion * 100), backgroundColor: '#E30613' }
            ]
        }
    });
}
function renderComparisonSummary() {
    const sumA = comparisonData.dataA.summary;
    const sumB = comparisonData.dataB.summary;
    const avgA = sumA.reduce((sum, s) => sum + s.Saturacion, 0) / sumA.length;
    const avgB = sumB.reduce((sum, s) => sum + s.Saturacion, 0) / sumB.length;
    const demA = sumA.reduce((sum, s) => sum + (s['Volumen anual'] || 0), 0);
    const demB = sumB.reduce((sum, s) => sum + (s['Volumen anual'] || 0), 0);

    const container = document.getElementById('summary-stats');
    container.innerHTML = `
        <div class="stat-item">
            <div class="stat-val">
                <span style="color:var(--text-muted); font-size: 0.8rem;">${(avgA * 100).toFixed(1)}%</span>
                <span style="margin: 0 10px;">➜</span>
                <span class="${(avgB > avgA) ? 'rpk-red-text' : 'text-success'}">${(avgB * 100).toFixed(1)}%</span>
            </div>
            <div class="stat-label">Saturación Media</div>
        </div>
        <div class="stat-item">
            <div class="stat-val">
                <span style="color:var(--text-muted); font-size: 0.8rem;">${Math.round(demA).toLocaleString()}</span>
                <span style="margin: 0 10px;">➜</span>
                <span>${Math.round(demB).toLocaleString()}</span>
            </div>
            <div class="stat-label">Demanda Total</div>
        </div>
    `;
}

function renderComparisonTable() {
    const tableBody = document.getElementById('table-body');
    const articles = [...new Set([
        ...comparisonData.dataA.detail.map(d => d.Articulo),
        ...comparisonData.dataB.detail.map(d => d.Articulo)
    ])];

    tableBody.innerHTML = articles.map(art => {
        const dA = comparisonData.dataA.detail.find(d => d.Articulo === art) || {};
        const dB = comparisonData.dataB.detail.find(d => d.Articulo === art) || {};
        const satA = dA.Saturacion || 0;
        const satB = dB.Saturacion || 0;
        const diff = (satB - satA) * 100;

        return `
            <tr>
                <td><strong>${art}</strong></td>
                <td class="text-center">${dB.Centro || dA.Centro}</td>
                <td class="text-right">${Math.round(dB['Volumen anual'] || dA['Volumen anual']).toLocaleString()}</td>
                <td class="text-right">${Math.round(dB['Piezas por minuto'] || dA['Piezas por minuto'])}</td>
                <td class="text-right">${((dB['%OEE'] || dA['%OEE']) * 100).toFixed(1)}%</td>
                <td class="text-center" style="white-space: nowrap;">${(satA * 100).toFixed(1)}% ➜ ${(satB * 100).toFixed(1)}%</td>
                <td class="text-right ${diff > 0.1 ? 'rpk-red' : diff < -0.1 ? 'text-success' : ''}">
                    ${diff > 0 ? '+' : ''}${diff.toFixed(2)}%
                </td>
                <td class="text-center">-</td>
            </tr>
        `;
    }).join('');
}
