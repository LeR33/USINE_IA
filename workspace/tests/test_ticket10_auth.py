"""Authentification : installation, connexion, CSRF, limitation des tentatives."""
import re

from app import models, security
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def _token(c, url):
    return re.search(r'name="csrf_token" value="([^"]+)"', c.get(url).text).group(1)


def _setup(c, email=TEST_EMAIL, pw=TEST_PASSWORD, conf=None):
    return c.post("/installation", data={"email": email, "mot_de_passe": pw, "confirmation": conf or pw,
                                         "csrf_token": _token(c, "/installation")}, follow_redirects=False)


# ---- hash ----
def test_hash_est_sale_et_verifiable():
    h1, h2 = security.hash_password("Abcdefghi1"), security.hash_password("Abcdefghi1")
    assert h1 != h2 and "Abcdefghi1" not in h1
    assert security.verify_password("Abcdefghi1", h1) and not security.verify_password("autre", h1)
    assert not security.verify_password("x", "format-invalide")


def test_regles_mot_de_passe():
    assert security.password_errors("court1")
    assert security.password_errors("uniquementdeslettres")
    assert security.password_errors("1234567890123")
    assert security.password_errors("Valide12345", "different")
    assert security.password_errors("Valide12345", "Valide12345") == []


# ---- accès ----
def test_sans_compte_tout_redirige_vers_installation(anon):
    r = anon.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/installation"
    assert anon.get("/installation").status_code == 200


def test_installation_cree_le_compte_et_connecte(anon, db):
    r = _setup(anon)
    assert r.status_code == 303
    u = db.query(models.Utilisateur).one()
    assert u.email == TEST_EMAIL and u.mot_de_passe_hash.startswith("pbkdf2_sha256$")
    assert TEST_PASSWORD not in u.mot_de_passe_hash
    assert anon.get("/").status_code == 200


