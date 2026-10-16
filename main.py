"""Genesis : pipeline séquentiel avec garde-fous, validation humaine et sorties sur disque.

Usage :
    python main.py                     # idée libre
    python main.py --niche "outils pour kinés"   # oriente la recherche
    python main.py --auto              # sans pause humaine (déconseillé)
    python main.py --from-step dev     # reprend à partir d'une étape (idea|plan|dev|qa|growth)
"""
import argparse
import json
import sys
import time
from datetime import datetime

from crewai import Crew, Process, Task

import ui
from config import (LOGS, MAX_QA_RETRIES, MAX_RPM, PLACEHOLDER_KEYS, WORKSPACE, resolve_connection)
from guardrails import (guardrail_code_exists, guardrail_idea, guardrail_marketing,
                        guardrail_plan, guardrail_tests_pass)

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))  # chemins relatifs fiables

STEPS = ["idea", "plan", "dev", "qa", "growth"]


def build_tasks(niche: str | None, human_gates: bool, A: dict):
    strategist, architect, developer = A['strategist'], A['architect'], A['developer']
    qa_engineer, growth = A['qa_engineer'], A['growth']
    focus = f" Domaine imposé : {niche}." if niche else ""

    t_idea = Task(
        description=(
            "Trouve UN micro-SaaS réaliste." + focus + "\n"
            "Méthode : (1) liste 3 candidats, (2) note chacun sur 100 avec ces critères : intensité du "
            "problème (30), disposition à payer (25), concurrence/différenciation (15), faisabilité MVP "
            "en <1 semaine (20), distribution accessible (10), (3) retiens le meilleur.\n"
            "Le document final DOIT contenir les sections : Problème, Cible, Solution, Concurrence, "
            "Monétisation, Risques, MVP (liste de fonctionnalités minimales), Score (format 'Score: NN/100').\n"
            "Règle d'or : tout fait de marché a une source (URL) ou est étiqueté 'HYPOTHÈSE NON VÉRIFIÉE'. "
            "Sauvegarde avec write_file dans 'docs/01_idee.md'."
        ),
        expected_output="Document Markdown structuré, scoré, honnête sur les sources, écrit dans docs/01_idee.md.",
        agent=strategist,
        output_file="workspace/docs/01_idee.out.md",
        guardrail=guardrail_idea,
        guardrail_max_retries=MAX_QA_RETRIES,
        human_input=human_gates,           # ⛳ point de contrôle n°1 : tu valides l'idée
    )

    t_plan = Task(
        description=(
            "Lis docs/01_idee.md. Écris docs/02_plan.md : architecture (stack FastAPI + SQLite + Jinja2), "
            "arborescence exacte, modèle de données, puis des TICKETS numérotés ('TICKET 1: ...'). "
            "Chaque ticket : objectif, fichiers à créer, signature des fonctions/endpoints, "
            "'Critères d'acceptation' testables. 5 à 10 tickets max, ordre de dépendance respecté. "
            "Le dernier ticket = README + lancement."
        ),
        expected_output="Plan technique en tickets numérotés avec critères d'acceptation, dans docs/02_plan.md.",
        agent=architect,
        context=[t_idea],
        output_file="workspace/docs/02_plan.out.md",
        guardrail=guardrail_plan,
        guardrail_max_retries=MAX_QA_RETRIES,
    )

    t_dev = Task(
        description=(
            "Lis docs/02_plan.md. Implémente CHAQUE ticket dans l'ordre, dans workspace/ (app/ pour le code, "
            "tests/ pour les tests). Cycle obligatoire par ticket : écrire le test -> écrire le code -> "
            "run_tests -> corriger tant que ce n'est pas vert. Fichiers COMPLETS, pas de placeholders. "
            "Pas de secret en dur (utilise des variables d'environnement). Valide toutes les entrées. "
            "Termine par un résumé des fichiers créés ET le dernier résultat de run_tests."
        ),
        expected_output="Code + tests dans workspace/, run_tests au vert, résumé des fichiers.",
        agent=developer,
        context=[t_plan],
        guardrail=guardrail_code_exists,
        guardrail_max_retries=MAX_QA_RETRIES,
    )

    t_qa = Task(
        description=(
            "Audit final. (1) list_files + read_file sur tout le code, (2) run_tests, (3) revue sécurité : "
            "secrets en dur, injection SQL, validation d'entrées, gestion d'erreurs, (4) vérifie que chaque "
            "critère d'acceptation du plan est couvert par un test. Si tu trouves un défaut mineur, CORRIGE-le "
            "toi-même avec write_file puis relance run_tests. Écris docs/03_rapport_qa.md : verdict "
            "(GO / NO-GO), défauts trouvés, défauts corrigés, risques résiduels."
        ),
        expected_output="Rapport QA avec verdict GO/NO-GO dans docs/03_rapport_qa.md, tests au vert.",
        agent=qa_engineer,
        context=[t_plan, t_dev],
        output_file="workspace/docs/03_rapport_qa.out.md",
        guardrail=guardrail_tests_pass,    # vérité terrain : on relance pytest nous-mêmes
        guardrail_max_retries=MAX_QA_RETRIES,
        human_input=human_gates,           # ⛳ point de contrôle n°2 : tu valides avant le marketing/mise en ligne
    )

    t_growth = Task(
        description=(
            "À partir de docs/01_idee.md et du produit réel, produis docs/04_marketing.md : "
            "(1) page de vente complète (titre, promesse, bénéfices, FAQ, CTA), "
            "(2) 3 emails de prospection personnalisables, chacun avec lien de désinscription et mention de "
            "l'origine des données (RGPD), (3) plan d'acquisition 30 jours avec canaux gratuits en premier, "
            "(4) 5 hypothèses à tester + métrique de succès pour chacune. "
            "Interdit : statistiques non sourcées, faux témoignages (sinon 'exemple fictif – à remplacer')."
        ),
        expected_output="Pack marketing honnête et conforme dans docs/04_marketing.md.",
        agent=growth,
        context=[t_idea, t_qa],
        output_file="workspace/docs/04_marketing.out.md",
        guardrail=guardrail_marketing,
        guardrail_max_retries=MAX_QA_RETRIES,
    )
    return {"idea": t_idea, "plan": t_plan, "dev": t_dev, "qa": t_qa, "growth": t_growth}


