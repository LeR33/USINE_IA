"""Ticket 2 : interventions modifiables."""
from datetime import date, timedelta

import pytest

from app import models, services
from tests.conftest import make_client, make_itv


def test_creer_via_http(client, db):
    c = make_client(db)
    r = client.post("/interventions/nouveau", data={
        "client_id": c.id, "date": "2026-11-10", "heure_debut": "08:00", "heure_fin": "10:30", "type": "Entretien",
        "technicien": "Léa", "statut": "planifiée", "description": "Contrôle", "ligne_designation": ["Visite"],
        "ligne_quantite": ["1"], "ligne_prix": ["90"], "ligne_tva": ["20"]}, follow_redirects=False)
    assert r.status_code == 303
    i = db.query(models.Intervention).one()
    assert i.numero.startswith("INT-2026-") and i.duree_minutes == 150 and i.duree_texte == "2 h 30"
    assert len(i.lignes) == 1


def test_modifier(client, db):
    c = make_client(db)
    i = make_itv(db, c.id)
    r = client.post(f"/interventions/{i.id}/modifier", data={
        "client_id": c.id, "date": "2026-12-01", "heure_debut": "14:00", "heure_fin": "15:00", "type": "Installation",
        "statut": "terminée", "ligne_designation": ["Seule ligne"], "ligne_quantite": ["3"], "ligne_prix": ["10"],
        "ligne_tva": ["5.5"]}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    i = db.get(models.Intervention, i.id)
    assert i.statut == "terminée" and i.date == date(2026, 12, 1) and i.type == "Installation"
    assert [l.designation for l in i.lignes] == ["Seule ligne"] and i.lignes[0].tva == 5.5


def test_supprimer(client, db):
    c = make_client(db)
    i = make_itv(db, c.id)
    assert client.post(f"/interventions/{i.id}/supprimer", follow_redirects=False).status_code == 303
    db.expire_all()
    assert db.query(models.Intervention).count() == 0
    assert db.query(models.LigneIntervention).count() == 0


def test_page_liste_contient_boutons_et_confirmation(client, db):
    c = make_client(db)
    make_itv(db, c.id)
    html = client.get("/interventions").text
    assert "Ajouter" in html and "/modifier" in html and "data-confirm" in html and "Supprimer l'intervention" in html


def test_filtres(client, db):
    a, b = make_client(db, "Alpha"), make_client(db, "Beta")
    today = date.today()
    make_itv(db, a.id, today, statut="terminée", description="fuite cuisine")
    make_itv(db, b.id, today + timedelta(days=10), statut="planifiée")
    assert len(services.list_interventions(db, statut="terminée")) == 1
    assert len(services.list_interventions(db, client_id=b.id)) == 1
    assert len(services.list_interventions(db, date_debut=(today + timedelta(days=5)).isoformat())) == 1
    assert len(services.list_interventions(db, date_fin=(today + timedelta(days=5)).isoformat())) == 1
    assert len(services.list_interventions(db, q="cuisine")) == 1
    assert len(services.list_interventions(db, q="beta")) == 1
    html = client.get("/interventions?statut=terminée").text
    assert "Alpha" in html and "Beta" not in html.split("<tbody>")[1]


def test_validation(db):
    c = make_client(db)
    with pytest.raises(services.ValidationError) as e:
        services.create_intervention(db, {"client_id": "", "date": "", "heure_debut": "25:00", "heure_fin": "09:00",
                                          "statut": "inconnu"})
    msg = " ".join(e.value.errors)
    assert "client valide" in msg and "date est obligatoire" in msg and "heure de début" in msg and "statut doit être" in msg
    with pytest.raises(services.ValidationError) as e:
        services.create_intervention(db, {"client_id": c.id, "date": "2026-01-01", "heure_debut": "10:00", "heure_fin": "09:00"})
    assert "postérieure" in e.value.errors[0]


def test_formulaire_invalide_renvoie_422_en_francais(client, db):
    r = client.post("/interventions/nouveau", data={"client_id": "", "date": "2026-01-01"})
    assert r.status_code == 422 and "Veuillez choisir un client valide" in r.text


def test_numerotation_unique(db):
    c = make_client(db)
    nums = {make_itv(db, c.id).numero for _ in range(5)}
    assert len(nums) == 5


def test_supprimer_intervention_supprime_sa_facture(db):
    c = make_client(db)
    i = make_itv(db, c.id)
    services.create_facture_from_intervention(db, i.id)
    assert services.delete_intervention(db, i.id)
    assert db.query(models.Facture).count() == 0
