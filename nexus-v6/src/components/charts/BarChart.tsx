'use client';

import React, { useRef, useEffect } from 'react';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

interface BarChartProps {
    labels: string[];
    datasets: {
        label: string;
        data: number[];
        backgroundColor?: string | string[];
        borderColor?: string;
        borderWidth?: number;
    }[];
    horizontal?: boolean;
    stacked?: boolean;
    yAxisFormatter?: (value: number) => string;
    tooltipFormatter?: (value: number) => string;
    height?: string;
    onClick?: (index: number, label: string) => void;
}

export const BarChart: React.FC<BarChartProps> = ({
    labels, datasets, horizontal = false, stacked = false,
    yAxisFormatter, tooltipFormatter, height = '400px', onClick,
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const chartRef = useRef<Chart | null>(null);

    useEffect(() => {
        if (!canvasRef.current) return;
        const ctx = canvasRef.current.getContext('2d');
        if (!ctx) return;

        if (chartRef.current) chartRef.current.destroy();

        chartRef.current = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: datasets.map(ds => ({
                    ...ds,
                    backgroundColor: ds.backgroundColor || '#E30613',
                    borderColor: ds.borderColor || 'transparent',
                    borderWidth: ds.borderWidth ?? 0,
                    borderRadius: 6,
                })),
            },
            options: {
                indexAxis: horizontal ? 'y' : 'x',
                responsive: true,
                maintainAspectRatio: false,
                onClick: (_, elements) => {
                    if (elements.length > 0 && onClick) {
                        const idx = elements[0].index;
                        onClick(idx, labels[idx]);
                    }
                },
                plugins: {
                    legend: { display: datasets.length > 1, labels: { color: '#9ca3af' } },
                    tooltip: {
                        backgroundColor: 'rgba(18, 18, 23, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#a0a0b0',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: tooltipFormatter
                                ? (context) => `${context.dataset.label}: ${tooltipFormatter(context.parsed[horizontal ? 'x' : 'y'])}`
                                : undefined,
                        },
                    },
                },
                scales: {
                    x: {
                        stacked,
                        grid: { color: horizontal ? 'rgba(255,255,255,0.05)' : 'transparent' },
                        ticks: {
                            color: '#63636e',
                            callback: horizontal && yAxisFormatter ? (value) => yAxisFormatter(value as number) : undefined,
                        },
                    },
                    y: {
                        stacked,
                        grid: { color: horizontal ? 'transparent' : 'rgba(255,255,255,0.05)' },
                        ticks: {
                            color: '#63636e',
                            callback: !horizontal && yAxisFormatter ? (value) => yAxisFormatter(value as number) : undefined,
                        },
                    },
                },
            },
        });

        return () => { if (chartRef.current) chartRef.current.destroy(); };
    }, [labels, datasets, horizontal, stacked, yAxisFormatter, tooltipFormatter, onClick]);

    return (
        <div style={{ height, position: 'relative' }}>
            <canvas ref={canvasRef} />
        </div>
    );
};
