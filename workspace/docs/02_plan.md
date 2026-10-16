# Plan Technique - FroidPro (MVP Frigoriste)

## 1. Architecture & Stack Technique

- **Langage / Runtime** : Python 3.11+
- **Framework Web** : FastAPI
- **Base de données** : SQLite (via SQLAlchemy)
- **Moteur de templates** : Jinja2
- **Interface UI** : HTML5 / CSS3 avec Tailwind CSS (CDN) – responsive pour mobile et desktop
- **Tests** : Pytest + FastAPI TestClient

## 2. Arborescence Exacte du Projet

```text
froidpro/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py          # Configuration SQLite + session
│   ├── models.py            # Définitions ORM (Client, Intervention, CatalogItem, Invoice, InvoiceItem)
│   ├── schemas.py           # Pydantic models pour validation API
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── dashboard.py     # Tableau de bord KPI
│   │   ├── clients.py        # Gestion annuaire clients
│   │   ├── interventions.py  # Agenda & interventions numérotées
│   │   ├── items.py          # Bibliothèque d'articles (style Henrri)
│   │   └── invoices.py       # Facturation & conversion intervention → facture
│   └── templates/
│       ├── base.html         # Layout commun (header, footer, navigation)
│       ├── dashboard.html    # KPIs, statistiques
│       ├── clients/
│       │   ├── list.html
│       │   └── detail.html
│       ├── interventions/
│       │   ├── list.html
│       │   ├── create.html
│       │   └── detail.html
│       ├── items/
│       │   └── list.html
│       └── invoices/
│           ├── list.html
│           ├── create.html
│           └── detail.html
├── static/
│   └── css/
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Fixtures pytest (base DB, clients)
│   ├── test_clients.py
│   ├── test_interventions.py
│   ├── test_items.py
│   └── test_invoices.py
├── docs/
│   ├── 01_idee.md
│   └── 02_plan.md
├── requirements.txt
└── README.md
```

## 3. Modèle de Données (SQLite – ORM SQLAlchemy)

| Table | Colonnes principales | Description |
|-------|---------------------|-------------|
| **Client** | id (PK), name, address, phone, email, created_at | Fiche client (site, contact) |
| **Intervention** | id (PK), reference (UNIQUE, ex: INT-2026-0001), client_id, scheduled_date, status, description, fluid_type, fluid_qty, signature, created_at | Intervention terrain avec numéro unique, notes, fluide frigorigène, signature tactile |
| **CatalogItem** | id (PK), code, label, unit_price_ht, vat_rate | Bibliothèque d'articles réutilisables (forfait déplacement, recharge R32, etc.) |
| **Invoice** | id (PK), reference (UNIQUE), type (DEVIS/FACTURE), client_id, intervention_id (FK), status, total_ht, total_ttc, created_at | Facture ou devis lié à une intervention |
| **InvoiceItem** | id (PK), invoice_id (FK), label, quantity, unit_price_ht, vat_rate, total_ht | Lignes de la facture (transformation intervention → facture) |

## 4. Tickets de Développement

### TICKET 1 : Infrastructure – Project setup, DB & initial tests
- **Objectif** : Mettre en place FastAPI, SQLite, modèles ORM et layout Jinja2 de base.
- **Fichiers concernés** : `requirements.txt`, `app/database.py`, `app/models.py`, `app/main.py`, `app/templates/base.html`.
- **Endpoints** : `GET /` (redirection vers dashboard).
- **Critères d'acceptation** :
  1. L'application démarre sans erreur via `uvicorn app.main:app --reload`.
  2. Les tables SQLite sont créées automatiquement au premier run.
  3. Un test pytest (`test_app_main.py`) confirme que `GET /` renvoie une réponse HTTP 200.

