"""Logique métier : validation (messages en français), CRUD, facturation, tableau de bord."""
import re
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models
from app.models import (CATEGORIES_ARTICLE, STATUTS_FACTURE, STATUTS_INTERVENTION)


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# ---------- helpers de validation ----------
def _s(v) -> str:
    return (v or "").strip() if isinstance(v, str) or v is None else str(v).strip()


def _float(v, label, errors, minimum=0.0, default=None) -> float:
    if v in (None, ""):
        if default is not None:
            return default
        errors.append(f"{label} est obligatoire.")
        return 0.0
    try:
        f = float(str(v).replace(",", "."))
    except ValueError:
        errors.append(f"{label} doit être un nombre.")
        return 0.0
    if f < minimum:
        errors.append(f"{label} ne peut pas être inférieur à {minimum:g}.")
    return f


def _date(v, label, errors, required=True) -> Optional[date]:
    if isinstance(v, date):
        return v
    v = _s(v)
    if not v:
        if required:
            errors.append(f"{label} est obligatoire.")
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{label} doit être une date valide (AAAA-MM-JJ).")
        return None


def _heure(v, label, errors) -> str:
    v = _s(v)
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
        errors.append(f"{label} doit être une heure valide (HH:MM).")
    return v


def _email(v, errors) -> str:
    v = _s(v)
    if v and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        errors.append("L'adresse e-mail n'est pas valide.")
    return v


def _color(v, errors) -> str:
    v = _s(v) or "#0d6efd"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        errors.append("La couleur principale doit être au format #RRGGBB.")
    return v


def _raise(errors):
    if errors:
        raise ValidationError(errors)


# ---------- Paramètres ----------
def get_parametres(db: Session) -> models.Parametres:
    p = db.query(models.Parametres).first()
    if p is None:
        p = models.Parametres()
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def update_parametres(db: Session, data: dict, logo_path: Optional[str] = None) -> models.Parametres:
    errors: list[str] = []
    nom = _s(data.get("nom_societe"))
    if not nom:
        errors.append("Le nom de la société est obligatoire.")
    email = _email(data.get("email"), errors)
    tva = _float(data.get("tva_defaut"), "Le taux de TVA par défaut", errors, 0.0, default=20.0)
    if tva > 100:
        errors.append("Le taux de TVA doit être compris entre 0 et 100.")
    prefixe = _s(data.get("prefixe_facture")) or "FACT"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", prefixe):
        errors.append("Le préfixe de facture doit contenir 1 à 12 caractères (lettres, chiffres, - ou _).")
    try:
        prochain = int(str(data.get("prochain_numero_facture") or 1).strip())
        if prochain < 1:
            raise ValueError
    except ValueError:
        errors.append("Le prochain numéro de facture doit être un entier positif.")
        prochain = 1
    couleur = _color(data.get("couleur_principale"), errors)
    siret = re.sub(r"\s", "", _s(data.get("siret")))
    if siret and not re.fullmatch(r"\d{14}", siret):
        errors.append("Le SIRET doit contenir 14 chiffres.")
    _raise(errors)

    p = get_parametres(db)
    p.nom_societe = nom
    p.adresse = _s(data.get("adresse"))
    p.siret = siret
    p.tva_numero = _s(data.get("tva_numero"))
    p.iban = _s(data.get("iban"))
    p.telephone = _s(data.get("telephone"))
    p.email = email
    p.mentions_legales = _s(data.get("mentions_legales"))
    p.conditions_paiement = _s(data.get("conditions_paiement"))
    p.prefixe_facture = prefixe
    p.prochain_numero_facture = prochain
    p.tva_defaut = tva
    p.couleur_principale = couleur
    if logo_path:
        p.logo = logo_path
    db.commit()
    db.refresh(p)
    return p


# ---------- Clients ----------
def list_clients(db: Session, q: str = "") -> list[models.Client]:
    query = db.query(models.Client)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Client.nom.ilike(like), models.Client.email.ilike(like),
                                 models.Client.telephone.ilike(like), models.Client.adresse.ilike(like)))
    return query.order_by(models.Client.nom).all()


