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
| `FROIDPRO_SECRET` | clé de signature des sessions. Si absente, une clé aléatoire est générée dans `data/.secret_key` (à conserver). |
| `FROIDPRO_AUTH` | `off` désactive la connexion (usage strictement local, déconseillé). |

> Bootstrap et Chart.js sont chargés depuis un CDN : une connexion Internet est nécessaire pour l'affichage.

## Connexion et sécurité

Au **premier lancement**, la page `/installation` demande de créer le compte administrateur (e-mail + mot de passe d'au moins
10 caractères avec une lettre et un chiffre). Ensuite toutes les pages exigent une connexion.

- Mots de passe hachés (PBKDF2-SHA256, sel aléatoire), jamais stockés en clair.
- Protection CSRF sur tous les formulaires et appels POST.
- Blocage après 5 échecs de connexion en 5 minutes (par adresse IP).
- Session de 12 h, renouvelée à chaque connexion. Mot de passe modifiable depuis le menu en haut à droite.
- **Mot de passe oublié** : supprimez la ligne de la table `utilisateurs` (ou le fichier `data/froidpro.db` si vous n'avez pas de données), puis relancez : la page d'installation réapparaît.
- En ligne publique, placez l'application derrière HTTPS (reverse-proxy) : sans HTTPS, les mots de passe circulent en clair.

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
6. **Devis** (`/devis`) : création avec lignes et catalogue, numéro `DEV-AAAA-NNNN`, validité 30 jours par défaut,
   statuts brouillon / envoyé / accepté / refusé (« expiré » calculé automatiquement), PDF avec « bon pour accord ».
   Un devis accepté se convertit en intervention (lignes reprises), puis en facture : les montants restent identiques.
7. **Facturation** : facture créée depuis une intervention, HT/TVA/TTC, statuts brouillon / envoyée / payée / en retard
   (calculé automatiquement après l'échéance), bouton « marquer payée », PDF avec logo et infos société.
8. **Tableau de bord** : cartes, raccourcis, prochaines interventions, factures en retard, activité, CA encaissé sur 6 mois.
9. **Design** : menu latéral, Bootstrap 5, tableaux triables/recherchables, responsive, mode sombre (bouton en haut à droite).

## Tests

Un fichier par fonctionnalité dans `tests/` (`test_ticket1_parametres.py` … `test_ticket11_devis.py`). `pytest` les lance tous.

## Structure

```
app/main.py        routes HTTP          app/services.py   logique métier + validation (messages en français)
app/models.py      modèles SQLAlchemy   app/utils/pdf_gen.py  génération du PDF
app/templates/     pages Jinja2         app/static/uploads/  logo envoyé
```

## Limites connues

- Un seul compte administrateur (pas de rôles ni de multi-utilisateurs).
- Une facture est liée à une seule intervention.
