"""Ticket 1 : paramètres de la société."""
from datetime import date

from app import services
from tests.conftest import make_client, make_itv

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _save(client, **over):
    data = {"nom_societe": "Frigo Plus", "adresse": "5 rue des Alpes, Lyon", "siret": "12345678901234",
            "tva_numero": "FR12345678901", "iban": "FR7600000000000000000000000", "telephone": "0400000000",
            "email": "contact@frigoplus.fr", "mentions_legales": "RCS Lyon 123", "conditions_paiement": "Paiement à 15 jours",
            "prefixe_facture": "FP", "prochain_numero_facture": "42", "tva_defaut": "10", "couleur_principale": "#aa3300"}
    data.update(over)
    return client.post("/admin/parametres", data=data, follow_redirects=False)


def test_page_parametres_accessible(client):
    assert client.get("/admin/parametres").status_code == 200


def test_enregistrement_et_rendu_entete(client):
    assert _save(client).status_code == 303
    html = client.get("/").text
    assert "Frigo Plus" in html and "#aa3300" in html
    assert "FroidPro SARL" not in html and "123 Rue du Froid" not in html


def test_nom_societe_dans_le_pdf(client, db):
    _save(client)
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    pdf = client.get(f"/factures/{f.id}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert f.numero.startswith("FP-")


def test_pdf_change_quand_le_nom_change(client, db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    from app.utils.pdf_gen import generate_invoice_pdf
    services.update_parametres(db, {"nom_societe": "Alpha Froid"})
    p1 = generate_invoice_pdf(f, services.get_parametres(db))
    services.update_parametres(db, {"nom_societe": "Beta Clim"})
    p2 = generate_invoice_pdf(f, services.get_parametres(db))
    assert p1 != p2


def test_numero_facture_prefixe_et_compteur(client, db):
    services.update_parametres(db, {"nom_societe": "X", "prefixe_facture": "ABC", "prochain_numero_facture": "7"})
    c = make_client(db)
    f1 = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    f2 = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    assert f1.numero == f"ABC-{date.today().year}-0007"
    assert f2.numero == f"ABC-{date.today().year}-0008"


def test_validation_messages_francais(client):
    r = _save(client, nom_societe="", siret="123", couleur_principale="rouge", email="pas-un-mail")
    assert r.status_code == 422
    import html
    texte = html.unescape(r.text)
    for msg in ("nom de la société est obligatoire", "SIRET doit contenir 14 chiffres",
                "couleur principale", "e-mail n'est pas valide"):
        assert msg in texte


def test_upload_logo_valide_et_invalide(client):
    r = client.post("/admin/parametres", data={"nom_societe": "Logo Co"},
                    files={"logo": ("logo.png", PNG, "image/png")}, follow_redirects=False)
    assert r.status_code == 303
    assert "/static/uploads/logo-" in client.get("/").text
    bad = client.post("/admin/parametres", data={"nom_societe": "Logo Co"},
                      files={"logo": ("x.png", b"<script>alert(1)</script>", "image/png")})
    assert bad.status_code == 422 and "PNG ou JPEG" in bad.text


def test_conditions_paiement_fixent_echeance(db):
    services.update_parametres(db, {"nom_societe": "X", "conditions_paiement": "Paiement à 15 jours"})
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    assert (f.date_echeance - f.date_emission).days == 15
