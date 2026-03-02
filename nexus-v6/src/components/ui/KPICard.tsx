// ui/KPICard.tsx
import React from 'react';

interface KPICardProps {
    title: string;
    value: string | number;
    label?: string;
    className?: string;
}

export const KPICard: React.FC<KPICardProps> = ({ title, value, label, className = '' }) => {
    return (
        <div className={`bg-[var(--color-dark-surface)] p-6 rounded-2xl border border-[var(--color-glass-border)] flex flex-col items-center justify-center text-center ${className}`}>
            <h3 className="text-[var(--color-text-muted)] mt-0 mb-4 font-semibold text-[0.85rem] uppercase tracking-widest border-b border-[#333] pb-2 w-full">{title}</h3>
            <div className="text-[2.5rem] font-bold my-2 text-white">{value}</div>
            {label && <div className="text-[0.8rem] text-[var(--color-text-muted)] font-medium uppercase tracking-wider">{label}</div>}
        </div>
    );
};
