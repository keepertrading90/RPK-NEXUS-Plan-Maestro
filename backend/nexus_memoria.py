"""
nexus_memoria.py — Memoria Conversacional RPK NEXUS
────────────────────────────────────────────────────
Mantiene historial por session_id (máx 8 turnos en memoria).
Inyecta el contexto previo en el prompt de Qwen para que
entienda referencias como "¿y cuánto hay de ese artículo?"
"""

from collections import deque
from datetime import datetime

class NexusMemoria:
    """Gestión de conversaciones multi-turno por sesión."""
    
    def __init__(self, max_turns: int = 8):
        self.sessions: dict[str, deque] = {}
        self.max_turns = max_turns
    
    def add(self, session_id: str, role: str, content: str):
        """Añade un mensaje al historial de la sesión."""
        if session_id not in self.sessions:
            self.sessions[session_id] = deque(maxlen=self.max_turns * 2)
        self.sessions[session_id].append({
            "role": role,
            "content": content[:400],   # Truncar para no inflar el prompt
            "ts": datetime.now().strftime("%H:%M")
        })
    
    def get_history(self, session_id: str) -> list:
        return list(self.sessions.get(session_id, []))
    
    def format_for_prompt(self, session_id: str) -> str:
        """Formatea los últimos 3 turnos para inyectar en el prompt de Qwen."""
        history = self.get_history(session_id)
        if not history:
            return ""
        # Solo los últimos 3 intercambios (6 mensajes)
        recientes = history[-6:]
        lineas = []
        for msg in recientes:
            quien = "Ismael" if msg["role"] == "user" else "Quen"
            lineas.append(f"[{msg['ts']}] {quien}: {msg['content']}")
        return "\n\n[CONVERSACION PREVIA - usa este contexto para entender referencias]:\n" + "\n".join(lineas) + "\n"
    
    def clear(self, session_id: str):
        """Limpia el historial de una sesión."""
        self.sessions.pop(session_id, None)
    
    def stats(self) -> dict:
        return {
            "sesiones_activas": len(self.sessions),
            "turnos_totales": sum(len(v) for v in self.sessions.values())
        }


# Singleton global
nexus_memoria = NexusMemoria()
