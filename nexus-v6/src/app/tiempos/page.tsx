'use client';

import React, { useEffect, useState } from 'react';
import { KPICard } from '@/components/ui/KPICard';
import { BarChart } from '@/components/charts/BarChart';
import Link from 'next/link';

interface CentroData {
    centro: string;
    carga_h: number;
    setup_h: number;
    oee: number;
    saturacion: number;
}

interface TiemposData {
    kpis: {
        total_carga_h: number;
        total_setup_h: number;
        media_oee: number;
        saturacion_general: number;
    };
    centros: CentroData[];
    rankings: { top_saturados: CentroData[]; top_libres: CentroData[] };
}

const fmtH = (v: number) => `${v.toFixed(0)}h`;

export default function TiemposPage() {
    const [data, setData] = useState<TiemposData | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'dashboard' | 'ranking'>('dashboard');
    const [selectedCentro, setSelectedCentro] = useState<string | null>(null);

    useEffect(() => {
        fetch('/api/v6/tiempos/summary')
            .then(r => r.json())
            .then(d => { setData(d); setIsLoading(false); })
            .catch(() => setIsLoading(false));
    }, []);

    const centros = data?.centros || [];
    const labels = centros.map(c => c.centro);
    const colors = centros.map(c => c.saturacion > 90 ? '#ef4444' : c.saturacion > 70 ? '#f59e0b' : '#10b981');

    return (
        <div className="min-h-screen bg-[var(--color-dark-bg)]">
            <header className="flex items-center justify-between px-8 py-6 border-b border-[var(--color-glass-border)]">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-[var(--color-text-muted)] hover:text-white transition-colors no-underline">← Portal</Link>
                    <h1 className="text-2xl font-bold text-white m-0">⏳ Carga y Tiempos</h1>
                </div>
                <div className="flex gap-2">
                    {(['dashboard', 'ranking'] as const).map(tab => (
                        <button key={tab} onClick={() => setActiveTab(tab)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium border-none cursor-pointer transition-all ${activeTab === tab
                                ? 'bg-[var(--color-rpk-red)] text-white shadow-[0_0_10px_rgba(227,6,19,0.3)]'
                                : 'bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] hover:text-white'
                                }`}
                        >
                            {tab === 'dashboard' ? '📊 Dashboard' : '🏆 Ranking'}
                        </button>
                    ))}
                </div>
            </header>

            <main className="p-8 max-w-7xl mx-auto">
                {/* KPIs */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <KPICard title="Carga Total" value={data ? fmtH(data.kpis.total_carga_h) : '---'} label="Horas producción" />
                    <KPICard title="Setup Total" value={data ? fmtH(data.kpis.total_setup_h) : '---'} label="Horas preparación" />
                    <KPICard title="OEE Medio" value={data ? `${data.kpis.media_oee.toFixed(1)}%` : '---'} label="Eficiencia global" />
                    <KPICard title="Saturación" value={data ? `${data.kpis.saturacion_general.toFixed(1)}%` : '---'} label="Capacidad utilizada" />
                </div>

                {activeTab === 'dashboard' && (
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Saturación por Centro de Trabajo</h3>
                        {centros.length > 0 ? (
                            <BarChart
                                labels={labels}
                                datasets={[{
                                    label: '% Saturación',
                                    data: centros.map(c => c.saturacion),
                                    backgroundColor: colors,
                                }]}
                                horizontal
                                yAxisFormatter={v => `${v}%`}
                                tooltipFormatter={v => `${v.toFixed(1)}%`}
                                onClick={(_, label) => setSelectedCentro(label)}
                                height="500px"
                            />
                        ) : (
                            <div className="h-[400px] flex items-center justify-center text-[var(--color-text-muted)]">
                                {isLoading ? 'Cargando...' : 'Sin datos'}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'ranking' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {[
                            { title: '🔴 Más Saturados', items: data?.rankings?.top_saturados || [] },
                            { title: '🟢 Más Libres', items: data?.rankings?.top_libres || [] },
                        ].map((section, si) => (
                            <div key={si} className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                                <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">{section.title}</h3>
                                <table className="w-full border-collapse">
                                    <thead>
                                        <tr>
                                            <th className="text-left p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Centro</th>
                                            <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Carga</th>
                                            <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Saturación</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {section.items.map((item, i) => (
                                            <tr key={i} className="hover:bg-white/[0.02]">
                                                <td className="p-3 font-bold text-white border-b border-white/5">{item.centro}</td>
                                                <td className="p-3 text-right text-white border-b border-white/5">{fmtH(item.carga_h)}</td>
                                                <td className={`p-3 text-right font-bold border-b border-white/5 ${item.saturacion > 90 ? 'text-red-500' : item.saturacion > 70 ? 'text-yellow-500' : 'text-emerald-500'}`}>
                                                    {item.saturacion.toFixed(1)}%
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ))}
                    </div>
                )}

                {/* Drilldown modal */}
                {selectedCentro && (
                    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center" onClick={() => setSelectedCentro(null)}>
                        <div className="bg-[var(--color-dark-surface)] border border-[var(--color-glass-border)] rounded-2xl p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="text-white font-bold text-lg">Detalle: {selectedCentro}</h3>
                                <button onClick={() => setSelectedCentro(null)} className="text-[var(--color-text-muted)] hover:text-white cursor-pointer bg-transparent border-none text-lg">✕</button>
                            </div>
                            {(() => {
                                const c = centros.find(x => x.centro === selectedCentro);
                                if (!c) return <p className="text-[var(--color-text-muted)]">Sin datos</p>;
                                return (
                                    <div className="space-y-3">
                                        <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Carga</span><span className="text-white font-bold">{fmtH(c.carga_h)}</span></div>
                                        <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Setup</span><span className="text-white font-bold">{fmtH(c.setup_h)}</span></div>
                                        <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">OEE</span><span className="text-white font-bold">{c.oee.toFixed(1)}%</span></div>
                                        <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">Saturación</span><span className={`font-bold ${c.saturacion > 90 ? 'text-red-500' : 'text-emerald-500'}`}>{c.saturacion.toFixed(1)}%</span></div>
                                    </div>
                                );
                            })()}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