def get_client(db: Session, client_id: int):
    return db.get(models.Client, client_id)


def _client_data(data: dict) -> dict:
    errors: list[str] = []
    nom = _s(data.get("nom"))
    if not nom:
        errors.append("Le nom du client est obligatoire.")
    email = _email(data.get("email"), errors)
    tel = _s(data.get("telephone"))
    if tel and not re.fullmatch(r"[0-9+().\s-]{6,20}", tel):
        errors.append("Le numéro de téléphone n'est pas valide.")
    _raise(errors)
    return {"nom": nom, "adresse": _s(data.get("adresse")), "telephone": tel, "email": email,
            "notes": _s(data.get("notes")), "actif": str(data.get("actif", "on")).lower() not in ("0", "false", "off", "")}


def create_client(db: Session, data: dict) -> models.Client:
    c = models.Client(**_client_data(data))
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_client(db: Session, client_id: int, data: dict):
    c = get_client(db, client_id)
    if not c:
        return None
    for k, v in _client_data(data).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


def count_client_links(db: Session, client_id: int) -> int:
    """Éléments liés au client (interventions + devis) qui seraient supprimés avec lui."""
    return (db.query(models.Intervention).filter_by(client_id=client_id).count()
            + db.query(models.Devis).filter_by(client_id=client_id).count())


def delete_client(db: Session, client_id: int, force: bool = False) -> bool:
    """Supprime un client. S'il a des interventions : refus sauf force=True (supprime tout)."""
    c = get_client(db, client_id)
    if not c:
        return False
    n = count_client_links(db, client_id)
    if n and not force:
        raise ValidationError([f"Ce client a {n} intervention(s) ou devis liés. Confirmez la suppression pour tout effacer."])
    for itv in list(c.interventions):
        delete_intervention(db, itv.id, commit=False)
    for f in db.query(models.Facture).filter_by(client_id=client_id).all():
        db.delete(f)
    for d in db.query(models.Devis).filter_by(client_id=client_id).all():
        db.delete(d)
    db.delete(c)
    db.commit()
    return True


# ---------- Articles ----------
def list_articles(db: Session, q: str = "", categorie: str = "", actifs_only: bool = False):
    query = db.query(models.Article)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Article.designation.ilike(like), models.Article.reference.ilike(like)))
    if categorie:
        query = query.filter(models.Article.categorie == categorie)
    if actifs_only:
        query = query.filter(models.Article.actif.is_(True))
    return query.order_by(models.Article.designation).all()


def get_article(db: Session, article_id: int):
    return db.get(models.Article, article_id)


def _article_data(data: dict) -> dict:
    errors: list[str] = []
    des = _s(data.get("designation"))
    if not des:
        errors.append("La désignation est obligatoire.")
    prix = _float(data.get("prix_ht"), "Le prix HT", errors, 0.0)
    tva = _float(data.get("tva"), "La TVA", errors, 0.0, default=20.0)
    if tva > 100:
        errors.append("La TVA doit être comprise entre 0 et 100.")
    cat = _s(data.get("categorie")) or "main d'oeuvre"
    if cat not in CATEGORIES_ARTICLE:
        errors.append(f"La catégorie doit être : {', '.join(CATEGORIES_ARTICLE)}.")
    _raise(errors)
    return {"reference": _s(data.get("reference")), "designation": des, "prix_ht": prix, "tva": tva,
            "unite": _s(data.get("unite")) or "u", "categorie": cat,
            "actif": str(data.get("actif", "")).lower() in ("on", "1", "true")}


def create_article(db: Session, data: dict) -> models.Article:
    data = {**data}
    data.setdefault("actif", "on")
    a = models.Article(**_article_data(data))
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def update_article(db: Session, article_id: int, data: dict):
    a = get_article(db, article_id)
    if not a:
        return None
    for k, v in _article_data(data).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


def delete_article(db: Session, article_id: int) -> bool:
    a = get_article(db, article_id)
    if not a:
        return False
    db.delete(a)
    db.commit()
    return True


