"""Génération du PDF de facture. Toutes les infos société viennent des Paramètres (rien en dur)."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def eur(v: float) -> str:
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


def _p(text, style):
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def generate_invoice_pdf(facture, parametres) -> bytes:
    return _generate_pdf(facture, parametres, kind="facture")


def generate_devis_pdf(devis, parametres) -> bytes:
    return _generate_pdf(devis, parametres, kind="devis")


def _generate_pdf(facture, parametres, kind: str = "facture") -> bytes:
    """Gabarit commun facture / devis."""
    is_devis = kind == "devis"
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm, title=f"{'Devis' if is_devis else 'Facture'} {facture.numero}")
    ss = getSampleStyleSheet()
    try:
        main = colors.HexColor(parametres.couleur_principale or "#0d6efd")
    except ValueError:
        main = colors.HexColor("#0d6efd")
    normal = ParagraphStyle("n", parent=ss["Normal"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=normal, fontSize=8, leading=10.5, textColor=colors.HexColor("#555555"))
    bold = ParagraphStyle("b", parent=normal, fontName="Helvetica-Bold")
    title = ParagraphStyle("t", parent=ss["Heading1"], fontSize=20, textColor=main, spaceAfter=0)
    right = ParagraphStyle("r", parent=normal, alignment=2)

    story = []

    # En-tête : logo + société | titre facture
    left = []
    logo = (STATIC_DIR / "uploads" / parametres.logo) if parametres.logo else None
    if logo and logo.is_file():
        try:
            img = Image(str(logo))
            ratio = img.imageWidth / img.imageHeight
            h = min(18 * mm, 55 * mm / ratio)
            img.drawHeight, img.drawWidth = h, h * ratio
            img.hAlign = "LEFT"
            left.append(img)
        except Exception:  # noqa: BLE001  (logo illisible : on l'ignore)
            pass
    left.append(Paragraph(f"<b>{escape(parametres.nom_societe)}</b>", ParagraphStyle("c", parent=normal, fontSize=12)))
    for line in (parametres.adresse,
                 f"SIRET : {parametres.siret}" if parametres.siret else "",
                 f"N° TVA : {parametres.tva_numero}" if parametres.tva_numero else "",
                 f"Tél : {parametres.telephone}" if parametres.telephone else "",
                 parametres.email):
        if line:
            left.append(_p(line, small))
    head = Table([[left, [Paragraph("DEVIS" if is_devis else "FACTURE", title), _p(f"N° {facture.numero}", right)]]],
                 colWidths=[100 * mm, 74 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story += [head, Spacer(1, 8 * mm)]

    # Client + dates
    c = facture.client
    cl = [Paragraph("<b>Destinataire</b>" if is_devis else "<b>Facturé à</b>", normal), _p(c.nom, bold)]
    for line in (c.adresse, c.telephone, c.email):
        if line:
            cl.append(_p(line, normal))
    dates = [_p(f"Date d'émission : {facture.date_emission.strftime('%d/%m/%Y')}", right)]
    if is_devis:
        dates.append(_p(f"Valable jusqu'au : {facture.date_validite.strftime('%d/%m/%Y')}", right))
        if facture.objet:
            dates.append(_p(f"Objet : {facture.objet}", right))
    else:
        dates.append(_p(f"Échéance : {facture.date_echeance.strftime('%d/%m/%Y')}", right))
        if facture.intervention:
            dates.append(_p(f"Intervention : {facture.intervention.numero}", right))
    info = Table([[cl, dates]], colWidths=[100 * mm, 74 * mm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [info, Spacer(1, 8 * mm)]

    # Lignes
    data = [["Désignation", "Qté", "PU HT", "TVA", "Total HT"]]
    for l in facture.lignes:
        data.append([_p(l.designation, normal), f"{l.quantite:g}", eur(l.prix_ht), f"{l.tva:g} %", eur(l.total_ht)])
    t = Table(data, colWidths=[78 * mm, 16 * mm, 28 * mm, 20 * mm, 32 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), main), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 5 * mm)]

    tot = Table([["Total HT", eur(facture.total_ht)], ["TVA", eur(facture.total_tva)],
                 ["Total TTC", eur(facture.total_ttc)]], colWidths=[40 * mm, 35 * mm], hAlign="RIGHT")
    tot.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                             ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                             ("LINEABOVE", (0, -1), (-1, -1), 1, main), ("TEXTCOLOR", (0, -1), (-1, -1), main)]))
    story += [tot, Spacer(1, 8 * mm)]

    # Paiement + mentions
    pay = []
    if is_devis:
        pay.append("Bon pour accord : date, signature et mention « lu et approuvé » du client.")
        if facture.notes:
            pay.append(f"Notes : {facture.notes}")
    if not is_devis and facture.statut == "payée" and facture.date_paiement:
        pay.append(f"Facture acquittée le {facture.date_paiement.strftime('%d/%m/%Y')}.")
    if parametres.conditions_paiement:
        pay.append(f"Conditions de paiement : {parametres.conditions_paiement}")
    if parametres.iban and not is_devis:
        pay.append(f"IBAN : {parametres.iban}")
    for line in pay:
        story.append(_p(line, normal))
    if parametres.mentions_legales:
        story += [Spacer(1, 6 * mm), _p(parametres.mentions_legales, small)]

    doc.build(story)
    return buf.getvalue()
