import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app import models

def generate_invoice_pdf(facture: models.Facture, filepath: str):
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12
    )
    
    normal_style = styles['Normal']
    
    story.append(Paragraph(f"FACTURE N° {facture.numero}", title_style))
    story.append(Spacer(1, 12))
    
    # Client info & Company info
    client = facture.intervention.client if facture.intervention and facture.intervention.client else None
    client_name = client.nom if client else "Client Inconnu"
    client_addr = client.adresse if client and client.adresse else ""
    client_tel = client.telephone if client and client.telephone else ""
    client_email = client.email if client and client.email else ""
    
    info_text = f"""
    <b>FroidPro SARL</b><br/>
    123 Rue du Froid, 75001 Paris<br/>
    SIRET: 123 456 789 00012 - TVA: FR34123456789<br/><br/>
    <b>Client :</b> {client_name}<br/>
    {client_addr}<br/>
    Tél: {client_tel} | Email: {client_email}<br/><br/>
    <b>Date d'émission :</b> {facture.date_emission}<br/>
    <b>Statut :</b> {facture.statut}
    """
    story.append(Paragraph(info_text, normal_style))
    story.append(Spacer(1, 20))
    
    # Table of lines
    table_data = [["Libellé", "Qté", "P.U. HT", "TVA %", "Total HT"]]
    total_ht = 0
    total_tva = 0
    
    for l in facture.lignes:
        ligne_ht = l.quantite * l.prix_unitaire_ht
        ligne_tva = ligne_ht * (l.taux_tva / 100.0)
        total_ht += ligne_ht
        total_tva += ligne_tva
        table_data.append([
            l.libelle,
            f"{l.quantite}",
            f"{l.prix_unitaire_ht:.2f} €",
            f"{l.taux_tva}%",
            f"{ligne_ht:.2f} €"
        ])
        
    t = Table(table_data, colWidths=[200, 50, 70, 60, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    total_ttc = total_ht + total_tva
    totals_text = f"""
    <b>Total HT :</b> {total_ht:.2f} €<br/>
    <b>Total TVA :</b> {total_tva:.2f} €<br/>
    <b>Total TTC :</b> {total_ttc:.2f} €
    """
    story.append(Paragraph(totals_text, ParagraphStyle('Totals', parent=normal_style, alignment=2)))
    
    doc.build(story)
