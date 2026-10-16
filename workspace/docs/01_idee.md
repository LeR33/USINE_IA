# Évaluation des Candidats & Sélection de l'Idée Micro-SaaS (Frigoriste)

## 1. Analyse et Comparatif de 3 Candidats (Gestion Frigoriste)

| Critère (Pondération) | Candidat 1 : FroidPro (Clouddi Métier + Henrri Facturation) | Candidat 2 : FroidSimple (MVP Facturation seule) | Candidat 3 : FroidMobile (App saisie terrain) |
| :--- | :---: | :---: | :---: |
| **Intensité du problème** (/30) | 30 | 25 | 20 |
| **Disposition à payer** (/25) | 25 | 20 | 15 |
| **Concurrence & Différenciation** (/15) | 14 | 10 | 10 |
| **Faisabilité MVP (<1 sem)** (/20) | 16 | 18 | 19 |
| **Distribution accessible** (/10) | 9 | 8 | 8 |
| **SCORE TOTAL** | **94/100** | **81/100** | **72/100** |

### Détail de l'arbitrage
- **FroidPro (94/100) - RETENU** : Fusionne exactement le meilleur des deux mondes dans une seule interface web responsive :
  1. **La puissance métier de Clouddi** : Agenda des interventions numérotées, dossier d'intervention complet (pièces jointes, photos, texte, dates/heures, signature de devis et fiches CERFA 15497, annuaire clients).
  2. **La simplicité de facturation d'Henrri** : Factures et devis 100% conformes aux mentions légales, bibliothèque d'articles/lignes réutilisables (ex: rappel automatique de la ligne "Déplacement" ou "Main d'œuvre"), gestion des statuts payé/impayé, et tableau de bord avec KPI financiers.

---

Score: 94/100

---

## Problème

Le technicien frigoriste indépendant perd quotidiennement entre 1h et 2h en double saisie et gestion administrative fragmentée :

1. **Rupture entre le terrain et la comptabilité** : L'artisan utilise un outil métier ou du papier pour ses interventions terrain (type Clouddi / fiches CERFA), puis doit réécrire manuellement toutes les lignes de prestation dans un logiciel de facturation séparé (type Henrri ou Tolteck).
2. **Saisie répétitive et perte de temps** : Absence de bibliothèque de lignes préenregistrées : il doit retaper manuellement les libellés récurrents ("Forfait déplacement zone 1", "Recherche de fuite", "Recharge R32").
3. **Impayés non suivis et manque de visibilité** : Incapacité à voir en temps réel depuis son smartphone le statut des règlements (qui a payé, qui doit être relancé) et le chiffre d'affaires généré par période ou par type d'intervention.
4. **Usines à gaz inadaptées** : Clouddi est un ERP complet souvent lourd et coûteux, tandis qu'Henrri est un facturier générique qui ignore les contraintes techniques du froid (CERFA 15497, gestion des fluides, photos avant/après).

---

## Cible

### Cible Principale (ICP)
- **Profil** : Technicien frigoriste / climaticien indépendant, artisan solo ou TPE de dépannage/maintenance CVC (1 à 3 techniciens).
- **Besoin central** : Une application web unique réunissant sur le même écran l'intervention technique (style Clouddi) et la facturation assistée avec KPI (style Henrri).
- **Comportement actuel** :
  - Jongle entre un agenda Google Calendar, des feuilles d'intervention papier ou photos WhatsApp, et un logiciel de devis/facture.
  - Paie déjà entre 20 € et 40 € HT/mois pour un ou plusieurs outils imparfaits, ou subit la lourdeur des ERP complexes.

---

## Solution

**FroidPro** : La plateforme web tout-en-un qui combine la gestion terrain de **Clouddi** et l'efficacité de facturation d'**Henrri**, 100% accessible sur navigateur mobile, tablette et desktop.

