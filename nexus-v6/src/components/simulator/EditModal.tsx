'use client';

import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const EditModal: React.FC = () => {
    const { editingArticle, setEditingArticle, currentData, addOverride, localOverrides } = useSimulatorStore();
    const [fields, setFields] = useState({ demanda: 0, cadencia: 0, oee: 0, setup_min: 0, traslado: 0 });

    const article = currentData?.centros.flatMap(c => c.articulos || []).find(a => a.articulo === editingArticle);

    useEffect(() => {
        if (article) {
            const existingOverrides = localOverrides.filter(o => o.articulo === editingArticle);
            setFields({
                demanda: existingOverrides.find(o => o.field === 'demanda')?.value ?? article.demanda,
                cadencia: existingOverrides.find(o => o.field === 'cadencia')?.value ?? article.cadencia,
                oee: existingOverrides.find(o => o.field === 'oee')?.value ?? article.oee,
                setup_min: existingOverrides.find(o => o.field === 'setup_min')?.value ?? (article.setup_min || 0),
                traslado: existingOverrides.find(o => o.field === 'traslado')?.value ?? (article.traslado || 0),
            });
        }
    }, [editingArticle, article, localOverrides]);

    if (!editingArticle || !article) return null;

    const handleSave = () => {
        const editableFields = [
            { key: 'demanda', label: 'Demanda' },
            { key: 'cadencia', label: 'Cadencia (PPM)' },
            { key: 'oee', label: 'OEE (%)' },
            { key: 'setup_min', label: 'Setup (min)' },
            { key: 'traslado', label: 'Traslado' },
        ] as const;

        editableFields.forEach(f => {
            const original = article[f.key] ?? 0;
            const newVal = fields[f.key];
            if (newVal !== original) {
                addOverride({
                    articulo: editingArticle,
                    centro: article.centro,
                    field: f.key,
                    original,
                    value: newVal,
                    label: f.label,
                });
            }
        });
        setEditingArticle(null);
    };

    const inputCls = "w-full bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2 rounded-lg text-sm outline-none focus:border-[var(--color-rpk-red)]";

    return (
        <Modal isOpen={true} onClose={() => setEditingArticle(null)} title={`Editar: ${editingArticle}`} width="max-w-lg">
            <div className="space-y-4">
                {[
                    { label: 'Demanda (uds)', key: 'demanda' as const },
                    { label: 'Cadencia (p/min)', key: 'cadencia' as const },
                    { label: 'OEE (%)', key: 'oee' as const },
                    { label: 'Setup (min)', key: 'setup_min' as const },
                    { label: 'Traslado', key: 'traslado' as const },
                ].map(f => (
                    <div key={f.key}>
                        <label className="block text-[var(--color-text-muted)] text-xs uppercase mb-1">{f.label}</label>
                        <input type="number" step="any" value={fields[f.key]}
                            onChange={e => setFields({ ...fields, [f.key]: Number(e.target.value) })}
                            className={inputCls} />
                    </div>
                ))}
                <div className="flex gap-3 pt-4">
                    <button onClick={handleSave}
                        className="flex-1 py-2.5 bg-[var(--color-rpk-red)] text-white rounded-lg font-medium text-sm border-none cursor-pointer hover:bg-[var(--color-rpk-dark)]">
                        Guardar Cambios
                    </button>
                    <button onClick={() => setEditingArticle(null)}
                        className="flex-1 py-2.5 bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] rounded-lg text-sm border border-[var(--color-glass-border)] cursor-pointer hover:text-white">
                        Cancelar
                    </button>
                </div>
            </div>
        </Modal>
    );
};
