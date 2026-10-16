"""Auto-tests de l'usine elle-même : lance `pytest selftest` après toute modification."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from guardrails import guardrail_idea, guardrail_marketing, guardrail_plan  # noqa: E402
from tools.workspace_tools import read_file, write_file  # noqa: E402


class O:
    def __init__(self, raw): self.raw = raw


def test_path_traversal_blocked():
    assert "interdit" in write_file.run(path="../evil.txt", content="x").lower()


def test_write_read_roundtrip():
    write_file.run(path="_selftest/a.txt", content="hello")
    assert read_file.run(path="_selftest/a.txt") == "hello"


def test_idea_rejects_incomplete():
    assert guardrail_idea(O("trop court"))[0] is False


def test_plan_requires_tickets(tmp_path, monkeypatch):
    import guardrails
    monkeypatch.setattr(guardrails, "WORKSPACE", tmp_path)   # ne pas polluer le vrai workspace
    assert guardrail_plan(O("pas de tickets"))[0] is False
    plan = "".join(f"TICKET {i}: objectif, fichiers, signatures. Critères d'acceptation: test vert.\n" for i in (1, 2, 3, 4))
    assert guardrail_plan(O(plan))[0] is True
    assert (tmp_path / "docs" / "02_plan.md").exists()


@pytest.mark.parametrize("txt,ok", [
    ("x" * 900 + " 87% des PME", False),            # stat inventée
    ("x" * 900 + " lien de désinscription", True),
])
def test_marketing_guardrail(txt, ok):
    assert guardrail_marketing(O(txt))[0] is ok


def test_idea_doc_is_saved_even_if_agent_only_answers_in_text(tmp_path, monkeypatch):
    """Régression: l'étape 'idée' ne doit jamais être 'ok' sans fichier docs/01_idee.md."""
    import guardrails
    monkeypatch.setattr(guardrails, "WORKSPACE", tmp_path)
    good = ("Problème ... Cible ... Solution ... Concurrence ... Monétisation ... Risques ... MVP ... "
            "Sources: https://x.com HYPOTHÈSE NON VÉRIFIÉE. Score: 72/100 " + "détail " * 250)
    ok, _ = guardrails.guardrail_idea(O(good))
    assert ok is True
    assert (tmp_path / "docs" / "01_idee.md").exists()
