"""Ticket 8 : design (menu, en-tête, responsive, mode sombre, tri/recherche)."""
import pytest

PAGES = ["/", "/planning", "/planning?vue=mois", "/clients", "/articles", "/interventions", "/factures",
         "/admin/parametres", "/clients/nouveau", "/articles/nouveau", "/interventions/nouveau", "/factures/nouvelle"]


@pytest.mark.parametrize("url", PAGES)
def test_pages_ok_menu_et_responsive(client, url):
    r = client.get(url)
    assert r.status_code == 200
    h = r.text
    assert 'name="viewport"' in h and "bootstrap@5" in h and "bootstrap-icons" in h
    assert 'id="sidebar"' in h and "bi-speedometer2" in h  # menu latéral avec icônes
    assert 'lang="fr"' in h


def test_entete_nom_et_couleur(client):
    client.post("/admin/parametres", data={"nom_societe": "Polaire & Co", "couleur_principale": "#112233"})
    h = client.get("/clients").text
    assert "Polaire &amp; Co" in h and "--brand: #112233" in h


def test_mode_sombre_et_tableaux(client):
    h = client.get("/clients").text
    assert 'id="themeBtn"' in h and "data-bs-theme" in h
    client.post("/clients/nouveau", data={"nom": "Zed"})
    h = client.get("/clients").text
    assert "data-table" in h and "sortable" in h


def test_etats_vides_soignes(client):
    for url, txt in (("/clients", "Aucun client pour le moment"), ("/interventions", "Aucune intervention"),
                     ("/factures", "Aucune facture"), ("/articles", "Le catalogue est vide")):
        assert txt in client.get(url).text


def test_messages_succes_erreur(client):
    r = client.post("/clients/nouveau", data={"nom": "Succès SARL"}, follow_redirects=True)
    assert "alert-success" in r.text and "créé" in r.text
    r = client.post("/clients/nouveau", data={"nom": ""})
    assert "alert-danger" in r.text
    r = client.post("/factures/99/payer")
    assert r.status_code == 404


def test_404_page(client):
    r = client.get("/clients/12345")
    assert r.status_code == 404 and "introuvable" in r.text.lower()


def test_xss_echappe(client):
    client.post("/clients/nouveau", data={"nom": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in client.get("/clients").text
