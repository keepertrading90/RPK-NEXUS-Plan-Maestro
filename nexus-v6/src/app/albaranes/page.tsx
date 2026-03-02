'use client';

import React, { useEffect, useState } from 'react';
import { KPICard } from '@/components/ui/KPICard';
import { LineChart } from '@/components/charts/LineChart';
import Link from 'next/link';

interface AlbaranesKpis {
    total_albaranes: number;
    total_importe: number;
    total_kg: number;
    num_clientes: number;
}

interface TopCliente {
    cliente: string;
    importe: number;
    cantidad: number;
}

const fmtEur = (v: number) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
const fmtNum = (v: number) => new Intl.NumberFormat('es-ES').format(v);

export default function AlbaranesPage() {
    const [kpis, setKpis] = useState<AlbaranesKpis | null>(null);
    const [evol, setEvol] = useState<{ fechas: string[]; importes: number[] } | null>(null);
    const [clientes, setClientes] = useState<TopCliente[]>([]);
    const [isOnline, setIsOnline] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [fechaStart, setFechaStart] = useState('');
    const [fechaEnd, setFechaEnd] = useState('');

    const loadData = async (start?: string, end?: string) => {
        setIsLoading(true);
        try {
            const params = new URLSearchParams();
            if (start) params.set('fecha_inicio', start);
            if (end) params.set('fecha_fin', end);
            const qs = params.toString() ? '?' + params.toString() : '';

            const [resumenRes, clientesRes] = await Promise.all([
                fetch(`/api/albaranes/resumen${qs}`),
                fetch(`/api/albaranes/clientes${qs}`),
            ]);
            const resumenData = await resumenRes.json();
            const clientesData = await clientesRes.json();

            if (resumenData.kpis) { setKpis(resumenData.kpis); setIsOnline(true); }
            if (resumenData.evolucion) setEvol(resumenData.evolucion);
            if (clientesData.clientes) setClientes(clientesData.clientes);
        } catch {
            setIsOnline(false);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => { loadData(); }, []);

    const handleFilter = () => { loadData(fechaStart, fechaEnd); };
    const handleClear = () => { setFechaStart(''); setFechaEnd(''); loadData(); };

    return (
        <div className="min-h-screen bg-[var(--color-dark-bg)]">
            {/* Header */}
            <header className="flex items-center justify-between px-8 py-6 border-b border-[var(--color-glass-border)]">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-[var(--color-text-muted)] hover:text-white transition-colors no-underline">← Portal</Link>
                    <h1 className="text-2xl font-bold text-white m-0">🚚 Albaranes de Entrega</h1>
                </div>
                <div className="flex items-center gap-3">
                    <input type="date" value={fechaStart} onChange={e => setFechaStart(e.target.value)}
                        className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-1.5 rounded-lg text-xs" />
                    <input type="date" value={fechaEnd} onChange={e => setFechaEnd(e.target.value)}
                        className="bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-1.5 rounded-lg text-xs" />
                    <button onClick={handleFilter} className="px-3 py-1.5 bg-[var(--color-rpk-red)] text-white rounded-lg text-xs border-none cursor-pointer hover:bg-[var(--color-rpk-dark)]">Filtrar</button>
                    <button onClick={handleClear} className="px-3 py-1.5 bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] rounded-lg text-xs border border-[var(--color-glass-border)] cursor-pointer hover:text-white">Limpiar</button>
                </div>
            </header>

            <main className="p-8 max-w-7xl mx-auto">
                {/* KPIs */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                    <KPICard title="Albaranes" value={kpis ? fmtNum(kpis.total_albaranes) : '---'} label="Documentos" />
                    <KPICard title="Importe Total" value={kpis ? fmtEur(kpis.total_importe) : '---'} label="Facturado" />
                    <KPICard title="Peso Total" value={kpis ? `${fmtNum(kpis.total_kg)} kg` : '---'} label="Kilogramos" />
                    <KPICard title="Clientes" value={kpis ? kpis.num_clientes.toString() : '---'} label="Clientes activos" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Chart */}
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Evolución Diaria</h3>
                        {evol ? (
                            <LineChart
                                labels={evol.fechas}
                                datasets={[{ label: 'Importe Diario (€)', data: evol.importes, fill: true }]}
                                yAxisFormatter={v => { if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M€'; if (v >= 1000) return (v / 1000).toFixed(0) + 'k€'; return v + '€'; }}
                                tooltipFormatter={v => fmtEur(v)}
                            />
                        ) : (
                            <div className="h-[400px] flex items-center justify-center text-[var(--color-text-muted)]">
                                {isLoading ? 'Cargando...' : 'Sin datos'}
                            </div>
                        )}
                    </div>

                    {/* Top Clientes */}
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">Top Clientes</h3>
                        <div className="overflow-y-auto max-h-[440px]">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr>
                                        <th className="text-left p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Cliente</th>
                                        <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Importe</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {clientes.length > 0 ? clientes.map((c, i) => (
                                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                            <td className="p-3 font-bold text-white border-b border-white/5">{c.cliente}</td>
                                            <td className="p-3 text-right font-bold text-[var(--color-rpk-red)] border-b border-white/5">{fmtEur(c.importe)}</td>
                                        </tr>
                                    )) : (
                                        <tr><td colSpan={2} className="text-center p-8 text-[var(--color-text-muted)]">{isLoading ? 'Cargando...' : 'Sin datos'}</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
