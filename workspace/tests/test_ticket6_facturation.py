"""Ticket 6 : facturation."""
from datetime import date, timedelta

import pytest

from app import models, services
from tests.conftest import make_client, make_itv


def test_facture_depuis_intervention_reprend_les_lignes(db):
    c = make_client(db)
    i = make_itv(db, c.id)
    f = services.create_facture_from_intervention(db, i.id)
    assert [l.designation for l in f.lignes] == ["Main d'oeuvre", "Gaz R32"]
    assert f.statut == "brouillon" and f.client_id == c.id


def test_calcul_ht_tva_ttc(db):
    c = make_client(db)
    i = make_itv(db, c.id, ligne_designation=["A", "B"], ligne_quantite=["2", "1"], ligne_prix=["50", "80"], ligne_tva=["20", "10"])
    f = services.create_facture_from_intervention(db, i.id)
    assert f.total_ht == 180.0 and f.total_tva == 28.0 and f.total_ttc == 208.0


def test_pas_de_doublon_de_facture(db):
    c = make_client(db)
    i = make_itv(db, c.id)
    f1 = services.create_facture_from_intervention(db, i.id)
    f2 = services.create_facture_from_intervention(db, i.id)
    assert f1.id == f2.id and db.query(models.Facture).count() == 1


def test_refus_sans_lignes(db):
    c = make_client(db)
    i = make_itv(db, c.id, lignes=False)
    with pytest.raises(services.ValidationError) as e:
        services.create_facture_from_intervention(db, i.id)
    assert "aucune ligne" in e.value.errors[0]


def test_echeance_par_defaut_30_jours(db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    assert f.date_echeance == date.today() + timedelta(days=30)


def test_marquer_payee_http(client, db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    assert client.post(f"/factures/{f.id}/payer", follow_redirects=False).status_code == 303
    db.expire_all()
    f = db.get(models.Facture, f.id)
    assert f.statut == "payée" and f.date_paiement == date.today()
    assert "payée" in client.get(f"/factures/{f.id}").text


def test_statuts_et_retard(db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    services.set_facture_statut(db, f.id, "envoyée")
    assert f.statut_effectif == "envoyée"
    f.date_echeance = date.today() - timedelta(days=1)
    db.commit()
    assert f.statut_effectif == "en retard"
    services.mark_paid(db, f.id)
    assert f.statut_effectif == "payée"
    with pytest.raises(services.ValidationError):
        services.set_facture_statut(db, f.id, "n'importe quoi")


def test_filtre_en_retard(db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    services.set_facture_statut(db, f.id, "envoyée")
    f.date_echeance = date.today() - timedelta(days=3)
    db.commit()
    assert len(services.list_factures(db, statut="en retard")) == 1
    assert len(services.list_factures(db, statut="payée")) == 0


def test_creation_via_http_et_pdf(client, db):
    c = make_client(db, "Cliente Éloïse")
    i = make_itv(db, c.id)
    r = client.post(f"/interventions/{i.id}/facturer", follow_redirects=False)
    assert r.status_code == 303
    f = db.query(models.Facture).one()
    assert r.headers["location"] == f"/factures/{f.id}"
    pdf = client.get(f"/factures/{f.id}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert client.get("/factures/9999/pdf").status_code == 404


def test_liste_et_page_nouvelle(client, db):
    c = make_client(db)
    i = make_itv(db, c.id)
    assert i.numero in client.get("/factures/nouvelle").text
    services.create_facture_from_intervention(db, i.id)
    assert "Toutes les interventions sont déjà facturées" in client.get("/factures/nouvelle").text
    assert "FACT-" in client.get("/factures").text


def test_supprimer_facture(client, db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    client.post(f"/factures/{f.id}/supprimer", follow_redirects=False)
    db.expire_all()
    assert db.query(models.Facture).count() == 0 and db.query(models.LigneFacture).count() == 0


def test_pdf_logo_illisible_ne_plante_pas(db):
    from app.utils.pdf_gen import generate_invoice_pdf
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    p = services.get_parametres(db)
    p.logo = "inexistant.png"
    db.commit()
    assert generate_invoice_pdf(f, p).startswith(b"%PDF")
