import io
import os
import duckdb
import pandas as pd
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_ANALYTICAL_PATH = BASE_DIR / "backend" / "db" / "rpk_analytical.duckdb"

class ObjectivesReportRequest(BaseModel):
    fecha_inicio: str
    fecha_fin: str
    cliente: Optional[str] = "ALL"

def get_duckdb_conn():
    if not DB_ANALYTICAL_PATH.exists():
        raise HTTPException(status_code=500, detail="Base de datos analítica no encontrada")
    return duckdb.connect(str(DB_ANALYTICAL_PATH), read_only=True)

def generate_objectives_pdf(req: ObjectivesReportRequest):
    conn = get_duckdb_conn()
    
    try:
        # Consulta para obtener la media de stock y el objetivo vigente (el último del periodo)
        query = f"""
            WITH ultimas_fechas AS (
                SELECT Articulo, MAX(Fecha) as max_f
                FROM existencias
                WHERE Fecha BETWEEN '{req.fecha_inicio}' AND '{req.fecha_fin}'
                GROUP BY Articulo
            ),
            objetivos_vigentes AS (
                SELECT e.Articulo, e.Stock_Objetivo
                FROM existencias e
                JOIN ultimas_fechas uf ON e.Articulo = uf.Articulo AND e.Fecha = uf.max_f
                WHERE e.Stock_Objetivo > 0
            )
            SELECT 
                e.Articulo, 
                MAX(e.Descripcion) as Descripcion,
                AVG(e.Cantidad) as Media_Cantidad,
                MAX(ov.Stock_Objetivo) as Objetivo,
                MAX(e.Cliente) as Cliente
            FROM existencias e
            JOIN objetivos_vigentes ov ON e.Articulo = ov.Articulo
            WHERE e.Fecha BETWEEN '{req.fecha_inicio}' AND '{req.fecha_fin}'
        """
        if req.cliente and req.cliente != "ALL":
            query += f" AND e.Cliente = '{req.cliente}'"
            
        query += " GROUP BY e.Articulo ORDER BY e.Articulo"
        
        df = conn.execute(query).df()
        
        if df.empty:
             raise HTTPException(status_code=404, detail="No hay datos de objetivos para el rango seleccionado.")

        # Cálculos de indicadores
        df['Cumplimiento_Pct'] = (df['Media_Cantidad'] / df['Objetivo']) * 100
        df['Desviacion_Abs'] = df['Media_Cantidad'] - df['Objetivo']
        
        # Categorización
        def get_status(pct):
            if pct <= 100: return "DENTRO"
            if pct <= 120: return "EXCESO LEVE"
            return "OVERSTOCK"

        df['Estado'] = df['Cumplimiento_Pct'].apply(get_status)
        
        total_articulos = len(df)
        dentro_objetivo = len(df[df['Cumplimiento_Pct'] <= 100])
        pct_exito = (dentro_objetivo / total_articulos * 100) if total_articulos > 0 else 0

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en Informe de Objetivos: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    # --------------- CONSTRUCCIÓN PDF ---------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleObj', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#E30613"), alignment=1, spaceAfter=20)
    h2_style = ParagraphStyle('H2Obj', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor("#1a1a1a"), spaceBefore=15, spaceAfter=10)
    normal_style = styles['Normal']
    
    # Header
    story.append(Paragraph("INFORME DE CUMPLIMIENTO DE STOCK OBJETIVO", title_style))
    story.append(Paragraph(f"Análisis de Medias: {req.fecha_inicio} al {req.fecha_fin}", ParagraphStyle('CenterLabel', parent=normal_style, alignment=1)))
    story.append(Spacer(1, 25))

    # 1. KPIs DE GESTIÓN
    story.append(Paragraph("1. KPIs de Cumplimiento de Objetivo", h2_style))
    
    kpi_data = [
        ["Métrica de Gestión", "Valor"],
        ["Artículos Analizados (con objetivo)", str(total_articulos)],
        ["Artículos en Objetivo (Stock Medio <= Obj)", str(dentro_objetivo)],
        ["% Índice de Cumplimiento Global", f"{pct_exito:.1f}%"]
    ]
    
    t_kpi = Table(kpi_data, colWidths=[3.5*inch, 2*inch])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 10),
        ('ALIGN', (1,1), (1,-1), 'CENTER'),
        ('BACKGROUND', (1,3), (1,3), colors.green if pct_exito > 80 else (colors.orange if pct_exito > 50 else colors.red)),
        ('TEXTCOLOR', (1,3), (1,3), colors.white)
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 20))

    # 2. LISTADO DETALLADO (TOP 50 por desviación)
    story.append(Paragraph("2. Detalle de Desviación por Artículo", h2_style))
    
    # Ordenar por el que más sobrepasa el objetivo
    df_sorted = df.sort_values(by='Cumplimiento_Pct', ascending=False).head(60)
    
    header_table = ["Referencia", "S. Medio", "Objetivo", "% Cumpl.", "Estado"]
    table_data = [header_table]
    
    for _, r in df_sorted.iterrows():
        color_status = colors.green if r['Cumplimiento_Pct'] <= 100 else (colors.orange if r['Cumplimiento_Pct'] <= 120 else colors.red)
        table_data.append([
            str(r['Articulo']),
            f"{int(r['Media_Cantidad']):,}",
            f"{int(r['Objetivo']):,}",
            f"{r['Cumplimiento_Pct']:.1f}%",
            Paragraph(f"<font color='{color_status.hexval()}'><b>{r['Estado']}</b></font>", normal_style)
        ])
    
    t_detail = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1*inch, 1.5*inch])
    t_detail.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.1, colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,1), (3,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_detail)
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>* El análisis calcula la media aritmética de las existencias diarias en el periodo seleccionado y la compara con el objetivo vigente al final del periodo.</i>", 
                           ParagraphStyle('Footnote', parent=normal_style, fontSize=7, textColor=colors.grey)))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/stock-objectives")
async def create_objectives_report(req: ObjectivesReportRequest):
    try:
        pdf_buffer = generate_objectives_pdf(req)
        filename = f"Analisis_Objetivos_{datetime.now().strftime('%Y%m%d')}.pdf"
        headers = { 'Content-Disposition': f'attachment; filename="{filename}"' }
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
