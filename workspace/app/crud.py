from sqlalchemy.orm import Session
from datetime import datetime
from app import models, schemas


# --- Clients ---
def get_client(db: Session, client_id: int):
    return db.query(models.Client).filter(models.Client.id == client_id).first()


def get_clients(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Client).offset(skip).limit(limit).all()


def create_client(db: Session, client: schemas.ClientCreate):
    db_client = models.Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


# --- Interventions ---
def generate_int_number(db: Session) -> str:
    year = datetime.now().year
    prefix = f"INT-{year}-"
    last_intervention = (
        db.query(models.Intervention)
        .filter(models.Intervention.numero.like(f"{prefix}%"))
        .order_by(models.Intervention.id.desc())
        .first()
    )
    if last_intervention:
        try:
            seq_str = last_intervention.numero.split("-")[-1]
            seq = int(seq_str) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


def get_intervention(db: Session, intervention_id: int):
    return db.query(models.Intervention).filter(models.Intervention.id == intervention_id).first()


def get_interventions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Intervention).offset(skip).limit(limit).all()


def create_intervention(db: Session, intervention: schemas.InterventionCreate):
    numero = generate_int_number(db)
    db_intervention = models.Intervention(
        client_id=intervention.client_id,
        numero=numero,
        date_prevue=intervention.date_prevue,
        description=intervention.description,
        statut=intervention.statut or "A_FAIRE",
    )
    db.add(db_intervention)
    db.commit()
    db.refresh(db_intervention)
    return db_intervention


def update_intervention_status(db: Session, intervention_id: int, statut: str):
    db_int = get_intervention(db, intervention_id)
    if db_int:
        db_int.statut = statut
        db.commit()
        db.refresh(db_int)
    return db_int


# --- Articles ---
def get_article(db: Session, article_id: int):
    return db.query(models.Article).filter(models.Article.id == article_id).first()


def get_articles(db: Session, q: str = None):
    query = db.query(models.Article)
    if q:
        query = query.filter(models.Article.libelle.ilike(f"%{q}%"))
    return query.all()


def create_article(db: Session, article: schemas.ArticleCreate):
    db_article = models.Article(**article.dict())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


# --- Factures ---
def generate_fact_number(db: Session) -> str:
    year = datetime.now().year
    prefix = f"FACT-{year}-"
    last_facture = (
        db.query(models.Facture)
        .filter(models.Facture.numero.like(f"{prefix}%"))
        .order_by(models.Facture.id.desc())
        .first()
    )
    if last_facture:
        try:
            seq_str = last_facture.numero.split("-")[-1]
            seq = int(seq_str) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


def get_facture(db: Session, facture_id: int):
    return db.query(models.Facture).filter(models.Facture.id == facture_id).first()


def get_factures(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Facture).offset(skip).limit(limit).all()


def create_facture_from_intervention(db: Session, intervention_id: int, lignes_data: list):
    # Check if invoice already exists
    existing = db.query(models.Facture).filter(models.Facture.intervention_id == intervention_id).first()
    if existing:
        return existing

    numero = generate_fact_number(db)
    date_emission = datetime.now().strftime("%Y-%m-%d")
    db_facture = models.Facture(
        intervention_id=intervention_id,
        numero=numero,
        date_emission=date_emission,
        statut="IMPAYE",
    )
    db.add(db_facture)
    db.commit()
    db.refresh(db_facture)

    for l in lignes_data:
        db_ligne = models.LigneFacture(
            facture_id=db_facture.id,
            libelle=l.libelle,
            quantite=l.quantite,
            prix_unitaire_ht=l.prix_unitaire_ht,
            taux_tva=l.taux_tva,
        )
        db.add(db_ligne)
    db.commit()
    db.refresh(db_facture)
    return db_facture


def toggle_facture_payment(db: Session, facture_id: int):
    db_facture = get_facture(db, facture_id)
    if db_facture:
        if db_facture.statut == "PAYE":
            db_facture.statut = "IMPAYE"
        else:
            db_facture.statut = "PAYE"
        db.commit()
        db.refresh(db_facture)
    return db_facture


# --- Dashboard KPI ---
def get_dashboard_kpis(db: Session):
    factures = get_factures(db, limit=1000)
    ca_total = sum(f.lignes_total_ttc() if hasattr(f, 'lignes_total_ttc') else sum(l.quantite * l.prix_unitaire_ht * (1 + l.taux_tva / 100.0) for l in f.lignes) for f in factures if f.statut == "PAYE")
    en_attente = sum(sum(l.quantite * l.prix_unitaire_ht * (1 + l.taux_tva / 100.0) for l in f.lignes) for f in factures if f.statut == "IMPAYE")
    return {
        "ca_total": ca_total,
        "en_attente": en_attente,
        "factures": factures,
    }
