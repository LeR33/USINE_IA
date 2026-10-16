# Cahier des charges V2 : FroidPro

## Ticket 1 : Paramètres de la société (page Admin)
- Page /admin/parametres : nom de la société, logo (upload), adresse, SIRET, n° TVA, IBAN, téléphone, email, mentions légales, conditions de paiement, préfixe et prochain numéro de facture, taux de TVA par défaut, couleur principale.
- Ces données alimentent la facture PDF, l'en-tête de l'appli et les devis (plus aucune donnée codée en dur type "FroidPro SARL, 123 Rue du Froid").
- Critères d'acceptation : modifier le nom de société change l'en-tête et le PDF ; test pytest.

## Ticket 2 : Interventions modifiables
- Liste des interventions avec boutons Ajouter, Modifier, Supprimer (avec confirmation), filtres par statut, client, date, recherche.
- Formulaire : client, date, heure début/fin, type, technicien, statut (planifiée, en cours, terminée, annulée), description, lignes d'articles, durée.
- Critères d'acceptation : créer, modifier, supprimer fonctionnent ; tests pytest.

## Ticket 3 : Vue Planning
- Page /planning en vue semaine et mois (calendrier avec créneaux horaires), interventions affichées sur leurs créneaux, couleur selon le statut, clic pour ouvrir/modifier, glisser-déposer pour déplacer, bouton "Nouvelle intervention" sur un créneau.
- Critères d'acceptation : une intervention créée apparaît dans le bon créneau ; déplacer met à jour la date.

## Ticket 4 : Clients CRUD complet
- Liste, fiche, création, modification, suppression (avec avertissement si interventions liées), recherche, notes, historique des interventions et des factures du client.

## Ticket 5 : Catalogue articles / prestations CRUD
- Liste, création, modification, suppression ; champs : référence, désignation, prix HT, TVA, unité, catégorie (main d'oeuvre, pièce, fluide), actif/inactif.
- Ajout rapide d'articles dans une intervention ou une facture depuis ce catalogue.

## Ticket 6 : Facturation
- Création de facture depuis une intervention (reprend les articles), calcul automatique HT/TVA/TTC, statut (brouillon, envoyée, payée, en retard), date d'échéance, PDF propre avec le logo et les infos société des Paramètres, bouton "marquer payée".

## Ticket 7 : Tableau de bord utile
- Cartes : interventions du jour, de la semaine, factures impayées (montant), chiffre d'affaires du mois, clients actifs.
- Raccourcis en grands boutons : Nouvelle intervention, Nouveau client, Nouvelle facture, Planning, Articles.
- Listes : prochaines interventions, factures en retard, activité récente. Graphique du CA sur 6 mois.

## Ticket 8 : Design professionnel
- Menu latéral avec icônes, en-tête avec nom de la société et logo, palette sobre configurable, polices lisibles, cartes avec ombres légères, tableaux avec tri et recherche, messages de succès/erreur, états vides soignés, responsive (mobile et tablette), mode sombre optionnel.
- Utiliser une bibliothèque CSS locale ou un CDN (Tailwind ou Bootstrap 5) plutôt que du CSS à la main.

## Ticket 9 : Qualité
- Validation des formulaires, messages en français, tests pytest pour chaque ticket, README mis à jour.
