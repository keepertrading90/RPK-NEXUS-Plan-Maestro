'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSimulatorStore } from '@/store/useSimulatorStore';
import { ScenarioTabs } from '@/components/simulator/ScenarioTabs';
import { FilterBar } from '@/components/simulator/FilterBar';
import { SaturationChart } from '@/components/simulator/SaturationChart';
import { CapacitySummary } from '@/components/simulator/CapacitySummary';
import { ArticleTable } from '@/components/simulator/ArticleTable';
import { EditModal } from '@/components/simulator/EditModal';
import { SaveModal } from '@/components/simulator/SaveModal';
import { ChangesPanel } from '@/components/simulator/ChangesPanel';
import { CompareView } from '@/components/simulator/CompareView';

export default function SimuladorPage() {
    const {
        isLoading, currentScenarioName, isComparisonMode,
        loadSimulation, loadScenarios, localOverrides,
    } = useSimulatorStore();

    const [showSave, setShowSave] = useState(false);

    useEffect(() => {
        loadScenarios();
        loadSimulation('base');
    }, [loadScenarios, loadSimulation]);

    return (
        <div className="min-h-screen bg-[var(--color-dark-bg)]">
            {/* Header */}
            <header className="flex items-center justify-between px-8 py-5 border-b border-[var(--color-glass-border)]">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-[var(--color-text-muted)] hover:text-white transition-colors no-underline">← Portal</Link>
                    <h1 className="text-2xl font-bold text-white m-0">🎮 Simulador de Producción</h1>
                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-glass-border)]">
                        {currentScenarioName}
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    {localOverrides.length > 0 && (
                        <button onClick={() => setShowSave(true)}
                            className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium border-none cursor-pointer hover:bg-emerald-700 shadow-[0_0_10px_rgba(16,185,129,0.3)]">
                            💾 Guardar Escenario ({localOverrides.length})
                        </button>
                    )}
                    {isLoading && (
                        <div className="flex items-center gap-2 text-[var(--color-text-muted)] text-sm">
                            <div className="w-4 h-4 border-2 border-[var(--color-rpk-red)] border-t-transparent rounded-full animate-spin" />
                            Calculando...
                        </div>
                    )}
                </div>
            </header>

            <main className="p-6 max-w-[1920px] mx-auto space-y-4">
                {/* Scenario Tabs */}
                <ScenarioTabs />

                {isComparisonMode ? (
                    <CompareView />
                ) : (
                    <>
                        {/* Filters */}
                        <FilterBar />

                        {/* Changes Panel (if any) */}
                        <ChangesPanel />

                        {/* Capacity Summary */}
                        <CapacitySummary />

                        {/* Chart */}
                        <SaturationChart />

                        {/* Article Table */}
                        <ArticleTable />
                    </>
                )}
            </main>

            {/* Modals */}
            <EditModal />
            <SaveModal isOpen={showSave} onClose={() => setShowSave(false)} />
        </div>
    );
}
