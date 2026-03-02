'use client';

import React from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const ChangesPanel: React.FC = () => {
    const { localOverrides, removeOverride, clearOverrides } = useSimulatorStore();

    if (localOverrides.length === 0) return null;

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-rpk-red)]/30 p-4">
            <div className="flex items-center justify-between mb-3">
                <h4 className="text-[var(--color-rpk-red)] text-sm font-bold uppercase tracking-wider flex items-center gap-2">
                    ⚡ Cambios Activos ({localOverrides.length})
                </h4>
                <button onClick={clearOverrides}
                    className="text-xs text-[var(--color-text-muted)] hover:text-red-400 cursor-pointer bg-transparent border-none">
                    🗑️ Limpiar todo
                </button>
            </div>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {localOverrides.map((o, i) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[var(--color-dark-surface-2)]">
                        <div>
                            <span className="text-white text-sm font-medium">{o.articulo}</span>
                            <span className="mx-2 text-[var(--color-text-muted)]">→</span>
                            <span className="text-xs text-[var(--color-text-muted)]">{o.label || o.field}:</span>
                            <span className="text-xs text-red-400 line-through mx-1">{o.original}</span>
                            <span className="text-xs text-emerald-400 font-bold">{o.value}</span>
                        </div>
                        <button onClick={() => removeOverride(o.articulo, o.field)}
                            className="text-[var(--color-text-muted)] hover:text-red-400 cursor-pointer bg-transparent border-none text-sm">✕</button>
                    </div>
                ))}
            </div>
        </div>
    );
};
