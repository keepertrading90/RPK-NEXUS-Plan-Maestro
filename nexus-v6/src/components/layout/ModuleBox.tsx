import React from 'react';
import Link from 'next/link';

interface ModuleBoxProps {
    title: string;
    description: string;
    href: string;
    icon: string;
    isNew?: boolean;
}

export const ModuleBox: React.FC<ModuleBoxProps> = ({ title, description, href, icon, isNew = false }) => {
    return (
        <div
            className={`
        glass rounded-2xl p-6 
        transition-all duration-300 ease-out
        hover:translate-y-[-4px] hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)]
        ${isNew ? 'border-l-4 border-l-[var(--color-rpk-red)]' : ''}
      `}
        >
            <h2 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                <span className="text-2xl">{icon}</span>
                {title}
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4 leading-relaxed">{description}</p>
            <Link
                href={href}
                className="
          inline-flex items-center px-5 py-2.5 
          bg-[var(--color-rpk-red)] text-white 
          rounded-lg font-medium text-sm
          no-underline
          transition-all duration-200
          hover:bg-[var(--color-rpk-dark)] hover:shadow-[0_0_15px_rgba(227,6,19,0.4)]
        "
            >
                Abrir Módulo
            </Link>
        </div>
    );
};
