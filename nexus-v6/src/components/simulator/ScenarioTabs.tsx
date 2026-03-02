'use client';

import React from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const ScenarioTabs: React.FC = () => {
    const { currentScenarioId, isModeActual, scenarios, loadSimulation, setModeActual, setComparisonMode } = useSimulatorStore();

    return (
        <div className="flex items-center gap-2 flex-wrap">
            <button
                onClick={() => loadSimulation('base', false)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border-none cursor-pointer transition-all ${currentScenarioId === 'base' && !isModeActual
                        ? 'bg-[var(--color-rpk-red)] text-white shadow-[0_0_10px_rgba(227,6,19,0.3)]'
                        : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] hover:text-white'
                    }`}
            >
                📊 Base
            </button>
            <button
                onClick={() => setModeActual(true)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border-none cursor-pointer transition-all ${isModeActual
                        ? 'bg-emerald-600 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                        : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] hover:text-white'
                    }`}
            >
                🏭 Actual (ERP)
            </button>
            {scenarios.map((s) => (
                <button
                    key={s.id}
                    onClick={() => loadSimulation(String(s.id))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border-none cursor-pointer transition-all ${String(currentScenarioId) === String(s.id)
                            ? 'bg-blue-600 text-white shadow-[0_0_10px_rgba(59,130,246,0.3)]'
                            : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] hover:text-white'
                        }`}
                >
                    💾 {s.name}
                </button>
            ))}
            <div className="ml-auto flex gap-2">
                <button
                    onClick={() => setComparisonMode(true)}
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-glass-border)] cursor-pointer hover:text-white transition-colors"
                >
                    🔀 Comparar
                </button>
            </div>
        </div>
    );
};