### 1. Module Terrain & Opérations (Capacités Clouddi) :
- **Agenda d'interventions numérotées** : Planning visuel avec numéro d'intervention unique incrémenté automatiquement (ex: `INT-2026-0042`), date, heure de début/fin, technicien assigné et statut (À faire, En cours, Terminé).
- **Dossier d'intervention complet** :
  - Rattachement immédiat à une fiche client.
  - Saisie de notes techniques et diagnostic.
  - Ajout de pièces jointes (photos avant/après du groupe froid, schémas).
  - Traçabilité des fluides frigorigènes et génération du **CERFA 15497**.
- **Signature électronique sur écran** : Faire signer au client le devis ou le compte-rendu d'intervention directement sur le smartphone/tablette.
- **Annuaire client centralisé** : Fiche client avec coordonnées, historique des équipements installés et historique de toutes les interventions passées.

### 2. Module Facturation, Lignes Réutilisables & KPI (Capacités Henrri) :
- **Conversion en 1 clic** : Transformation instantanée d'une intervention terminée en devis ou facture conforme.
- **Bibliothèque d'articles et lignes enregistrables** :
  - Chaque ligne saisie sur une facture (ex: "Déplacement forfaitaire", "Contrôle d'étanchéité", "Fluide R410A au kg") peut être enregistrée en bibliothèque.
  - Recherche instantanée par auto-complétion : taper "déplac..." remplit automatiquement la description, le taux de TVA et le tarif unitaire.
