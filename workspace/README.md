# FroidPro V2

Application web de gestion pour techniciens frigoristes : clients, interventions, planning, catalogue d'articles,
facturation PDF et tableau de bord. Stack : Python 3.11+, FastAPI, SQLite, Jinja2, Bootstrap 5 (CDN), Chart.js (CDN).

## Installation et lancement

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
pytest                                                  # lance les tests (base temporaire, vos données ne sont pas touchées)
uvicorn app.main:app --reload                           # http://127.0.0.1:8000
```

Ou simplement `bash run.sh`. La base SQLite est créée dans `data/froidpro.db` au premier lancement.

Variables d'environnement (facultatives) :

| Variable | Rôle |
|---|---|
| `FROIDPRO_DB` | chemin du fichier SQLite (défaut `data/froidpro.db`) |
| `FROIDPRO_SECRET` | clé de signature des sessions (messages flash). **À définir en production.** |

> Bootstrap et Chart.js sont chargés depuis un CDN : une connexion Internet est nécessaire pour l'affichage.
> L'application n'a **pas d'authentification** : ne l'exposez pas sur Internet sans reverse-proxy protégé (Basic Auth, VPN).

## Fonctionnalités

1. **Paramètres** (`/admin/parametres`) : nom, logo (PNG/JPEG, 2 Mo), adresse, SIRET, TVA, IBAN, contacts, mentions légales,
   conditions de paiement (le nombre de jours fixe l'échéance), préfixe et prochain numéro de facture, TVA par défaut,
   couleur principale. Ces données alimentent l'en-tête, la couleur de l'interface et le PDF.
2. **Interventions** (`/interventions`) : ajouter, modifier, supprimer (avec confirmation), filtres statut / client / dates /
   recherche, lignes d'articles, durée calculée.
3. **Planning** (`/planning`) : vues semaine et mois, couleur selon le statut, clic sur un créneau pour créer,
   glisser-déposer pour déplacer (la durée est conservée).
4. **Clients** : CRUD complet, recherche, notes, historique des interventions et factures, avertissement avant suppression.
5. **Articles** : catalogue (référence, prix HT, TVA, unité, catégorie, actif), ajout rapide dans une intervention.
6. **Facturation** : facture créée depuis une intervention, HT/TVA/TTC, statuts brouillon / envoyée / payée / en retard
   (calculé automatiquement après l'échéance), bouton « marquer payée », PDF avec logo et infos société.
7. **Tableau de bord** : cartes, raccourcis, prochaines interventions, factures en retard, activité, CA encaissé sur 6 mois.
8. **Design** : menu latéral, Bootstrap 5, tableaux triables/recherchables, responsive, mode sombre (bouton en haut à droite).

## Tests

Un fichier par ticket dans `tests/` (`test_ticket1_parametres.py` … `test_ticket9_qualite.py`). `pytest` les lance tous.

## Structure

```
app/main.py        routes HTTP          app/services.py   logique métier + validation (messages en français)
app/models.py      modèles SQLAlchemy   app/utils/pdf_gen.py  génération du PDF
app/templates/     pages Jinja2         app/static/uploads/  logo envoyé
```

## Limites connues

- Pas d'authentification ni de multi-utilisateurs.
- Pas de devis dédiés : seules les factures sont générées (le modèle de paramètres est prêt à les accueillir).
- Une facture est liée à une seule intervention.