# ---------- Interventions ----------
def generate_int_number(db: Session, jour: Optional[date] = None) -> str:
    year = (jour or date.today()).year
    prefix = f"INT-{year}-"
    n = db.query(func.count(models.Intervention.id)).filter(models.Intervention.numero.like(f"{prefix}%")).scalar()
    while True:
        n += 1
        numero = f"{prefix}{n:04d}"
        if not db.query(models.Intervention).filter_by(numero=numero).first():
            return numero


def _lignes_from_form(data: dict, errors: list[str]) -> list[dict]:
    """Lignes : listes parallèles ligne_designation[], ligne_quantite[], ligne_prix[], ligne_tva[]."""
    def lst(key):
        v = data.get(key, [])
        return v if isinstance(v, list) else [v]
    des, qte, prix, tva = (lst("ligne_designation"), lst("ligne_quantite"), lst("ligne_prix"), lst("ligne_tva"))
    out = []
    for i, d in enumerate(des):
        d = _s(d)
        if not d:
            continue
        n = i + 1
        out.append({
            "designation": d,
            "quantite": _float(qte[i] if i < len(qte) else 1, f"La quantité (ligne {n})", errors, 0.0001, default=1.0),
            "prix_ht": _float(prix[i] if i < len(prix) else 0, f"Le prix (ligne {n})", errors, 0.0, default=0.0),
            "tva": _float(tva[i] if i < len(tva) else 20, f"La TVA (ligne {n})", errors, 0.0, default=20.0),
        })
    return out


def _intervention_data(db: Session, data: dict):
    errors: list[str] = []
    try:
        client_id = int(data.get("client_id"))
        if not get_client(db, client_id):
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Veuillez choisir un client valide.")
        client_id = 0
    jour = _date(data.get("date"), "La date", errors)
    debut = _heure(data.get("heure_debut") or "08:00", "L'heure de début", errors)
    fin = _heure(data.get("heure_fin") or "09:00", "L'heure de fin", errors)
    if not errors and fin <= debut:
        errors.append("L'heure de fin doit être postérieure à l'heure de début.")
    statut = _s(data.get("statut")) or "planifiée"
    if statut not in STATUTS_INTERVENTION:
        errors.append(f"Le statut doit être : {', '.join(STATUTS_INTERVENTION)}.")
    lignes = _lignes_from_form(data, errors)
    _raise(errors)
    return ({"client_id": client_id, "date": jour, "heure_debut": debut, "heure_fin": fin,
             "type": _s(data.get("type")) or "Dépannage", "technicien": _s(data.get("technicien")),
             "statut": statut, "description": _s(data.get("description"))}, lignes)


def create_intervention(db: Session, data: dict) -> models.Intervention:
    fields, lignes = _intervention_data(db, data)
    itv = models.Intervention(numero=generate_int_number(db, fields["date"]), **fields)
    itv.lignes = [models.LigneIntervention(**l) for l in lignes]
    db.add(itv)
    db.commit()
    db.refresh(itv)
    return itv


def update_intervention(db: Session, itv_id: int, data: dict):
    itv = db.get(models.Intervention, itv_id)
    if not itv:
        return None
    fields, lignes = _intervention_data(db, data)
    for k, v in fields.items():
        setattr(itv, k, v)
    itv.lignes.clear()
    db.flush()
    itv.lignes.extend(models.LigneIntervention(**l) for l in lignes)
    db.commit()
    db.refresh(itv)
    return itv


def move_intervention(db: Session, itv_id: int, new_date: str, heure_debut: Optional[str] = None):
    """Déplacement (glisser-déposer) : change la date, et l'heure si fournie (durée conservée)."""
    itv = db.get(models.Intervention, itv_id)
    if not itv:
        return None
    errors: list[str] = []
    d = _date(new_date, "La date", errors)
    if heure_debut:
        h = _heure(heure_debut, "L'heure", errors)
    _raise(errors)
    if heure_debut:
        duree = itv.duree_minutes or 60
        start = int(h[:2]) * 60 + int(h[3:])
        end = min(start + duree, 23 * 60 + 59)
        itv.heure_debut, itv.heure_fin = h, f"{end // 60:02d}:{end % 60:02d}"
    itv.date = d
    db.commit()
    db.refresh(itv)
    return itv


