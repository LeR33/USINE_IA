"""Ticket 5 : catalogue articles / prestations."""
import pytest

from app import models, services
from tests.conftest import make_client


def test_crud_http(client, db):
    r = client.post("/articles/nouveau", data={"reference": "MO1", "designation": "Main d'oeuvre", "prix_ht": "55,50",
                                               "tva": "20", "unite": "h", "categorie": "main d'oeuvre", "actif": "on"},
                    follow_redirects=False)
    assert r.status_code == 303
    a = db.query(models.Article).one()
    assert a.prix_ht == 55.5 and a.actif is True
    client.post(f"/articles/{a.id}/modifier", data={"designation": "Main d'oeuvre jour", "prix_ht": "60", "tva": "10",
                                                    "categorie": "pièce"}, follow_redirects=False)
    db.expire_all()
    a = db.get(models.Article, a.id)
    assert a.designation == "Main d'oeuvre jour" and a.categorie == "pièce" and a.actif is False  # case décochée
    assert client.post(f"/articles/{a.id}/supprimer", follow_redirects=False).status_code == 303
    db.expire_all()
    assert db.query(models.Article).count() == 0


def test_filtres_liste(db):
    services.create_article(db, {"designation": "Gaz R32", "prix_ht": "80", "tva": "20", "categorie": "fluide", "reference": "R32"})
    services.create_article(db, {"designation": "Pressostat", "prix_ht": "30", "tva": "20", "categorie": "pièce"})
    assert [a.designation for a in services.list_articles(db, "r32")] == ["Gaz R32"]
    assert [a.designation for a in services.list_articles(db, categorie="pièce")] == ["Pressostat"]


def test_inactif_absent_du_catalogue_api(client, db):
    a = services.create_article(db, {"designation": "Vieux", "prix_ht": "1", "tva": "20"})
    services.update_article(db, a.id, {"designation": "Vieux", "prix_ht": "1", "tva": "20"})  # actif décoché
    services.create_article(db, {"designation": "Actif", "prix_ht": "2", "tva": "20"})
    noms = [x["designation"] for x in client.get("/api/articles").json()]
    assert noms == ["Actif"]


def test_validation(db):
    with pytest.raises(services.ValidationError) as e:
        services.create_article(db, {"designation": "", "prix_ht": "-5", "tva": "150", "categorie": "bidon"})
    msg = " ".join(e.value.errors)
    assert "désignation est obligatoire" in msg and "prix HT ne peut pas être inférieur" in msg
    assert "TVA doit être comprise" in msg and "catégorie doit être" in msg
    with pytest.raises(services.ValidationError) as e:
        services.create_article(db, {"designation": "X", "prix_ht": "abc"})
    assert "doit être un nombre" in e.value.errors[0]


def test_ajout_rapide_depuis_le_catalogue(client, db):
    services.create_article(db, {"designation": "Détendeur", "prix_ht": "120", "tva": "20", "actif": "on"})
    html = client.get("/interventions/nouveau").text
    assert "D\\u00e9tendeur" in html and "Ajouter depuis le catalogue" in html  # catalogue injecté (JSON)
    assert client.get("/api/articles?q=détend").json()[0]["prix_ht"] == 120
    c = make_client(db)
    from tests.conftest import make_itv
    i = make_itv(db, c.id, lignes=False, ligne_designation=["Détendeur"], ligne_quantite=["1"], ligne_prix=["120"], ligne_tva=["20"])
    assert i.lignes[0].prix_ht == 120


def test_page_liste_etat_vide(client):
    assert "Le catalogue est vide" in client.get("/articles").text
