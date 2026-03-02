'use client';

import React, { useEffect, useState } from 'react';
import { KPICard } from '@/components/ui/KPICard';
import { ModuleBox } from '@/components/layout/ModuleBox';
import { StatusBadge } from '@/components/layout/StatusBadge';
import { ChatPopup } from '@/components/layout/ChatPopup';
import type { HubStats } from '@/types/api-contracts';

export default function PortalPage() {
  const [stats, setStats] = useState<HubStats | null>(null);
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    fetch('/api/v1/hub_stats')
      .then(r => r.json())
      .then((data: HubStats) => {
        if (!data.stock) return;
        setStats(data);
        setIsOnline(true);
      })
      .catch(() => setIsOnline(false));
  }, []);

  return (
    <div className="min-h-screen bg-[var(--color-dark-bg)] p-8 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex justify-between items-center mb-12">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-white m-0">
            RPK<span className="text-[var(--color-rpk-red)]">NEXUS</span>
          </h1>
        </div>
        <StatusBadge isOnline={isOnline} />
      </header>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <KPICard
          title="STOCK"
          value={stats ? stats.stock.total.toLocaleString('es-ES') : '---'}
          label="Cantidad en piezas"
        />
        <KPICard
          title="Saturación Media"
          value={stats ? `${stats.saturation}%` : '---'}
          label="Centros de Trabajo"
        />
        <KPICard
          title="Cobertura Real"
          value={stats ? stats.cobertura : '---'}
          label="Días de producción"
        />
      </div>

      {/* Modules */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <ModuleBox
          icon="📦"
          title="Dashboard de Stock"
          description="Acceso al análisis detallado de existencias, ubicaciones y obsoletos."
          href="/stock"
        />
        <ModuleBox
          icon="⏳"
          title="Dashboard de Tiempos"
          description="Visualización de cargas de trabajo, OEE y saturación por máquina."
          href="/tiempos"
        />
        <ModuleBox
          icon="🎮"
          title="Simulador de Producción"
          description="Simulación de escenarios, cambios de cadencia y optimización de fleje."
          href="/simulador"
        />
        <ModuleBox
          icon="💰"
          title="Pedidos de Venta"
          description="Análisis de pedidos pendientes, fechas de entrega e importe total de cartera."
          href="/pedidos"
          isNew
        />
        <ModuleBox
          icon="🚚"
          title="Albaranes de Entrega"
          description="KPIs financieros, análisis de clientes y evolución histórica de expediciones."
          href="/albaranes"
          isNew
        />
      </div>

      {/* Chat Assistant */}
      <ChatPopup />
    </div>
  );
}
