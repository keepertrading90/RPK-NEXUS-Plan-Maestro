'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { useSimulatorStore } from '@/store/useSimulatorStore';

export const SaveModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
    const { saveScenario, localOverrides } = useSimulatorStore();
    const [name, setName] = useState('');
    const [saving, setSaving] = useState(false);

    const handleSave = async () => {
        if (!name.trim()) return;
        setSaving(true);
        const ok = await saveScenario(name.trim());
        setSaving(false);
        if (ok) {
            setName('');
            onClose();
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Guardar Escenario" width="max-w-md">
            <div className="space-y-4">
                <p className="text-[var(--color-text-muted)] text-sm">
                    Se guardarán <strong className="text-white">{localOverrides.length}</strong> modificaciones como un nuevo escenario.
                </p>
                <div>
                    <label className="block text-[var(--color-text-muted)] text-xs uppercase mb-1">Nombre del Escenario</label>
                    <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Ej: Escenario Turno Extra"
                        className="w-full bg-[var(--color-dark-surface-2)] border border-[var(--color-glass-border)] text-white px-3 py-2.5 rounded-lg text-sm outline-none focus:border-[var(--color-rpk-red)]" />
                </div>
                <div className="flex gap-3">
                    <button onClick={handleSave} disabled={saving || !name.trim()}
                        className="flex-1 py-2.5 bg-[var(--color-rpk-red)] text-white rounded-lg font-medium text-sm border-none cursor-pointer hover:bg-[var(--color-rpk-dark)] disabled:opacity-50">
                        {saving ? 'Guardando...' : '💾 Guardar'}
                    </button>
                    <button onClick={onClose}
                        className="flex-1 py-2.5 bg-[var(--color-dark-surface-2)] text-[var(--color-text-muted)] rounded-lg text-sm border border-[var(--color-glass-border)] cursor-pointer hover:text-white">
                        Cancelar
                    </button>
                </div>
            </div>
        </Modal>
    );
};
