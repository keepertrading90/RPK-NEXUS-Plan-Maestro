'use client';

import React, { useState } from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';

const fmtH = (v: number) => `${v.toFixed(1)}h`;
const fmtPct = (v: number) => `${v.toFixed(1)}%`;

export const CompareView: React.FC = () => {
    const { scenarios, runComparison, comparisonData, comparisonViewMode, setComparisonViewMode, setComparisonMode, isLoading } = useSimulatorStore();
    const [scenarioA, setScenarioA] = useState('base');
    const [scenarioB, setScenarioB] = useState('base');

    const options = [{ id: 'base', name: 'Base' }, ...scenarios.map(s => ({ id: String(s.id), name: s.name }))];

    return (
        <div className="space-y-4">
            {/* Controls */}
            <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-4 flex items-center gap-4 flex-wrap">
                <span className="text-[var(--color-text-muted)] text-sm font-medium">Comparar:</span>
                <select value={scenarioA} onChange={e => setScenarioA(e.target.value)}
                    className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm">
                    {options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
                <span className="text-[var(--color-text-muted)]">vs</span>
                <select value={scenarioB} onChange={e => setScenarioB(e.target.value)}
                    className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm">
                    {options.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
                <button onClick={() => runComparison(scenarioA, scenarioB)} disabled={isLoading}
                    className="px-4 py-2 bg-[var(--color-rpk-red)] text-white rounded-lg text-sm font-medium border-none cursor-pointer hover:bg-[var(--color-rpk-dark)] disabled:opacity-50">
                    {isLoading ? 'Comparando...' : '🔀 Ejecutar'}
                </button>
                <div className="ml-auto flex gap-2">
                    <button onClick={() => setComparisonViewMode('absolute')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border-none cursor-pointer ${comparisonViewMode === 'absolute' ? 'bg-blue-600 text-white' : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)]'}`}>
                        Absoluto
                    </button>
                    <button onClick={() => setComparisonViewMode('delta')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border-none cursor-pointer ${comparisonViewMode === 'delta' ? 'bg-blue-600 text-white' : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)]'}`}>
                        Delta (Δ)
                    </button>
                    <button onClick={() => setComparisonMode(false)}
                        className="px-3 py-1.5 rounded-lg text-xs bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-glass-border)] cursor-pointer hover:text-white">
                        ← Volver
                    </button>
                </div>
            </div>

            {/* Results */}
            {comparisonData && (
                <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                    <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Resultados de Comparación</h3>
                    <table className="w-full border-collapse">
                        <thead>
                            <tr>
                                <th className="text-left p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Centro</th>
                                <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Sat. A</th>
                                <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Sat. B</th>
                                <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Δ Delta</th>
                            </tr>
                        </thead>
                        <tbody>
                            {comparisonData.centros.map((c, i) => (
                                <tr key={i} className="hover:bg-white/[0.02]">
                                    <td className="p-3 font-bold text-white border-b border-white/5">{c.centro}</td>
                                    <td className="p-3 text-right text-white border-b border-white/5">{fmtPct(c.saturacion_a)}</td>
                                    <td className="p-3 text-right text-white border-b border-white/5">{fmtPct(c.saturacion_b)}</td>
                                    <td className={`p-3 text-right font-bold border-b border-white/5 ${c.delta > 0 ? 'text-red-400' : c.delta < 0 ? 'text-emerald-400' : 'text-[var(--color-text-muted)]'}`}>
                                        {c.delta > 0 ? '+' : ''}{fmtPct(c.delta)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
