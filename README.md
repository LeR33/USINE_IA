# Genesis : usine IA de micro-SaaS (CrewAI)

Pipeline séquentiel : **Idée -> Plan -> Dev -> QA -> Marketing**, avec outils réels, garde-fous objectifs
et deux points de contrôle humains.

## Installation
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis remplir FREELLMAPI_KEY (et SERPER_API_KEY si possible)
```

## Démarrage rapide (appli desktop FreeLLMAPI)
1. Lance FreeLLMAPI (icône dans la barre des tâches) et colle tes clés de fournisseurs dans son onglet **Clés**.
2. Copie la **clé unifiée** (`freellmapi-...`) : onglet Clés, ou icône > *Copy Key*.
3. Dans `.env` du projet, seulement :
   ```
   FREELLMAPI_KEY=freellmapi-ta-cle
   FREELLMAPI_MODEL=auto
   ```
   Le port est détecté automatiquement (desktop = 31415, Docker = 3001).
4. Teste : `python main.py --check`  (fait un vrai appel et explique l'erreur si besoin).

## Lancer
```bash
python main.py --niche "outils pour kinésithérapeutes"
python main.py --from-step dev      # reprendre après un arrêt
python main.py --auto               # sans validation humaine
python main.py --debug              # détail brut de CrewAI
```

## Ce qui change vs la V1
| V1 | V2 |
|---|---|
| 10 agents, même LLM, aucun outil | 4 agents, outils réels (fichiers, pytest, web) |
| Mode hiérarchique (coûteux, instable) | Séquentiel + `context=[...]` explicites |
| QA = avis d'un LLM | QA = `pytest` relancé par le code (guardrail) |
| 1 tâche "écris tout" | Tickets numérotés, TDD, boucle de correction |
| Aucun contrôle | 2 validations humaines, budget d'itérations, logs, reprise |
| Chiffres inventés possibles | Faits sourcés ou "HYPOTHÈSE NON VÉRIFIÉE" |

## Si FreeLLMAPI répond « 502 empty_completion »
Les modèles gratuits renvoient parfois des réponses vides ou saturées : ce n'est pas ta configuration.
Genesis réessaie tout seul (3 essais au démarrage, 5 par appel). Si ça persiste :
- FreeLLMAPI > Modèles : stratégie « Le plus fiable » plutôt que « Le plus intelligent »
- Onglet Clés : garde plusieurs fournisseurs actifs (pastille verte)
- `python main.py --skip-check --niche "..."` pour lancer malgré l'échec du test

## Limites assumées
- Le produit n'est **jamais déployé ni vendu automatiquement** : tu valides et tu distribues.
- Aucun email n'est envoyé : l'agent rédige, un humain envoie (RGPD, réputation du domaine).
- Sans `SERPER_API_KEY`, l'idée repose sur des hypothèses étiquetées comme telles.
