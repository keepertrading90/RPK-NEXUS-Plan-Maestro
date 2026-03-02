import React, { useEffect } from 'react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    width?: string;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children, width = 'max-w-2xl' }) => {
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        if (isOpen) {
            document.body.style.overflow = 'hidden';
            window.addEventListener('keydown', handleEsc);
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
            window.removeEventListener('keydown', handleEsc);
        };
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
            <div className={`bg-[var(--color-dark-surface)] border border-[var(--color-glass-border)] rounded-2xl w-full ${width} shadow-2xl relative animate-slide-up`}>

                {/* Header */}
                <div className="flex justify-between items-center p-6 border-b border-[var(--color-glass-border)]">
                    <h2 className="text-xl font-bold text-white m-0">{title}</h2>
                    <button
                        onClick={onClose}
                        className="text-[var(--color-text-muted)] hover:text-white hover:bg-[var(--color-dark-surface-2)] p-2 rounded-lg transition-colors cursor-pointer"
                    >
                        ✕
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto max-h-[70vh]">
                    {children}
                </div>
            </div>
        </div>
    );
};