### TICKET 2 : Module Clients – Annuaire & fiches
- **Objectif** : CRUD pour les clients (création, liste, détail) avec liaison vers les interventions.
- **Fichiers concernés** : `app/schemas.py`, `app/routers/clients.py`, `app/templates/clients/list.html`, `app/templates/clients/detail.html`.
- **Endpoints** : `GET /clients` (liste), `POST /clients` (création), `GET /clients/{id}` (détail).
- **Critères d'acceptation** :
  1. On peut ajouter un client (nom, adresse, téléphone, email) via formulaire POST.
  2. La liste `/clients` affiche tous les clients avec leurs infos.
  3. Le détail d'un client montre ses interventions associées.
  4. Test pytest valide la création d'un client en base et son affichage.

### TICKET 3 : Module Interventions – Agenda & numérotation
- **Objectif** : Gérer le planning des interventions avec numéro unique (`INT-XXXX`), notes, fluide, signature.
- **Fichiers concernés** : `app/routers/interventions.py`, `app/templates/interventions/list.html`, `create.html`, `detail.html`.
- **Endpoints** : `GET /interventions` (liste filtrée), `GET /interventions/new` (création), `POST /interventions` (création), `GET /interventions/{id}`, `POST /interventions/{id}/sign` (signature).
- **Critères d'acceptation** :
  1. Chaque intervention reçoit un numéro séquentiel unique (ex: `INT-2026-0001`).
  2. L'interface permet de saisir date, description, type de fluide, quantité, et uploader des photos.
  3. La signature tactile est stockée en base (base64) et liée à l'intervention.
  4. Test pytest vérifie la génération du numéro et l'insertion en base.

### TICKET 4 : Bibliothèque d'Articles – Lignes réutilisables (style Henrri)
- **Objectif** : Créer et gérer la bibliothèque d'articles préenregistrés pour accélérer la facturation.
- **Fichiers concernés** : `app/routers/items.py`, `app/templates/items/list.html`.
- **Endpoints** : `GET /items` (liste), `POST /items` (ajout article), `GET /api/items` (API JSON pour auto‑complétion front‑end).
- **Critères d'acceptation** :
  1. Un artisan peut ajouter un article (code, label, prix HT, TVA) dans la bibliothèque.
  2. L'endpoint `/api/items` retourne tous les articles avec leur code et prix.
  3. Test pytest valide l'ajout d'un article et sa récupération via l'API.

### TICKET 5 : Moteur de Facturation – Conversion intervention → facture
- **Objectif** : Transformer une intervention en Devis ou Facture conforme, avec bibliothèque d'articles, calcul automatique des totaux et gestion des statuts de paiement.
- **Fichiers concernés** : `app/routers/invoices.py`, `app/templates/invoices/list.html`, `create.html`, `detail.html`.
- **Endpoints** : `GET /invoices` (liste), `GET /invoices/new` (création), `POST /invoices` (enregistrement), `GET /invoices/{id}` (détail), `POST /invoices/{id}/status` (basculer Payée/Impayée).
- **Critères d'acceptation** :
  1. On peut créer une facture liée à un client en ajoutant des lignes de la bibliothèque (ou personnalisées).
  2. Les totaux HT et TTC sont calculés automatiquement (TVA incluse).
  3. Le statut d'une facture peut être changé de "Émise" à "Payée" via l'endpoint.
  4. Test pytest vérifie le calcul des montants et la mise à jour du statut.

### TICKET 6 : Tableau de Bord KPI & Documentation Finale
- **Objectif** : Dashboard synthétique (CA, impayés, interventions) et README + instructions de lancement.
- **Fichiers concernés** : `app/routers/dashboard.py`, `app/templates/dashboard.html`, `README.md`.
- **Endpoints** : `GET /dashboard` (KPIs).
- **Critères d'acceptation** :
  1. Le tableau de bord affiche le Chiffre d'Affaires total, le montant des impayés et le nombre d'interventions terminées.
  2. Le `README.md` décrit l'installation (`pip install -r requirements.txt`), les commandes de test (`pytest`), et le lancement (`uvicorn app.main:app --reload`).
  3. Tous les tests unitaires et d'intégration passent sous `pytest`.

---

**Résumé des dépendances** : TICKET 1 → TICKET 2 → TICKET 3 → TICKET 4 → TICKET 5 → TICKET 6 (linéaire, chaque ticket s'appuie sur les précédents).
