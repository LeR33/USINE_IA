from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False, index=True)
    adresse = Column(String, nullable=True)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    interventions = relationship("Intervention", back_populates="client")


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    numero = Column(String, unique=True, index=True, nullable=False)
    date_prevue = Column(String, nullable=True)  # YYYY-MM-DD
    description = Column(String, nullable=True)
    statut = Column(String, default="A_FAIRE")  # A_FAIRE, TERMINE

    client = relationship("Client", back_populates="interventions")
    facture = relationship("Facture", back_populates="intervention", uselist=False)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    libelle = Column(String, nullable=False, index=True)
    prix_unitaire_ht = Column(Float, nullable=False)
    taux_tva = Column(Float, default=20.0, nullable=False)


class Facture(Base):
    __tablename__ = "factures"

    id = Column(Integer, primary_key=True, index=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False, unique=True)
    numero = Column(String, unique=True, index=True, nullable=False)
    date_emission = Column(String, nullable=True)
    statut = Column(String, default="IMPAYE")  # IMPAYE, PAYE

    intervention = relationship("Intervention", back_populates="facture")
    lignes = relationship("LigneFacture", back_populates="facture", cascade="all, delete-orphan")


class LigneFacture(Base):
    __tablename__ = "lignes_facture"

    id = Column(Integer, primary_key=True, index=True)
    facture_id = Column(Integer, ForeignKey("factures.id"), nullable=False)
    libelle = Column(String, nullable=False)
    quantite = Column(Float, nullable=False, default=1.0)
    prix_unitaire_ht = Column(Float, nullable=False)
    taux_tva = Column(Float, default=20.0, nullable=False)

    facture = relationship("Facture", back_populates="lignes")
