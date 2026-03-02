'use client';

import React, { useRef, useEffect } from 'react';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

interface LineChartProps {
    labels: string[];
    datasets: {
        label: string;
        data: number[];
        borderColor?: string;
        backgroundColor?: string;
        fill?: boolean;
    }[];
    yAxisFormatter?: (value: number) => string;
    tooltipFormatter?: (value: number) => string;
    height?: string;
}

export const LineChart: React.FC<LineChartProps> = ({
    labels,
    datasets,
    yAxisFormatter,
    tooltipFormatter,
    height = '400px',
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const chartRef = useRef<Chart | null>(null);

    useEffect(() => {
        if (!canvasRef.current) return;
        const ctx = canvasRef.current.getContext('2d');
        if (!ctx) return;

        if (chartRef.current) {
            chartRef.current.destroy();
        }

        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(227, 6, 19, 0.4)');
        gradient.addColorStop(1, 'rgba(227, 6, 19, 0)');

        chartRef.current = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: datasets.map(ds => ({
                    ...ds,
                    borderColor: ds.borderColor || '#E30613',
                    backgroundColor: ds.fill ? gradient : (ds.backgroundColor || 'transparent'),
                    fill: ds.fill ?? true,
                    tension: 0.4,
                    borderWidth: 3,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#E30613',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2,
                })),
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: datasets.length > 1 },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(18, 18, 23, 0.9)',
                        titleColor: '#fff',
                        bodyColor: '#a0a0b0',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: tooltipFormatter
                                ? (context) => tooltipFormatter(context.parsed.y)
                                : undefined,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: {
                            color: '#63636e',
                            callback: yAxisFormatter
                                ? (value) => yAxisFormatter(value as number)
                                : undefined,
                        },
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#63636e', maxRotation: 45, minRotation: 45 },
                    },
                },
            },
        });

        return () => {
            if (chartRef.current) {
                chartRef.current.destroy();
            }
        };
    }, [labels, datasets, yAxisFormatter, tooltipFormatter]);

    return (
        <div style={{ height, position: 'relative' }}>
            <canvas ref={canvasRef} />
        </div>
    );
};
