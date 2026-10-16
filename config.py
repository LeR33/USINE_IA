"""Configuration centrale : connexion FreeLLMAPI, modèles, chemins, garde-fous.
Aucun effet de bord réseau à l'import : tout est résolu par resolve_connection()."""
import json
import os
import socket
from pathlib import Path

from crewai import LLM
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.resolve()
WORKSPACE = ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

MAX_QA_RETRIES = int(os.getenv("MAX_QA_RETRIES", "3"))
MAX_RPM = int(os.getenv("MAX_RPM", "20"))
TASK_TIMEOUT = int(os.getenv("PIPELINE_TIMEOUT_PER_TASK", "900"))

DEFAULT_PORT = 31415   # port par défaut de l'appli desktop FreeLLMAPI (3001 = Docker/serveur)
PLACEHOLDER_KEYS = ("", "missing", "change-me", "colle-ici-la-cle-unifiee")


def _open_port(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _app_config_ports() -> list[int]:
    appdata = os.getenv("APPDATA")
    paths = [
        Path(appdata) / "FreeLLMAPI" / "config.json" if appdata else None,
        Path.home() / "Library/Application Support/FreeLLMAPI/config.json",
        Path.home() / ".config/FreeLLMAPI/config.json",
    ]
    ports = []
    for p in filter(None, paths):
        try:
            port = json.loads(p.read_text(encoding="utf-8")).get("port")
            if isinstance(port, int):
                ports.append(port)
        except Exception:  # noqa: BLE001
            pass
    return ports


def detect_base_url() -> str | None:
    """URL explicite si elle répond, sinon port lu dans config.json, sinon scan des ports usuels."""
    explicit = os.getenv("FREELLMAPI_BASE_URL")
    if explicit:
        port = explicit.split("://")[-1].split("/")[0].rsplit(":", 1)[-1]
        if port.isdigit() and _open_port(int(port)):
            return explicit
    for port in dict.fromkeys(_app_config_ports() + list(range(DEFAULT_PORT, DEFAULT_PORT + 10)) + [3001]):
        if _open_port(port):
            return f"http://localhost:{port}/v1"
    return None


def resolve_connection() -> dict:
    """Résout URL / clé / modèle MAINTENANT (au démarrage, pas à l'import)."""
    url = detect_base_url() or os.getenv("FREELLMAPI_BASE_URL") or f"http://localhost:{DEFAULT_PORT}/v1"
    return {
        "url": url.rstrip("/"),
        "key": os.getenv("FREELLMAPI_KEY", ""),
        "model": os.getenv("FREELLMAPI_MODEL", "auto"),
    }


def make_llm(temperature: float, strong: bool = False) -> LLM:
    """Construit un LLM pointant sur FreeLLMAPI. 'strong' utilise STRONG_LLM_* si défini."""
    conn = resolve_connection()
    model, url, key = conn["model"], conn["url"], conn["key"]
    if strong and os.getenv("STRONG_LLM_MODEL"):
        model = os.environ["STRONG_LLM_MODEL"]
        url = (os.getenv("STRONG_LLM_BASE_URL") or url).rstrip("/")
        key = os.getenv("STRONG_LLM_KEY") or key
    # Client OpenAI-compatible de CrewAI. Le message d'erreur "OpenAI API" désigne ce protocole,
    # PAS les serveurs d'OpenAI : la requête part bien vers `url`.
    return LLM(
        model=f"openai/{model}",
        base_url=url,
        api_key=key or "missing",
        temperature=temperature,
        timeout=180,
        max_retries=5,
    )
