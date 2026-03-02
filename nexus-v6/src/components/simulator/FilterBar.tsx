'use client';

import React from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const FilterBar: React.FC = () => {
    const {
        workDays, workShifts, setWorkDays, setWorkShifts,
        currentData, selectedCenters, toggleCenter, loadSimulation,
        currentScenarioId, isModeActual,
    } = useSimulatorStore();

    const allCenters = currentData?.centros.map(c => c.centro) || [];

    const handleApply = () => {
        loadSimulation(currentScenarioId, isModeActual);
    };

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-4 flex flex-wrap items-center gap-4">
            {/* Work Days */}
            <div className="flex items-center gap-2">
                <label className="text-[var(--color-text-muted)] text-xs font-medium uppercase">Días Laborales</label>
                <input
                    type="number" min={1} max={365}
                    value={workDays}
                    onChange={e => setWorkDays(Number(e.target.value))}
                    className="w-20 bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-2 py-1.5 rounded-lg text-sm text-center"
                />
            </div>

            {/* Shifts */}
            <div className="flex items-center gap-2">
                <label className="text-[var(--color-text-muted)] text-xs font-medium uppercase">Horas/Turno</label>
                <input
                    type="number" min={1} max={24}
                    value={workShifts}
                    onChange={e => setWorkShifts(Number(e.target.value))}
                    className="w-20 bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-2 py-1.5 rounded-lg text-sm text-center"
                />
            </div>

            <button
                onClick={handleApply}
                className="px-4 py-2 bg-[var(--color-rpk-red)] text-white rounded-lg text-sm font-medium border-none cursor-pointer hover:bg-[var(--color-rpk-dark)]"
            >
                Aplicar
            </button>

            {/* Center filter chips */}
            <div className="flex-1" />
            <div className="flex flex-wrap gap-1.5">
                {allCenters.map(c => (
                    <button
                        key={c}
                        onClick={() => toggleCenter(c)}
                        className={`px-3 py-1 rounded-full text-xs font-medium border-none cursor-pointer transition-all ${selectedCenters.length === 0 || selectedCenters.includes(c)
                                ? 'bg-[var(--color-rpk-red)]/20 text-[var(--color-rpk-red)] border border-[var(--color-rpk-red)]/30'
                                : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] opacity-50'
                            }`}
                    >
                        {c}
                    </button>
                ))}
            </div>
        </div>
    );
};