def delete_intervention(db: Session, itv_id: int, commit: bool = True) -> bool:
    itv = db.get(models.Intervention, itv_id)
    if not itv:
        return False
    if itv.facture is not None:
        db.delete(itv.facture)
    db.delete(itv)
    if commit:
        db.commit()
    return True


def list_interventions(db: Session, statut: str = "", client_id: Optional[int] = None,
                       date_debut: str = "", date_fin: str = "", q: str = ""):
    query = db.query(models.Intervention).join(models.Client, models.Intervention.client_id == models.Client.id)
    if statut:
        query = query.filter(models.Intervention.statut == statut)
    if client_id:
        query = query.filter(models.Intervention.client_id == client_id)
    if date_debut:
        d = _date(date_debut, "", [], required=False)
        if d:
            query = query.filter(models.Intervention.date >= d)
    if date_fin:
        d = _date(date_fin, "", [], required=False)
        if d:
            query = query.filter(models.Intervention.date <= d)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Intervention.numero.ilike(like), models.Intervention.description.ilike(like),
                                 models.Intervention.technicien.ilike(like), models.Intervention.type.ilike(like),
                                 models.Client.nom.ilike(like)))
    return query.order_by(models.Intervention.date.desc(), models.Intervention.heure_debut).all()


def interventions_between(db: Session, start: date, end: date):
    return (db.query(models.Intervention)
            .filter(models.Intervention.date >= start, models.Intervention.date <= end)
            .order_by(models.Intervention.date, models.Intervention.heure_debut).all())


# ---------- Factures ----------
def generate_fact_number(db: Session) -> str:
    """Numéro = préfixe-AAAA-NNNN depuis les paramètres ; incrémente le compteur."""
    p = get_parametres(db)
    while True:
        numero = f"{p.prefixe_facture}-{date.today().year}-{p.prochain_numero_facture:04d}"
        p.prochain_numero_facture += 1
        if not db.query(models.Facture).filter_by(numero=numero).first():
            return numero


def _echeance(conditions: str, emission: date) -> date:
    m = re.search(r"(\d+)\s*jours?", conditions or "", re.I)
    return emission + timedelta(days=int(m.group(1)) if m else 30)


def create_facture_from_intervention(db: Session, itv_id: int):
    itv = db.get(models.Intervention, itv_id)
    if not itv:
        raise ValidationError(["Intervention introuvable."])
    if itv.facture is not None:
        return itv.facture
    if not itv.lignes:
        raise ValidationError(["Cette intervention n'a aucune ligne d'article : ajoutez-en avant de facturer."])
    p = get_parametres(db)
    emission = date.today()
    f = models.Facture(numero=generate_fact_number(db), intervention_id=itv.id, client_id=itv.client_id,
                       date_emission=emission, date_echeance=_echeance(p.conditions_paiement, emission),
                       statut="brouillon")
    f.lignes = [models.LigneFacture(designation=l.designation, quantite=l.quantite, prix_ht=l.prix_ht, tva=l.tva)
                for l in itv.lignes]
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def get_facture(db: Session, facture_id: int):
    return db.get(models.Facture, facture_id)


def list_factures(db: Session, statut: str = "", client_id: Optional[int] = None, q: str = ""):
    query = db.query(models.Facture).join(models.Client, models.Facture.client_id == models.Client.id)
    if client_id:
        query = query.filter(models.Facture.client_id == client_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Facture.numero.ilike(like), models.Client.nom.ilike(like)))
    res = query.order_by(models.Facture.date_emission.desc(), models.Facture.id.desc()).all()
    if statut:
        res = [f for f in res if f.statut_effectif == statut]
    return res


