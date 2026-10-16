"""Outils fichiers + exécution, tous confinés dans workspace/ (anti path-traversal)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from crewai.tools import tool

from config import WORKSPACE

MAX_READ = 20_000       # caractères renvoyés à l'agent (évite d'exploser le contexte)
CMD_TIMEOUT = 120       # secondes


def _safe(path: str) -> Path:
    """Résout un chemin relatif et refuse toute sortie de workspace/."""
    p = (WORKSPACE / path).resolve()
    if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
        raise ValueError(f"Chemin interdit (hors workspace) : {path}")
    return p


@tool("write_file")
def write_file(path: str, content: str) -> str:
    """Écrit (ou écrase) un fichier texte. `path` est RELATIF au workspace, ex: 'app/main.py'.
    Crée les dossiers manquants. Renvoie une confirmation avec le nombre de lignes."""
    try:
        p = _safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: {path} écrit ({content.count(chr(10)) + 1} lignes)."
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"


@tool("read_file")
def read_file(path: str) -> str:
    """Lit un fichier du workspace. `path` est RELATIF au workspace."""
    try:
        p = _safe(path)
        if not p.exists():
            return f"ERREUR: {path} n'existe pas. Utilise list_files pour voir ce qui existe."
        txt = p.read_text(encoding="utf-8", errors="replace")
        if len(txt) > MAX_READ:
            return txt[:MAX_READ] + f"\n...[tronqué, {len(txt)} caractères au total]"
        return txt
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"


@tool("list_files")
def list_files(subdir: str = ".") -> str:
    """Liste récursivement les fichiers du workspace (ou d'un sous-dossier)."""
    try:
        base = _safe(subdir)
        if not base.exists():
            return "Dossier inexistant."
        out = []
        for f in sorted(base.rglob("*")):
            if f.is_file() and ".venv" not in f.parts and "__pycache__" not in f.parts \
                    and "node_modules" not in f.parts:
                out.append(str(f.relative_to(WORKSPACE)))
        return "\n".join(out[:300]) or "(vide)"
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"


@tool("run_tests")
def run_tests(target: str = "tests") -> str:
    """Lance pytest sur `target` (dossier ou fichier, relatif au workspace) et renvoie la sortie
    complète. C'est la SEULE source de vérité pour dire si le code fonctionne."""
    try:
        t = _safe(target)
        if not t.exists():
            return f"ECHEC: {target} introuvable. Aucun test n'a été écrit."
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(t), "-x", "-q", "--tb=short", "-p", "no:cacheprovider"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=CMD_TIMEOUT,
            env={**os.environ, "PYTHONPATH": str(WORKSPACE)},
        )
        out = (proc.stdout + "\n" + proc.stderr).strip()
        status = "PASSED" if proc.returncode == 0 else "FAILED"
        return f"[{status}] returncode={proc.returncode}\n{out[-6000:]}"
    except subprocess.TimeoutExpired:
        return f"[FAILED] timeout après {CMD_TIMEOUT}s (boucle infinie ?)."
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"


@tool("run_python_check")
def run_python_check(path: str) -> str:
    """Vérifie la syntaxe d'un fichier Python (compile) et lance pyflakes-like via compileall.
    Renvoie OK ou la liste des erreurs."""
    try:
        p = _safe(path)
        if not p.exists():
            return f"ERREUR: {path} introuvable."
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(p)],
            capture_output=True, text=True, timeout=30,
        )
        return "OK: syntaxe valide." if proc.returncode == 0 else f"ERREUR SYNTAXE:\n{proc.stderr}"
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"


@tool("reset_workspace_app")
def reset_workspace_app(subdir: str) -> str:
    """Supprime un sous-dossier du workspace (ex: pour repartir d'une base propre). Irréversible."""
    try:
        p = _safe(subdir)
        if p == WORKSPACE.resolve():
            return "REFUSÉ: impossible de supprimer la racine du workspace."
        if p.exists():
            shutil.rmtree(p)
        return f"OK: {subdir} supprimé."
    except Exception as e:  # noqa: BLE001
        return f"ERREUR: {e}"
