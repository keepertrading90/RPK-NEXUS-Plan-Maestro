import React from 'react';

interface StatusBadgeProps {
    isOnline: boolean;
    label?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ isOnline, label = 'DATABASE ONLINE' }) => {
    return (
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--color-dark-surface)] border border-[var(--color-glass-border)]">
            <div
                className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-red-500 shadow-[0_0_8px_#ef4444]'}`}
            />
            <span className="text-xs font-medium text-[var(--color-text-muted)] tracking-widest uppercase">
                {isOnline ? label : 'OFFLINE'}
            </span>
        </div>
    );
};
