from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

STATUTS_INTERVENTION = ["planifiée", "en cours", "terminée", "annulée"]
STATUTS_FACTURE = ["brouillon", "envoyée", "payée", "en retard"]
CATEGORIES_ARTICLE = ["main d'oeuvre", "pièce", "fluide"]


class Parametres(Base):
    """Paramètres de la société (une seule ligne)."""
    __tablename__ = "parametres"

    id = Column(Integer, primary_key=True)
    nom_societe = Column(String, default="Ma Société", nullable=False)
    logo = Column(String, nullable=True)  # chemin relatif sous app/static/uploads
    adresse = Column(String, default="")
    siret = Column(String, default="")
    tva_numero = Column(String, default="")
    iban = Column(String, default="")
    telephone = Column(String, default="")
    email = Column(String, default="")
    mentions_legales = Column(Text, default="")
    conditions_paiement = Column(String, default="Paiement à 30 jours")
    prefixe_facture = Column(String, default="FACT")
    prochain_numero_facture = Column(Integer, default=1, nullable=False)
    tva_defaut = Column(Float, default=20.0, nullable=False)
    couleur_principale = Column(String, default="#0d6efd")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False, index=True)
    adresse = Column(String, nullable=True)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    actif = Column(Boolean, default=True, nullable=False)

    interventions = relationship("Intervention", back_populates="client")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String, nullable=True, index=True)
    designation = Column(String, nullable=False, index=True)
    prix_ht = Column(Float, nullable=False, default=0.0)
    tva = Column(Float, nullable=False, default=20.0)
    unite = Column(String, default="u")
    categorie = Column(String, default="main d'oeuvre")
    actif = Column(Boolean, default=True, nullable=False)


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    date = Column(Date, nullable=False, default=date.today, index=True)
    heure_debut = Column(String, default="08:00")  # HH:MM
    heure_fin = Column(String, default="09:00")
    type = Column(String, default="Dépannage")
    technicien = Column(String, default="")
    statut = Column(String, default="planifiée", nullable=False, index=True)
    description = Column(Text, default="")

    client = relationship("Client", back_populates="interventions")
    lignes = relationship("LigneIntervention", back_populates="intervention",
                          cascade="all, delete-orphan")
    facture = relationship("Facture", back_populates="intervention", uselist=False)

    @property
    def duree_minutes(self) -> int:
        try:
            h1, m1 = map(int, (self.heure_debut or "0:0").split(":"))
            h2, m2 = map(int, (self.heure_fin or "0:0").split(":"))
            return max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
        except ValueError:
            return 0

    @property
    def duree_texte(self) -> str:
        m = self.duree_minutes
        return f"{m // 60} h {m % 60:02d}"


class LigneIntervention(Base):
    __tablename__ = "lignes_intervention"

    id = Column(Integer, primary_key=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False)
    designation = Column(String, nullable=False)
    quantite = Column(Float, nullable=False, default=1.0)
    prix_ht = Column(Float, nullable=False, default=0.0)
    tva = Column(Float, nullable=False, default=20.0)

    intervention = relationship("Intervention", back_populates="lignes")


class Facture(Base):
    __tablename__ = "factures"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True, nullable=False)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=True, unique=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    date_emission = Column(Date, nullable=False, default=date.today)
    date_echeance = Column(Date, nullable=False)
    statut = Column(String, default="brouillon", nullable=False, index=True)
    date_paiement = Column(Date, nullable=True)

    intervention = relationship("Intervention", back_populates="facture")
    client = relationship("Client")
    lignes = relationship("LigneFacture", back_populates="facture", cascade="all, delete-orphan")

    @property
    def total_ht(self) -> float:
        return round(sum(l.quantite * l.prix_ht for l in self.lignes), 2)

    @property
    def total_tva(self) -> float:
        return round(sum(l.quantite * l.prix_ht * l.tva / 100.0 for l in self.lignes), 2)

    @property
    def total_ttc(self) -> float:
        return round(self.total_ht + self.total_tva, 2)

    @property
    def statut_effectif(self) -> str:
        """Une facture envoyée dont l'échéance est dépassée est 'en retard'."""
        if self.statut in ("envoyée",) and self.date_echeance < date.today():
            return "en retard"
        return self.statut


class LigneFacture(Base):
    __tablename__ = "lignes_facture"

    id = Column(Integer, primary_key=True)
    facture_id = Column(Integer, ForeignKey("factures.id"), nullable=False)
    designation = Column(String, nullable=False)
    quantite = Column(Float, nullable=False, default=1.0)
    prix_ht = Column(Float, nullable=False, default=0.0)
    tva = Column(Float, nullable=False, default=20.0)

    facture = relationship("Facture", back_populates="lignes")

    @property
    def total_ht(self) -> float:
        return round(self.quantite * self.prix_ht, 2)


class Utilisateur(Base):
    """Compte de connexion (un seul administrateur pour l'instant)."""
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    mot_de_passe_hash = Column(String, nullable=False)
    cree_le = Column(DateTime, default=datetime.utcnow, nullable=False)


class Devis(Base):
    __tablename__ = "devis"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    date_emission = Column(Date, nullable=False, default=date.today)
    date_validite = Column(Date, nullable=False)
    statut = Column(String, default="brouillon", nullable=False, index=True)
    objet = Column(String, default="")
    notes = Column(Text, default="")
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=True)  # rempli à la conversion

    client = relationship("Client")
    intervention = relationship("Intervention")
    lignes = relationship("LigneDevis", back_populates="devis", cascade="all, delete-orphan")

    @property
    def total_ht(self) -> float:
        return round(sum(l.quantite * l.prix_ht for l in self.lignes), 2)

    @property
    def total_tva(self) -> float:
        return round(sum(l.quantite * l.prix_ht * l.tva / 100.0 for l in self.lignes), 2)

    @property
    def total_ttc(self) -> float:
        return round(self.total_ht + self.total_tva, 2)

    @property
    def statut_effectif(self) -> str:
        """Un devis envoyé dont la validité est dépassée est 'expiré'."""
        if self.statut == "envoyé" and self.date_validite < date.today():
            return "expiré"
        return self.statut


class LigneDevis(Base):
    __tablename__ = "lignes_devis"

    id = Column(Integer, primary_key=True)
    devis_id = Column(Integer, ForeignKey("devis.id"), nullable=False)
    designation = Column(String, nullable=False)
    quantite = Column(Float, nullable=False, default=1.0)
    prix_ht = Column(Float, nullable=False, default=0.0)
    tva = Column(Float, nullable=False, default=20.0)

    devis = relationship("Devis", back_populates="lignes")

    @property
    def total_ht(self) -> float:
        return round(self.quantite * self.prix_ht, 2)


class Compteur(Base):
    """Compteurs de numérotation additionnels (devis...). Table neuve : aucune migration sur l'existant."""
    __tablename__ = "compteurs"

    nom = Column(String, primary_key=True)
    valeur = Column(Integer, nullable=False, default=1)
