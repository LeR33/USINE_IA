from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class ClientCreate(BaseModel):
    nom: str = Field(..., min_length=1)
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None


class ClientResponse(ClientCreate):
    id: int

    class Config:
        from_attributes = True


class InterventionCreate(BaseModel):
    client_id: int
    date_prevue: Optional[str] = None
    description: Optional[str] = None
    statut: Optional[str] = "A_FAIRE"


class InterventionResponse(InterventionCreate):
    id: int
    numero: str

    class Config:
        from_attributes = True


class ArticleCreate(BaseModel):
    libelle: str = Field(..., min_length=1)
    prix_unitaire_ht: float = Field(..., ge=0)
    taux_tva: float = Field(default=20.0, ge=0)


class ArticleResponse(ArticleCreate):
    id: int

    class Config:
        from_attributes = True


class LigneFactureCreate(BaseModel):
    libelle: str = Field(..., min_length=1)
    quantite: float = Field(default=1.0, gt=0)
    prix_unitaire_ht: float = Field(..., ge=0)
    taux_tva: float = Field(default=20.0, ge=0)


class FactureFromInterventionCreate(BaseModel):
    lignes: List[LigneFactureCreate] = []


class LigneFactureResponse(LigneFactureCreate):
    id: int
    facture_id: int

    class Config:
        from_attributes = True


class FactureResponse(BaseModel):
    id: int
    intervention_id: int
    numero: str
    date_emission: Optional[str] = None
    statut: str
    lignes: List[LigneFactureResponse] = []

    class Config:
        from_attributes = True
