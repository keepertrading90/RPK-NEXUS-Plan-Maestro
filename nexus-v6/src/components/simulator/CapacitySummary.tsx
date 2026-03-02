'use client';

import React from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';

const fmtH = (v: number) => `${v.toFixed(1)}h`;
const fmtPct = (v: number) => `${v.toFixed(1)}%`;

export const CapacitySummary: React.FC = () => {
    const { currentData } = useSimulatorStore();

    if (!currentData?.summary) return null;

    const { total_carga_h, total_setup_h, total_capacidad_h, saturacion_media } = currentData.summary;
    const disponible = total_capacidad_h - total_carga_h - total_setup_h;

    const items = [
        { label: 'Capacidad Total', value: fmtH(total_capacidad_h), color: 'text-white' },
        { label: 'Carga Producción', value: fmtH(total_carga_h), color: 'text-blue-400' },
        { label: 'Setup', value: fmtH(total_setup_h), color: 'text-yellow-400' },
        { label: 'Disponible', value: fmtH(Math.max(0, disponible)), color: disponible > 0 ? 'text-emerald-400' : 'text-red-400' },
        { label: 'Saturación Media', value: fmtPct(saturacion_media), color: saturacion_media > 90 ? 'text-red-400' : 'text-emerald-400' },
    ];

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
            <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Resumen de Capacidad</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {items.map((item, i) => (
                    <div key={i} className="text-center">
                        <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
                        <div className="text-xs text-[var(--color-text-muted)] mt-1 uppercase">{item.label}</div>
                    </div>
                ))}
            </div>
            {/* Progress bar */}
            <div className="mt-4 h-3 rounded-full bg-[var(--color-dark-surface-2)] overflow-hidden flex">
                <div className="bg-blue-500 h-full" style={{ width: `${(total_carga_h / total_capacidad_h * 100).toFixed(1)}%` }} />
                <div className="bg-yellow-500 h-full" style={{ width: `${(total_setup_h / total_capacidad_h * 100).toFixed(1)}%` }} />
            </div>
            <div className="flex justify-between text-xs text-[var(--color-text-muted)] mt-1">
                <span>🔵 Carga {((total_carga_h / total_capacidad_h) * 100).toFixed(1)}%</span>
                <span>🟡 Setup {((total_setup_h / total_capacidad_h) * 100).toFixed(1)}%</span>
                <span>⚪ Libre {((Math.max(0, disponible) / total_capacidad_h) * 100).toFixed(1)}%</span>
            </div>
        </div>
    );
};