- **Factures conformes** : Respect des mentions légales obligatoires (numérotation chronologique continue, TVA, mentions d'assurance décennale, pénalités de retard).
- **Suivi des règlements** : Statut visuel clair pour chaque facture (**Payée**, **En attente**, **En retard / Impayée**).
- **Tableau de bord & KPI** :
  - Chiffre d'affaires mensuel et annuel en direct.
  - Montant total des factures impayées à relancer.
  - Taux de transformation des devis et volume d'interventions réalisées.

---

## Concurrence

| Concurrent | Positionnement & Prix | Limites face à notre cible | Notre Différenciation |
| :--- | :--- | :--- | :--- |
| **Clouddi** | ERP complet de maintenance/SAV (Source : https://clouddi.fr/). | Solution lourde, paramétrage complexe, interface dense moins rapide pour la facturation d'un artisan solo. | **Expérience utilisateur ultra-rapide** : interface web épurée, prise en main en 5 minutes, aucun déploiement lourd. |
| **Henrri** | Facturation gratuite en ligne pour TPE (Source : https://www.henrri.com/). | Facturier 100% généraliste : **aucun agenda d'intervention**, pas de gestion de fluides frigorigènes, pas de CERFA 15497, pas de signature de bon terrain. | **Spécialisation métier frigoriste** intégrée nativement à la facturation. |
| **Organilog / InterFast** | Logiciels d'intervention F-Gas. Prix : 35 € à 40 € HT/mois (Source : https://fr.organilog.com/offre/). | Souvent orientés PME multi-équipes avec options tarifaires fragmentées. | **Le meilleur des deux mondes** (Clouddi + Henrri) pour un tarif indépendant accessible de 29 € HT/mois. |

---

## Monétisation

### Modèle tarifaire (SaaS B2B sans engagement)
- **Essai gratuit 14 jours** : Sans carte bancaire, accès complet à l'agenda, à la facturation et à 10 interventions/factures d'essai.
- **Formule Artisan Solo** : **29 € HT / mois** (ou 290 € HT / an avec 2 mois offerts)
  - Nombre d'interventions et de clients illimité.
  - Agenda complet et numérotation automatique.
  - Génération de factures/devis conformes et CERFA 15497 PDF.
  - Bibliothèque de lignes réutilisables illimitée.
  - Tableau de bord KPI (CA, factures payées/impayées).
- **Formule Équipe (jusqu'à 3 techniciens)** : **59 € HT / mois** (partage d'agenda et synchronisation des chantiers).

---

## Risques & Mitigations

1. **Périmètre fonctionnel ambitieux pour le MVP (< 1 semaine)**
   - *Risque* : Vouloir coder un ERP géant dès le départ.
   - *Mitigation* : Coder uniquement le flux direct linéaire : **Créer Client -> Planifier Intervention numérotée -> Générer Facture avec lignes préenregistrées -> Marquer Payé/Impayé**. Les fonctionnalités avancées (gestion fine des stocks, export comptable FEC complexe) sont remises en v2.
2. **Conformité stricte de la facturation**
   - *Risque* : Rejet par les experts-comptables si les mentions légales de facturation sont incomplètes.
   - *Mitigation* : Utiliser un gabarit PDF standardisé intégrant toutes les mentions obligatoires du Code de commerce (TVA, numéro SIRET, date d'échéance, pénalités de retard).
3. **Utilisation sur le terrain sans réseau (Zone blanche)**
   - *Risque* : Le technicien dans une cave ou un local technique froid n'a pas de réseau 4G.
   - *Mitigation* : Web application développée en PWA (Progressive Web App) avec cache local pour permettre la consultation de l'intervention et la prise de notes hors-ligne, synchronisée dès le retour du réseau.

---

## MVP (Liste des fonctionnalités minimales livrables en < 1 semaine)

*Architecture technique : Next.js 14 (App Router) + Supabase (PostgreSQL, Auth, Storage) + Tailwind CSS + PDFKit / React-PDF + Stripe Billing.*

1. **Module Clients & Annuaire (0.5 jour)**
   - Fiche client : Nom/Société, adresse du site, téléphone, e-mail.
   - Historique des interventions rattachées.

2. **Module Agenda & Interventions Numérotées (1.5 jour)**
   - Calendrier hebdomadaire et mensuel réactif.
   - Modal de création d'intervention avec numéro unique auto-généré (`INT-XXXX`).
   - Champs : Client, date/heure, description technique, upload photos/pièces jointes (Supabase Storage).
   - Zone de signature tactile sur écran (HTML5 Canvas).

3. **Moteur de Facturation & Bibliothèque d'Articles "Style Henrri" (1.5 jour)**
   - Transformation directe d'une intervention en Facture (`FACT-XXXX`) ou Devis.
   - **Bibliothèque de lignes réutilisables** : table d'articles mémorisés (intitulé, prix unitaire HT, TVA). Recherche dynamique avec auto-complétion pour insérer "Déplacement", "Recherche de fuite", etc.
   - Génération du PDF de facture conforme et téléchargeable.

4. **Tableau de Bord KPI & Statuts Financiers (1 jour)**
   - Statut de chaque facture : Bouton bascule 🟢 **Payée** / 🔴 **Impayée**.
   - 3 widgets KPI clés : Chiffre d'Affaires du mois, Total des Factures Impayées, Nombre d'interventions clôturées.

5. **Abonnement & Accès Stripe (0.5 jour)**
   - Portail client Stripe Checkout pour activer l'abonnement à 29 € HT/mois à l'issue de l'essai.

---

## Sources et Références de Marché

1. **Positionnement ERP Clouddi** : Site officiel Clouddi - *"ERP métier des entreprises de maintenance, SAV et installation : planning, interventions, facturation..."*  
   URL : https://clouddi.fr/
2. **Fonctionnalités Facturation Henrri** : Site officiel Henrri - *"Logiciel de facturation en ligne, création de devis et factures, suivi des paiements et relances..."*  
   URL : https://www.henrri.com/
3. **Tarification Logiciels Métier Froid (Organilog)** : Organilog Offre Officielle - *"Tarif Logiciel gestion d'interventions : 35 € HT par mois et par utilisateur..."*  
   URL : https://fr.organilog.com/offre/
4. **Tarification Logiciel Facturation BTP (Tolteck)** : Tolteck France - *"Dès 19 € à 25 € / mois pour artisans du bâtiment..."*  
   URL : https://www.tolteck.com/fr-fr/
5. **Cadre réglementaire de l'intervention frigorifique (CERFA 15497\*04)** : Service Public Entreprendre - *"Fiche d'intervention pour les opérations nécessitant une manipulation de fluides frigorigènes..."*  
   URL : https://entreprendre.service-public.gouv.fr/vosdroits/R43122
