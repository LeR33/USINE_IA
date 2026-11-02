"""Ticket 7 : tableau de bord."""
from datetime import date, timedelta

from app import services
from tests.conftest import make_client, make_itv


def test_dashboard_vide(client):
    r = client.get("/")
    assert r.status_code == 200
    for txt in ("Aucune intervention à venir", "Aucune facture en retard", "Aucune activité"):
        assert txt in r.text


def test_cartes_et_kpi(db):
    today = date.today()
    c = make_client(db)
    make_itv(db, c.id, today)
    make_itv(db, c.id, today + timedelta(days=1) if today.weekday() < 6 else today - timedelta(days=1))
    make_itv(db, c.id, today + timedelta(days=40))
    inactif = make_client(db, "Inactif")
    services.update_client(db, inactif.id, {"nom": "Inactif", "actif": "0"})

    f1 = services.create_facture_from_intervention(db, make_itv(db, c.id, today).id)   # TTC = 100+80=180 HT -> 216
    services.mark_paid(db, f1.id)
    f2 = services.create_facture_from_intervention(db, make_itv(db, c.id, today).id)
    services.set_facture_statut(db, f2.id, "envoyée")
    f2.date_echeance = today - timedelta(days=2)
    db.commit()

    d = services.dashboard(db, today)
    assert d["nb_jour"] == 3 and d["nb_semaine"] >= 3
    assert d["ca_mois"] == 216.0
    assert d["impayees_montant"] == 216.0 and d["impayees_nb"] == 1
    assert d["clients_actifs"] == 1
    assert [f.id for f in d["en_retard"]] == [f2.id]
    assert len(d["prochaines"]) >= 1 and len(d["activite"]) >= 1


def test_graphique_6_mois(db):
    d = services.dashboard(db, date(2026, 11, 2))
    assert d["graph_labels"] == ["juin 2026", "juil. 2026", "août 2026", "sept. 2026", "oct. 2026", "nov. 2026"]
    assert d["graph_values"] == [0] * 6


def test_graphique_cumule_par_mois(db):
    c = make_client(db)
    f = services.create_facture_from_intervention(db, make_itv(db, c.id).id)
    services.mark_paid(db, f.id)
    f.date_paiement = date(2026, 9, 15)
    db.commit()
    d = services.dashboard(db, date(2026, 11, 2))
    assert d["graph_values"][3] == 216.0 and d["ca_mois"] == 0


def test_graphique_traverse_les_annees(db):
    d = services.dashboard(db, date(2026, 2, 10))
    assert d["graph_labels"][0] == "sept. 2025" and d["graph_labels"][-1] == "févr. 2026"


def test_raccourcis_presents(client):
    html = client.get("/").text
    for lbl in ("Nouvelle intervention", "Nouveau client", "Nouvelle facture", "Planning", "Articles"):
        assert lbl in html
    for url in ("/interventions/nouveau", "/clients/nouveau", "/factures/nouvelle", "/planning", "/articles"):
        assert f'href="{url}"' in html
        assert client.get(url).status_code == 200
