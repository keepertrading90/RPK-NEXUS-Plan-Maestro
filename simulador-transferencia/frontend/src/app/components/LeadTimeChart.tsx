'use client';

export default function LeadTimeChart({ data }: { data: any }) {
  if (!data) {
    return (
      <div className="flex items-center justify-center h-full bg-[#1a1a1a] border border-gray-800 rounded-xl min-h-[400px]">
        <p className="text-gray-500">Configura los parámetros y haz clic en Simular</p>
      </div>
    );
  }

  const { traditional, proposed } = data;

  const renderMetric = (label: string, oldVal: number, newVal: number, suffix = 'h') => {
    const diff = oldVal - newVal;
    const percent = ((diff / oldVal) * 100).toFixed(1);
    const isGood = diff > 0;
    return (
      <div className="bg-[#0f0f0f] border border-gray-800 rounded-lg p-4">
        <p className="text-sm text-gray-400 mb-1">{label}</p>
        <div className="flex items-end justify-between">
          <p className="text-3xl font-bold text-white">{newVal}{suffix}</p>
          <div className="text-right">
            <p className="text-xs text-gray-500 line-through">{oldVal}{suffix}</p>
            <p className={`text-sm font-semibold flex items-center ${isGood ? 'text-green-500' : 'text-red-500'}`}>
              {isGood ? '↓' : '↑'} {Math.abs(diff).toFixed(1)}{suffix} ({percent}%)
            </p>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#1a1a1a] p-6 rounded-xl border border-gray-800 shadow-xl">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            Impacto Global
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderMetric("Lead Time Total", traditional.lead_time_hours, proposed.lead_time_hours)}
          {renderMetric("WIP Máximo (Piezas en cola)", traditional.max_queue, proposed.max_queue, ' pzas')}
        </div>
      </div>

      <div className="bg-[#1a1a1a] p-6 rounded-xl border border-gray-800 shadow-xl overflow-hidden">
        <h2 className="text-xl font-semibold mb-6">Comparativa de Gantt Simplificada (Tiempo)</h2>
        
        <div className="space-y-8">
          {/* Lote Tradicional */}
          <div>
            <h3 className="text-md text-gray-400 mb-2">Modelo Tradicional (Lote Completo)</h3>
            <div className="relative h-12 bg-[#0f0f0f] rounded-md overflow-hidden flex border border-gray-800">
                <div 
                  className="h-full bg-gray-600 border-r border-[#1a1a1a] flex items-center justify-center text-xs font-bold" 
                  style={{ width: '50%' }}
                  title="Máquina Origen Procesando"
                >
                  Maq. Origen
                </div>
                <div 
                  className="h-full bg-[#E30613] flex items-center justify-center text-xs font-bold text-white" 
                  style={{ width: '50%' }}
                  title="Máquina Destino Procesando (Esperó al lote completo)"
                >
                  Maq. Destino (Esperando {traditional.timeline[0]?.wait_time_for_c}h)
                </div>
            </div>
            <p className="text-xs text-right mt-1 text-gray-500">Total: {traditional.lead_time_hours}h</p>
          </div>

          {/* Lotes de Transferencia */}
          <div>
            <h3 className="text-md text-gray-400 mb-2">Modelo Propuesto (Lote de Transferencia)</h3>
            <div className="relative h-20 bg-[#0f0f0f] rounded-md overflow-hidden border border-gray-800 p-1 flex flex-col gap-1 relative overflow-x-auto">
              <div className="flex h-1/2 w-full">
                {proposed.timeline.map((batch: any, i: number) => {
                  const width = (batch.pieces / traditional.timeline[0].pieces) * 50; 
                  return (
                    <div 
                      key={`a-${i}`} 
                      className="h-full bg-gray-600 border-r border-[#1a1a1a] text-[10px] flex items-center justify-center" 
                      style={{ width: `${width}%` }}
                    >
                      B{i+1}
                    </div>
                  );
                })}
              </div>
              <div className="flex h-1/2 w-full relative">
                 {/* Offset for wait time */}
                 <div style={{ width: `${(proposed.timeline[0].wait_time_for_c / traditional.lead_time_hours) * 100}%` }}></div>
                 {proposed.timeline.map((batch: any, i: number) => {
                  const width = (batch.pieces / traditional.timeline[0].pieces) * 50; 
                  return (
                    <div 
                      key={`c-${i}`} 
                      className="h-full bg-[#E30613] border-r border-[#1a1a1a] text-[10px] flex items-center justify-center text-white" 
                      style={{ width: `${width}%` }}
                    >
                       C{i+1}
                    </div>
                  );
                })}
              </div>
            </div>
             <p className="text-xs text-right mt-1 text-gray-500">Total: {proposed.lead_time_hours}h</p>
          </div>

          <p className="text-sm text-gray-400 mt-4 bg-[#E30613]/10 border border-[#E30613]/20 p-3 rounded-lg">
            <strong>Análisis:</strong> Al usar lotes de transferencia, la Máquina Destino no espera a que el Lote Total termine. Empieza a producir en cuanto recibe el primer lote de {proposed.timeline[0]?.pieces} piezas (tan pronto como {proposed.timeline[0]?.wait_time_for_c}h). El WIP (Inventario en Proceso) disminuye considerablemente de {traditional.max_queue} a {proposed.max_queue} piezas.
          </p>

        </div>
      </div>
    </div>
  );
}
