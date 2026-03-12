import io
import os
import duckdb
import pandas as pd
from datetime import datetime, timedelta
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

class PDFReportRequest(BaseModel):
    fecha_analisis: Optional[str] = None
    cliente: Optional[str] = "ALL"
    incluir_graficos: Optional[bool] = True

def format_currency(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_duckdb_conn():
    if not DB_ANALYTICAL_PATH.exists():
        raise HTTPException(status_code=500, detail="Base de datos analítica no encontrada")
    return duckdb.connect(str(DB_ANALYTICAL_PATH), read_only=True)

def generate_stock_pdf(req: PDFReportRequest):
    conn = get_duckdb_conn()
    
    try:
        # 1. Obtener la fecha máxima disponible si no se provee
        if not req.fecha_analisis:
            df_max = conn.execute("SELECT MAX(Fecha) as max_f FROM existencias").df()
            fecha_target = df_max['max_f'].iloc[0]
        else:
            fecha_target = req.fecha_analisis

        # 1. Resumen Ejecutivo (Visión Financiera)
        query_total = f"SELECT SUM(Valor_Total) as total FROM existencias WHERE Fecha = '{fecha_target}'"
        if req.cliente and req.cliente != "ALL":
            query_total += f" AND Cliente = '{req.cliente}'"
        total_val_actual = conn.execute(query_total).df()['total'].iloc[0] or 0.0

        # Total anterior (~7 días)
        query_prev_date = f"SELECT MAX(Fecha) as prev_f FROM existencias WHERE Fecha <= CAST('{fecha_target}' AS DATE) - INTERVAL 7 DAY"
        prev_date_df = conn.execute(query_prev_date).df()
        prev_date = prev_date_df['prev_f'].iloc[0]
        
        total_val_prev = 0.0
        if prev_date:
            query_total_prev = f"SELECT SUM(Valor_Total) as total FROM existencias WHERE Fecha = '{prev_date}'"
            if req.cliente and req.cliente != "ALL":
                query_total_prev += f" AND Cliente = '{req.cliente}'"
            total_val_prev = conn.execute(query_total_prev).df()['total'].iloc[0] or 0.0
            
        delta_percent = ((total_val_actual - total_val_prev) / total_val_prev * 100) if total_val_prev > 0 else 0

        # 2. Situación Financiera por Cliente (Top 10)
        query_clientes = f"""
            SELECT Cliente, SUM(Cantidad) as Cantidad_Total, SUM(Valor_Total) as Valor_Euros
            FROM existencias
            WHERE Fecha = '{fecha_target}'
            GROUP BY Cliente
            ORDER BY Valor_Euros DESC
            LIMIT 10
        """
        df_clientes = conn.execute(query_clientes).df()

        # 3. Análisis de Stock vs Objetivo
        query_objetivos = f"""
            SELECT Articulo, Descripcion, SUM(Cantidad) as Cantidad, MAX(Stock_Objetivo) as Stock_Objetivo
            FROM existencias
            WHERE Fecha = '{fecha_target}' AND Stock_Objetivo > 0
        """
        if req.cliente and req.cliente != "ALL":
             query_objetivos += f" AND Cliente = '{req.cliente}'"
        query_objetivos += " GROUP BY Articulo, Descripcion"
        
        df_obj = conn.execute(query_objetivos).df()
        if not df_obj.empty:
            df_obj['Desviacion_Pct'] = (df_obj['Cantidad'] / df_obj['Stock_Objetivo']) * 100
            df_overstock = df_obj[df_obj['Desviacion_Pct'] > 150].sort_values(by='Desviacion_Pct', ascending=False).head(15)
        else:
            df_overstock = pd.DataFrame()
        
        # Riesgo Rotura (Próximos 15 días)
        query_pedidos = f"""
            SELECT Articulo, SUM(Cant_Pendiente) as Demanda_Pendiente
            FROM pedidos
            WHERE Fecha_Snapshot = '{fecha_target}'
              AND TRY_CAST(Fecha_Entrega AS DATE) <= CAST('{fecha_target}' AS DATE) + INTERVAL 15 DAY
            GROUP BY Articulo
        """
        df_pedidos = conn.execute(query_pedidos).df()
        
        query_stock_now = f"SELECT Articulo, SUM(Cantidad) as Stock_Total FROM existencias WHERE Fecha = '{fecha_target}' GROUP BY Articulo"
        df_stock_now = conn.execute(query_stock_now).df()
        
        if not df_pedidos.empty:
            df_risk = pd.merge(df_pedidos, df_stock_now, on='Articulo', how='left')
            df_risk['Stock_Total'] = df_risk['Stock_Total'].fillna(0)
            df_risk = df_risk[df_risk['Stock_Total'] < df_risk['Demanda_Pendiente']].sort_values(by='Demanda_Pendiente', ascending=False).head(15)
        else:
            df_risk = pd.DataFrame()

    except Exception as e:
        print(f"Error PDF Estándar (DuckDB): {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

    # --------------- GENERACIÓN PDF ---------------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#E30613"), spaceAfter=15)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor("#1A3A5A"), spaceAfter=10)
    normal_style = styles["Normal"]
    italic_small = ParagraphStyle('ItalicSmall', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.grey)
    
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
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1a")),
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
        risk_data = [["Artículo", "Stock Actual", "Demanda (15d)", "Déficit"]]
        for _, row in df_risk.iterrows():
            deficit = row['Demanda_Pendiente'] - row['Stock_Total']
            risk_data.append([
                str(row['Articulo']), 
                f"{int(row['Stock_Total']):,}",
                f"{int(row['Demanda_Pendiente']):,}",
                f"{int(deficit):,}",
            ])
            
        t_risk = Table(risk_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        t_risk.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_risk)
        story.append(Paragraph("* Atención prioritaria sugerida para estos artículos. Posible parada de cadena en cliente.", italic_small))
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
        story.append(Paragraph("* Exceso inmovilizado. Valorar acciones de venta u obsolescencia.", italic_small))
    else:
        story.append(Paragraph("No se supera el 150% en ningún artículo analizado.", normal_style))

    # FINALIZAR DOCUMENTO
    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/stock-pdf")
def create_stock_pdf(req: PDFReportRequest):
    try:
        pdf_buffer = generate_stock_pdf(req)
        headers = { 'Content-Disposition': f'attachment; filename="Inventory_Health_{datetime.now().strftime("%Y%m%d")}.pdf"' }
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
