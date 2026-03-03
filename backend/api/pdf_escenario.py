import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class KPIModel(BaseModel):
    name: str
    value: float
    unit: str = ""

class CentroModel(BaseModel):
    centro: str
    saturacion: float
    mod: float

class EscenarioRequest(BaseModel):
    escenario_nombre: str
    kpis: List[KPIModel]
    centros: List[CentroModel]
    cambios_activos: List[Dict[str, Any]]
    dias_laborales: int
    turnos: int

def format_num(val, decimals=1):
    return f"{float(val):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generate_escenario_pdf(req: EscenarioRequest):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#E30613"), spaceAfter=5, alignment=1)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontSize=12, textColor=colors.darkgray, spaceAfter=20, alignment=1)
    
    section_title = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor("#1a1a1a"), spaceBefore=15, spaceAfter=10)
    normal_style = styles["Normal"]
    
    # --- HEADER ---
    story.append(Paragraph("INFORME DE ESCENARIO SIMULADOR RPK", title_style))
    story.append(Paragraph(f"Escenario: <b>{req.escenario_nombre}</b>", subtitle_style))
    story.append(Paragraph(f"Fecha de extracción: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle('Fecha', parent=normal_style, alignment=1, fontSize=9, textColor=colors.grey)))
    story.append(Spacer(1, 25))

    # --- 1. RESUMEN EJECUTIVO (KPIs) ---
    story.append(Paragraph("1. Resumen de Capacidad Global", section_title))
    
    kpi_data = [["Indicador", "Valor Calculado"]]
    for k in req.kpis:
        kpi_data.append([
            k.name, 
            Paragraph(f"<b>{format_num(k.value)}{k.unit}</b>", normal_style)
        ])
    
    t_kpis = Table(kpi_data, colWidths=[3*inch, 2.5*inch])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a1a1a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (0,-1), colors.whitesmoke),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 20))

    # --- 2. SATURACIÓN POR CENTRO ---
    story.append(Paragraph("2. Top 15 Centros Más Saturados", section_title))
    
    if req.centros:
        centros_data = [["Máquina / Centro", "Saturación", "Ratio MOD Actual"]]
        for c in req.centros:
            color_sat = "red" if c.saturacion > 85 else "black"
            sat_str = f"<font color='{color_sat}'>{format_num(c.saturacion)}%</font>"
            
            centros_data.append([
                c.centro,
                Paragraph(sat_str, normal_style),
                format_num(c.mod)
            ])
            
        t_centros = Table(centros_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
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
        story.append(Paragraph("No hay datos de centros disponibles.", styles["Italic"]))
        
    story.append(Spacer(1, 20))

    # --- 3. MODIFICACIONES ---
    story.append(KeepTogether([
        Paragraph("3. Registro de Cambios Activos", section_title)
    ]))
    
    if req.cambios_activos:
        cambios_data = [["Sub-Centro / Artículo", "Modificación Aplicada (Impacto en Matriz)"]]
        for camb in req.cambios_activos:
            tipo_p = Paragraph(f"<b>{camb.get('tipo', '')}</b>", normal_style)
            detalle_p = Paragraph(camb.get("detalle", ""), normal_style)
            cambios_data.append([tipo_p, detalle_p])
            
        t_cambios = Table(cambios_data, colWidths=[2.5*inch, 3*inch])
        t_cambios.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#374151")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(t_cambios)
    else:
        story.append(Paragraph("<i>Análisis de Integridad: Este escenario se basa exclusivamente en los parámetros maestros del ERP sin modificaciones manuales detectadas.</i>", ParagraphStyle('ItalicInfo', parent=normal_style, fontSize=9, textColor=colors.gray)))

    # Footer Configuration
    story.append(Spacer(1, 40))
    story.append(Paragraph(f"Parámetros del modelo: {req.dias_laborales} Días Laborales | {req.turnos} Horas/Turno", ParagraphStyle('FooterParams', parent=normal_style, fontSize=8, textColor=colors.grey, alignment=1)))

    doc.build(story)
    buffer.seek(0)
    return buffer

@router.post("/reports/escenario-pdf")
def create_escenario_pdf(req: EscenarioRequest):
    pdf_buffer = generate_escenario_pdf(req)
    clean_name = req.escenario_nombre.replace(" ", "_")
    headers = {
        'Content-Disposition': f'attachment; filename="Simulacion_{clean_name}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
