'use client';
import { useState } from 'react';

export default function SimulationControls({ onSimulate }: { onSimulate: (data: any) => void }) {
  const [params, setParams] = useState({
    article_name: '404003',
    total_lot: 240000,
    transfer_batch: 40000,
    rate_a: 1000,
    rate_c: 2200
  });
  
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setParams({
      ...params,
      [e.target.name]: e.target.type === 'number' ? Number(e.target.value) : e.target.value
    });
  };

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      const result = await res.json();
      if (result.status === 'success') {
        onSimulate(result.data);
      }
    } catch (e) {
      console.error(e);
      alert("Error conectando con el simulador backend");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm text-gray-400 mb-1">Nombre Artículo</label>
        <input 
          type="text" name="article_name" value={params.article_name} onChange={handleChange}
          className="w-full bg-[#0f0f0f] border border-gray-700 rounded-md p-2 text-white focus:border-[#E30613] focus:outline-none"
        />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Lote Producción Total (pzas)</label>
        <input 
          type="number" name="total_lot" value={params.total_lot} onChange={handleChange}
          className="w-full bg-[#0f0f0f] border border-gray-700 rounded-md p-2 text-white focus:border-[#E30613] focus:outline-none"
        />
      </div>
      <div className="border-t border-gray-800 pt-4 mt-4">
        <label className="block text-sm font-semibold text-[#E30613] mb-1">Lote de Transferencia</label>
        <div className="flex flex-col gap-2">
            <input 
            type="range" name="transfer_batch" 
            min="1000" max={params.total_lot} step="1000"
            value={params.transfer_batch} onChange={handleChange}
            className="w-full accent-[#E30613]"
            />
            <input 
            type="number" name="transfer_batch" 
            value={params.transfer_batch} onChange={handleChange}
            className="w-full bg-[#0f0f0f] border border-gray-700 rounded-md p-2 text-white focus:border-[#E30613] focus:outline-none text-center font-mono"
            />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-gray-800 pt-4 mt-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Cadencia Maq. Origen (p/h)</label>
          <input 
            type="number" name="rate_a" value={params.rate_a} onChange={handleChange}
            className="w-full bg-[#0f0f0f] border border-gray-700 rounded-md p-2 text-white focus:border-[#E30613] focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Cadencia Maq. Destino (p/h)</label>
          <input 
            type="number" name="rate_c" value={params.rate_c} onChange={handleChange}
            className="w-full bg-[#0f0f0f] border border-gray-700 rounded-md p-2 text-white focus:border-[#E30613] focus:outline-none"
          />
        </div>
      </div>
      
      <button 
        onClick={handleSimulate}
        disabled={loading}
        className="w-full bg-[#E30613] hover:bg-red-700 text-white font-bold py-3 px-4 rounded-md mt-6 transition-colors disabled:opacity-50"
      >
        {loading ? 'Simulando...' : 'Simular y Comparar'}
      </button>
    </div>
  );
}
