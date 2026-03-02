'use client';

import React from 'react';
import { BarChart } from '@/components/charts/BarChart';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const SaturationChart: React.FC = () => {
    const { currentData, selectedCenters } = useSimulatorStore();

    if (!currentData) return null;

    const centros = selectedCenters.length > 0
        ? currentData.centros.filter(c => selectedCenters.includes(c.centro))
        : currentData.centros;

    const labels = centros.map(c => c.centro_label || c.centro);
    const saturations = centros.map(c => c.saturacion);
    const colors = saturations.map(s => s > 100 ? '#ef4444' : s > 85 ? '#f59e0b' : '#10b981');

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
            <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">
                Saturación por Centro de Trabajo
            </h3>
            <BarChart
                labels={labels}
                datasets={[{
                    label: '% Saturación',
                    data: saturations,
                    backgroundColor: colors,
                }]}
                horizontal
                yAxisFormatter={v => `${v}%`}
                tooltipFormatter={v => `${v.toFixed(1)}%`}
                height="400px"
            />
        </div>
    );
};