def set_facture_statut(db: Session, facture_id: int, statut: str):
    f = get_facture(db, facture_id)
    if not f:
        return None
    if statut not in STATUTS_FACTURE:
        raise ValidationError([f"Le statut doit être : {', '.join(STATUTS_FACTURE)}."])
    f.statut = statut
    f.date_paiement = date.today() if statut == "payée" else None
    db.commit()
    db.refresh(f)
    return f


def mark_paid(db: Session, facture_id: int):
    return set_facture_statut(db, facture_id, "payée")


def delete_facture(db: Session, facture_id: int) -> bool:
    f = get_facture(db, facture_id)
    if not f:
        return False
    db.delete(f)
    db.commit()
    return True


# ---------- Tableau de bord ----------
# ---------- Devis ----------
STATUTS_DEVIS = ["brouillon", "envoyé", "accepté", "refusé"]
VALIDITE_DEVIS_JOURS = 30


def generate_devis_number(db: Session) -> str:
    """DEV-AAAA-NNNN ; compteur dans la table `compteurs`."""
    c = db.get(models.Compteur, "devis")
    if c is None:
        c = models.Compteur(nom="devis", valeur=1)
        db.add(c)
        db.flush()
    while True:
        numero = f"DEV-{date.today().year}-{c.valeur:04d}"
        c.valeur += 1
        if not db.query(models.Devis).filter_by(numero=numero).first():
            return numero


def _devis_data(db: Session, data: dict):
    errors: list[str] = []
    try:
        client_id = int(str(data.get("client_id") or "").strip())
        if not db.get(models.Client, client_id):
            raise ValueError
    except ValueError:
        client_id = None
        errors.append("Veuillez choisir un client valide.")
    emission = _date(data.get("date_emission") or date.today().isoformat(), "La date d'émission", errors)
    validite = _date(data.get("date_validite"), "La date de validité", errors, required=False)
    if emission and not validite:
        validite = emission + timedelta(days=VALIDITE_DEVIS_JOURS)
    if emission and validite and validite < emission:
        errors.append("La date de validité ne peut pas être antérieure à la date d'émission.")
    lignes = _lignes_from_form(data, errors)
    if not lignes:
        errors.append("Ajoutez au moins une ligne au devis.")
    return errors, {"client_id": client_id, "date_emission": emission, "date_validite": validite,
                    "objet": _s(data.get("objet")), "notes": _s(data.get("notes"))}, lignes


def create_devis(db: Session, data: dict) -> models.Devis:
    errors, fields, lignes = _devis_data(db, data)
    _raise(errors)
    d = models.Devis(numero=generate_devis_number(db), statut="brouillon", **fields)
    d.lignes = [models.LigneDevis(**l) for l in lignes]
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def get_devis(db: Session, devis_id: int):
    return db.get(models.Devis, devis_id)


def update_devis(db: Session, devis_id: int, data: dict):
    d = get_devis(db, devis_id)
    if not d:
        return None
    if d.statut in ("accepté", "refusé") or d.intervention_id:
        raise ValidationError(["Un devis accepté, refusé ou déjà converti ne peut plus être modifié."])
    errors, fields, lignes = _devis_data(db, data)
    _raise(errors)
    for k, v in fields.items():
        setattr(d, k, v)
    d.lignes = [models.LigneDevis(**l) for l in lignes]
    db.commit()
    db.refresh(d)
    return d


def list_devis(db: Session, statut: str = "", client_id: Optional[int] = None, q: str = ""):
    query = db.query(models.Devis).join(models.Client, models.Devis.client_id == models.Client.id)
    if client_id:
        query = query.filter(models.Devis.client_id == client_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(models.Devis.numero.ilike(like), models.Client.nom.ilike(like),
                                 models.Devis.objet.ilike(like)))
    res = query.order_by(models.Devis.date_emission.desc(), models.Devis.id.desc()).all()
    if statut:
        res = [d for d in res if d.statut_effectif == statut]
    return res


def set_devis_statut(db: Session, devis_id: int, statut: str):
    d = get_devis(db, devis_id)
    if not d:
        return None
    if statut not in STATUTS_DEVIS:
        raise ValidationError([f"Le statut doit être l'un de : {', '.join(STATUTS_DEVIS)}."])
    if d.intervention_id and statut != "accepté":
        raise ValidationError(["Ce devis a déjà été converti en intervention : son statut ne peut plus changer."])
    d.statut = statut
    db.commit()
    return d


