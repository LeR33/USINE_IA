"""Garde-fous objectifs : un agent ne peut PAS déclarer une tâche finie si ces contrôles échouent.
CrewAI renvoie le message d'erreur à l'agent, qui retente (jusqu'à guardrail_max_retries)."""
import re
import subprocess
import sys
from typing import Any, Tuple

from config import WORKSPACE

IDEA_REQUIRED_SECTIONS = [
    "problème", "cible", "solution", "concurrence", "monétisation",
    "risques", "score", "mvp",
]


def _ensure_doc(output: Any, rel_path: str) -> Tuple[bool, str]:
    """Le document attendu doit exister dans workspace/. Si l'agent a juste répondu en texte au lieu
    d'appeler write_file, on l'enregistre nous-mêmes (rien n'est perdu) et on le signale."""
    target = WORKSPACE / rel_path
    if target.exists() and target.stat().st_size > 200:
        return True, ""
    txt = _text(output)
    if len(txt) > 200:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(txt, encoding="utf-8")
        return True, "enregistré automatiquement"
    return False, (f"Le fichier {rel_path} n'existe pas. Utilise l'outil write_file avec path='{rel_path}' "
                   "pour l'écrire, puis donne-moi le contenu final.")


def _text(output: Any) -> str:
    return getattr(output, "raw", None) or str(output)


def guardrail_idea(output) -> Tuple[bool, Any]:
    """L'idée doit être structurée, scorée, et honnête sur ce qui est vérifié."""
    t = _text(output).lower()
    missing = [s for s in IDEA_REQUIRED_SECTIONS if s not in t]
    if missing:
        return False, f"Sections manquantes dans le document d'idée : {missing}. Complète-les."
    if "hypothèse" not in t and "source" not in t:
        return False, ("Aucune distinction entre faits sourcés et hypothèses. Ajoute des 'Sources' "
                       "ou étiquette les affirmations 'HYPOTHÈSE NON VÉRIFIÉE'.")
    m = re.search(r"score[^0-9]{0,20}(\d{1,3})\s*/\s*100", t)
    if not m:
        return False, "Donne un score global au format 'Score: NN/100' avec le détail des critères."
    if len(t) < 1200:
        return False, "Document trop court (<1200 caractères). Détaille davantage."
    ok, msg = _ensure_doc(output, "docs/01_idee.md")
    if not ok:
        return False, msg
    return True, output


def guardrail_plan(output) -> Tuple[bool, Any]:
    """Le plan doit être découpé en tickets numérotés et testables."""
    t = _text(output)
    tickets = re.findall(r"(?im)^\s*(?:#+\s*)?(?:ticket|t)[\s-]*\d+", t)
    if len(tickets) < 3:
        return False, ("Le plan doit contenir au moins 3 tickets numérotés (ex: 'TICKET 1: ...'), "
                       "chacun avec fichiers concernés + critères d'acceptation testables.")
    if "acceptation" not in t.lower():
        return False, "Chaque ticket doit avoir des 'Critères d'acceptation'."
    ok, msg = _ensure_doc(output, "docs/02_plan.md")
    if not ok:
        return False, msg
    return True, output


def guardrail_code_exists(output) -> Tuple[bool, Any]:
    """Le dev doit avoir réellement écrit des fichiers ET des tests dans le workspace."""
    py = [p for p in WORKSPACE.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]
    src = [p for p in py if "test" not in p.name.lower()]
    tests = [p for p in py if p.name.startswith("test_") or p.parent.name == "tests"]
    if not src:
        return False, "Aucun fichier source .py dans workspace/. Utilise write_file pour créer le code."
    if not tests:
        return False, "Aucun test trouvé. Écris des tests pytest dans workspace/tests/test_*.py."
    for f in src:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(f)], capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"Erreur de syntaxe dans {f.relative_to(WORKSPACE)}:\n{r.stderr[-800:]}"
    return True, output


def guardrail_tests_pass(output) -> Tuple[bool, Any]:
    """Vérité terrain : on relance pytest nous-mêmes. L'avis de l'agent QA ne suffit pas."""
    tests_dir = WORKSPACE / "tests"
    if not tests_dir.exists():
        return False, "workspace/tests/ n'existe pas. Le code n'est pas testé, donc pas validable."
    ok, msg = _ensure_doc(output, "docs/03_rapport_qa.md")
    if not ok:
        return False, msg
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-x", "-q", "--tb=short", "-p", "no:cacheprovider"],
        cwd=WORKSPACE, capture_output=True, text=True, timeout=180,
        env={"PYTHONPATH": str(WORKSPACE), "PATH": __import__("os").environ.get("PATH", "")},
    )
    if proc.returncode != 0:
        return False, ("pytest ÉCHOUE. Corrige le CODE (pas les tests, sauf s'ils sont faux) puis "
                       f"relance run_tests.\n{(proc.stdout + proc.stderr)[-2500:]}")
    return True, output


def guardrail_marketing(output) -> Tuple[bool, Any]:
    """Contenu marketing : pas de chiffres inventés, pas de promesses légales douteuses."""
    t = _text(output)
    low = t.lower()
    if len(t) < 800:
        return False, "Contenu trop court. Fournis page de vente complète + 3 emails + plan d'acquisition."
    fake_stats = re.findall(r"\b\d{2,3}\s?%\s+(?:des|of)\b", low)
    if fake_stats and "source" not in low:
        return False, ("Statistiques chiffrées sans source détectées. Supprime-les ou cite la source ; "
                       "n'invente jamais de chiffres.")
    if "désinscri" not in low and "unsubscribe" not in low:
        return False, "Chaque email de prospection doit contenir un lien de désinscription (RGPD)."
    if "témoignage" in low and "exemple fictif" not in low and "à remplacer" not in low:
        return False, ("Faux témoignages interdits. Marque-les 'exemple fictif – à remplacer' ou retire-les.")
    ok, msg = _ensure_doc(output, "docs/04_marketing.md")
    if not ok:
        return False, msg
    return True, output
