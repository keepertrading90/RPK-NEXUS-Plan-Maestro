'use client';
import { useState, useMemo } from 'react';

type Scenario = {
  id: number;
  ts: string;
  articleA: string;
  articleB: string;
  transferA: number;
  transferB: number;
  leadTimeA: number;
  leadTimeB: number;
  setupH: number;
  idleH: number;
  efficiency: number;
};

export default function Home() {
  const [maqA, setMaqA] = useState({ article: '404003', cadence: 1000, lot: 240000, transfer: 40000 });
  const [maqB, setMaqB] = useState({ article: '453288', cadence: 1200, lot: 150000, transfer: 30000 });
  const [maqC, setMaqC] = useState({ cadence: 2200 });

  // Simulador de Eventos Discretos para Gantt (Zero-Latency)
  const schedule = useMemo(() => {
    let batchesA = Math.ceil(maqA.lot / maqA.transfer);
    let batchesB = Math.ceil(maqB.lot / maqB.transfer);

    let queue = [];
    let ganttA = [];
    let ganttB = [];
    let ganttC = [];

    // Generar llegadas a cola
    for (let i = 0; i < batchesA; i++) {
       let size = i === batchesA - 1 && maqA.lot % maqA.transfer !== 0 ? maqA.lot % maqA.transfer : maqA.transfer;
       let duration = size / maqA.cadence;
       let end = (i + 1) * duration;
       ganttA.push({ start: i * duration, end, type: 'A', size });
       queue.push({ time: end, type: 'A', size, id: `A${i}` });
    }
    
    for (let i = 0; i < batchesB; i++) {
       let size = i === batchesB - 1 && maqB.lot % maqB.transfer !== 0 ? maqB.lot % maqB.transfer : maqB.transfer;
       let duration = size / maqB.cadence;
       let end = (i + 1) * duration;
       ganttB.push({ start: i * duration, end, type: 'B', size });
       queue.push({ time: end, type: 'B', size, id: `B${i}` });
    }

    // Ordenar por tiempo de llegada
    queue.sort((a, b) => a.time - b.time);

    let currentTimeC = 0;
    let waitTimes = { A: 0, B: 0 };
    let setupTimeCount = 0;
    let lastProcessedType = null;

    // Procesar en Maq C
    queue.forEach(item => {
      // Si C está libre cuando llega el lote, empieza a procesar
      if (currentTimeC < item.time) {
         currentTimeC = item.time;
      }
      
      // Comprobar si hay cambio de modelo (Reglaje)
      if (lastProcessedType !== null && lastProcessedType !== item.type) {
         // Añadir 1 hora de reglaje (setup) a la máquina C
         ganttC.push({
            start: currentTimeC,
            end: currentTimeC + 1,
            type: 'SETUP',
            size: 'Reglaje'
         });
         currentTimeC += 1; // Avanza el reloj
         setupTimeCount += 1;
      }

      // Añadir la espera que el lote sufrió antes de entrar (y después de posibles reglajes)
      let wait = currentTimeC - item.time;
      waitTimes[item.type] += wait;

      let duration = item.size / maqC.cadence;
      ganttC.push({
         start: currentTimeC,
         end: currentTimeC + duration,
         type: item.type,
         size: item.size
      });

      currentTimeC += duration;
      lastProcessedType = item.type;
    });

    let leadTimeA = ganttC.filter(i => i.type === 'A').pop()?.end || 0;
    let leadTimeB = ganttC.filter(i => i.type === 'B').pop()?.end || 0;
    let totalSpanC = Math.max(leadTimeA, leadTimeB);
    
    // Cálculo del Tiempo Ocioso: Tiempo total desde t=0 hasta que acaba el último artículo, MENOS lo que estuvo trabajando o de reglaje.
    let activeTimeC = (maqA.lot / maqC.cadence) + (maqB.lot / maqC.cadence);
    let idleTimeC = totalSpanC - activeTimeC - setupTimeCount;

    return { ganttA, ganttB, ganttC, waitTimes, setupTimeCount, idleTimeC: Math.max(0, idleTimeC), leadTimeA, leadTimeB, totalSpan: Math.max(leadTimeA, leadTimeB, ganttA.at(-1)?.end || 0, ganttB.at(-1)?.end || 0) };
  }, [maqA, maqB, maqC]);

  const [history, setHistory] = useState<Scenario[]>([]);
  const [scenarioName, setScenarioName] = useState('');

  const efficiency = schedule.totalSpan > 0
    ? (((schedule.totalSpan - schedule.idleTimeC - schedule.setupTimeCount) / schedule.totalSpan) * 100)
    : 0;

  const handleSave = () => {
    const label = scenarioName.trim() || `Escenario ${history.length + 1}`;
    const entry: Scenario = {
      id: Date.now(),
      ts: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
      articleA: maqA.article,
      articleB: maqB.article,
      transferA: maqA.transfer,
      transferB: maqB.transfer,
      leadTimeA: schedule.leadTimeA,
      leadTimeB: schedule.leadTimeB,
      setupH: schedule.setupTimeCount,
      idleH: schedule.idleTimeC,
      efficiency,
    };
    setHistory(prev => [entry, ...prev].slice(0, 10));
    setScenarioName('');
  };

  return (
    <main className="min-h-screen bg-[#0f0f0f] text-white p-8 font-sans">
      <div className="w-full space-y-8">
        <header className="flex items-center border-b border-gray-800 pb-4">
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <span className="bg-[#E30613] w-3 h-8 block rounded-sm"></span>
            Simulador Interactivo de Lotes de Transferencia
          </h1>
        </header>

        {/* Diagram Area */}
        <div className="flex flex-col lg:flex-row items-center justify-between gap-6 py-6 relative">
          
          {/* Col 1: Maquinas Origen */}
          <div className="flex flex-col gap-8 w-full lg:w-1/3 z-10">
            {/* MAQ A */}
            <div className="bg-[#1a1a1a] border-2 border-gray-700 rounded-xl p-6 relative">
              <h2 className="text-2xl font-bold mb-4 flex justify-between text-[#E30613]">
                <span>MAQ A</span>
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Cadencia (p/h):</span>
                  <input type="number" className="bg-[#0f0f0f] border border-gray-700 w-20 text-center rounded text-white" value={maqA.cadence} onChange={e => setMaqA({...maqA, cadence: Number(e.target.value)})} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Lote Produc.:</span>
                  <input type="number" className="bg-[#0f0f0f] border border-gray-700 w-20 text-center rounded text-white" value={maqA.lot} onChange={e => setMaqA({...maqA, lot: Number(e.target.value)})} />
                </div>
                <div className="pt-4 border-t border-gray-800">
                  <label className="text-sm font-bold text-white mb-2 flex justify-between">
                    Lote Transferencia: <span className="text-[#E30613]">{maqA.transfer} pzas</span>
                  </label>
                  <input type="range" min="1000" max={maqA.lot} step="1000" className="w-full accent-[#E30613]" value={maqA.transfer} onChange={e => setMaqA({...maqA, transfer: Number(e.target.value)})} />
                  <p className="text-xs text-gray-500 mt-1">Gantt: {Math.ceil(maqA.lot / maqA.transfer)} bloque(s)</p>
                </div>
              </div>
            </div>

            {/* MAQ B */}
            <div className="bg-[#1a1a1a] border-2 border-gray-700 rounded-xl p-6 relative">
              <h2 className="text-2xl font-bold mb-4 flex justify-between text-blue-400">
                <span>MAQ B</span>
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Cadencia (p/h):</span>
                  <input type="number" className="bg-[#0f0f0f] border border-gray-700 w-20 text-center rounded text-white" value={maqB.cadence} onChange={e => setMaqB({...maqB, cadence: Number(e.target.value)})} />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Lote Produc.:</span>
                  <input type="number" className="bg-[#0f0f0f] border border-gray-700 w-20 text-center rounded text-white" value={maqB.lot} onChange={e => setMaqB({...maqB, lot: Number(e.target.value)})} />
                </div>
                <div className="pt-4 border-t border-gray-800">
                  <label className="text-sm font-bold text-white mb-2 flex justify-between">
                    Lote Transferencia: <span className="text-blue-400">{maqB.transfer} pzas</span>
                  </label>
                  <input type="range" min="1000" max={maqB.lot} step="1000" className="w-full accent-blue-500" value={maqB.transfer} onChange={e => setMaqB({...maqB, transfer: Number(e.target.value)})} />
                  <p className="text-xs text-gray-500 mt-1">Gantt: {Math.ceil(maqB.lot / maqB.transfer)} bloque(s)</p>
                </div>
              </div>
            </div>
          </div>

          {/* Col 2: Maquina Secundario (Cuello Botella) */}
          <div className="w-full lg:w-1/3 flex justify-center z-10">
            <div className="bg-[#242424] border-2 border-green-600 rounded-xl p-8 shadow-xl w-full">
              <h2 className="text-3xl font-bold mb-4 text-center">MAQ C</h2>
              <div className="flex flex-col items-center space-y-4">
                <div className="flex justify-between items-center w-full text-md">
                  <span className="text-gray-400 mr-4">Cadencia (p/h):</span>
                  <input type="number" className="bg-[#0f0f0f] border border-gray-500 w-24 text-center rounded text-white font-bold p-1" value={maqC.cadence} onChange={e => setMaqC({cadence: Number(e.target.value)})} />
                </div>
                
                <div className="mt-8 bg-[#0f0f0f] p-4 rounded-lg w-full border border-gray-800 space-y-3">
                  <h3 className="text-gray-500 text-xs uppercase tracking-widest text-center border-b border-gray-800 pb-2">Penalizaciones Maq C</h3>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-[#E30613] font-bold">Espera Mq. A:</span>
                    <span className="font-mono">{schedule.waitTimes.A.toFixed(1)}h</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-blue-400 font-bold">Espera Mq. B:</span>
                    <span className="font-mono">{schedule.waitTimes.B.toFixed(1)}h</span>
                  </div>
                  <div className="flex justify-between items-center text-sm border-t border-gray-800 pt-3">
                    <span className="text-yellow-500 font-bold">Total Cambios/Reglajes:</span>
                    <span className="font-mono text-yellow-500 bg-yellow-900/40 px-2 rounded-sm">{schedule.setupTimeCount}h</span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-400 font-bold">Tiempo Ocioso (Sin carga):</span>
                    <span className="font-mono text-gray-400 bg-gray-800/50 px-2 rounded-sm">{schedule.idleTimeC.toFixed(1)}h</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Col 3: Resultados Globales */}
          <div className="w-full lg:w-1/3 flex justify-end z-10">
            <div className="bg-[#1a1a1a] border-2 border-gray-700 rounded-xl p-6 shadow-xl w-full flex flex-col justify-center">
              <h2 className="text-2xl font-bold mb-6 text-center text-gray-200">Fin / Lead Time</h2>
              
              <div className="space-y-6">
                <div className="bg-[#0f0f0f] p-4 rounded-lg flex justify-between items-center border border-[#E30613]/50">
                  <span className="text-gray-400 block text-xs">FINALIZA A<br/><strong className="text-white text-xl">{schedule.leadTimeA.toFixed(1)}h</strong></span>
                </div>

                <div className="bg-[#0f0f0f] p-4 rounded-lg flex justify-between items-center border border-blue-500/50">
                  <span className="text-gray-400 block text-xs">FINALIZA B<br/><strong className="text-white text-xl">{schedule.leadTimeB.toFixed(1)}h</strong></span>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* GANTT CHART VISUALIZER */}
        <div className="mt-12 bg-[#1a1a1a] p-6 rounded-xl border border-gray-700 overflow-x-auto relative">
          <div className="flex justify-between items-center border-b border-gray-800 pb-3 mb-6">
            <h2 className="text-xl font-bold text-white">Cronograma Visual (Gantt Interactivo)</h2>
            {/* Leyenda */}
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-[#E30613] rounded-sm inline-block"></span> MAQ A</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded-sm inline-block"></span> MAQ B</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-yellow-500 rounded-sm inline-block"></span> Reglaje</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-gray-700 rounded-sm inline-block border border-dashed border-gray-500"></span> Ocioso</span>
            </div>
          </div>

          <div className="min-w-[800px] space-y-4 pb-4">
            
            {/* Eje de tiempo referencial con 4 marcas */}
            <div className="relative h-5 text-xs text-gray-500 mb-2">
              <span className="absolute left-0">0h</span>
              <span className="absolute" style={{left: '25%'}}>{(schedule.totalSpan * 0.25).toFixed(0)}h</span>
              <span className="absolute" style={{left: '50%'}}>{(schedule.totalSpan * 0.5).toFixed(0)}h</span>
              <span className="absolute" style={{left: '75%'}}>{(schedule.totalSpan * 0.75).toFixed(0)}h</span>
              <span className="absolute right-0">{schedule.totalSpan.toFixed(0)}h</span>
              {/* líneas verticales guía */}
              {[25, 50, 75].map(p => (
                <span key={p} className="absolute top-0 bottom-0 border-l border-dashed border-gray-800" style={{left: `${p}%`}} />
              ))}
            </div>

            {/* Fila MAQ A */}
            <div className="flex items-center gap-2">
              <div className="w-20 text-sm font-bold text-[#E30613] shrink-0">MAQ A</div>
              <div className="flex-1 h-8 bg-[#0f0f0f] border border-gray-800 relative rounded overflow-hidden">
                {schedule.ganttA.map((block, i) => (
                  <div key={i}
                    className="absolute h-full bg-[#E30613] border-r border-[#1a1a1a] opacity-80"
                    style={{ left: `${(block.start / schedule.totalSpan) * 100}%`, width: `${((block.end - block.start) / schedule.totalSpan) * 100}%` }}
                    title={`Lote ${i+1}: ${block.size} pzas | Inicio: ${block.start.toFixed(1)}h | Fin: ${block.end.toFixed(1)}h`}
                  />
                ))}
              </div>
            </div>

            {/* Fila MAQ B */}
            <div className="flex items-center gap-2">
              <div className="w-20 text-sm font-bold text-blue-400 shrink-0">MAQ B</div>
              <div className="flex-1 h-8 bg-[#0f0f0f] border border-gray-800 relative rounded overflow-hidden">
                {schedule.ganttB.map((block, i) => (
                  <div key={i}
                    className="absolute h-full bg-blue-500 border-r border-[#1a1a1a] opacity-80"
                    style={{ left: `${(block.start / schedule.totalSpan) * 100}%`, width: `${((block.end - block.start) / schedule.totalSpan) * 100}%` }}
                    title={`Lote ${i+1}: ${block.size} pzas | Inicio: ${block.start.toFixed(1)}h | Fin: ${block.end.toFixed(1)}h`}
                  />
                ))}
              </div>
            </div>

            {/* Separador MAQ C */}
            <div className="border-t border-gray-700 pt-3 mt-2">
              <div className="flex items-center gap-2">
                <div className="w-20 text-sm font-bold text-green-400 shrink-0">MAQ C<br/><span className="text-[10px] text-gray-500 font-normal">(Cuello Bot.)</span></div>
                <div className="flex-1 h-12 bg-[#0f0f0f] border border-green-900 relative rounded overflow-hidden shadow-inner">
                  {schedule.ganttC.map((block, i) => {
                    const color = block.type === 'A' ? 'bg-[#E30613]' : block.type === 'B' ? 'bg-blue-500' : 'bg-yellow-500';
                    const label = block.type === 'SETUP' ? '⚙ Reglaje' : `${block.size}`;
                    const tooltip = block.type === 'SETUP'
                      ? `Reglaje (1h) | ${block.start.toFixed(1)}h → ${block.end.toFixed(1)}h`
                      : `${block.type === 'A' ? maqA.article : maqB.article} | ${block.size} pzas | ${block.start.toFixed(1)}h → ${block.end.toFixed(1)}h`;
                    return (
                      <div key={i}
                        className={`absolute h-10 top-1 ${color} border-l border-r border-[#1a1a1a] flex items-center justify-center text-[9px] font-bold overflow-hidden rounded-sm shadow`}
                        style={{ left: `${(block.start / schedule.totalSpan) * 100}%`, width: `${((block.end - block.start) / schedule.totalSpan) * 100}%` }}
                        title={tooltip}
                      >
                        {label}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <p className="text-gray-600 text-xs text-center pt-1">Pasa el ratón por encima de cada bloque para ver detalles. MAQ C procesa en orden de llegada (FIFO). Los bloques amarillos son cambios de referencia (reglajes).</p>
          </div>
        </div>

        {/* SECCIÓN INFERIOR: IZQUIERDA=GUARDAR/HISTORIAL | DERECHA=KPIs */}
        <div className="mt-6 flex flex-col lg:flex-row gap-6">

          {/* ── IZQUIERDA: Guardar escenario + Historial ── */}
          <div className="w-full lg:w-2/5 flex flex-col gap-4">

            {/* Guardar escenario */}
            <div className="bg-[#1a1a1a] rounded-xl border border-gray-700 p-5">
              <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <span className="text-green-400">💾</span> Guardar Escenario
              </h2>
              <input
                type="text"
                placeholder="Nombre del escenario (opcional)"
                className="w-full bg-[#0f0f0f] border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-600 mb-3 focus:outline-none focus:border-gray-500"
                value={scenarioName}
                onChange={e => setScenarioName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSave()}
              />
              <button
                onClick={handleSave}
                className="w-full bg-[#E30613] hover:bg-red-700 active:scale-95 text-white font-bold py-3 rounded-lg transition-all text-sm tracking-wide shadow-lg shadow-red-900/30"
              >
                GUARDAR ESCENARIO ACTUAL
              </button>
            </div>

            {/* Historial */}
            <div className="bg-[#1a1a1a] rounded-xl border border-gray-700 flex-1 overflow-hidden">
              <div className="bg-[#242424] px-5 py-3 border-b border-gray-700 flex items-center justify-between">
                <h2 className="text-sm font-bold text-white">🕓 Historial de Escenarios</h2>
                {history.length > 0 && (
                  <button onClick={() => setHistory([])} className="text-xs text-gray-600 hover:text-red-400 transition-colors">Borrar todo</button>
                )}
              </div>
              <div className="divide-y divide-gray-800 max-h-72 overflow-y-auto">
                {history.length === 0 ? (
                  <p className="text-gray-600 text-xs text-center py-8 px-4">Aún no hay escenarios guardados.<br/>Pulsa el botón de arriba para registrar el escenario actual.</p>
                ) : history.map((s, idx) => (
                  <div key={s.id} className={`px-5 py-3 hover:bg-[#242424] transition-colors ${idx === 0 ? 'border-l-2 border-[#E30613]' : ''}`}>
                    <div className="flex justify-between items-center text-xs text-gray-500 mb-1">
                      <span className="font-bold text-gray-300">{`#${history.length - idx} · ${s.ts}`}</span>
                      <span className={`font-bold px-2 py-0.5 rounded-full text-[10px] ${s.efficiency >= 80 ? 'bg-green-900/50 text-green-400' : s.efficiency >= 60 ? 'bg-yellow-900/50 text-yellow-400' : 'bg-red-900/50 text-red-400'}`}>
                        {s.efficiency.toFixed(0)}% efic.
                      </span>
                    </div>
                    <div className="flex gap-4 text-xs text-gray-500">
                      <span><span className="text-[#E30613]">A:</span> Lt={s.leadTimeA.toFixed(0)}h T={s.transferA.toLocaleString()}</span>
                      <span><span className="text-blue-400">B:</span> Lt={s.leadTimeB.toFixed(0)}h T={s.transferB.toLocaleString()}</span>
                    </div>
                    <div className="flex gap-4 text-xs text-gray-600 mt-0.5">
                      <span>⚙ Reglajes: {s.setupH}h</span>
                      <span>⏸ Ocioso: {s.idleH.toFixed(1)}h</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── DERECHA: KPIs Verticales ── */}
          <div className="w-full lg:w-3/5 bg-[#1a1a1a] rounded-xl border border-gray-700 overflow-hidden">
            <div className="bg-[#242424] px-6 py-3 border-b border-gray-700">
              <h2 className="text-lg font-bold text-white">📊 KPIs del Escenario Actual</h2>
            </div>
            <div className="grid grid-cols-2 divide-x divide-y divide-gray-800">
              {/* Fila 1 */}
              <div className="p-5 flex items-center gap-4">
                <div className="bg-[#E30613]/10 p-2 rounded-lg"><span className="text-xl">🔴</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Lead Time A</p>
                  <p className="text-2xl font-black text-[#E30613]">{schedule.leadTimeA.toFixed(1)}<span className="text-sm font-normal text-gray-400">h</span></p>
                  <p className="text-xs text-gray-600">{maqA.article} · {maqA.transfer.toLocaleString()} pzas/lote</p>
                </div>
              </div>
              <div className="p-5 flex items-center gap-4">
                <div className="bg-blue-900/20 p-2 rounded-lg"><span className="text-xl">🔵</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Lead Time B</p>
                  <p className="text-2xl font-black text-blue-400">{schedule.leadTimeB.toFixed(1)}<span className="text-sm font-normal text-gray-400">h</span></p>
                  <p className="text-xs text-gray-600">{maqB.article} · {maqB.transfer.toLocaleString()} pzas/lote</p>
                </div>
              </div>
              {/* Fila 2 */}
              <div className="p-5 flex items-center gap-4">
                <div className="bg-yellow-900/20 p-2 rounded-lg"><span className="text-xl">⚙️</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Reglajes en MAQ C</p>
                  <p className="text-2xl font-black text-yellow-400">{schedule.setupTimeCount}<span className="text-sm font-normal text-gray-400">h perdidas</span></p>
                  <p className="text-xs text-gray-600">{schedule.setupTimeCount} cambio(s) de referencia</p>
                </div>
              </div>
              <div className="p-5 flex items-center gap-4">
                <div className="bg-gray-800 p-2 rounded-lg"><span className="text-xl">⏸</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Tiempo Ocioso C</p>
                  <p className="text-2xl font-black text-gray-300">{schedule.idleTimeC.toFixed(1)}<span className="text-sm font-normal text-gray-400">h</span></p>
                  <p className="text-xs text-gray-600">MAQ C esperando material</p>
                </div>
              </div>
              {/* Fila 3 */}
              <div className="p-5 flex items-center gap-4">
                <div className="bg-red-900/20 p-2 rounded-lg"><span className="text-xl">📦</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Cola WIP · A</p>
                  <p className="text-2xl font-black text-red-300">{schedule.waitTimes.A.toFixed(1)}<span className="text-sm font-normal text-gray-400">h espera</span></p>
                  <p className="text-xs text-gray-600">Piezas de A esperando en suelo</p>
                </div>
              </div>
              <div className="p-5 flex items-center gap-4">
                <div className="bg-blue-900/10 p-2 rounded-lg"><span className="text-xl">📦</span></div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest">Cola WIP · B</p>
                  <p className="text-2xl font-black text-blue-300">{schedule.waitTimes.B.toFixed(1)}<span className="text-sm font-normal text-gray-400">h espera</span></p>
                  <p className="text-xs text-gray-600">Piezas de B esperando en suelo</p>
                </div>
              </div>
              {/* Fila 4: Eficiencia ocupa toda la fila */}
              <div className="p-5 col-span-2 flex items-center justify-between bg-[#0f0f0f]">
                <div className="flex items-center gap-4">
                  <div className="bg-green-900/20 p-2 rounded-lg"><span className="text-2xl">⚡</span></div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-widest">Eficiencia Global MAQ C</p>
                    <p className="text-xs text-gray-600 mt-0.5">Tiempo produciendo ÷ tiempo total del escenario</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-4xl font-black ${efficiency >= 80 ? 'text-green-400' : efficiency >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {efficiency.toFixed(1)}<span className="text-xl font-normal text-gray-400">%</span>
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    {efficiency >= 80 ? '✅ Alta eficiencia' : efficiency >= 60 ? '⚠️ Eficiencia media' : '❌ Baja eficiencia'}
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>
    </main>
  );
}

