"""Ticket 9 : qualité (validation, français, README, aucune donnée en dur)."""
from pathlib import Path

import pytest

from app import services

ROOT = Path(__file__).resolve().parent.parent


def test_aucune_donnee_societe_en_dur():
    banned = ["FroidPro SARL", "123 Rue du Froid", "123 456 789", "FR34123456789"]
    for f in list((ROOT / "app").rglob("*.py")) + list((ROOT / "app").rglob("*.html")):
        txt = f.read_text(encoding="utf-8")
        for b in banned:
            assert b not in txt, f"{b!r} en dur dans {f}"


def test_readme_a_jour():
    txt = (ROOT / "README.md").read_text(encoding="utf-8")
    for k in ("Paramètres", "Planning", "pytest", "uvicorn", "Facturation"):
        assert k in txt


def test_pas_de_secret_en_dur_obligatoire():
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert 'os.getenv("FROIDPRO_SECRET")' in main


@pytest.mark.parametrize("fn,args", [
    (services.create_client, ({"nom": ""},)),
    (services.create_article, ({"designation": ""},)),
    (services.update_parametres, ({"nom_societe": ""},)),
])
def test_erreurs_en_francais(db, fn, args):
    with pytest.raises(services.ValidationError) as e:
        fn(db, *args)
    assert any("obligatoire" in m for m in e.value.errors)


def test_virgule_decimale_acceptee(db):
    a = services.create_article(db, {"designation": "X", "prix_ht": "12,5", "tva": "5,5"})
    assert a.prix_ht == 12.5 and a.tva == 5.5


def test_sql_injection_inoffensive(db):
    services.create_client(db, {"nom": "Robert'); DROP TABLE clients;--"})
    assert len(services.list_clients(db, "'); DROP")) == 1
    assert len(services.list_clients(db)) == 1


def test_endpoints_inconnus_404(client):
    for url in ("/interventions/9999/modifier", "/articles/9999/modifier", "/factures/9999"):
        assert client.get(url).status_code == 404
