import { create } from 'zustand';
import type {
    SimulationData, SimulatorOverride, CenterConfig,
    ScenarioMeta, ComparisonResult,
} from '@/types/simulator';

const API_BASE = '/api';

interface SimulatorState {
    // Data
    currentData: SimulationData | null;
    baseData: SimulationData | null;
    scenarios: ScenarioMeta[];
    comparisonData: ComparisonResult | null;

    // UI State
    currentScenarioId: string;
    currentScenarioName: string;
    isModeActual: boolean;
    isLoading: boolean;
    isComparisonMode: boolean;
    comparisonViewMode: 'absolute' | 'delta';
    selectedCenters: string[];
    localOverrides: SimulatorOverride[];
    centerConfigs: Record<string, CenterConfig>;
    editingArticle: string | null;

    // Filters
    workDays: number;
    workShifts: number;

    // Actions
    loadSimulation: (scenarioId: string, useActual?: boolean) => Promise<void>;
    loadScenarios: () => Promise<void>;
    setSelectedCenters: (centers: string[]) => void;
    toggleCenter: (centro: string) => void;
    addOverride: (override: SimulatorOverride) => void;
    removeOverride: (articulo: string, field: string) => void;
    clearOverrides: () => void;
    setCenterConfig: (centro: string, config: CenterConfig) => void;
    setWorkDays: (days: number) => void;
    setWorkShifts: (shifts: number) => void;
    setEditingArticle: (articulo: string | null) => void;
    setComparisonMode: (isOn: boolean) => void;
    setComparisonViewMode: (mode: 'absolute' | 'delta') => void;
    runComparison: (scenarioA: string, scenarioB: string) => Promise<void>;
    saveScenario: (name: string) => Promise<boolean>;
    setModeActual: (isActual: boolean) => void;
}

export const useSimulatorStore = create<SimulatorState>((set, get) => ({
    // Initial State
    currentData: null,
    baseData: null,
    scenarios: [],
    comparisonData: null,
    currentScenarioId: 'base',
    currentScenarioName: 'Escenario Base',
    isModeActual: false,
    isLoading: false,
    isComparisonMode: false,
    comparisonViewMode: 'absolute',
    selectedCenters: [],
    localOverrides: [],
    centerConfigs: {},
    editingArticle: null,
    workDays: 238,
    workShifts: 16,

    // Actions
    loadSimulation: async (scenarioId, useActual = false) => {
        const { workDays, workShifts, localOverrides, centerConfigs } = get();
        set({ isLoading: true });

        try {
            const url = scenarioId === 'base'
                ? `${API_BASE}/simulate/base?dias_laborales=${workDays}&horas_turno=${workShifts}&use_actual=${useActual}`
                : `${API_BASE}/simulate/${scenarioId}?dias_laborales=${workDays}&horas_turno=${workShifts}`;

            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: SimulationData = await res.json();

            const scenarioName = useActual
                ? 'Escenario Actual (ERP)'
                : scenarioId === 'base'
                    ? 'Escenario Base'
                    : get().scenarios.find(s => String(s.id) === String(scenarioId))?.name || `Escenario #${scenarioId}`;

            set({
                currentData: data,
                currentScenarioId: scenarioId,
                currentScenarioName: scenarioName,
                isModeActual: useActual,
                isLoading: false,
                isComparisonMode: false,
            });

            // Also store as baseData if loading 'base'
            if (scenarioId === 'base' && !useActual) {
                set({ baseData: data });
            }
        } catch (err) {
            console.error('Error loading simulation:', err);
            set({ isLoading: false });
        }
    },

    loadScenarios: async () => {
        try {
            const res = await fetch(`${API_BASE}/scenarios`);
            const data = await res.json();
            set({ scenarios: Array.isArray(data) ? data : [] });
        } catch (err) {
            console.error('Error loading scenarios:', err);
        }
    },

    setSelectedCenters: (centers) => set({ selectedCenters: centers }),

    toggleCenter: (centro) => {
        const { selectedCenters } = get();
        const next = selectedCenters.includes(centro)
            ? selectedCenters.filter(c => c !== centro)
            : [...selectedCenters, centro];
        set({ selectedCenters: next });
    },

    addOverride: (override) => {
        const { localOverrides } = get();
        const existing = localOverrides.findIndex(
            o => o.articulo === override.articulo && o.field === override.field
        );
        if (existing >= 0) {
            const updated = [...localOverrides];
            updated[existing] = override;
            set({ localOverrides: updated });
        } else {
            set({ localOverrides: [...localOverrides, override] });
        }
    },

    removeOverride: (articulo, field) => {
        set({ localOverrides: get().localOverrides.filter(o => !(o.articulo === articulo && o.field === field)) });
    },

    clearOverrides: () => set({ localOverrides: [], centerConfigs: {} }),

    setCenterConfig: (centro, config) => {
        set({ centerConfigs: { ...get().centerConfigs, [centro]: config } });
    },

    setWorkDays: (days) => set({ workDays: days }),
    setWorkShifts: (shifts) => set({ workShifts: shifts }),
    setEditingArticle: (articulo) => set({ editingArticle: articulo }),

    setComparisonMode: (isOn) => set({ isComparisonMode: isOn, comparisonData: isOn ? get().comparisonData : null }),

    setComparisonViewMode: (mode) => set({ comparisonViewMode: mode }),

    runComparison: async (scenarioA, scenarioB) => {
        const { workDays, workShifts } = get();
        set({ isLoading: true });
        try {
            const res = await fetch(
                `${API_BASE}/simulate/compare?scenario_a=${scenarioA}&scenario_b=${scenarioB}&dias_laborales=${workDays}&horas_turno=${workShifts}`
            );
            const data = await res.json();
            set({ comparisonData: data, isComparisonMode: true, isLoading: false });
        } catch {
            set({ isLoading: false });
        }
    },

    saveScenario: async (name) => {
        const { localOverrides, centerConfigs, workDays, workShifts, isModeActual } = get();
        try {
            const res = await fetch(`${API_BASE}/scenarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    overrides: localOverrides,
                    center_configs: centerConfigs,
                    dias_laborales: workDays,
                    horas_turno: workShifts,
                    use_actual: isModeActual,
                }),
            });
            if (res.ok) {
                await get().loadScenarios();
                return true;
            }
            return false;
        } catch {
            return false;
        }
    },

    setModeActual: (isActual) => {
        set({ isModeActual: isActual, localOverrides: [], centerConfigs: {} });
        get().loadSimulation('base', isActual);
    },
}));
