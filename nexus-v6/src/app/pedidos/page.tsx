'use client';

import React, { useEffect, useState } from 'react';
import { KPICard } from '@/components/ui/KPICard';
import { LineChart } from '@/components/charts/LineChart';
import Link from 'next/link';

interface PedidosKpis {
    total_importe: number;
    total_piezas: number;
    num_referencias: number;
}

interface TopArticulo {
    articulo: string;
    referencia: string;
    cantidad: number;
    importe: number;
}

interface PedidosData {
    kpis: PedidosKpis;
    ultima_fecha: string;
    evolucion: { fechas: string[]; importes: number[] };
}

const fmtEur = (v: number) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
const fmtNum = (v: number) => new Intl.NumberFormat('es-ES').format(v);

export default function PedidosPage() {
    const [data, setData] = useState<PedidosData | null>(null);
    const [articulos, setArticulos] = useState<TopArticulo[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isOnline, setIsOnline] = useState(false);

    useEffect(() => {
        const load = async () => {
            try {
                const [summaryRes, artRes] = await Promise.all([
                    fetch('/api/pedidos/summary'),
                    fetch('/api/pedidos/articulos'),
                ]);
                const summaryData = await summaryRes.json();
                const artData = await artRes.json();

                if (summaryData.kpis) {
                    setData(summaryData);
                    setIsOnline(true);
                }
                if (artData.articulos) {
                    setArticulos(artData.articulos);
                }
            } catch {
                setIsOnline(false);
            } finally {
                setIsLoading(false);
            }
        };
        load();
    }, []);

    return (
        <div className="min-h-screen bg-[var(--color-dark-bg)]">
            {/* Header */}
            <header className="flex items-center justify-between px-8 py-6 border-b border-[var(--color-glass-border)]">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-[var(--color-text-muted)] hover:text-white transition-colors no-underline">
                        ← Portal
                    </Link>
                    <h1 className="text-2xl font-bold text-white m-0">
                        💰 Pedidos de Venta
                    </h1>
                </div>
                <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-red-500'}`} />
                    <span className="text-xs text-[var(--color-text-muted)]">
                        {data?.ultima_fecha ? `Snapshot: ${data.ultima_fecha}` : 'Cargando...'}
                    </span>
                    <button
                        onClick={() => window.location.reload()}
                        className="px-3 py-1.5 rounded-lg bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-glass-border)] text-xs cursor-pointer hover:text-white transition-colors"
                    >
                        🔄 Actualizar
                    </button>
                </div>
            </header>

            <main className="p-8 max-w-7xl mx-auto">
                {/* KPIs */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <KPICard
                        title="Importe Total Cartera"
                        value={data ? fmtEur(data.kpis.total_importe) : '---'}
                        label="Euros pendientes"
                    />
                    <KPICard
                        title="Total Piezas"
                        value={data ? fmtNum(data.kpis.total_piezas) : '---'}
                        label="Unidades pedidas"
                    />
                    <KPICard
                        title="Referencias Activas"
                        value={data ? data.kpis.num_referencias.toString() : '---'}
                        label="Artículos distintos"
                    />
                </div>

                {/* Chart + Table Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Evolution Chart */}
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">
                            Evolución Cartera
                        </h3>
                        {data?.evolucion ? (
                            <LineChart
                                labels={data.evolucion.fechas}
                                datasets={[{
                                    label: 'Importe Cartera (€)',
                                    data: data.evolucion.importes,
                                    fill: true,
                                }]}
                                yAxisFormatter={(v) => {
                                    if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M€';
                                    if (v >= 1000) return (v / 1000).toFixed(0) + 'k€';
                                    return v + '€';
                                }}
                                tooltipFormatter={(v) => fmtEur(v)}
                            />
                        ) : (
                            <div className="h-[400px] flex items-center justify-center text-[var(--color-text-muted)]">
                                {isLoading ? 'Cargando gráfico...' : 'Sin datos disponibles'}
                            </div>
                        )}
                    </div>

                    {/* Top Articulos Table */}
                    <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6">
                        <h3 className="text-[var(--color-text-muted)] text-sm font-semibold uppercase tracking-wider mb-4">
                            Top Artículos por Importe
                        </h3>
                        <div className="overflow-y-auto max-h-[440px]">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr>
                                        <th className="text-left p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Artículo</th>
                                        <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Cantidad</th>
                                        <th className="text-right p-3 text-[var(--color-text-muted)] text-xs uppercase border-b border-[var(--color-glass-border)]">Importe</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {articulos.length > 0 ? articulos.map((art, i) => (
                                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                            <td className="p-3 border-b border-white/5">
                                                <div className="font-bold text-white">{art.articulo}</div>
                                                <div className="text-xs text-[var(--color-text-muted)]">{art.referencia || ''}</div>
                                            </td>
                                            <td className="p-3 text-right text-white border-b border-white/5">
                                                {fmtNum(art.cantidad)} uds.
                                            </td>
                                            <td className="p-3 text-right font-bold text-[var(--color-rpk-red)] border-b border-white/5">
                                                {fmtEur(art.importe)}
                                            </td>
                                        </tr>
                                    )) : (
                                        <tr>
                                            <td colSpan={3} className="text-center p-8 text-[var(--color-text-muted)]">
                                                {isLoading ? 'Cargando artículos...' : 'Sin datos'}
                                            </td>
                                        </tr>
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
