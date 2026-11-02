"""Ticket 4 : clients CRUD complet."""
import pytest

from app import models, services
from tests.conftest import make_client, make_itv


def test_crud_http(client, db):
    r = client.post("/clients/nouveau", data={"nom": "Boulangerie Martin", "email": "m@b.fr", "telephone": "01 02 03 04 05",
                                              "notes": "Chambre froide"}, follow_redirects=False)
    assert r.status_code == 303
    c = db.query(models.Client).one()
    assert client.get(f"/clients/{c.id}").status_code == 200 and "Chambre froide" in client.get(f"/clients/{c.id}").text
    r = client.post(f"/clients/{c.id}/modifier", data={"nom": "Boulangerie Martin & Fils", "actif": "0"}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    c = db.get(models.Client, c.id)
    assert c.nom.endswith("Fils") and c.actif is False
    assert client.post(f"/clients/{c.id}/supprimer", follow_redirects=False).status_code == 303
    db.expire_all()
    assert db.query(models.Client).count() == 0


def test_recherche(client, db):
    make_client(db, "Alpha Froid", email="a@x.fr")
    make_client(db, "Beta Clim", telephone="0607080910")
    assert [c.nom for c in services.list_clients(db, "alpha")] == ["Alpha Froid"]
    assert [c.nom for c in services.list_clients(db, "0607")] == ["Beta Clim"]
    html = client.get("/clients?q=beta").text
    assert "Beta Clim" in html and "Alpha Froid" not in html


def test_validation(client, db):
    r = client.post("/clients/nouveau", data={"nom": " ", "email": "x", "telephone": "abc"})
    assert r.status_code == 422
    import html
    t = html.unescape(r.text)
    assert "nom du client est obligatoire" in t and "e-mail n'est pas valide" in t and "téléphone n'est pas valide" in t
    assert db.query(models.Client).count() == 0


def test_suppression_avec_interventions_avertit(db):
    c = make_client(db)
    make_itv(db, c.id)
    with pytest.raises(services.ValidationError) as e:
        services.delete_client(db, c.id)
    assert "1 intervention(s) liée(s)" in e.value.errors[0]
    assert db.query(models.Client).count() == 1


def test_suppression_forcee_supprime_tout(db):
    c = make_client(db)
    i = make_itv(db, c.id)
    services.create_facture_from_intervention(db, i.id)
    assert services.delete_client(db, c.id, force=True)
    for m in (models.Client, models.Intervention, models.Facture, models.LigneFacture, models.LigneIntervention):
        assert db.query(m).count() == 0


def test_avertissement_dans_la_page(client, db):
    c = make_client(db)
    make_itv(db, c.id)
    html = client.get(f"/clients/{c.id}").text
    assert "intervention(s)" in html and "liées" in html


def test_historique_interventions_et_factures(client, db):
    c = make_client(db)
    i = make_itv(db, c.id)
    f = services.create_facture_from_intervention(db, i.id)
    html = client.get(f"/clients/{c.id}").text
    assert i.numero in html and f.numero in html


def test_client_inconnu_404(client):
    assert client.get("/clients/999").status_code == 404
    assert client.get("/clients/999/modifier").status_code == 404
