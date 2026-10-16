Le plan technique pour **FroidPro** a été structuré pour permettre un développement modulaire et testable, en respectant la stack imposée (FastAPI, SQLite, Jinja2).

Voici le contenu complet du fichier `docs/02_plan.md` :

```markdown
# FroidPro — Plan Technique (MVP)

> Objectif : livrer le flux linéaire **Client → Intervention numérotée → Facture (lignes réutilisables) → Statut payé/impayé → KPI**, en une semaine, sur une stack exécutable partout.

## 1. Stack imposée

- **Python 3.11**
- **FastAPI** (API + service web)
- **SQLite** (base unique, fichier `froidpro.db`)
- **Jinja2** (templates HTML simples, responsive mobile-first)
- **pytest** + **httpx** (tests d'acceptation)
- **reportlab** (génération PDF de facture conforme)

## 2. Arborescence exacte

```text
froidpro/
├── app/
│   ├── __init__.py
│   ├── main.py            # Initialisation FastAPI, montage des routes, gestion Jinja2
│   ├── database.py        # Session SQLite, création des tables (SQLAlchemy)
│   ├── models.py          # Modèles SQLAlchemy (ORM)
│   ├── schemas.py         # Schémas Pydantic (Validation)
│   ├── crud.py            # Logique d'accès aux données
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── clients.py     # Gestion de l'annuaire
│   │   ├── interventions.py # Agenda et fiches techniques
│   │   ├── invoices.py    # Facturation et bibliothèque d'articles
│   │   └── dashboard.py   # KPI et accueil
│   ├── static/
│   │   └── style.css      # CSS minimaliste (Water.css ou simple flexbox)
│   └── templates/
│       ├── base.html      # Layout commun (Navbar, Footer)
│       ├── dashboard.html
│       ├── clients/       # list.html, detail.html
│       ├── interventions/ # list.html, form.html
│       └── invoices/      # list.html, detail.html
├── tests/
│   ├── __init__.py
│   ├── test_clients.py
│   ├── test_interventions.py
│   └── test_invoices.py
├── docs/
│   ├── 01_idee.md
│   └── 02_plan.md
├── requirements.txt
└── README.md
```

## 3. Modèle de données (SQLite)

- **Client** : `id`, `nom`, `adresse`, `telephone`, `email`.
- **Intervention** : `id`, `client_id`, `numero` (ex: INT-2024-001), `date_prevue`, `description`, `statut` (A_FAIRE, TERMINE).
- **Article** (Bibliothèque) : `id`, `libelle`, `prix_unitaire_ht`, `taux_tva`.
- **Facture** : `id`, `intervention_id`, `numero` (ex: FACT-2024-001), `date_emission`, `statut` (IMPAYE, PAYE).
- **LigneFacture** : `id`, `facture_id`, `libelle`, `quantite`, `prix_unitaire_ht`, `taux_tva`.

---

## 4. TICKETS

### TICKET 1 : Socle Technique & Base de données
- **Objectif** : Initialiser FastAPI, SQLite et les modèles ORM.
- **Fichiers à créer** : `app/main.py`, `app/database.py`, `app/models.py`, `requirements.txt`.
- **Signature** : `get_db()` pour l'injection de dépendance de session.
- **Critères d'acceptation** :
  - L'application démarre sans erreur (`uvicorn app.main:app`).
  - Le fichier `froidpro.db` est créé avec les tables vides au premier lancement.
  - `pytest` s'exécute et confirme que `/` répond 200.

### TICKET 2 : Annuaire Clients (CRUD)
- **Objectif** : Créer, lister et voir le détail d'un client.
- **Fichiers à créer** : `app/routers/clients.py`, `app/templates/clients/list.html`, `app/templates/clients/form.html`.
- **Signature** : `GET /clients`, `POST /clients/create`, `GET /clients/{id}`.
- **Critères d'acceptation** :
  - Formulaire de création fonctionnel avec validation (nom obligatoire).
  - Liste des clients affichée avec lien vers le détail.
  - Test `test_create_client` valide l'insertion en DB.

### TICKET 3 : Gestion des Interventions & Numérotation
- **Objectif** : Planifier une intervention rattachée à un client avec un numéro auto-incrémenté.
- **Fichiers à créer** : `app/routers/interventions.py`, `app/templates/interventions/list.html`.
- **Signature** : `generate_int_number() -> str`, `POST /interventions/create`.
- **Critères d'acceptation** :
  - Le numéro suit le format `INT-YYYY-XXXX`.
  - Une intervention peut être marquée comme "TERMINEE".
  - Test `test_intervention_numbering` vérifie que deux interventions n'ont pas le même numéro.

### TICKET 4 : Bibliothèque d'Articles & Autocomplétion
- **Objectif** : Gérer les articles réutilisables pour la facturation.
- **Fichiers à créer** : `app/routers/invoices.py` (partie articles), `app/templates/invoices/articles.html`.
- **Signature** : `GET /api/articles/search?q=...` (renvoie du JSON pour l'autocomplétion).
- **Critères d'acceptation** :
  - Possibilité d'ajouter un article (ex: "Déplacement", 45€ HT, 20% TVA).
  - L'API de recherche renvoie les articles correspondants au libellé.

### TICKET 5 : Moteur de Facturation & PDF
- **Objectif** : Transformer une intervention en facture et générer le PDF.
- **Fichiers à créer** : `app/routers/invoices.py`, `app/templates/invoices/detail.html`, `app/utils/pdf_gen.py`.
- **Signature** : `POST /invoices/from-intervention/{id}`, `GET /invoices/{id}/pdf`.
- **Critères d'acceptation** :
  - La facture reprend les lignes saisies (ou issues de la bibliothèque).
  - Le PDF généré contient les mentions légales (SIRET, TVA, Total TTC).
  - Le statut initial est "IMPAYE".

### TICKET 6 : Dashboard, KPI & Statuts
- **Objectif** : Vue d'ensemble financière et bascule de paiement.
- **Fichiers à créer** : `app/routers/dashboard.py`, `app/templates/dashboard.html`.
- **Signature** : `GET /dashboard`, `POST /invoices/{id}/toggle-payment`.
- **Critères d'acceptation** :
  - Affichage du CA total (somme des factures payées).
  - Affichage du montant "En attente" (somme des factures impayées).
  - Un clic sur "Marquer comme payé" met à jour la DB et les KPI instantanément.

### TICKET 7 : README & Finalisation
- **Objectif** : Documentation de lancement et script de démarrage.
- **Fichiers à créer** : `README.md`, `run.sh`.
- **Critères d'acceptation** :
  - Le README explique comment installer les dépendances et lancer l'app.
  - Une commande unique permet de lancer les tests et le serveur.
```