"""Devis : création, statuts, expiration, conversion en intervention, PDF."""
from datetime import date, timedelta

import pytest

from app import models, services
from tests.conftest import make_client

LIGNES = {"ligne_designation": ["Groupe froid", "Pose"], "ligne_quantite": ["1", "4"], "ligne_prix": ["1200", "55"],
          "ligne_tva": ["20", "10"]}


def make_devis(db, client_id, **kw):
    return services.create_devis(db, {"client_id": client_id, "objet": "Chambre froide", **LIGNES, **kw})


def test_creation_et_totaux(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    assert d.numero == f"DEV-{date.today().year}-0001" and d.statut == "brouillon"
    assert d.date_validite == date.today() + timedelta(days=30)
    assert d.total_ht == 1420.0 and d.total_tva == 262.0 and d.total_ttc == 1682.0   # 1200*20% + 220*10%


def test_numerotation_sequentielle_et_independante_des_factures(db):
    c = make_client(db)
    assert [make_devis(db, c.id).numero[-4:] for _ in range(3)] == ["0001", "0002", "0003"]
    services.update_parametres(db, {"nom_societe": "X", "prefixe_facture": "ZZ", "prochain_numero_facture": "50"})
    assert make_devis(db, c.id).numero.endswith("0004")


def test_validation(db):
    c = make_client(db)
    with pytest.raises(services.ValidationError) as e:
        services.create_devis(db, {"client_id": "", "date_emission": "2026-05-10", "date_validite": "2026-05-01"})
    msg = " ".join(e.value.errors)
    assert "client valide" in msg and "antérieure" in msg and "au moins une ligne" in msg
    with pytest.raises(services.ValidationError):
        services.create_devis(db, {"client_id": c.id, "ligne_designation": ["X"], "ligne_quantite": ["abc"],
                                   "ligne_prix": ["1"], "ligne_tva": ["20"]})


def test_expiration_calculee(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    services.set_devis_statut(db, d.id, "envoyé")
    d.date_validite = date.today() - timedelta(days=1)
    db.commit()
    assert d.statut_effectif == "expiré" and len(services.list_devis(db, statut="expiré")) == 1
    services.set_devis_statut(db, d.id, "accepté")
    assert d.statut_effectif == "accepté"          # un devis accepté n'expire pas


def test_statut_invalide(db):
    c = make_client(db)
    with pytest.raises(services.ValidationError):
        services.set_devis_statut(db, make_devis(db, c.id).id, "n'importe quoi")
    assert services.set_devis_statut(db, 999, "envoyé") is None


def test_conversion_exige_acceptation(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    with pytest.raises(services.ValidationError) as e:
        services.convert_devis_to_intervention(db, d.id)
    assert "accepté" in e.value.errors[0]


def test_conversion_reprend_les_lignes_et_est_idempotente(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    services.set_devis_statut(db, d.id, "accepté")
    itv = services.convert_devis_to_intervention(db, d.id, "2026-12-01")
    assert itv.client_id == c.id and itv.date == date(2026, 12, 1) and d.numero in itv.description
    assert [(l.designation, l.quantite, l.prix_ht, l.tva) for l in itv.lignes] == [("Groupe froid", 1, 1200, 20), ("Pose", 4, 55, 10)]
    assert services.convert_devis_to_intervention(db, d.id).id == itv.id
    assert db.query(models.Intervention).count() == 1
    # la facture issue de l'intervention a les mêmes montants que le devis
    f = services.create_facture_from_intervention(db, itv.id)
    assert f.total_ttc == services.get_devis(db, d.id).total_ttc == 1682.0


def test_devis_converti_ou_clos_non_modifiable(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    services.set_devis_statut(db, d.id, "accepté")
    with pytest.raises(services.ValidationError) as e:
        services.update_devis(db, d.id, {"client_id": c.id, **LIGNES})
    assert "ne peut plus être modifié" in e.value.errors[0]
    d2 = make_devis(db, c.id)
    services.set_devis_statut(db, d2.id, "accepté")
    services.convert_devis_to_intervention(db, d2.id)
    with pytest.raises(services.ValidationError):
        services.set_devis_statut(db, d2.id, "refusé")


def test_modification(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    services.update_devis(db, d.id, {"client_id": c.id, "objet": "Nouvel objet", "ligne_designation": ["Seule"],
                                     "ligne_quantite": ["2"], "ligne_prix": ["10"], "ligne_tva": ["20"]})
    d = services.get_devis(db, d.id)
    assert d.objet == "Nouvel objet" and len(d.lignes) == 1 and d.total_ttc == 24.0
    assert db.query(models.LigneDevis).count() == 1          # anciennes lignes supprimées


def test_filtres_et_recherche(db):
    a, b = make_client(db, "Alpha"), make_client(db, "Beta")
    make_devis(db, a.id)
    d2 = make_devis(db, b.id, objet="Vitrine réfrigérée")
    services.set_devis_statut(db, d2.id, "envoyé")
    assert len(services.list_devis(db, client_id=a.id)) == 1
    assert len(services.list_devis(db, statut="envoyé")) == 1
    assert len(services.list_devis(db, q="vitrine")) == 1 and len(services.list_devis(db, q="beta")) == 1


def test_suppression(db):
    c = make_client(db)
    d = make_devis(db, c.id)
    assert services.delete_devis(db, d.id) and not services.delete_devis(db, d.id)
    assert db.query(models.LigneDevis).count() == 0


# ---- HTTP ----
def test_parcours_http(client, db):
    c = make_client(db, "Boucherie Léon")
    r = client.post("/devis/nouveau", data={"client_id": c.id, "objet": "Vitrine", **LIGNES}, follow_redirects=False)
    assert r.status_code == 303
    d = db.query(models.Devis).one()
    assert r.headers["location"] == f"/devis/{d.id}"
    page = client.get(f"/devis/{d.id}").text
    assert d.numero in page and "1 682,00" in page.replace("\u202f", " ").replace("\xa0", " ")
    assert "Marquer envoyé" in page and "Créer l'intervention" not in page
    client.post(f"/devis/{d.id}/statut", data={"statut": "accepté"})
    assert "Créer l'intervention" in client.get(f"/devis/{d.id}").text
    r = client.post(f"/devis/{d.id}/convertir", follow_redirects=False)
    assert r.status_code == 303 and "/interventions/" in r.headers["location"]
    db.expire_all()
    assert db.get(models.Devis, d.id).intervention_id is not None


def test_pages_liste_et_formulaire(client, db):
    assert "Aucun devis pour le moment" in client.get("/devis").text
    c = make_client(db)
    page = client.get(f"/devis/nouveau?client_id={c.id}").text
    assert f'value="{c.id}" selected' in page and "Lignes du devis" in page
    make_devis(db, c.id)
    assert "DEV-" in client.get("/devis").text
    assert client.get("/devis/999").status_code == 404 and client.get("/devis/999/modifier").status_code == 404


def test_formulaire_invalide_422(client):
    r = client.post("/devis/nouveau", data={"client_id": ""})
    assert r.status_code == 422 and "client valide" in r.text


def test_pdf_devis(client, db):
    from pypdf import PdfReader
    from io import BytesIO
    services.update_parametres(db, {"nom_societe": "Glacier SARL", "iban": "FR761234"})
    c = make_client(db, "Boucherie Léon")
    d = make_devis(db, c.id)
    r = client.get(f"/devis/{d.id}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    txt = PdfReader(BytesIO(r.content)).pages[0].extract_text()
    assert "DEVIS" in txt and d.numero in txt and "Valable jusqu'au" in txt and "Bon pour accord" in txt
    assert "Glacier SARL" in txt and "Boucherie Léon" in txt and "1 682,00" in txt.replace("\u202f", " ").replace("\xa0", " ")
    assert "FACTURE" not in txt and "IBAN" not in txt      # pas de mention de facture sur un devis
    assert client.get("/devis/999/pdf").status_code == 404


def test_devis_protege_par_connexion_et_csrf(client):
    client.csrf = None
    assert client.post("/devis/1/supprimer").status_code == 403
    assert client.post("/devis/nouveau", data={"client_id": "1"}).status_code == 403
    c2 = type(client)(client.app)
    with c2:
        assert c2.get("/devis", follow_redirects=False).status_code == 303
        assert c2.get("/devis/1/pdf", follow_redirects=False).status_code == 303


def test_menu_et_raccourcis(client, db):
    assert 'href="/devis"' in client.get("/").text and 'href="/devis/nouveau"' in client.get("/").text
    c = make_client(db)
    assert f"/devis/nouveau?client_id={c.id}" in client.get(f"/clients/{c.id}").text


def test_suppression_client_avec_devis_possible(db):
    c = make_client(db)
    make_devis(db, c.id)
    services.delete_client(db, c.id, force=True)
    assert db.query(models.Devis).count() == 0


def test_historique_devis_sur_fiche_client(client, db):
    c = make_client(db)
    assert "Aucun devis" in client.get(f"/clients/{c.id}").text
    d = make_devis(db, c.id)
    page = client.get(f"/clients/{c.id}").text
    assert d.numero in page and "1 devis" in page.replace("\xa0", " ")   # visible aussi dans l'avertissement de suppression


def test_client_avec_devis_seul_demande_confirmation(db):
    c = make_client(db)
    make_devis(db, c.id)
    with pytest.raises(services.ValidationError):
        services.delete_client(db, c.id)