def preflight(skip_check: bool = False) -> dict:
    """Vérifie l'environnement ET fait un vrai appel de test. Retourne la connexion résolue."""
    import importlib.util
    import json
    import urllib.error
    import urllib.request

    problems: list[str] = []
    conn = resolve_connection()
    url, key, model = conn["url"], conn["key"], conn["model"]

    if importlib.util.find_spec("pytest") is None:
        problems.append("pytest manquant  ->  pip install -r requirements.txt")

    if key in PLACEHOLDER_KEYS:
        found = [k for k in ("GROQ_KEY", "GOOGLE_KEY", "COHERE_KEY", "OPENROUTER_KEY", "CLOUDFLARE_KEY") if os.getenv(k)]
        msg = ("FREELLMAPI_KEY absente du .env. Dans FreeLLMAPI : onglet Clés (ou icône de la barre des tâches > "
               "Copy Key), puis ajoute  FREELLMAPI_KEY=freellmapi-...")
        if found:
            msg += f"\n  Tes clés de fournisseurs ({', '.join(found)}) ne servent pas ici : elles se collent dans FreeLLMAPI."
        problems.append(msg)
    if problems:
        ui.fail("Configuration incomplète", problems)
        sys.exit(2)

    # Vrai appel de test : prouve que l'URL, la clé et le modèle fonctionnent ensemble.
    # Marge de tokens large (les modèles "réflexion" en consomment avant de répondre) et plusieurs essais :
    # un 502 "empty_completion" est un incident passager d'un fournisseur gratuit, pas une panne de config.
    def probe() -> tuple[bool, str]:
        body = json.dumps({"model": model, "max_tokens": 256,
                           "messages": [{"role": "user", "content": "Réponds par le mot: ok"}]}).encode()
        req = urllib.request.Request(url + "/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return bool(text.strip()), text

    last_detail, attempts = "", 3
    for i in range(1, attempts + 1):
        try:
            with ui.console.status(f"[cyan]Test de connexion à FreeLLMAPI (essai {i}/{attempts})...[/]"):
                got_text, _ = probe()
            if got_text:
                ui.ok(f"FreeLLMAPI répond  ({url}, modèle « {model} »)")
                break
            last_detail = "réponse vide du modèle"
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode(errors="replace")[:400]
            except Exception:  # noqa: BLE001
                detail = str(e.reason or "")
            if e.code in (401, 403):
                ui.fail("Clé refusée par FreeLLMAPI", [
                    "La clé unifiée du .env n'est pas la bonne (ni une clé Groq/Google).",
                    "Copie-la à nouveau depuis FreeLLMAPI > Clés, sans espace ni guillemets."])
                sys.exit(2)
            if e.code == 404 or ("model" in detail.lower() and "not" in detail.lower() and e.code != 502):
                ui.fail(f"Modèle « {model} » refusé ({e.code})", [
                    detail, "Essaie FREELLMAPI_MODEL=auto dans le .env, ou un identifiant visible dans FreeLLMAPI > Modèles."])
                sys.exit(2)
            last_detail = f"erreur {e.code} : {detail}"   # 429/502/503 : souvent passager, on réessaie
        except Exception as e:  # noqa: BLE001
            ui.fail("FreeLLMAPI injoignable", [
                f"Adresse essayée : {url}",
                "Ouvre l'appli FreeLLMAPI (icône dans la barre des tâches) et laisse-la tourner.",
                "Port desktop par défaut : 31415. Vérifie aussi %APPDATA%\\FreeLLMAPI\\config.json (champ port).",
                f"Détail technique : {e}"])
            sys.exit(2)
        if i < attempts:
            time.sleep(4 * i)
    else:
        ui.fail("FreeLLMAPI est joignable, mais aucun modèle n'a répondu", [
            f"Dernier retour : {last_detail}",
            "La connexion et la clé sont bonnes. Les fournisseurs gratuits renvoient des réponses vides ou saturées.",
            "Dans FreeLLMAPI > Modèles : passe la stratégie sur « Le plus fiable » (au lieu de « Le plus intelligent »).",
            "Vérifie aussi qu'au moins quelques fournisseurs ont une clé valide (onglet Clés, pastille verte).",
            "Puis relance : python main.py --check.  Pour continuer malgré tout : python main.py --skip-check ..."])
        if not skip_check:
            sys.exit(2)

    if not os.getenv("SERPER_API_KEY"):
        ui.warn("SERPER_API_KEY absente : pas de recherche web, l'idée reposera sur des hypothèses étiquetées.")
    return conn


def main():
    ap = argparse.ArgumentParser(description="Genesis : usine IA de micro-SaaS")
    ap.add_argument("--niche", help="Domaine à explorer")
    ap.add_argument("--auto", action="store_true", help="Désactive les validations humaines")
    ap.add_argument("--from-step", choices=STEPS, default="idea", help="Reprendre à une étape")
    ap.add_argument("--check", action="store_true", help="Teste seulement la connexion puis quitte")
    ap.add_argument("--skip-check", action="store_true", help="Ignore l'échec du test de connexion")
    ap.add_argument("--debug", action="store_true", help="Affiche le détail brut de CrewAI")
    args = ap.parse_args()

    ui.quiet_logs(args.debug)
    conn = preflight(args.skip_check)
    if args.check:
        ui.ok("Tout est prêt. Lance maintenant : python main.py --niche \"ton domaine\"")
        return

    from agents import build_agents   # import tardif : les LLM lisent l'URL résolue ci-dessus
    A = build_agents()
    if args.debug:
        for a in A.values():
            a.verbose = True

    (WORKSPACE / "docs").mkdir(parents=True, exist_ok=True)
    tasks = build_tasks(args.niche, human_gates=not args.auto, A=A)
    start = STEPS.index(args.from_step)
    step_keys = STEPS[start:]
    selected = [tasks[s] for s in step_keys]
    used = []
    for t in selected:
        if t.agent not in used:
            used.append(t.agent)

    ui.banner(step_keys, not args.auto, conn["url"], conn["model"], bool(os.getenv("SERPER_API_KEY")))
    progress = ui.Progress(step_keys)
    progress.register()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crew = Crew(agents=used, tasks=selected, process=Process.sequential, memory=False, max_rpm=MAX_RPM,
                output_log_file=str(LOGS / f"run_{stamp}.log"), verbose=args.debug)
    try:
        result = crew.kickoff()
    except KeyboardInterrupt:
        ui.warn("Interrompu. Relance avec --from-step <étape> pour reprendre ; workspace/ est conservé.")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        ui.fail("L'usine s'est arrêtée", [*ui.explain_error(str(e), conn["url"]), str(e)[:400],
                f"Détail complet : logs/run_{stamp}.log  (ou relance avec --debug)",
                "Reprendre sans tout refaire : python main.py --from-step <idea|plan|dev|qa|growth>"])
        sys.exit(1)

    usage = getattr(result, "token_usage", None)
    tokens = usage.model_dump() if hasattr(usage, "model_dump") else str(usage)
    (LOGS / f"run_{stamp}.json").write_text(json.dumps(
        {"date": stamp, "étapes": step_keys, "tokens": tokens}, indent=2, ensure_ascii=False, default=str))
    progress.summary(WORKSPACE, tokens)


if __name__ == "__main__":
    main()
