'use client';

import React, { useEffect, useState } from 'react';
import { BarChart } from '@/components/charts/BarChart';

interface CentroSaturado {
    centro: string;
    horas_wip: number;
    horas_entrantes: number;
    saturacion_total_proyectada: number;
    max_fecha_simulada: string;
    warning: boolean;
}

interface OfProyectada {
    of: string;
    articulo: string;
    cabecera: string;
    secundario: string;
    fase_sec: number;
    cantidad: number;
    fecha_llegada: string;
    horas_uso: number;
}

interface PredictiveData {
    status: string;
    dias_horizonte: number;
    fecha_actual: string;
    centros_saturados: CentroSaturado[];
    of_proyectadas: OfProyectada[];
}

export const PredictiveDashboard: React.FC = () => {
    const [data, setData] = useState<PredictiveData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('/api/v1/predictive/saturation?dias_horizonte=14');
                const result = await response.json();
                if (result.status === 'success' && result.data.status === 'success') {
                    setData(result.data);
                }
            } catch (error) {
                console.error("Error fetching predictive data:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-12 bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)]">
                <div className="flex items-center gap-3 text-[var(--color-text-muted)] animate-pulse">
                    <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                    Generando Gemelo Digital (Forward-Pass)...
                </div>
            </div>
        );
    }

    if (!data || !data.centros_saturados || data.centros_saturados.length === 0) {
        return (
            <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6 text-center text-[var(--color-text-muted)]">
                No hay datos de saturación predictiva (Carril B cerrado o sin OFs en Fase 10).
            </div>
        );
    }

    // Preparar gráficos de barras apiladas: WIP vs Proyectado
    const labels = data.centros_saturados.map(c => `C. ${c.centro}`);
    const dataWip = data.centros_saturados.map(c => c.horas_wip);
    const dataProyectado = data.centros_saturados.map(c => c.horas_entrantes);

    return (
        <div className="bg-[var(--color-dark-surface)] rounded-2xl border border-[var(--color-glass-border)] p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-emerald-400 text-sm font-bold uppercase tracking-wider">
                        Gemelo Digital: Proyección de Secundarios
                    </h3>
                    <p className="text-[var(--color-text-muted)] text-xs mt-1">
                        Horizonte predictivo: {data.dias_horizonte} días | Basado en Fase 10 actual
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 gap-6">
                <div>
                    <h4 className="text-[var(--color-text-muted)] text-sm mb-4">Saturación (Horas)</h4>
                    <BarChart
                        labels={labels}
                        datasets={[
                            {
                                label: 'WIP Actual',
                                data: dataWip,
                                backgroundColor: '#3b82f6', // blue-500
                            },
                            {
                                label: 'Carga Entrante Predictiva',
                                data: dataProyectado,
                                backgroundColor: '#f59e0b', // amber-500
                            }
                        ]}
                        horizontal={false}
                        yAxisFormatter={v => `${v}h`}
                        tooltipFormatter={v => `${Number(v).toFixed(1)}h`}
                        height="300px"
                    />
                </div>
            </div>
            
            <div className="text-xs text-[var(--color-text-muted)] bg-[var(--color-dark-surface-2)] p-4 rounded-xl border border-[var(--color-glass-border)]">
                <strong>¿Cómo interpretarlo?</strong> Las barras azules muestran lo que físicamente hay acumulado en el centro secundario. Las naranjas muestran lo que le llegará desde cabeceras (Prensas/Compresión/Retenes) a medida que procesen la carga actual. Si ambas suman sobrepasan la línea de 112h semanales, se formará embudo (Cuello de Botella Predictivo).
            </div>

            {/* Impact table */}
            {data.of_proyectadas && data.of_proyectadas.length > 0 && (
                <div className="mt-8">
                    <h4 className="text-[var(--color-text-muted)] text-sm mb-4">
                        Flujo hacia Adelante - Lotes Proyectados a Secundarios
                    </h4>
                    <div className="overflow-x-auto rounded-xl border border-[var(--color-glass-border)]">
                        <table className="w-full text-left text-sm text-[var(--color-text-muted)]">
                            <thead className="bg-[var(--color-dark-surface-2)] text-[var(--color-text-primary)]">
                                <tr>
                                    <th className="px-4 py-3 font-medium">OF</th>
                                    <th className="px-4 py-3 font-medium">Artículo</th>
                                    <th className="px-4 py-3 font-medium">Desde (Cabecera)</th>
                                    <th className="px-4 py-3 font-medium">Hacia (Secundario)</th>
                                    <th className="px-4 py-3 font-medium text-right">Cantidad Piezas</th>
                                    <th className="px-4 py-3 font-medium">Fecha Proyectada Llegada</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.of_proyectadas.slice(0, 50).map((ofp, i) => (
                                    <tr key={`${ofp.of}-${ofp.secundario}-${i}`} className="border-t border-[var(--color-glass-border)] hover:bg-[var(--color-dark-surface-2)]/50 transition-colors">
                                        <td className="px-4 py-3 text-[var(--color-text-primary)]">{ofp.of}</td>
                                        <td className="px-4 py-3 text-[var(--color-text-primary)]">{ofp.articulo}</td>
                                        <td className="px-4 py-3">{ofp.cabecera}</td>
                                        <td className="px-4 py-3">{ofp.secundario} (Fase {ofp.fase_sec})</td>
                                        <td className="px-4 py-3 text-right">{ofp.cantidad.toLocaleString()}</td>
                                        <td className="px-4 py-3">
                                            <span className="px-2 py-1 bg-blue-500/10 text-blue-400 rounded-md text-xs font-semibold">
                                                {ofp.fecha_llegada}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};
