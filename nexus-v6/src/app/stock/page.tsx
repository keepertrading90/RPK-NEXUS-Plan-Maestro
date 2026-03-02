'use client';

import React, { useEffect, useState } from 'react';
import { KPICard } from '@/components/ui/KPICard';
import { BarChart } from '@/components/charts/BarChart';
import Link from 'next/link';

interface StockKpis {
    total_cantidad: number;
    total_valor: number;
    num_articulos: number;
}

interface TopCliente {
    cliente: string;
    cantidad: number;
    valor: number;
}

interface ArticuloStock {
    articulo: string;
    descripcion: string;
    cantidad: number;
    valor: number;
}

const fmtEur = (v: number) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
const fmtNum = (v: number) => new Intl.NumberFormat('es-ES').format(v);

export default function StockPage() {
    const [kpis, setKpis] = useState<StockKpis | null>(null);
    const [clientes, setClientes] = useState<TopCliente[]>([]);
    const [articulos, setArticulos] = useState<ArticuloStock[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [section, setSection] = useState<'summary' | 'ranking'>('summary');
    const [fechaStart, setFechaStart] = useState('');
    const [fechaEnd, setFechaEnd] = useState('');
    const [searchTerm, setSearchTerm] = useState('');

    const loadData = async (start?: string, end?: string) => {
        setIsLoading(true);
        try {
            const params = new URLSearchParams();
            if (start) params.set('start', start);
            if (end) params.set('end', end);
            const qs = params.toString() ? '?' + params.toString() : '';

            const [summaryRes, clientesRes] = await Promise.all([
                fetch(`/api/summary${qs}`),
                fetch(`/api/customers${qs}`),
            ]);
            const summaryData = await summaryRes.json();
            const clientesData = await clientesRes.json();

            if (summaryData.kpis) setKpis(summaryData.kpis);
            if (clientesData.clientes) setClientes(clientesData.clientes);
            if (summaryData.articulos) setArticulos(summaryData.articulos);
        } catch { /* graceful degradation */ }
        finally { setIsLoading(false); }
    };

    useEffect(() => { loadData(); }, []);

    const filteredArticulos = articulos.filter(a =>
        a.articulo?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.descripcion?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="min-h-screen bg-[var(--color-dark-bg)] flex">
            {/* Sidebar */}
            <aside className="w-56 border-r border-[var(--color-glass-border)] p-6 flex flex-col gap-6 shrink-0">
                <Link href="/" className="no-underline">
                    <h2 className="text-xl font-black text-white">RPK<span className="text-[var(--color-rpk-red)]">NEXUS</span></h2>
                </Link>
                <nav className="flex flex-col gap-2">
                    {[{ id: 'summary' as const, label: '📊 Resumen General' }, { id: 'ranking' as const, label: '📦 Análisis por Artículo' }].map(s => (
                        <button key={s.id} onClick={() => setSection(s.id)}
                            className={`text-left px-4 py-3 rounded-xl text-sm font-medium border-none cursor-pointer transition-all ${section === s.id
                                    ? 'bg-[var(--color-rpk-red)]/10 text-[var(--color-rpk-red)] border-l-2 border-[var(--color-rpk-red)]'
                                    : 'text-[var(--color-text-muted)] hover:text-white hover:bg-white/5'
                                }`}
                        >{s.label}</button>
                    ))}
                </nav>
            </aside>

            {/* Main */}
            <main className="flex-1 p-8 overflow-y-auto">
                {/* Filters */}
                <div className="flex items-center gap-3 mb-8">
                    <input type="date" value={fechaStart} onChange={e => setFechaStart(e.target.value)}
                        className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm" />
                    <input type="date" value={fechaEnd} onChange={e => setFechaEnd(e.target.value)}
                        className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm" />
                    <button onClick={() => loadData(fechaStart, fechaEnd)}
                        className="px-4 py-2 bg-[var(--color-rpk-red)] text-white rounded-lg text-sm border-none cursor-pointer font-medium hover:bg-[var(--color-rpk-dark)]">
                        Filtrar
                    </button>
                    <button onClick={() => { setFechaStart(''); setFechaEnd(''); loadData(); }}
                        className="px-4 py-2 bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] rounded-lg text-sm border border-[var(--color-glass-border)] cursor-pointer hover:text-white">
                        Limpiar
                    </button>
                </div>

                {section === 'summary' && (
                    <>
                        {/* KPIs */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                            <KPICard title="Stock Total" value={kpis ? fmtNum(kpis.total_cantidad) : '---'} label="Piezas en almacén" />
                            <KPICard title="Valor Total" value={kpis ? fmtEur(kpis.total_valor) : '---'} label="Euros almacenados" />
                            <KPICard title="Referencias" value={kpis ? fmtNum(kpis.num_articulos) : '---'} label="Artículos distintos" />
                        </div>

                        {/* Top Clientes Chart */}
                        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                            <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Top Clientes por Valor</h3>
                            {clientes.length > 0 ? (
                                <BarChart
                                    labels={clientes.map(c => c.cliente)}
                                    datasets={[{ label: 'Valor (€)', data: clientes.map(c => c.valor), backgroundColor: '#E30613' }]}
                                    horizontal
                                    yAxisFormatter={v => v >= 1000 ? (v / 1000).toFixed(0) + 'k€' : v + '€'}
                                    tooltipFormatter={v => fmtEur(v)}
                                    height="400px"
                                />
                            ) : (
                                <div className="h-[300px] flex items-center justify-center text-[var(--color-text-muted)]">
                                    {isLoading ? 'Cargando...' : 'Sin datos'}
                                </div>
                            )}
                        </div>
                    </>
                )}

                {section === 'ranking' && (
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Análisis por Artículo</h3>
                        <input
                            type="text" placeholder="🔍 Buscar artículo..."
                            value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                            className="w-full bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-4 py-2.5 rounded-lg text-sm mb-4 outline-none focus:border-[var(--color-rpk-red)]"
                        />
                        <div className="overflow-y-auto max-h-[500px]">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr>
                                        <th className="text-left p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Artículo</th>
                                        <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Cantidad</th>
                                        <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Valor</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredArticulos.length > 0 ? filteredArticulos.map((a, i) => (
                                        <tr key={i} className="hover:bg-white/[0.02]">
                                            <td className="p-3 border-b border-white/5">
                                                <div className="font-bold text-white">{a.articulo}</div>
                                                <div className="text-xs text-[var(--color-text-muted)]">{a.descripcion}</div>
                                            </td>
                                            <td className="p-3 text-right text-white border-b border-white/5">{fmtNum(a.cantidad)}</td>
                                            <td className="p-3 text-right font-bold text-[var(--color-rpk-red)] border-b border-white/5">{fmtEur(a.valor)}</td>
                                        </tr>
                                    )) : (
                                        <tr><td colSpan={3} className="text-center p-8 text-[var(--color-text-muted)]">{isLoading ? 'Cargando...' : 'Sin resultados'}</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
