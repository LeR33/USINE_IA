"""Outils de recherche. Dégradent proprement si SERPER_API_KEY est absent."""
import os

from crewai.tools import tool


def get_research_tools():
    tools = []
    if os.getenv("SERPER_API_KEY"):
        from crewai_tools import ScrapeWebsiteTool, SerperDevTool
        tools += [SerperDevTool(), ScrapeWebsiteTool()]
    else:
        tools.append(no_web_notice)
    return tools


@tool("no_web_notice")
def no_web_notice() -> str:
    """Indique qu'aucun accès web n'est configuré. À appeler pour savoir si tes affirmations
    de marché sont vérifiables."""
    return ("AUCUN ACCÈS WEB configuré (SERPER_API_KEY absente). Tu dois étiqueter chaque "
            "affirmation de marché comme 'HYPOTHÈSE NON VÉRIFIÉE' et ne jamais inventer de chiffres.")
