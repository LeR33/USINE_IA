"""Ticket 3 : vue planning."""
from datetime import date, timedelta

from app import models, services
from tests.conftest import make_client, make_itv


def test_planning_semaine_et_mois(client):
    assert client.get("/planning").status_code == 200
    r = client.get("/planning?vue=mois")
    assert r.status_code == 200 and 'data-vue="mois"' in r.text
    assert client.get("/planning?jour=pas-une-date").status_code == 200


def test_intervention_apparait_dans_le_bon_creneau(client, db):
    c = make_client(db, "Client Planning")
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    i = make_itv(db, c.id, monday + timedelta(days=2), heure_debut="10:00", heure_fin="11:00")
    html = client.get(f"/planning?jour={monday.isoformat()}").text
    cell = f'data-date="{(monday + timedelta(days=2)).isoformat()}" data-hour="10:00"'
    assert cell in html
    after = html.split(cell)[1].split("</td>")[0]
    assert f'data-id="{i.id}"' in after and "Client Planning" in after


def test_couleur_selon_statut(client, db):
    c = make_client(db)
    make_itv(db, c.id, statut="annulée")
    assert "#6c757d" in client.get("/planning").text


def test_deplacer_met_a_jour_la_date(client, db):
    c = make_client(db)
    i = make_itv(db, c.id, date(2026, 11, 2), heure_debut="09:00", heure_fin="11:00")
    r = client.post(f"/api/interventions/{i.id}/deplacer", json={"date": "2026-11-05", "heure_debut": "14:00"})
    assert r.status_code == 200 and r.json()["ok"]
    db.expire_all()
    i = db.get(models.Intervention, i.id)
    assert i.date == date(2026, 11, 5) and i.heure_debut == "14:00" and i.heure_fin == "16:00"  # durée conservée


def test_deplacer_sans_heure_garde_horaire(client, db):
    c = make_client(db)
    i = make_itv(db, c.id, date(2026, 11, 2))
    assert client.post(f"/api/interventions/{i.id}/deplacer", json={"date": "2026-11-20"}).status_code == 200
    db.expire_all()
    i = db.get(models.Intervention, i.id)
    assert i.date == date(2026, 11, 20) and i.heure_debut == "09:00"


def test_deplacer_erreurs(client, db):
    c = make_client(db)
    i = make_itv(db, c.id)
    assert client.post(f"/api/interventions/{i.id}/deplacer", json={"date": "nimporte"}).status_code == 422
    assert client.post("/api/interventions/9999/deplacer", json={"date": "2026-11-20"}).status_code == 404
    assert client.post(f"/api/interventions/{i.id}/deplacer", content=b"pas du json").status_code == 400


def test_bouton_nouvelle_intervention_prerempli(client):
    r = client.get("/interventions/nouveau?date=2026-11-09&heure=15:00")
    assert 'value="2026-11-09"' in r.text and 'value="15:00"' in r.text and 'value="16:00"' in r.text
    assert "Nouvelle intervention" in client.get("/planning").text
    assert "/interventions/nouveau?date=" in client.get("/planning").text  # clic sur créneau
