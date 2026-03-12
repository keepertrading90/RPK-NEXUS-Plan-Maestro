import io
import os
import pandas as pd
import duckdb
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_ANALYTICAL_PATH = BASE_DIR / "backend" / "db" / "rpk_analytical.duckdb"

class AdvancedReportRequest(BaseModel):
    fecha_inicio: str
    fecha_fin: str
    cliente: Optional[str] = "ALL"
    articulo: Optional[str] = None
    valor_minimo: Optional[float] = 0.0

def format_currency(value):
    return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_duckdb_conn():
    if not DB_ANALYTICAL_PATH.exists():
        raise HTTPException(status_code=500, detail="Base de datos analítica no encontrada")
    return duckdb.connect(str(DB_ANALYTICAL_PATH), read_only=True)

def generate_advanced_pdf(req: AdvancedReportRequest):
    conn = get_duckdb_conn()
    
    try:
        # 1. Datos de Evolución (Carril B) - Sumamos por día
        query_evo = f"""
            SELECT Fecha, SUM(Valor_Total) as Valor
            FROM existencias
            WHERE Fecha BETWEEN '{req.fecha_inicio}' AND '{req.fecha_fin}'
        """
        if req.cliente and req.cliente != "ALL": query_evo += f" AND Cliente = '{req.cliente}'"
        if req.articulo: query_evo += f" AND Articulo = '{req.articulo}'"
        query_evo += " GROUP BY Fecha ORDER BY Fecha"
        df_evo = conn.execute(query_evo).df()

        # 2. Comparativa Mensual (Suma del último día de cada mes)
        query_month = f"""
            WITH month_ends AS (
                SELECT MAX(Fecha) as last_day
                FROM existencias
                WHERE Fecha BETWEEN '{req.fecha_inicio}' AND '{req.fecha_fin}'
                GROUP BY strftime(TRY_CAST(Fecha AS DATE), '%Y-%m')
            )
            SELECT strftime(TRY_CAST(Fecha AS DATE), '%Y-%m') as Mes, SUM(Valor_Total) as Valor_Cierre
            FROM existencias
            WHERE Fecha IN (SELECT last_day FROM month_ends)
        """
        if req.cliente and req.cliente != "ALL": query_month += f" AND Cliente = '{req.cliente}'"
        query_month += " GROUP BY Mes ORDER BY Mes"
        df_months = conn.execute(query_month).df()

        # 3. Top Clientes (Pareto) - Usando la fecha más reciente disponible
        query_top_cust = f"""
            SELECT Cliente, SUM(Valor_Total) as Valor
            FROM existencias
            WHERE Fecha = (SELECT MAX(Fecha) FROM existencias WHERE Fecha <= '{req.fecha_fin}')
            GROUP BY Cliente
            ORDER BY Valor DESC
            LIMIT 10
        """
        df_top_cust = conn.execute(query_top_cust).df()

        # 4. Desviación vs Objetivo
        query_obj = f"""
            SELECT Articulo, SUM(Cantidad) as Cantidad, MAX(Stock_Objetivo) as Stock_Objetivo
            FROM existencias
            WHERE Fecha = (SELECT MAX(Fecha) FROM existencias WHERE Fecha <= '{req.fecha_fin}')
              AND Stock_Objetivo > 0
        """
        if req.cliente and req.cliente != "ALL": query_obj += f" AND Cliente = '{req.cliente}'"
        query_obj += " GROUP BY Articulo"
        
        df_obj = conn.execute(query_obj).df()
        if not df_obj.empty:
            df_obj['Desv'] = df_obj['Cantidad'] - df_obj['Stock_Objetivo']
            df_obj = df_obj[df_obj['Desv'].abs() > 0].sort_values(by='Desv', ascending=False).head(15)

    except Exception as e:
        print(f"Error DuckDB: {e}")
        raise HTTPException(status_code=500, detail=f"Error en consulta de datos: {str(e)}")
    finally:
        conn.close()

    # --- PDF CONSTRUCTION ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#E30613"), alignment=1, spaceAfter=20)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=10, textColor=colors.grey, alignment=1, spaceAfter=30)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor("#1a1a1a"), spaceBefore=15, spaceAfter=10)
    normal_style = styles['Normal']
    
    # Header
    story.append(Paragraph("INFORME ESTRATÉGICO DE EXISTENCIAS", title_style))
    story.append(Paragraph(f"Periodo: {req.fecha_inicio} a {req.fecha_fin} | Filtro Cliente: {req.cliente}", sub_style))

    # RESUMEN EJECUTIVO
    story.append(Paragraph("1. Evolución del Capital Inmovilizado", h2_style))
    if not df_evo.empty:
        val_ini = df_evo['Valor'].iloc[0]
        val_fin = df_evo['Valor'].iloc[-1]
        ahorro = val_ini - val_fin
        color_delta = colors.green if ahorro > 0 else colors.red
        
        summary_data = [
            ["Métrica", "Valor"],
            ["Valor Inicial Inmovilizado", format_currency(val_ini)],
            ["Valor Final Inmovilizado", format_currency(val_fin)],
            ["Variación Neta de Capital", format_currency(val_fin - val_ini)]
        ]
        t_summary = Table(summary_data, colWidths=[3*inch, 3*inch])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1a")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 8),
            ('TEXTCOLOR', (1, 3), (1, 3), color_delta)
        ]))
        story.append(t_summary)
    else:
        story.append(Paragraph("Sin datos de evolución para el periodo seleccionado.", normal_style))
    
    story.append(Spacer(1, 20))

    # COMPARATIVA MENSUAL
    story.append(Paragraph("2. Análisis Mensual de Cierre", h2_style))
    if not df_months.empty:
        month_data = [["Mes de Cierre", "Valor Stock a Fin de Mes"]]
        for _, r in df_months.iterrows():
            month_data.append([r['Mes'], format_currency(r['Valor_Cierre'])])
        
        t_month = Table(month_data, colWidths=[2.5*inch, 3.5*inch])
        t_month.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,0), 2, colors.HexColor("#E30613")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_month)
    else:
        story.append(Paragraph("No hay cierres mensuales en el rango.", normal_style))

    # PARETO CLIENTES
    story.append(Paragraph("3. Pareto de Clientes (Top Capital)", h2_style))
    if not df_top_cust.empty:
        cust_data = [["Cliente", "Valor Inmovilizado", "% s/ Total"]]
        total_p = df_top_cust['Valor'].sum()
        for _, r in df_top_cust.iterrows():
            pct = (r['Valor'] / total_p * 100) if total_p > 0 else 0
            cust_data.append([str(r['Cliente'])[:40], format_currency(r['Valor']), f"{pct:.1f}%"])
            
        t_cust = Table(cust_data, colWidths=[3.5*inch, 1.5*inch, 1*inch])
        t_cust.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        story.append(t_cust)

    story.append(PageBreak())

    # BALANCE DE OBJETIVOS
    story.append(Paragraph("4. Análisis de Desviación vs Stock Objetivo (TOP 15)", h2_style))
    if not df_obj.empty:
        obj_data = [["Referencia", "Stock Actual", "Objetivo", "Exceso/Déficit"]]
        for _, r in df_obj.iterrows():
            obj_data.append([
                str(r['Articulo']), 
                f"{int(r['Cantidad']):,}", 
                f"{int(r['Stock_Objetivo']):,}",
                f"{int(r['Desv']):+,.0f}"
            ])
            
        t_obj = Table(obj_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.4*inch])
        t_obj.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3B5924")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        story.append(t_obj)
        italic_style = ParagraphStyle('ItalicStyle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.grey)
        story.append(Paragraph("<br/>Valores positivos indican Overstock (Inmovilizado innecesario). Valores negativos indican Riesgo de Rotura.", italic_style))
    else:
        story.append(Paragraph("Sin datos de objetivos para los artículos filtrados.", normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/stock-advanced")
async def create_advanced_stock_report(req: AdvancedReportRequest):
    try:
        pdf_buffer = generate_advanced_pdf(req)
        headers = { 'Content-Disposition': f'attachment; filename="RPK_Stock_Advanced_{datetime.now().strftime("%Y%m%d")}.pdf"' }
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
