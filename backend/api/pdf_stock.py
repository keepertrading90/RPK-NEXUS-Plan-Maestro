import io
import os
import sqlite3
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "rpk_industrial.db")

class PDFReportRequest(BaseModel):
    fecha_analisis: Optional[str] = None
    cliente: Optional[str] = "ALL"
    incluir_graficos: Optional[bool] = True

def format_currency(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def generate_stock_pdf(req: PDFReportRequest):
    conn = get_db_connection()
    
    # 1. Obtener la fecha máxima disponible si no se provee
    if not req.fecha_analisis:
        df_max = pd.read_sql("SELECT MAX(Fecha) as max_f FROM stock_snapshot", conn)
        fecha_target = df_max['max_f'].iloc[0]
    else:
        fecha_target = req.fecha_analisis

    # 1. Resumen Ejecutivo (Visión Financiera)
    # Total actual
    query_total = f"SELECT SUM(Valor_Total) as total FROM stock_snapshot WHERE Fecha = '{fecha_target}'"
    if req.cliente != "ALL":
        query_total += f" AND Cliente = '{req.cliente}'"
    total_val_actual = pd.read_sql(query_total, conn)['total'].iloc[0] or 0.0

    # Total anterior (hace ~7 dias aprox)
    # Buscar la fecha inmediatamente anterior que sea al menos 7 días antes
    query_prev_date = f"SELECT MAX(Fecha) as prev_f FROM stock_snapshot WHERE Fecha <= date('{fecha_target}', '-7 day')"
    prev_date = pd.read_sql(query_prev_date, conn)['prev_f'].iloc[0]
    if prev_date:
        query_total_prev = f"SELECT SUM(Valor_Total) as total FROM stock_snapshot WHERE Fecha = '{prev_date}'"
        if req.cliente != "ALL":
            query_total_prev += f" AND Cliente = '{req.cliente}'"
        total_val_prev = pd.read_sql(query_total_prev, conn)['total'].iloc[0] or 0.0
    else:
        total_val_prev = 0.0
        
    delta_percent = ((total_val_actual - total_val_prev) / total_val_prev * 100) if total_val_prev > 0 else 0

    # 2. Situación Financiera por Cliente (Top 10)
    query_clientes = f"""
        SELECT Cliente, SUM(Cantidad) as Cantidad_Total, SUM(Valor_Total) as Valor_Euros
        FROM stock_snapshot
        WHERE Fecha = '{fecha_target}'
        GROUP BY Cliente
        ORDER BY Valor_Euros DESC
        LIMIT 10
    """
    df_clientes = pd.read_sql(query_clientes, conn)

    # 3. Análisis de Stock vs Objetivo (Solo items desviados para limpiar el reporte)
    query_objetivos = f"""
        SELECT Articulo, Descripcion, Cantidad, Stock_Objetivo
        FROM stock_snapshot
        WHERE Fecha = '{fecha_target}' AND Stock_Objetivo > 0
    """
    if req.cliente != "ALL":
         query_objetivos += f" AND Cliente = '{req.cliente}'"
    
    df_obj = pd.read_sql(query_objetivos, conn)
    df_obj['Desviacion_Pct'] = (df_obj['Cantidad'] / df_obj['Stock_Objetivo']) * 100
    
    # Filtramos para el reporte: Overstock (>150%)
    df_overstock = df_obj[df_obj['Desviacion_Pct'] > 150].sort_values(by='Desviacion_Pct', ascending=False).head(15)
    
    # Riesgo Rotura (Stockout warning cruzando con Pedidos)
    query_pedidos = f"""
        SELECT p.Articulo, SUM(p.Cant_Pendiente) as Demanda_Pendiente
        FROM pedidos_venta p
        WHERE p.Fecha_Snapshot = '{fecha_target}' 
          AND date(p.Fecha_Entrega) <= date('{fecha_target}', '+15 day')
        GROUP BY p.Articulo
    """
    df_pedidos = pd.read_sql(query_pedidos, conn)
    
    # Cruzar stock actual con demanda
    query_stock_full = f"SELECT Articulo, Descripcion, SUM(Cantidad) as Stock_Total FROM stock_snapshot WHERE Fecha = '{fecha_target}' GROUP BY Articulo"
    df_stock_full = pd.read_sql(query_stock_full, conn)
    df_risk = pd.merge(df_pedidos, df_stock_full, on='Articulo', how='left')
    df_risk['Stock_Total'] = df_risk['Stock_Total'].fillna(0)
    df_risk = df_risk[df_risk['Stock_Total'] < df_risk['Demanda_Pendiente']].sort_values(by='Demanda_Pendiente', ascending=False).head(15)

    conn.close()

    # --------------- GENERACIÓN PDF ---------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#E30613"), spaceAfter=15)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=14, textColor=colors.darkblue, spaceAfter=10)
    normal_style = styles["Normal"]
    
    # CABECERA
    story.append(Paragraph("INVENTORY HEALTH & CAPITAL REPORT - RPK NEXUS v5.5", title_style))
    story.append(Paragraph(f"<b>Fecha de Análisis (Snapshot):</b> {fecha_target}", normal_style))
    story.append(Paragraph(f"<b>Filtro Cliente:</b> {req.cliente}", normal_style))
    story.append(Spacer(1, 20))

    # 1. RESUMEN EJECUTIVO
    story.append(Paragraph("1. Resumen Ejecutivo (Capital Inmovilizado)", subtitle_style))
    delta_color = "red" if delta_percent > 0 else "green"
    delta_text = f"<font color='{delta_color}'>{delta_percent:+.2f}% vs semana anterior</font>"
    
    resumen_data = [
        ["Valor Económico Total", format_currency(total_val_actual)],
        ["Tendencia vs 7 días", Paragraph(delta_text, normal_style)],
        ["Salud General", "Estable" if abs(delta_percent) < 5 else ("Alerta Capital" if delta_percent > 5 else "Liberación de Caja")]
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

    # 2. TOP CLIENTES POR VALOR INMOVILIZADO
    story.append(Paragraph("2. Top 10 Clientes por Valor Inmovilizado", subtitle_style))
    if not df_clientes.empty:
        clientes_data = [["Cliente", "Piezas Totales", "Valor Inmovilizado (€)"]]
        for _, row in df_clientes.iterrows():
            clientes_data.append([
                str(row['Cliente'])[:40], 
                f"{int(row['Cantidad_Total']):,}", 
                format_currency(row['Valor_Euros'])
            ])
            
        t_clientes = Table(clientes_data, colWidths=[4*inch, 1.2*inch, 1.8*inch])
        t_clientes.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_clientes)
    else:
        story.append(Paragraph("No hay datos de clientes para esta fecha.", normal_style))
        
    story.append(Spacer(1, 20))

    # 3. RIESGO INMINENTE DE ROTURA (Stockout Warning)
    story.append(Paragraph("3. Riesgo Inminente de Rotura (Próximos 15 días)", subtitle_style))
    if not df_risk.empty:
        risk_data = [["Artículo", "Descripción", "Stock Actual", "Demanda (15 días)", "Déficit"]]
        for _, row in df_risk.iterrows():
            deficit = row['Demanda_Pendiente'] - row['Stock_Total']
            risk_data.append([
                str(row['Articulo']), 
                str(row['Descripcion'])[:30],
                f"{int(row['Stock_Total']):,}",
                f"{int(row['Demanda_Pendiente']):,}",
                f"{int(deficit):,}",
            ])
            
        t_risk = Table(risk_data, colWidths=[1.5*inch, 2.5*inch, 1*inch, 1*inch, 1*inch])
        t_risk.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('TEXTCOLOR', (-1, 1), (-1, -1), colors.red),  # Deficit en rojo
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_risk)
        story.append(Paragraph("<i>* Atención prioritaria sugerida para estos artículos. Posible parada de cadena en cliente.</i>", styles["Italic"]))
    else:
        story.append(Paragraph("Sin riesgo inminente detectado con el stock actual.", normal_style))

    story.append(PageBreak())

    # 4. OVERSTOCK CRÍTICO (>150% DEL OBJETIVO)
    story.append(Paragraph("4. Top 15 - Overstock Crítico (>150% del Objetivo)", subtitle_style))
    if not df_overstock.empty:
        over_data = [["Artículo", "Stock Actual", "Objetivo", "% Desviación"]]
        for _, row in df_overstock.iterrows():
            over_data.append([
                str(row['Articulo']), 
                f"{int(row['Cantidad']):,}",
                f"{int(row['Stock_Objetivo']):,}",
                f"{row['Desviacion_Pct']:.1f}%",
            ])
            
        t_over = Table(over_data, colWidths=[3*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        t_over.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.orange),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_over)
        story.append(Paragraph("<i>* Exceso inmovilizado. Valorar acciones de venta u obsolescencia.</i>", styles["Italic"]))
    else:
        story.append(Paragraph("No se supera el 150% en ningún artículo analizado.", normal_style))

    # FINALIZAR DOCUMENTO
    doc.build(story)
    
    buffer.seek(0)
    return buffer

@router.post("/reports/stock-pdf")
def create_stock_pdf(req: PDFReportRequest):
    pdf_buffer = generate_stock_pdf(req)
    
    headers = {
        'Content-Disposition': f'attachment; filename="Inventory_Health_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
