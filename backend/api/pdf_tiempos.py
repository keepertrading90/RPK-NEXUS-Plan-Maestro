import io
import os
import sqlite3
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "rpk_industrial.db")

class PDFTiemposRequest(BaseModel):
    fecha_analisis: Optional[str] = None
    centro: Optional[str] = "ALL"
    incluir_graficos: Optional[bool] = True

def format_number(value):
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def generate_tiempos_pdf(req: PDFTiemposRequest):
    conn = get_db_connection()
    if not req.fecha_analisis:
        df_max = pd.read_sql("SELECT MAX(Fecha) as max_f FROM tiempos_carga", conn)
        fecha_target = df_max['max_f'].iloc[0]
    else:
        fecha_target = req.fecha_analisis

    # 1. Resumen de carga total
    query_total = f"SELECT SUM(Carga_Dia) as total FROM tiempos_carga WHERE Fecha = '{fecha_target}'"
    if req.centro != "ALL":
        query_total += f" AND Centro = '{req.centro}'"
    total_carga_actual = pd.read_sql(query_total, conn)['total'].iloc[0] or 0.0

    query_prev_date = f"SELECT MAX(Fecha) as prev_f FROM tiempos_carga WHERE Fecha <= date('{fecha_target}', '-7 day')"
    prev_date = pd.read_sql(query_prev_date, conn)['prev_f'].iloc[0]
    if prev_date:
        query_total_prev = f"SELECT SUM(Carga_Dia) as total FROM tiempos_carga WHERE Fecha = '{prev_date}'"
        if req.centro != "ALL":
            query_total_prev += f" AND Centro = '{req.centro}'"
        total_carga_prev = pd.read_sql(query_total_prev, conn)['total'].iloc[0] or 0.0
    else:
        total_carga_prev = 0.0
        
    delta_percent = ((total_carga_actual - total_carga_prev) / total_carga_prev * 100) if total_carga_prev > 0 else 0

    # 2. Ranking de saturación por centro (Cuellos de botella)
    query_centros = f"""
        SELECT Centro, Carga_Dia as Carga_Total, Media_Mensual as Media_Diaria
        FROM tiempos_carga
        WHERE Fecha = '{fecha_target}'
    """
    if req.centro != "ALL":
        query_centros += f" AND Centro = '{req.centro}'"
    query_centros += " ORDER BY Carga_Dia DESC LIMIT 15"
    df_centros = pd.read_sql(query_centros, conn)

    # 3. Desglose detallado de Órdenes de Fabricación (OFs) Críticas
    query_ofs = f"""
        SELECT Centro, Articulo, OF as OrdenFabricacion, SUM(Horas_Pte) as Horas_Pendientes
        FROM tiempos_detalle_articulo
        WHERE Fecha = '{fecha_target}'
    """
    if req.centro != "ALL":
        query_ofs += f" AND Centro = '{req.centro}'"
    query_ofs += " GROUP BY Centro, Articulo, OF ORDER BY Horas_Pendientes DESC LIMIT 20"
    df_ofs = pd.read_sql(query_ofs, conn)

    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#E30613"), spaceAfter=15)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=14, textColor=colors.darkblue, spaceAfter=10)
    normal_style = styles["Normal"]
    
    story.append(Paragraph("WORKLOAD & SATURATION REPORT - RPK NEXUS v5.5", title_style))
    story.append(Paragraph(f"<b>Fecha de Análisis (Snapshot):</b> {fecha_target}", normal_style))
    story.append(Paragraph(f"<b>Filtro Centro:</b> {req.centro}", normal_style))
    story.append(Spacer(1, 20))

    # 1. RESUMEN EJECUTIVO
    story.append(Paragraph("1. Resumen Ejecutivo (Carga Activa)", subtitle_style))
    delta_color = "red" if delta_percent > 0 else "green"
    delta_text = f"<font color='{delta_color}'>{delta_percent:+.2f}% vs semana anterior</font>"
    
    resumen_data = [
        ["Carga Total Acumulada", f"{format_number(total_carga_actual)} Horas"],
        ["Tendencia vs 7 días", Paragraph(delta_text, normal_style)],
        ["Estado Planta", "Saturación Crítica" if delta_percent > 10 else ("Estable" if abs(delta_percent) <= 10 else "Liberación de Capacidad")]
    ]
    t_resumen = Table(resumen_data, colWidths=[3*inch, 3*inch])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.lightgrey),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 20))

    # 2. TOP CENTROS
    story.append(Paragraph("2. Top 15 Centros Más Saturados (Cuellos de Botella)", subtitle_style))
    if not df_centros.empty:
        centros_data = [["Centro", "Carga Activa (h)", "Media Histórica (h)", "Desviación"]]
        for _, row in df_centros.iterrows():
            desv_h = row['Carga_Total'] - row['Media_Diaria']
            desv_txt = f"{format_number(desv_h)}h"
            centros_data.append([
                str(row['Centro']), 
                format_number(row['Carga_Total']), 
                format_number(row['Media_Diaria']),
                desv_txt
            ])
            
        t_centros = Table(centros_data, colWidths=[2*inch, 1.8*inch, 1.8*inch, 1.4*inch])
        t_centros.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
            ('TEXTCOLOR', (3,1), (3,-1), colors.red), 
        ]))
        story.append(t_centros)
        story.append(Paragraph("<i>* Desviación positiva indica posible sobrecarga frente a la tendencia del centro.</i>", styles["Italic"]))
    else:
        story.append(Paragraph("No hay carga de centros para esta fecha.", normal_style))
    story.append(Spacer(1, 20))

    story.append(PageBreak())

    # 3. OFs CRITICAS
    story.append(Paragraph("3. Top 20 Órdenes de Fabricación (OF) Pendientes Críticas", subtitle_style))
    if not df_ofs.empty:
        ofs_data = [["O.F.", "Artículo", "Centro", "Horas Pendientes"]]
        for _, row in df_ofs.iterrows():
            ofs_data.append([
                str(row['OrdenFabricacion']), 
                str(row['Articulo'])[:20],
                str(row['Centro']),
                format_number(row['Horas_Pendientes'])
            ])
            
        t_ofs = Table(ofs_data, colWidths=[1.8*inch, 2.5*inch, 1.2*inch, 1.5*inch])
        t_ofs.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_ofs)
        story.append(Paragraph("<i>* Órdenes de fabricación individuales de mayor duración estimadas.</i>", styles["Italic"]))
    else:
        story.append(Paragraph("No hay O.F. en este periodo.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/tiempos-pdf")
def create_tiempos_pdf(req: PDFTiemposRequest):
    pdf_buffer = generate_tiempos_pdf(req)
    headers = {
        'Content-Disposition': f'attachment; filename="Workload_Saturation_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