def convert_devis_to_intervention(db: Session, devis_id: int, jour: Optional[str] = None):
    """Un devis accepté devient une intervention planifiée qui reprend ses lignes (idempotent)."""
    d = get_devis(db, devis_id)
    if not d:
        raise ValidationError(["Devis introuvable."])
    if d.intervention_id:
        return d.intervention
    if d.statut != "accepté":
        raise ValidationError(["Seul un devis accepté peut être converti en intervention."])
    itv = create_intervention(db, {
        "client_id": d.client_id, "date": jour or date.today().isoformat(), "heure_debut": "09:00", "heure_fin": "11:00",
        "type": "Installation", "statut": "planifiée", "description": f"Issue du devis {d.numero}. {d.objet}".strip(),
        "ligne_designation": [l.designation for l in d.lignes], "ligne_quantite": [str(l.quantite) for l in d.lignes],
        "ligne_prix": [str(l.prix_ht) for l in d.lignes], "ligne_tva": [str(l.tva) for l in d.lignes]})
    d = get_devis(db, devis_id)
    d.intervention_id = itv.id
    db.commit()
    return itv


def delete_devis(db: Session, devis_id: int) -> bool:
    d = get_devis(db, devis_id)
    if not d:
        return False
    db.delete(d)
    db.commit()
    return True


def _month_start(d: date, offset: int = 0) -> date:
    m = d.year * 12 + d.month - 1 + offset
    return date(m // 12, m % 12 + 1, 1)


MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def dashboard(db: Session, today: Optional[date] = None) -> dict:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    factures = db.query(models.Facture).all()

    impayees = [f for f in factures if f.statut_effectif in ("envoyée", "en retard")]
    en_retard = [f for f in factures if f.statut_effectif == "en retard"]
    m0 = _month_start(today)
    ca_mois = sum(f.total_ttc for f in factures
                  if f.statut == "payée" and f.date_paiement and f.date_paiement >= m0)

    labels, values = [], []
    for off in range(-5, 1):
        s, e = _month_start(today, off), _month_start(today, off + 1)
        labels.append(f"{MOIS[s.month - 1]} {s.year}")
        values.append(round(sum(f.total_ttc for f in factures
                                if f.statut == "payée" and f.date_paiement and s <= f.date_paiement < e), 2))

    prochaines = (db.query(models.Intervention)
                  .filter(models.Intervention.date >= today, models.Intervention.statut.in_(["planifiée", "en cours"]))
                  .order_by(models.Intervention.date, models.Intervention.heure_debut).limit(5).all())
    activite = []
    for i in db.query(models.Intervention).order_by(models.Intervention.id.desc()).limit(5).all():
        activite.append({"type": "Intervention", "texte": f"{i.numero} · {i.client.nom}", "date": i.date,
                         "url": f"/interventions/{i.id}/modifier"})
    for f in db.query(models.Facture).order_by(models.Facture.id.desc()).limit(5).all():
        activite.append({"type": "Facture", "texte": f"{f.numero} · {f.client.nom} ({f.statut_effectif})",
                         "date": f.date_emission, "url": f"/factures/{f.id}"})
    activite.sort(key=lambda a: a["date"], reverse=True)

    return {
        "nb_jour": db.query(models.Intervention).filter(models.Intervention.date == today).count(),
        "nb_semaine": db.query(models.Intervention).filter(models.Intervention.date >= week_start,
                                                           models.Intervention.date <= week_end).count(),
        "impayees_montant": round(sum(f.total_ttc for f in impayees), 2),
        "impayees_nb": len(impayees),
        "ca_mois": round(ca_mois, 2),
        "clients_actifs": db.query(models.Client).filter(models.Client.actif.is_(True)).count(),
        "prochaines": prochaines, "en_retard": en_retard, "activite": activite[:8],
        "graph_labels": labels, "graph_values": values,
    }
