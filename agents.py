"""Équipe resserrée : 4 agents avec des outils réels. Moins de rôles = moins de bruit et de coût."""
from crewai import Agent

from config import MAX_RPM, TASK_TIMEOUT, make_llm
from tools.research_tools import get_research_tools
from tools.workspace_tools import (list_files, read_file, run_python_check,
                                   run_tests, write_file)


def build_agents() -> dict:
    """Construit les agents APRÈS le contrôle de connexion (les LLM lisent l'URL à ce moment-là)."""
    llm_strong = make_llm(0.1, strong=True)
    llm_code = make_llm(0.1)
    llm_creative = make_llm(0.4)

    strategist = Agent(
        role="Stratège Produit",
        goal=("Choisir UN micro-SaaS réaliste (faisable par 1 dev en <1 semaine) en justifiant par des "
              "faits sourcés, et distinguer rigoureusement faits vérifiés et hypothèses."),
        backstory=("Ex-product manager en startup. Tu détestes les idées 'Uber pour X'. Tu exiges un problème "
                   "douloureux, une cible précise qui paie déjà pour une solution imparfaite, et un MVP minimal. "
                   "Tu n'inventes JAMAIS de chiffre de marché : sans source, c'est une hypothèse étiquetée."),
        llm=llm_strong,
        tools=get_research_tools() + [write_file, read_file],
        max_iter=12,
        max_rpm=MAX_RPM,
        max_execution_time=TASK_TIMEOUT,
        allow_delegation=False,
        respect_context_window=True,
        verbose=False,
    )

    architect = Agent(
        role="Architecte Technique",
        goal="Transformer l'idée en tickets numérotés, petits, indépendants et testables.",
        backstory=("Tech lead pragmatique. Stack imposée par défaut : Python 3.11 + FastAPI + SQLite + HTML "
                   "simple (Jinja2), pour rester exécutable partout. Chaque ticket nomme les fichiers à créer "
                   "et des critères d'acceptation vérifiables par pytest."),
        llm=llm_strong,
        tools=[write_file, read_file],
        max_iter=10,
        max_rpm=MAX_RPM,
        max_execution_time=TASK_TIMEOUT,
        allow_delegation=False,
        respect_context_window=True,
        verbose=False,
    )

    developer = Agent(
        role="Développeur Full-Stack",
        goal=("Implémenter les tickets UN PAR UN dans workspace/, avec des tests pytest, jusqu'à ce que "
              "`run_tests` passe. Ne jamais déclarer fini sans test vert."),
        backstory=("Développeur senior TDD. Tu écris le test, puis le code. Tu lis toujours le résultat de "
                   "run_tests et tu corriges le CODE quand il échoue. Tu écris des fichiers complets, jamais de "
                   "'...' ni de TODO. Les imports respectent l'arborescence réelle (list_files)."),
        llm=llm_code,
        tools=[write_file, read_file, list_files, run_tests, run_python_check],
        max_iter=40,                 # le dev a besoin de beaucoup d'itérations (écrire, tester, corriger)
        max_rpm=MAX_RPM,
        max_execution_time=TASK_TIMEOUT * 2,
        allow_delegation=False,
        respect_context_window=True,
        verbose=False,
    )

    qa_engineer = Agent(
        role="Ingénieur QA",
        goal=("Valider le produit par l'EXÉCUTION : lancer les tests, relire le code pour la sécurité "
              "(injections, secrets en dur, validation d'entrées) et rendre un verdict argumenté."),
        backstory=("Auditeur méfiant. Tu ne crois que ce que tu exécutes. Tu cherches : secrets en clair, "
                   "SQL concaténé, absence de validation, endpoints sans test, README absent."),
        llm=llm_strong,
        tools=[read_file, list_files, run_tests, run_python_check, write_file],
        max_iter=15,
        max_rpm=MAX_RPM,
        max_execution_time=TASK_TIMEOUT,
        allow_delegation=False,
        respect_context_window=True,
        verbose=False,
    )

    growth = Agent(
        role="Responsable Acquisition",
        goal=("Produire page de vente, emails et plan d'acquisition honnêtes, conformes RGPD, "
              "sans statistiques ni témoignages inventés."),
        backstory=("Marketeur orienté preuve. Tu écris pour la cible identifiée, tu proposes des canaux "
                   "gratuits d'abord (communautés, SEO long tail, démos). Tout chiffre non sourcé est interdit. "
                   "Tu n'automatises aucun envoi : tu rédiges, un humain envoie."),
        llm=llm_creative,
        tools=[read_file, write_file],
        max_iter=10,
        max_rpm=MAX_RPM,
        max_execution_time=TASK_TIMEOUT,
        allow_delegation=False,
        respect_context_window=True,
        verbose=False,
    )

    return {"strategist": strategist, "architect": architect, "developer": developer,
            "qa_engineer": qa_engineer, "growth": growth}
