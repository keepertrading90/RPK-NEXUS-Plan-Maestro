"""
nexus_rag.py — Fase 3: Motor RAG ligero para RPK NEXUS
───────────────────────────────────────────────────────
Al arrancar, indexa en memoria:
  - Catálogo de artículos (de existencias + maestro_fleje)
  - Catálogo de centros/máquinas (de maestro_fleje + carga_centros)
  - Relaciones artículo-centro
  - Últimas cifras clave (stock, carga, OEE)

Cuando el usuario pregunta:
  1. Busca entidades reconocibles (artículo, centro) en la pregunta
  2. Recupera el contexto exacto de DuckDB para esas entidades
  3. Inyecta ese contexto en el prompt de Qwen → respuesta precisa
"""

import duckdb
import json
import re
import os
import threading
import time
from pathlib import Path

DUCK_DB_PATH = Path(r"C:\Users\ismael.rodriguez\MIS HERRAMIENTAS\Plan Maestro RPK NEXUS\backend\db\rpk_analytical.duckdb")

class NexusRAG:
    """Índice en memoria del universo de datos NEXUS."""
    
    def __init__(self):
        self.articulos: dict = {}      # {"422016": {"stock": 55M, "cliente": "THYSS", ...}}
        self.centros: dict = {}         # {"142": {"oee": 0.87, "piezas_hora": 1200, ...}}
        self.art_to_centros: dict = {}  # {"422016": [142, 260, ...]}
        self.carga_reciente: dict = {}  # {"260": 12.15, ...}
        self._ready = False
        self._lock = threading.Lock()
    
    def build_index(self):
        """Construye el índice en memoria desde DuckDB. Se ejecuta en background."""
        if not DUCK_DB_PATH.exists():
            print("[RAG] DuckDB no encontrada. Índice no construido.")
            return
        
        try:
            con = duckdb.connect(str(DUCK_DB_PATH), read_only=True)
            
            # ── 1. Índice de artículos ──────────────────────────────────────
            df_art = con.execute("""
                SELECT 
                    CAST(e.Articulo AS VARCHAR) as art,
                    e.Descripcion,
                    SUM(e.Cantidad) as stock_total,
                    STRING_AGG(DISTINCT e.Cliente, ', ') as clientes,
                    MAX(e.Stock_Objetivo) as stock_objetivo
                FROM existencias e
                GROUP BY e.Articulo, e.Descripcion
                LIMIT 5000
            """).fetchdf()
            
            for _, row in df_art.iterrows():
                art_id = str(row['art']).strip()
                self.articulos[art_id] = {
                    "descripcion": row.get('Descripcion', ''),
                    "stock": int(row['stock_total']) if row['stock_total'] else 0,
                    "clientes": row.get('clientes', ''),
                    "stock_objetivo": float(row['stock_objetivo']) if row['stock_objetivo'] else 0,
                }
            
            # ── 2. Índice de centros desde maestro_fleje ────────────────────
            df_centros = con.execute("""
                SELECT 
                    CAST(Centro AS VARCHAR) as centro,
                    COUNT(DISTINCT Articulo) as n_articulos,
                    AVG(Piezas_Hora) as piezas_hora_media,
                    AVG(OEE) as oee_media,
                    AVG(Cadencia_Actual) as cadencia_media
                FROM maestro_fleje
                GROUP BY Centro
            """).fetchdf()
            
            for _, row in df_centros.iterrows():
                cid = str(row['centro']).strip()
                self.centros[cid] = {
                    "n_articulos": int(row['n_articulos']),
                    "piezas_hora_media": round(float(row['piezas_hora_media']), 1) if row['piezas_hora_media'] else 0,
                    "oee_media": round(float(row['oee_media']), 3) if row['oee_media'] else 0,
                    "cadencia_media": round(float(row['cadencia_media']), 1) if row['cadencia_media'] else 0,
                    "fuente": "maestro_fleje"
                }
            
            # ── 3. Añadir centros de carga_centros (producción real) ─────────
            df_carga = con.execute("""
                SELECT Centro, AVG(Carga_Dia) as carga_media
                FROM carga_centros
                GROUP BY Centro
            """).fetchdf()
            
            for _, row in df_carga.iterrows():
                cid = str(row['Centro']).strip()
                self.carga_reciente[cid] = round(float(row['carga_media']), 2)
                if cid not in self.centros:
                    self.centros[cid] = {"fuente": "carga_centros"}
                self.centros[cid]["carga_media_dia"] = self.carga_reciente[cid]
            
            # ── 4. Relaciones artículo → centros (del maestro) ──────────────
            df_rel = con.execute("""
                SELECT CAST(Articulo AS VARCHAR) as art, CAST(Centro AS VARCHAR) as centro
                FROM maestro_fleje
            """).fetchdf()
            
            for _, row in df_rel.iterrows():
                a = str(row['art']).strip()
                c = str(row['centro']).strip()
                if a not in self.art_to_centros:
                    self.art_to_centros[a] = []
                self.art_to_centros[a].append(c)
            
            con.close()
            
            with self._lock:
                self._ready = True
            
            print(f"[RAG] Indice construido: {len(self.articulos)} articulos, {len(self.centros)} centros")
        
        except Exception as e:
            print(f"[RAG] Error construyendo indice: {e}")
    
    def start_async(self):
        """Construye el índice en background sin bloquear el servidor."""
        t = threading.Thread(target=self.build_index, daemon=True)
        t.start()
    
    # ─── BÚSQUEDA DE ENTIDADES ─────────────────────────────────────────────────
    
    def find_articulo(self, texto: str) -> tuple[str, dict]:
        """Busca un artículo en el índice por ID exacto o parcial."""
        if not self._ready:
            return None, {}
        texto = texto.strip().upper()
        # Exacto primero
        if texto in self.articulos:
            return texto, self.articulos[texto]
        # Parcial
        for art_id, data in self.articulos.items():
            if texto in art_id or art_id in texto:
                return art_id, data
        return None, {}
    
    def find_centro(self, texto: str) -> tuple[str, dict]:
        """Busca un centro/máquina en el índice."""
        if not self._ready:
            return None, {}
        texto = texto.strip()
        if texto in self.centros:
            return texto, self.centros[texto]
        for cid, data in self.centros.items():
            if texto in cid:
                return cid, data
        return None, {}
    
    # ─── EXTRACCIÓN DE CONTEXTO ────────────────────────────────────────────────
    
    def get_context_for_query(self, pregunta: str) -> str:
        """
        Analiza la pregunta, extrae entidades y devuelve contexto
        específico listo para inyectar en el prompt de Qwen.
        """
        if not self._ready:
            return ""
        
        pregunta_upper = pregunta.upper().strip()
        numeros = re.findall(r'\d+', pregunta)
        contexto_partes = []
        
        # ── Buscar artículos mencionados ──────────────────────────────
        for num in numeros:
            art_id, art_data = self.find_articulo(num)
            if art_id and art_data:
                centros_art = self.art_to_centros.get(art_id, [])
                ctx = f"ARTICULO {art_id}: stock={art_data['stock']:,} pzs, clientes='{art_data['clientes']}', stockObj={art_data['stock_objetivo']:,.0f}"
                if centros_art:
                    ctx += f", centros_produccion={centros_art[:5]}"
                if art_data.get('descripcion'):
                    ctx += f", descripcion='{art_data['descripcion']}'"
                contexto_partes.append(ctx)
                break  # Solo primer artículo encontrado
        
        # ── Buscar centros/máquinas mencionados ──────────────────────
        for num in numeros:
            cid, c_data = self.find_centro(num)
            if cid and c_data:
                ctx = f"CENTRO/MAQUINA {cid}: {json.dumps(c_data, ensure_ascii=False)}"
                contexto_partes.append(ctx)
                break
        
        if contexto_partes:
            return "\n\n[CONTEXTO RPK NEXUS - usa estos datos en tu respuesta]:\n" + "\n".join(contexto_partes)
        
        return ""
    
    def status(self) -> dict:
        """Devuelve estado del índice RAG."""
        return {
            "ready": self._ready,
            "articulos_indexados": len(self.articulos),
            "centros_indexados": len(self.centros),
        }


# Singleton global
nexus_rag = NexusRAG()
