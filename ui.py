"""Console propre pour Genesis : une ligne par événement utile, un tableau de bord final.
Le détail brut de CrewAI part dans logs/run_*.log (verbose=False côté agents)."""
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def quiet_logs(debug: bool = False) -> None:
    """Réduit le bruit des bibliothèques : les erreurs utiles passent par nos messages."""
    import logging
    import warnings
    if debug:
        return
    warnings.filterwarnings("ignore")
    # CrewAI imprime certains avertissements d'événements directement sur stdout : on les filtre.
    import builtins
    import io
    import sys

    class _Filter(io.TextIOBase):
        def __init__(self, inner):
            self.inner = inner
        def write(self, text):
            if "[CrewAIEventsBus]" in text or "Event pairing mismatch" in text or text.strip() in ("'llm_call_started')",):
                return len(text)
            return self.inner.write(text)
        def flush(self):
            self.inner.flush()
        def __getattr__(self, name):
            return getattr(self.inner, name)

    if not isinstance(sys.stdout, _Filter):
        sys.stdout = _Filter(sys.stdout)
        console.file = sys.stdout
    for name in ("root", "crewai", "crewai.flow.runtime", "LiteLLM", "httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    logging.disable(logging.CRITICAL)


def explain_error(err: str, base_url: str) -> list[str]:
    """Traduit les erreurs CrewAI/OpenAI-client en cause concrète. 'OpenAI API' = le protocole, pas le service."""
    low = err.lower()
    if "connection error" in low or "connect" in low:
        return [f"Genesis n'arrive plus à joindre FreeLLMAPI ({base_url}).",
                "Ce n'est PAS OpenAI : « OpenAI API » désigne seulement le format de dialogue utilisé.",
                "Vérifie que l'appli FreeLLMAPI tourne toujours (icône dans la barre des tâches), puis relance avec --from-step."]
    if "401" in low or "invalid api key" in low or "authentication" in low:
        return ["Clé refusée : recopie la clé unifiée depuis FreeLLMAPI > Clés."]
    if "429" in low or "rate limit" in low or "quota" in low:
        return ["Quotas gratuits atteints chez les fournisseurs. Attends quelques minutes ou ajoute des clés dans FreeLLMAPI."]
    if "timeout" in low or "timed out" in low:
        return ["Le modèle a mis trop de temps à répondre. Réessaie, ou baisse la charge avec MAX_RPM dans le .env."]
    return []

STEP_LABELS = {
    "idea": ("1", "Idée", "Stratège Produit"),
    "plan": ("2", "Plan", "Architecte Technique"),
    "dev": ("3", "Développement", "Développeur Full-Stack"),
    "qa": ("4", "Contrôle qualité", "Ingénieur QA"),
    "growth": ("5", "Marketing", "Responsable Acquisition"),
}


def banner(steps: list[str], human: bool, base_url: str, model: str, web: bool) -> None:
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column()
    t.add_row("Étapes", "  >  ".join(STEP_LABELS[s][1] for s in steps))
    t.add_row("Validation humaine", "oui (idée + QA)" if human else "non (mode auto)")
    t.add_row("LLM", f"{model}  @  {base_url}")
    t.add_row("Recherche web", "[green]activée[/]" if web else "[yellow]désactivée (hypothèses étiquetées)[/]")
    console.print(Panel(t, title="[bold cyan]GENESIS[/]  usine IA de micro-SaaS", border_style="cyan", padding=(1, 2)))


def ok(msg: str) -> None:
    console.print(f"[green]✔[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]![/] {msg}")


def fail(title: str, lines: list[str]) -> None:
    body = Text()
    for i, l in enumerate(lines):
        body.append(("• " if i else "") + l + "\n")
    console.print(Panel(body, title=f"[bold red]{title}[/]", border_style="red", padding=(1, 2)))


class Progress:
    """Suit les tâches via le bus d'événements CrewAI et affiche une ligne par changement d'état."""

    def __init__(self, steps: list[str]):
        self.steps = steps
        self.index = 0
        self.t0 = time.time()
        self.step_t0 = time.time()
        self.tools = 0
        self.rows: list[tuple[str, str, float, int]] = []  # (étape, statut, durée, appels d'outils)
        self.registered = False

    def register(self) -> None:
        if self.registered:
            return
        from crewai.events import crewai_event_bus
        from crewai.events.types.task_events import TaskCompletedEvent, TaskFailedEvent, TaskStartedEvent
        from crewai.events.types.tool_usage_events import ToolUsageFinishedEvent

        @crewai_event_bus.on(TaskStartedEvent)
        def _start(source, event):  # noqa: ANN001
            self.step_t0, self.tools = time.time(), 0
            key = self.steps[min(self.index, len(self.steps) - 1)]
            n, label, agent = STEP_LABELS[key]
            console.rule(f"[bold]Étape {n}/5  {label}[/]  [dim]{agent}[/]", style="cyan")

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def _tool(source, event):  # noqa: ANN001
            self.tools += 1
            name = getattr(event, "tool_name", "outil")
            console.print(f"   [dim]·[/] {name}", highlight=False)

        @crewai_event_bus.on(TaskCompletedEvent)
        def _done(source, event):  # noqa: ANN001
            key = self.steps[min(self.index, len(self.steps) - 1)]
            d = time.time() - self.step_t0
            self.rows.append((key, "ok", d, self.tools))
            ok(f"{STEP_LABELS[key][1]} terminé en {d:.0f}s ({self.tools} appels d'outils)")
            self.index += 1

        @crewai_event_bus.on(TaskFailedEvent)
        def _failed(source, event):  # noqa: ANN001
            key = self.steps[min(self.index, len(self.steps) - 1)]
            self.rows.append((key, "échec", time.time() - self.step_t0, self.tools))

        self.registered = True

    def summary(self, workspace, tokens) -> None:
        t = Table(title="Résumé", title_style="bold", border_style="dim", header_style="bold cyan")
        for c in ("Étape", "Statut", "Durée", "Outils"):
            t.add_column(c)
        for key, status, d, tools in self.rows:
            t.add_row(STEP_LABELS[key][1], "[green]ok[/]" if status == "ok" else "[red]échec[/]", f"{d:.0f}s", str(tools))
        console.print(t)

        total = time.time() - self.t0
        if isinstance(tokens, dict):
            tok = (f"{tokens.get('total_tokens', 0):,} tokens  ·  {tokens.get('successful_requests', 0)} requêtes"
                   .replace(",", " "))
        else:
            tok = str(tokens)
        names = ["01_idee.md", "02_plan.md", "03_rapport_qa.md", "04_marketing.md"]
        docs = workspace / "docs"
        made = [n for n in names if (docs / n).exists()]
        files = "  ".join(made) if made else "(aucun fichier .md dans docs/)"
        console.print(Panel(
            f"Durée : [bold]{total/60:.1f} min[/]   ·   {tok}\n"
            f"Dossier : [bold]{workspace}[/]\n"
            f"Livrables : {files}\n\n"
            "[yellow]Relis le rapport QA et le pack marketing avant toute mise en ligne ou envoi.[/]",
            title="[bold green]Terminé[/]", border_style="green", padding=(1, 2)))
