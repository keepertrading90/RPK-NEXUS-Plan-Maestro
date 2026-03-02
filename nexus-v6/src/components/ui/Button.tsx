import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
    children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({ variant = 'primary', children, className = '', ...props }) => {
    const baseStyles = "px-4 py-2 rounded-lg font-medium transition-all duration-200 cursor-pointer flex items-center justify-center gap-2";

    const variants = {
        primary: "bg-[var(--color-rpk-red)] text-white border-none hover:bg-rpk-dark shadow-[0_0_15px_rgba(227,6,19,0.3)] hover:shadow-[0_0_20px_rgba(227,6,19,0.5)]",
        secondary: "bg-[var(--color-dark-surface-2)] text-[var(--color-text-main)] border border-[var(--color-glass-border)] hover:bg-[#3A3A3A]",
        outline: "bg-transparent text-[var(--color-rpk-red)] border border-[var(--color-rpk-red)] hover:bg-[rgba(227,6,19,0.1)]",
        ghost: "bg-transparent text-[var(--color-text-muted)] border-none hover:text-[var(--color-rpk-red)]"
    };

    return (
        <button className={`${baseStyles} ${variants[variant]} ${className}`} {...props}>
            {children}
        </button>
    );
};
