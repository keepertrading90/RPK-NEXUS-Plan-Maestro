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

class PDFPedidosRequest(BaseModel):
    fecha_analisis: Optional[str] = None
    incluir_graficos: Optional[bool] = True

def format_number(value):
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_currency(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def generate_pedidos_pdf(req: PDFPedidosRequest):
    conn = get_db_connection()
    if not req.fecha_analisis:
        df_max = pd.read_sql("SELECT MAX(Fecha_Snapshot) as max_f FROM pedidos_venta", conn)
        fecha_target = df_max['max_f'].iloc[0]
    else:
        fecha_target = req.fecha_analisis

    # 1. Resumen de Cartera Total
    query_total = f"SELECT SUM(Cant_Pendiente) as total_piezas, SUM(Importe_EUR) as total_eur, COUNT(DISTINCT Articulo) as refs FROM pedidos_venta WHERE Fecha_Snapshot = '{fecha_target}'"
    res_actual = pd.read_sql(query_total, conn)
    total_piezas = res_actual['total_piezas'].iloc[0] or 0.0
    total_eur = res_actual['total_eur'].iloc[0] or 0.0
    total_refs = res_actual['refs'].iloc[0] or 0

    query_prev_date = f"SELECT MAX(Fecha_Snapshot) as prev_f FROM pedidos_venta WHERE Fecha_Snapshot <= date('{fecha_target}', '-7 day')"
    prev_date = pd.read_sql(query_prev_date, conn)['prev_f'].iloc[0]
    if prev_date:
        query_total_prev = f"SELECT SUM(Importe_EUR) as total_eur FROM pedidos_venta WHERE Fecha_Snapshot = '{prev_date}'"
        total_eur_prev = pd.read_sql(query_total_prev, conn)['total_eur'].iloc[0] or 0.0
    else:
        total_eur_prev = 0.0
        
    delta_percent = ((total_eur - total_eur_prev) / total_eur_prev * 100) if total_eur_prev > 0 else 0

    # 2. Top 15 Artículos con Mayor Cartera Pendiente (Importe)
    query_top_articulos = f"""
        SELECT Articulo, Referencia, SUM(Cant_Pendiente) as Piezas, SUM(Importe_EUR) as Importe
        FROM pedidos_venta
        WHERE Fecha_Snapshot = '{fecha_target}'
        GROUP BY Articulo, Referencia
        ORDER BY Importe DESC LIMIT 15
    """
    df_articulos = pd.read_sql(query_top_articulos, conn)

    # 3. Riesgos Inminentes: Próximas entregas en 15 días con más valor
    query_inminente = f"""
        SELECT Fecha_Entrega, Articulo, Cant_Pendiente as Piezas, Importe_EUR as Importe
        FROM pedidos_venta
        WHERE Fecha_Snapshot = '{fecha_target}' AND Fecha_Entrega BETWEEN '{fecha_target}' AND date('{fecha_target}', '+15 day')
        ORDER BY Fecha_Entrega ASC, Importe DESC LIMIT 20
    """
    df_inminente = pd.read_sql(query_inminente, conn)

    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#E30613"), spaceAfter=15)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=14, textColor=colors.darkblue, spaceAfter=10)
    normal_style = styles["Normal"]
    
    story.append(Paragraph("SALES ORDERS & BACKLOG REPORT - RPK NEXUS v5.5", title_style))
    story.append(Paragraph(f"<b>Fecha de Análisis (Snapshot):</b> {fecha_target}", normal_style))
    story.append(Spacer(1, 20))

    # 1. RESUMEN EJECUTIVO
    story.append(Paragraph("1. Resumen Ejecutivo (Cartera Activa)", subtitle_style))
    delta_color = "green" if delta_percent > 0 else "red"  # Incremento de pedidos es positivo
    delta_text = f"<font color='{delta_color}'>{delta_percent:+.2f}% vs semana anterior</font>"
    
    resumen_data = [
        ["Importe Total Pendiente", format_currency(total_eur)],
        ["Tendencia USD/EUR (7d)", Paragraph(delta_text, normal_style)],
        ["Piezas Totales a Fabricar", format_number(total_piezas)],
        ["Referencias Afectadas", str(int(total_refs))],
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

    # 2. TOP ARTÍCULOS
    story.append(Paragraph("2. Top 15 Artículos con Mayor Cartera (€)", subtitle_style))
    if not df_articulos.empty:
        articulos_data = [["Artículo", "Ref Cliente", "Piezas", "Importe EUR"]]
        for _, row in df_articulos.iterrows():
            articulos_data.append([
                str(row['Articulo']), 
                str(row['Referencia'])[:15], 
                format_number(row['Piezas']),
                format_currency(row['Importe'])
            ])
            
        t_arts = Table(articulos_data, colWidths=[2.2*inch, 1.8*inch, 1.3*inch, 1.7*inch])
        t_arts.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
            ('TEXTCOLOR', (3,1), (3,-1), colors.HexColor("#E30613")), 
        ]))
        story.append(t_arts)
    else:
        story.append(Paragraph("No hay cartera en esta fecha.", normal_style))
    story.append(Spacer(1, 20))

    story.append(PageBreak())

    # 3. ENTREGAS CRITICAS (Próximas 15 días)
    story.append(Paragraph("3. Entregas Próximas Críticas (15 días)", subtitle_style))
    if not df_inminente.empty:
        inm_data = [["Fecha Entrega", "Artículo", "Piezas", "Importe EUR"]]
        for _, row in df_inminente.iterrows():
            inm_data.append([
                str(row['Fecha_Entrega'])[:10], 
                str(row['Articulo'])[:25],
                format_number(row['Piezas']),
                format_currency(row['Importe'])
            ])
            
        t_inm = Table(inm_data, colWidths=[1.8*inch, 2.7*inch, 1.2*inch, 1.4*inch])
        t_inm.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_inm)
        story.append(Paragraph("<i>* Listado de requerimientos de entrega a corto plazo.</i>", styles["Italic"]))
    else:
        story.append(Paragraph("No hay entregas en los próximos 15 días.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/pedidos-pdf")
def create_pedidos_pdf(req: PDFPedidosRequest):
    pdf_buffer = generate_pedidos_pdf(req)
    headers = {
        'Content-Disposition': f'attachment; filename="Sales_Backlog_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