def test_installation_impossible_deux_fois(anon, db):
    _setup(anon)
    anon.post("/deconnexion", data={"csrf_token": _token(anon, "/admin/parametres")})
    r = anon.get("/installation", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"
    # sans jeton : bloqué par le CSRF
    r = anon.post("/installation", data={"email": "pirate@x.fr", "mot_de_passe": "Pirate12345", "confirmation": "Pirate12345"})
    assert r.status_code == 403
    # avec un jeton valide : bloqué par la règle « un seul compte »
    tok = _token(anon, "/connexion")
    r = anon.post("/installation", data={"email": "pirate@x.fr", "mot_de_passe": "Pirate12345", "confirmation": "Pirate12345",
                                         "csrf_token": tok}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"
    assert db.query(models.Utilisateur).count() == 1


def test_installation_validation(anon, db):
    r = _setup(anon, email="pas-un-mail", pw="court", conf="autre")
    assert r.status_code == 422 and db.query(models.Utilisateur).count() == 0


def test_pages_protegees_sans_session(client):
    c2 = type(client)(client.app)  # nouveau client, sans cookie
    with c2:
        for url in ("/", "/clients", "/factures", "/planning", "/admin/parametres", "/factures/1/pdf"):
            r = c2.get(url, follow_redirects=False)
            assert r.status_code == 303 and r.headers["location"] == "/connexion", url
        r = c2.get("/api/articles")
        assert r.status_code == 401


def test_static_reste_public(anon):
    assert anon.get("/static/uploads/.gitkeep").status_code in (200, 404)  # pas de redirection vers la connexion


# ---- connexion ----
def _logout_and_fresh(client):
    client.post("/deconnexion")
    client.csrf = None


def test_connexion_ok_et_mauvais_mot_de_passe(client):
    _logout_and_fresh(client)
    tok = _token(client, "/connexion")
    bad = client.post("/connexion", data={"email": TEST_EMAIL, "mot_de_passe": "FauxMotDePasse1", "csrf_token": tok})
    assert bad.status_code == 401 and "incorrect" in bad.text
    unk = client.post("/connexion", data={"email": "inconnu@x.fr", "mot_de_passe": TEST_PASSWORD, "csrf_token": tok})
    assert unk.status_code == 401 and "incorrect" in unk.text  # même message : pas d'énumération de comptes
    ok = client.post("/connexion", data={"email": TEST_EMAIL, "mot_de_passe": TEST_PASSWORD, "csrf_token": tok},
                     follow_redirects=False)
    assert ok.status_code == 303 and client.get("/").status_code == 200


def test_deconnexion(client):
    assert client.post("/deconnexion", follow_redirects=False).status_code == 303
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/connexion"


def test_limitation_des_tentatives(client):
    _logout_and_fresh(client)
    tok = _token(client, "/connexion")
    codes = [client.post("/connexion", data={"email": TEST_EMAIL, "mot_de_passe": f"Mauvais{i}12345", "csrf_token": tok}).status_code
             for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    # même le BON mot de passe est refusé pendant le blocage
    r = client.post("/connexion", data={"email": TEST_EMAIL, "mot_de_passe": TEST_PASSWORD, "csrf_token": tok})
    assert r.status_code == 429 and "Trop de tentatives" in r.text


def test_fenetre_de_limitation_expire():
    security.reset_attempts()
    for _ in range(5):
        security.record_failure("1.2.3.4", now=1000.0)
    assert security.too_many_attempts("1.2.3.4", now=1100.0)
    assert not security.too_many_attempts("1.2.3.4", now=1000.0 + security.WINDOW_S + 1)


def test_session_regeneree_a_la_connexion(client):
    _logout_and_fresh(client)
    tok_avant = _token(client, "/connexion")
    client.post("/connexion", data={"email": TEST_EMAIL, "mot_de_passe": TEST_PASSWORD, "csrf_token": tok_avant})
    tok_apres = _token(client, "/admin/parametres")
    assert tok_avant != tok_apres


# ---- CSRF ----
def test_csrf_refuse_sans_jeton(client):
    client.csrf = None  # n'ajoute plus l'en-tête automatiquement
    r = client.post("/clients/nouveau", data={"nom": "Pirate"})
    assert r.status_code == 403
    r = client.post("/clients/nouveau", data={"nom": "Pirate", "csrf_token": "faux"})
    assert r.status_code == 403


def test_csrf_accepte_avec_jeton(client):
    tok = _token(client, "/clients/nouveau")
    client.csrf = None
    r = client.post("/clients/nouveau", data={"nom": "Légitime", "csrf_token": tok}, follow_redirects=False)
    assert r.status_code == 303


def test_csrf_sur_api_deplacement(client):
    client.csrf = None
    r = client.post("/api/interventions/1/deplacer", json={"date": "2026-11-20"})
    assert r.status_code == 403


def test_csrf_sur_suppression_et_facture(client):
    client.csrf = None
    for url in ("/clients/1/supprimer", "/factures/1/payer", "/interventions/1/supprimer", "/deconnexion"):
        assert client.post(url).status_code == 403, url


# ---- changement de mot de passe ----
def test_changer_mot_de_passe(client, db):
    ok = client.post("/admin/mot-de-passe", data={"actuel": TEST_PASSWORD, "nouveau": "NouveauMdp2026", "confirmation": "NouveauMdp2026"},
                     follow_redirects=False)
    assert ok.status_code == 303
    db.expire_all()
    u = db.query(models.Utilisateur).one()
    assert security.verify_password("NouveauMdp2026", u.mot_de_passe_hash)
    bad = client.post("/admin/mot-de-passe", data={"actuel": "faux", "nouveau": "AutreMdp20261", "confirmation": "AutreMdp20261"})
    assert bad.status_code == 422 and "actuel est incorrect" in bad.text.replace("&#39;", "'")


# ---- option locale ----
def test_auth_desactivable_en_local(anon, monkeypatch):
    monkeypatch.setenv("FROIDPRO_AUTH", "off")
    assert anon.get("/", follow_redirects=False).status_code == 200


def test_secret_de_session_pas_en_dur():
    src = open("app/main.py", encoding="utf-8").read()
    assert "dev-change-me" not in src
