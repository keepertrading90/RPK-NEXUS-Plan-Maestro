'use client';

import React, { useState, useRef, useEffect } from 'react';

export const ChatPopup: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<{ role: 'user' | 'nexus'; text: string }[]>([
        { role: 'nexus', text: 'Hola Ismael, soy el asistente NEXUS. ¿En qué puedo ayudarte hoy?' }
    ]);
    const [input, setInput] = useState('');
    const bodyRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (bodyRef.current) {
            bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
        }
    }, [messages]);

    const sendMessage = async () => {
        const text = input.trim();
        if (!text) return;

        setMessages(prev => [...prev, { role: 'user', text }]);
        setInput('');

        try {
            const res = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });
            const data = await res.json();
            setMessages(prev => [...prev, { role: 'nexus', text: data.response || 'Sin respuesta' }]);
        } catch {
            setMessages(prev => [...prev, { role: 'nexus', text: 'Error de conexión con el servidor.' }]);
        }
    };

    const handleKey = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') sendMessage();
    };

    return (
        <>
            {/* Trigger */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="
          fixed bottom-6 right-6 z-50
          w-14 h-14 rounded-full
          bg-[var(--color-rpk-red)] text-white text-2xl
          flex items-center justify-center
          shadow-[0_4px_20px_rgba(227,6,19,0.5)]
          hover:scale-110 transition-transform duration-200
          cursor-pointer border-none
        "
            >
                🤖
            </button>

            {/* Chat Window */}
            {isOpen && (
                <div className="fixed bottom-24 right-6 z-50 w-[360px] rounded-2xl overflow-hidden shadow-2xl border border-[var(--color-glass-border)] bg-[var(--color-dark-surface)]">
                    {/* Header */}
                    <div className="flex justify-between items-center px-4 py-3 bg-[var(--color-dark-surface-2)] border-b border-[var(--color-glass-border)]">
                        <strong className="text-white text-sm">Nexus Assistant</strong>
                        <button onClick={() => setIsOpen(false)} className="text-[var(--color-text-muted)] hover:text-white cursor-pointer bg-transparent border-none text-lg">✕</button>
                    </div>

                    {/* Body */}
                    <div ref={bodyRef} className="p-4 h-[300px] overflow-y-auto flex flex-col gap-3">
                        {messages.map((msg, i) => (
                            <div key={i} className={`text-sm ${msg.role === 'user' ? 'text-white' : 'text-[var(--color-rpk-red)]'}`}>
                                <strong>{msg.role === 'user' ? 'Tú' : 'Nexus'}:</strong>{' '}
                                <span className="whitespace-pre-wrap">{msg.text}</span>
                            </div>
                        ))}
                    </div>

                    {/* Input */}
                    <div className="flex border-t border-[var(--color-glass-border)]">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKey}
                            placeholder="Pregunta algo..."
                            className="
                flex-1 bg-transparent text-white text-sm
                px-4 py-3 border-none outline-none
                placeholder-[var(--color-text-muted)]
              "
                        />
                        <button
                            onClick={sendMessage}
                            className="
                px-4 bg-[var(--color-rpk-red)] text-white 
                border-none cursor-pointer text-lg
                hover:bg-[var(--color-rpk-dark)] transition-colors
              "
                        >
                            ➤
                        </button>
                    </div>
                </div>
            )}
        </>
    );
};
