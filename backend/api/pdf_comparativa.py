import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()

class KPIModel(BaseModel):
    name: str
    valA: float
    valB: float
    unit: str = ""
    higher_is_better: bool = True

class CentroImpacto(BaseModel):
    centro: str
    sat_a: float
    sat_b: float
    mod_a: float
    mod_b: float

class ComparativaRequest(BaseModel):
    escenario_a: str
    escenario_b: str
    kpis: List[KPIModel]
    centros_impacto: List[CentroImpacto]
    cambios_activos: List[Dict[str, Any]] # e.g. [{"tipo": "MOD", "detalle": "...", "a": 1, "b": 2}]
    dias_laborales: int
    turnos: int

def format_num(val, decimals=1):
    return f"{float(val):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generate_comparativa_pdf(req: ComparativaRequest):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#E30613"), spaceAfter=5, alignment=1)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=12, textColor=colors.darkgray, spaceAfter=20, alignment=1)
    
    section_title = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor("#1a1a1a"), spaceBefore=15, spaceAfter=10)
    normal_style = styles["Normal"]
    
    # --- HEADER ---
    story.append(Paragraph("INFORME DE IMPACTO SIMULADOR RPK", title_style))
    story.append(Paragraph(f"Análisis Estratégico: <b>{req.escenario_a}</b> vs <b>{req.escenario_b}</b>", subtitle_style))
    story.append(Paragraph(f"Fecha de extracción: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle('Fecha', parent=normal_style, alignment=1, fontSize=9, textColor=colors.grey)))
    story.append(Spacer(1, 25))

    # --- 1. RESUMEN EJECUTIVO (KPIs) ---
    story.append(Paragraph("1. Resumen Ejecutivo (KPI Globales)", section_title))
    
    kpi_data = [["Indicador", req.escenario_a, req.escenario_b, "Delta / Impacto"]]
    for k in req.kpis:
        delta = k.valB - k.valA
        delta_str = f"{'+' if delta > 0 else ''}{format_num(delta)}{k.unit}"
        
        # Color logic
        if delta == 0:
            color = colors.grey
        else:
            is_positive = delta > 0
            is_good = is_positive if k.higher_is_better else not is_positive
            color = colors.HexColor("#22c55e") if is_good else colors.HexColor("#ef4444")
            
        color_hex = color.hexval()[2:] # strip 0x
        delta_p = Paragraph(f"<font color='#{color_hex}'><b>{delta_str}</b></font>", normal_style)
        
        kpi_data.append([
            k.name, 
            f"{format_num(k.valA)}{k.unit}", 
            f"<b>{format_num(k.valB)}{k.unit}</b>", 
            delta_p
        ])
    
    t_kpis = Table(kpi_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (0,-1), colors.whitesmoke),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 20))

    # --- 2. IMPACTO POR CENTRO (TOP DIFERENCIAS) ---
    story.append(Paragraph("2. Centros Críticos o Modificados", section_title))
    
    if req.centros_impacto:
        centros_data = [["Máquina / Centro", f"Sat. {req.escenario_a}", f"Sat. {req.escenario_b}", "Delta Sat.", "Ratio MOD Actual"]]
        for c in req.centros_impacto:
            delta_sat = c.sat_b - c.sat_a
            color_sat = "red" if delta_sat > 0 and c.sat_b > 85 else ("green" if delta_sat < 0 else "black")
            delta_sat_str = f"<font color='{color_sat}'>{'+' if delta_sat>0 else ''}{format_num(delta_sat)}%</font>"
            
            centros_data.append([
                c.centro,
                f"{format_num(c.sat_a)}%",
                f"{format_num(c.sat_b)}%",
                Paragraph(delta_sat_str, normal_style),
                format_num(c.mod_b)
            ])
            
        t_centros = Table(centros_data, colWidths=[2.5*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.2*inch])
        t_centros.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E30613")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_centros)
    else:
        story.append(Paragraph("No se registraron variaciones de saturación mayores al 1% en los centros analizados.", styles["Italic"]))
        
    story.append(Spacer(1, 20))

    # --- 3. AUDITORÍA DE CAMBIOS (OVERRIDES APLICADOS) ---
    story.append(KeepTogether([
        Paragraph("3. Registro de Modificaciones Activas", section_title)
    ]))
    
    if req.cambios_activos:
        cambios_data = [["Tipo", "Detalle Adicional", "Valor Original", "Nuevo Valor"]]
        for camb in req.cambios_activos:
            cambios_data.append([
                camb.get("tipo", ""),
                camb.get("detalle", ""),
                str(camb.get("a", "")),
                Paragraph(f"<b>{camb.get('b', '')}</b>", normal_style)
            ])
            
        t_cambios = Table(cambios_data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 1.5*inch])
        t_cambios.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#374151")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_cambios)
    else:
        story.append(Paragraph("La comparación no detecta inputs manuales (ajustes puramente matemáticos de la matriz de base).", styles["Italic"]))

    # Footer Configuration
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Parámetros globales del modelo B: {req.dias_laborales} Días Laborales | {req.turnos} Horas/Turno", ParagraphStyle('FooterParams', parent=normal_style, fontSize=8, textColor=colors.grey, alignment=1)))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/comparativa-pdf")
def create_comparativa_pdf(req: ComparativaRequest):
    pdf_buffer = generate_comparativa_pdf(req)
    clean_name = req.escenario_b.replace(" ", "_")
    headers = {
        'Content-Disposition': f'attachment; filename="Simulacion_Impacto_vs_{clean_name}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
