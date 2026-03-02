'use client';

import React, { useState } from 'react';
import { useSimulatorStore } from '@/store/useSimulatorStore';
import type { ArticuloRow } from '@/types/simulator';

const fmtNum = (v: number) => new Intl.NumberFormat('es-ES').format(v);

export const ArticleTable: React.FC = () => {
    const { currentData, selectedCenters, setEditingArticle, localOverrides } = useSimulatorStore();
    const [searchTerm, setSearchTerm] = useState('');
    const [expandedCenters, setExpandedCenters] = useState<string[]>([]);

    if (!currentData) return null;

    const centros = selectedCenters.length > 0
        ? currentData.centros.filter(c => selectedCenters.includes(c.centro))
        : currentData.centros;

    const toggleExpand = (centro: string) => {
        setExpandedCenters(prev =>
            prev.includes(centro) ? prev.filter(c => c !== centro) : [...prev, centro]
        );
    };

    const hasOverride = (articulo: string) => localOverrides.some(o => o.articulo === articulo);

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider">
                    Detalle por Artículo ({centros.reduce((acc, c) => acc + (c.articulos?.length || 0), 0)} refs.)
                </h3>
                <input
                    type="text" placeholder="🔍 Buscar artículo..."
                    value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                    className="w-64 bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm outline-none focus:border-[var(--color-rpk-red)]"
                />
            </div>

            <div className="overflow-y-auto max-h-[500px]">
                {centros.map(centro => {
                    const arts = (centro.articulos || []).filter(a =>
                        a.articulo?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        a.descripcion?.toLowerCase().includes(searchTerm.toLowerCase())
                    );
                    if (arts.length === 0 && searchTerm) return null;
                    const isExpanded = expandedCenters.includes(centro.centro);

                    return (
                        <div key={centro.centro} className="mb-2">
                            {/* Center Header */}
                            <button
                                onClick={() => toggleExpand(centro.centro)}
                                className="w-full flex items-center justify-between px-4 py-3 bg-[var(--color-dark-surface-2)] rounded-xl border-none cursor-pointer text-left text-white font-bold hover:bg-white/5 transition-colors"
                            >
                                <span className="flex items-center gap-2">
                                    <span className="text-lg">{isExpanded ? '▾' : '▸'}</span>
                                    {centro.centro_label || centro.centro}
                                    <span className={`text-sm font-medium px-2 py-0.5 rounded-full ${centro.saturacion > 100 ? 'bg-red-500/20 text-red-400' :
                                            centro.saturacion > 85 ? 'bg-yellow-500/20 text-yellow-400' :
                                                'bg-emerald-500/20 text-emerald-400'
                                        }`}>
                                        {centro.saturacion.toFixed(1)}%
                                    </span>
                                </span>
                                <span className="text-sm text-[var(--color-text-muted)]">{arts.length} artículos</span>
                            </button>

                            {/* Articles */}
                            {isExpanded && (
                                <table className="w-full border-collapse mt-1">
                                    <thead>
                                        <tr>
                                            {['Artículo', 'Demanda', 'Cadencia', 'OEE', 'Carga (h)', 'Setup (min)', ''].map((h, i) => (
                                                <th key={i} className="text-left p-2 text-[var(--color-text-muted)] text-xs uppercase border-b border-white/5">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {arts.map((art, i) => (
                                            <tr key={i} className={`hover:bg-white/[0.02] transition-colors ${hasOverride(art.articulo) ? 'bg-[var(--color-rpk-red)]/5' : ''}`}>
                                                <td className="p-2 border-b border-white/5">
                                                    <div className="font-medium text-white text-sm">{art.articulo}</div>
                                                    {art.descripcion && <div className="text-xs text-[var(--color-text-muted)]">{art.descripcion}</div>}
                                                </td>
                                                <td className="p-2 text-white text-sm border-b border-white/5">{fmtNum(art.demanda)}</td>
                                                <td className="p-2 text-white text-sm border-b border-white/5">{fmtNum(art.cadencia)}</td>
                                                <td className="p-2 text-white text-sm border-b border-white/5">{art.oee?.toFixed(1)}%</td>
                                                <td className="p-2 text-white text-sm border-b border-white/5">{art.carga_h?.toFixed(1)}</td>
                                                <td className="p-2 text-white text-sm border-b border-white/5">{art.setup_min?.toFixed(0) || '-'}</td>
                                                <td className="p-2 border-b border-white/5">
                                                    <button
                                                        onClick={() => setEditingArticle(art.articulo)}
                                                        className="px-2 py-1 rounded bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] text-xs border border-[var(--color-glass-border)] cursor-pointer hover:text-[var(--color-rpk-red)] hover:border-[var(--color-rpk-red)] transition-colors"
                                                    >
                                                        ✏️
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
