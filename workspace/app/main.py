"""FroidPro V2 : application FastAPI + Jinja2 (Bootstrap 5)."""
import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import models, security, services
from app.database import get_db, init_db
from app.services import ValidationError
from app.utils.pdf_gen import generate_devis_pdf, generate_invoice_pdf

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
MAX_LOGO = 2 * 1024 * 1024
LOGO_TYPES = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


async def csrf_protect(request: Request):
    """Vérifie le jeton CSRF sur toute requête modifiante (champ de formulaire ou en-tête X-CSRF-Token)."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE") or security.auth_disabled():
        return
    if request.url.path in ("/connexion", "/installation") and not request.session.get("user_id"):
        pass  # ces formulaires ont aussi leur jeton, vérifié ci-dessous
    token = request.headers.get("x-csrf-token")
    if token is None:
        try:
            form = await request.form()
            token = form.get("csrf_token")
        except Exception:  # noqa: BLE001
            token = None
    if not security.csrf_ok(request.session.get("csrf"), token):
        raise HTTPException(status_code=403, detail="Session expirée ou requête non autorisée (CSRF).")


app = FastAPI(title="FroidPro", lifespan=lifespan, dependencies=[Depends(csrf_protect)])
import os  # noqa: E402


def _secret() -> str:
    """Clé de session : FROIDPRO_SECRET, sinon générée et conservée dans data/ (jamais une valeur publique)."""
    env = os.getenv("FROIDPRO_SECRET")
    if env:
        return env
    from app.database import DB_PATH
    f = DB_PATH.parent / ".secret_key"
    if not f.exists():
        import secrets as _s
        f.write_text(_s.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip()



PUBLIC_PREFIXES = ("/static/", "/connexion", "/installation")


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    """Toutes les pages exigent une session ; sans compte créé, on force /installation."""
    path = request.url.path
    if security.auth_disabled() or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        has_user = db.query(models.Utilisateur).first() is not None
    finally:
        db.close()
    if not has_user:
        return RedirectResponse("/installation", status_code=303)
    if not request.session.get("user_id"):
        if path.startswith("/api/"):
            return JSONResponse({"ok": False, "erreur": "Authentification requise."}, status_code=401)
        return RedirectResponse("/connexion", status_code=303)
    return await call_next(request)


app.add_middleware(SessionMiddleware, secret_key=_secret(), same_site="lax", https_only=False,
                   max_age=60 * 60 * 12)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]
STATUT_COULEURS = {"planifiée": "#0d6efd", "en cours": "#fd7e14", "terminée": "#198754", "annulée": "#6c757d"}


def _eur(v):
    return f"{(v or 0):,.2f} €".replace(",", " ").replace(".", ",")


def _datefr(d):
    return d.strftime("%d/%m/%Y") if d else ""


templates.env.filters["eur"] = _eur
templates.env.filters["datefr"] = _datefr
templates.env.globals.update(STATUTS_INTERVENTION=models.STATUTS_INTERVENTION, STATUTS_FACTURE=models.STATUTS_FACTURE,
                             CATEGORIES=models.CATEGORIES_ARTICLE, STATUT_COULEURS=STATUT_COULEURS, JOURS=JOURS,
                             MOIS_LONG=MOIS_LONG, today=date.today)


def render(request: Request, name: str, db: Session, status_code: int = 200, **ctx):
    flashes = request.session.pop("flashes", [])
    if "csrf" not in request.session:
        request.session["csrf"] = security.new_csrf_token()
    ctx.update(request=request, p=services.get_parametres(db), flashes=flashes, path=request.url.path,
               csrf_token=request.session["csrf"], user_email=request.session.get("user_email"),
               auth_on=not security.auth_disabled())
    return templates.TemplateResponse(request=request, name=name, context=ctx, status_code=status_code)


def flash(request: Request, message: str, kind: str = "success"):
    request.session.setdefault("flashes", [])
    request.session["flashes"] = request.session["flashes"] + [{"kind": kind, "message": message}]


def redirect(url: str):
    return RedirectResponse(url=url, status_code=303)


async def form_dict(request: Request) -> dict:
    form = await request.form()
    out: dict = {}
    for k in form.keys():
        vals = [v for v in form.getlist(k) if isinstance(v, str)]
        if not vals:
            continue
        out[k] = vals if (k.endswith("[]") or k.startswith("ligne_")) else vals[0]
    return {k.rstrip("[]") if k.endswith("[]") else k: v for k, v in out.items()}


def _articles_json(db):
    return [{"id": a.id, "designation": a.designation, "prix_ht": a.prix_ht, "tva": a.tva, "reference": a.reference,
             "unite": a.unite} for a in services.list_articles(db, actifs_only=True)]


# ======================= Authentification =======================
def _ip(request: Request) -> str:
    return request.client.host if request.client else "inconnu"


@app.get("/installation", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if db.query(models.Utilisateur).first():
        return redirect("/connexion")
    return render(request, "auth/installation.html", db, errors=[], form={})


@app.post("/installation")
async def setup_save(request: Request, db: Session = Depends(get_db)):
    if db.query(models.Utilisateur).first():
        return redirect("/connexion")
    data = await form_dict(request)
    errors = []
    email = (data.get("email") or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("L'adresse e-mail n'est pas valide.")
    errors += security.password_errors(data.get("mot_de_passe", ""), data.get("confirmation", ""))
    if errors:
        return render(request, "auth/installation.html", db, status_code=422, errors=errors, form={"email": email})
    u = models.Utilisateur(email=email, mot_de_passe_hash=security.hash_password(data["mot_de_passe"]))
    db.add(u)
    db.commit()
    request.session.clear()
    request.session.update(user_id=u.id, user_email=u.email, csrf=security.new_csrf_token())
    flash(request, "Compte administrateur créé. Bienvenue !")
    return redirect("/admin/parametres")


@app.get("/connexion", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if not db.query(models.Utilisateur).first():
        return redirect("/installation")
    if request.session.get("user_id"):
        return redirect("/")
    return render(request, "auth/connexion.html", db, errors=[], form={})


@app.post("/connexion")
async def login(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    key = _ip(request)
    if security.too_many_attempts(key):
        return render(request, "auth/connexion.html", db, status_code=429, form={},
                      errors=["Trop de tentatives. Réessayez dans quelques minutes."])
    email = (data.get("email") or "").strip().lower()
    u = db.query(models.Utilisateur).filter_by(email=email).first()
    # on vérifie toujours un hash pour garder un temps de réponse comparable
    ok = security.verify_password(data.get("mot_de_passe", ""), u.mot_de_passe_hash if u else
                                  "pbkdf2_sha256$1$00$00")
    if not (u and ok):
        security.record_failure(key)
        return render(request, "auth/connexion.html", db, status_code=401, form={"email": email},
                      errors=["E-mail ou mot de passe incorrect."])
    security.reset_attempts(key)
    request.session.clear()  # nouvelle session : évite la fixation de session
    request.session.update(user_id=u.id, user_email=u.email, csrf=security.new_csrf_token())
    return redirect("/")


@app.post("/deconnexion")
def logout(request: Request):
    request.session.clear()
    return redirect("/connexion")


@app.get("/admin/mot-de-passe", response_class=HTMLResponse)
def password_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "auth/mot_de_passe.html", db, errors=[])


@app.post("/admin/mot-de-passe")
async def password_change(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    u = db.get(models.Utilisateur, request.session.get("user_id") or 0)
    errors = []
    if not u or not security.verify_password(data.get("actuel", ""), u.mot_de_passe_hash):
        errors.append("Le mot de passe actuel est incorrect.")
    errors += security.password_errors(data.get("nouveau", ""), data.get("confirmation", ""))
    if errors:
        return render(request, "auth/mot_de_passe.html", db, status_code=422, errors=errors)
    u.mot_de_passe_hash = security.hash_password(data["nouveau"])
    db.commit()
    flash(request, "Mot de passe modifié.")
    return redirect("/admin/parametres")


# ======================= Tableau de bord =======================
@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    return render(request, "dashboard.html", db, d=services.dashboard(db))


# ======================= Paramètres =======================
@app.get("/admin/parametres", response_class=HTMLResponse)
def parametres_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "admin/parametres.html", db, form=None, errors=[])


@app.post("/admin/parametres")
async def parametres_save(request: Request, logo: UploadFile = File(None), db: Session = Depends(get_db)):
    data = await form_dict(request)
    errors, logo_name = [], None
    if logo is not None and logo.filename:
        content = await logo.read(MAX_LOGO + 1)
        ext = next((e for sig, e in LOGO_TYPES.items() if content.startswith(sig)), None)
        if len(content) > MAX_LOGO:
            errors.append("Le logo ne doit pas dépasser 2 Mo.")
        elif ext is None:
            errors.append("Le logo doit être une image PNG ou JPEG.")
        else:
            logo_name = f"logo-{uuid.uuid4().hex[:10]}{ext}"
            (UPLOADS / logo_name).write_bytes(content)
    if not errors:
        try:
            services.update_parametres(db, data, logo_name)
            flash(request, "Paramètres enregistrés.")
            return redirect("/admin/parametres")
        except ValidationError as e:
            errors = e.errors
    return render(request, "admin/parametres.html", db, status_code=422, form=data, errors=errors)


# ======================= Clients =======================
@app.get("/clients", response_class=HTMLResponse)
def clients_list(request: Request, q: str = "", db: Session = Depends(get_db)):
    return render(request, "clients/list.html", db, clients=services.list_clients(db, q), q=q)


@app.get("/clients/nouveau", response_class=HTMLResponse)
def client_new(request: Request, db: Session = Depends(get_db)):
    return render(request, "clients/form.html", db, client=None, form=None, errors=[])


@app.post("/clients/nouveau")
async def client_create(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        c = services.create_client(db, data)
    except ValidationError as e:
        return render(request, "clients/form.html", db, status_code=422, client=None, form=data, errors=e.errors)
    flash(request, f"Client « {c.nom} » créé.")
    return redirect(f"/clients/{c.id}")


@app.get("/clients/{cid}", response_class=HTMLResponse)
def client_detail(request: Request, cid: int, db: Session = Depends(get_db)):
    c = services.get_client(db, cid)
    if not c:
        return render(request, "404.html", db, status_code=404)
    factures = services.list_factures(db, client_id=cid)
    itvs = services.list_interventions(db, client_id=cid)
    devis = services.list_devis(db, client_id=cid)
    return render(request, "clients/detail.html", db, c=c, factures=factures, interventions=itvs, devis=devis)


@app.get("/clients/{cid}/modifier", response_class=HTMLResponse)
def client_edit(request: Request, cid: int, db: Session = Depends(get_db)):
    c = services.get_client(db, cid)
    if not c:
        return render(request, "404.html", db, status_code=404)
    return render(request, "clients/form.html", db, client=c, form=None, errors=[])


@app.post("/clients/{cid}/modifier")
async def client_update(request: Request, cid: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        c = services.update_client(db, cid, data)
    except ValidationError as e:
        c = services.get_client(db, cid)
        return render(request, "clients/form.html", db, status_code=422, client=c, form=data, errors=e.errors)
    if not c:
        return render(request, "404.html", db, status_code=404)
    flash(request, "Client mis à jour.")
    return redirect(f"/clients/{cid}")


@app.post("/clients/{cid}/supprimer")
async def client_delete(request: Request, cid: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        ok = services.delete_client(db, cid, force=data.get("force") == "1")
    except ValidationError as e:
        flash(request, e.errors[0], "danger")
        return redirect(f"/clients/{cid}")
    flash(request, "Client supprimé." if ok else "Client introuvable.", "success" if ok else "danger")
    return redirect("/clients")


# ======================= Articles =======================
@app.get("/articles", response_class=HTMLResponse)
def articles_list(request: Request, q: str = "", categorie: str = "", db: Session = Depends(get_db)):
    return render(request, "articles/list.html", db, articles=services.list_articles(db, q, categorie), q=q,
                  categorie=categorie)


@app.get("/articles/nouveau", response_class=HTMLResponse)
def article_new(request: Request, db: Session = Depends(get_db)):
    return render(request, "articles/form.html", db, a=None, form=None, errors=[])


@app.post("/articles/nouveau")
async def article_create(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        a = services.create_article(db, data)
    except ValidationError as e:
        return render(request, "articles/form.html", db, status_code=422, a=None, form=data, errors=e.errors)
    flash(request, f"Article « {a.designation} » créé.")
    return redirect("/articles")


@app.get("/articles/{aid}/modifier", response_class=HTMLResponse)
def article_edit(request: Request, aid: int, db: Session = Depends(get_db)):
    a = services.get_article(db, aid)
    if not a:
        return render(request, "404.html", db, status_code=404)
    return render(request, "articles/form.html", db, a=a, form=None, errors=[])


@app.post("/articles/{aid}/modifier")
async def article_update(request: Request, aid: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        a = services.update_article(db, aid, data)
    except ValidationError as e:
        return render(request, "articles/form.html", db, status_code=422, a=services.get_article(db, aid),
                      form=data, errors=e.errors)
    if not a:
        return render(request, "404.html", db, status_code=404)
    flash(request, "Article mis à jour.")
    return redirect("/articles")


@app.post("/articles/{aid}/supprimer")
def article_delete(request: Request, aid: int, db: Session = Depends(get_db)):
    ok = services.delete_article(db, aid)
    flash(request, "Article supprimé." if ok else "Article introuvable.", "success" if ok else "danger")
    return redirect("/articles")


@app.get("/api/articles")
def api_articles(q: str = "", db: Session = Depends(get_db)):
    return [{"id": a.id, "reference": a.reference, "designation": a.designation, "prix_ht": a.prix_ht, "tva": a.tva,
             "unite": a.unite, "categorie": a.categorie} for a in services.list_articles(db, q, actifs_only=True)]


# ======================= Interventions =======================
@app.get("/interventions", response_class=HTMLResponse)
def interventions_list(request: Request, statut: str = "", client_id: str = "", date_debut: str = "",
                       date_fin: str = "", q: str = "", db: Session = Depends(get_db)):
    cid = int(client_id) if client_id.isdigit() else None
    items = services.list_interventions(db, statut, cid, date_debut, date_fin, q)
    return render(request, "interventions/list.html", db, items=items, clients=services.list_clients(db),
                  f={"statut": statut, "client_id": client_id, "date_debut": date_debut, "date_fin": date_fin, "q": q})


def _itv_form(request, db, itv, form, errors, status_code=200, defaults=None):
    return render(request, "interventions/form.html", db, status_code=status_code, itv=itv, form=form, errors=errors,
                  clients=services.list_clients(db), catalogue=_articles_json(db), defaults=defaults or {})


@app.get("/interventions/nouveau", response_class=HTMLResponse)
def intervention_new(request: Request, date: str = "", heure: str = "", client_id: str = "",
                     db: Session = Depends(get_db)):
    defaults = {"date": date or datetime.now().strftime("%Y-%m-%d"), "client_id": client_id}
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", heure or ""):
        h = int(heure[:2])
        defaults.update(heure_debut=heure, heure_fin=f"{min(h + 1, 23):02d}:{heure[3:]}")
    return _itv_form(request, db, None, None, [], defaults=defaults)


@app.post("/interventions/nouveau")
async def intervention_create(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        i = services.create_intervention(db, data)
    except ValidationError as e:
        return _itv_form(request, db, None, data, e.errors, 422)
    flash(request, f"Intervention {i.numero} créée.")
    return redirect("/interventions")


@app.get("/interventions/{iid}/modifier", response_class=HTMLResponse)
def intervention_edit(request: Request, iid: int, db: Session = Depends(get_db)):
    i = db.get(models.Intervention, iid)
    if not i:
        return render(request, "404.html", db, status_code=404)
    return _itv_form(request, db, i, None, [])


@app.post("/interventions/{iid}/modifier")
async def intervention_update(request: Request, iid: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        i = services.update_intervention(db, iid, data)
    except ValidationError as e:
        return _itv_form(request, db, db.get(models.Intervention, iid), data, e.errors, 422)
    if not i:
        return render(request, "404.html", db, status_code=404)
    flash(request, f"Intervention {i.numero} mise à jour.")
    return redirect("/interventions")


@app.post("/interventions/{iid}/supprimer")
def intervention_delete(request: Request, iid: int, db: Session = Depends(get_db)):
    ok = services.delete_intervention(db, iid)
    flash(request, "Intervention supprimée." if ok else "Intervention introuvable.", "success" if ok else "danger")
    return redirect("/interventions")


@app.post("/interventions/{iid}/facturer")
def intervention_invoice(request: Request, iid: int, db: Session = Depends(get_db)):
    try:
        f = services.create_facture_from_intervention(db, iid)
    except ValidationError as e:
        flash(request, e.errors[0], "danger")
        return redirect(f"/interventions/{iid}/modifier")
    flash(request, f"Facture {f.numero} créée.")
    return redirect(f"/factures/{f.id}")


# ======================= Planning =======================
@app.get("/planning", response_class=HTMLResponse)
def planning(request: Request, vue: str = "semaine", jour: str = "", db: Session = Depends(get_db)):
    try:
        ref = datetime.strptime(jour, "%Y-%m-%d").date() if jour else date.today()
    except ValueError:
        ref = date.today()
    vue = "mois" if vue == "mois" else "semaine"
    if vue == "semaine":
        start = ref - timedelta(days=ref.weekday())
        days = [start + timedelta(days=i) for i in range(7)]
        prev, nxt = start - timedelta(days=7), start + timedelta(days=7)
        titre = f"Semaine du {start.strftime('%d/%m/%Y')} au {days[-1].strftime('%d/%m/%Y')}"
    else:
        first = ref.replace(day=1)
        start = first - timedelta(days=first.weekday())
        days = [start + timedelta(days=i) for i in range(42)]
        while days[-7].month != ref.month and days[-7] > first:
            days = days[:-7]
        prev = (first - timedelta(days=1)).replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        titre = f"{MOIS_LONG[ref.month - 1].capitalize()} {ref.year}"
    items = services.interventions_between(db, days[0], days[-1])
    by_day: dict = {}
    for i in items:
        by_day.setdefault(i.date, []).append(i)
    return render(request, "planning.html", db, vue=vue, ref=ref, days=days, by_day=by_day, titre=titre,
                  prev=prev, nxt=nxt, heures=list(range(7, 20)))


@app.post("/api/interventions/{iid}/deplacer")
async def api_move(iid: int, request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "erreur": "Requête invalide."}, status_code=400)
    try:
        i = services.move_intervention(db, iid, str(body.get("date", "")), body.get("heure_debut"))
    except ValidationError as e:
        return JSONResponse({"ok": False, "erreur": e.errors[0]}, status_code=422)
    if not i:
        return JSONResponse({"ok": False, "erreur": "Intervention introuvable."}, status_code=404)
    return {"ok": True, "date": i.date.isoformat(), "heure_debut": i.heure_debut, "heure_fin": i.heure_fin}


# ======================= Factures =======================
# ======================= Devis =======================
def _devis_form(request: Request, db: Session, devis, form, errors, status_code: int = 200):
    defaults = {"date_emission": date.today().isoformat(), "date_validite": (date.today() + timedelta(days=30)).isoformat()}
    cid = request.query_params.get("client_id")
    if cid and not devis:
        defaults["client_id"] = cid
    return render(request, "devis/form.html", db, status_code=status_code, devis=devis, form=form, errors=errors,
                  defaults=defaults, clients=services.list_clients(db),
                  catalogue=[{"id": a.id, "designation": a.designation, "prix_ht": a.prix_ht, "tva": a.tva}
                             for a in services.list_articles(db, actifs_only=True)])


@app.get("/devis", response_class=HTMLResponse)
def devis_list(request: Request, statut: str = "", q: str = "", db: Session = Depends(get_db)):
    return render(request, "devis/list.html", db, devis_list=services.list_devis(db, statut, None, q), statut=statut, q=q)


@app.get("/devis/nouveau", response_class=HTMLResponse)
def devis_new(request: Request, db: Session = Depends(get_db)):
    return _devis_form(request, db, None, None, [])


@app.post("/devis/nouveau")
async def devis_create(request: Request, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        d = services.create_devis(db, data)
    except ValidationError as e:
        return _devis_form(request, db, None, data, e.errors, 422)
    flash(request, f"Devis {d.numero} créé.")
    return redirect(f"/devis/{d.id}")


@app.get("/devis/{did}", response_class=HTMLResponse)
def devis_detail(request: Request, did: int, db: Session = Depends(get_db)):
    d = services.get_devis(db, did)
    if not d:
        return render(request, "404.html", db, status_code=404)
    return render(request, "devis/detail.html", db, d=d)


@app.get("/devis/{did}/modifier", response_class=HTMLResponse)
def devis_edit(request: Request, did: int, db: Session = Depends(get_db)):
    d = services.get_devis(db, did)
    if not d:
        return render(request, "404.html", db, status_code=404)
    return _devis_form(request, db, d, None, [])


@app.post("/devis/{did}/modifier")
async def devis_update(request: Request, did: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        d = services.update_devis(db, did, data)
    except ValidationError as e:
        return _devis_form(request, db, services.get_devis(db, did), data, e.errors, 422)
    if not d:
        return render(request, "404.html", db, status_code=404)
    flash(request, f"Devis {d.numero} mis à jour.")
    return redirect(f"/devis/{did}")


@app.post("/devis/{did}/statut")
async def devis_statut(request: Request, did: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        d = services.set_devis_statut(db, did, data.get("statut", ""))
    except ValidationError as e:
        flash(request, e.errors[0], "danger")
        return redirect(f"/devis/{did}")
    if not d:
        return render(request, "404.html", db, status_code=404)
    flash(request, f"Devis {d.numero} : statut « {d.statut} ».")
    return redirect(f"/devis/{did}")


@app.post("/devis/{did}/convertir")
async def devis_convert(request: Request, did: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        itv = services.convert_devis_to_intervention(db, did, data.get("date") or None)
    except ValidationError as e:
        flash(request, e.errors[0], "danger")
        return redirect(f"/devis/{did}")
    flash(request, f"Intervention {itv.numero} créée à partir du devis. Ajustez la date et l'horaire si besoin.")
    return redirect(f"/interventions/{itv.id}/modifier")


@app.post("/devis/{did}/supprimer")
def devis_delete(request: Request, did: int, db: Session = Depends(get_db)):
    ok = services.delete_devis(db, did)
    flash(request, "Devis supprimé." if ok else "Devis introuvable.", "success" if ok else "danger")
    return redirect("/devis")


@app.get("/devis/{did}/pdf")
def devis_pdf(did: int, db: Session = Depends(get_db)):
    d = services.get_devis(db, did)
    if not d:
        return Response("Devis introuvable.", status_code=404)
    return Response(generate_devis_pdf(d, services.get_parametres(db)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{quote(d.numero)}.pdf"'})


@app.get("/factures", response_class=HTMLResponse)
def factures_list(request: Request, statut: str = "", q: str = "", db: Session = Depends(get_db)):
    return render(request, "factures/list.html", db, factures=services.list_factures(db, statut, None, q),
                  statut=statut, q=q)


@app.get("/factures/nouvelle", response_class=HTMLResponse)
def facture_new(request: Request, db: Session = Depends(get_db)):
    """Une facture naît d'une intervention : on propose celles qui n'ont pas encore de facture."""
    sans = [i for i in services.list_interventions(db) if i.facture is None and i.statut != "annulée"]
    return render(request, "factures/nouvelle.html", db, interventions=sans)


@app.get("/factures/{fid}", response_class=HTMLResponse)
def facture_detail(request: Request, fid: int, db: Session = Depends(get_db)):
    f = services.get_facture(db, fid)
    if not f:
        return render(request, "404.html", db, status_code=404)
    return render(request, "factures/detail.html", db, f=f)


@app.post("/factures/{fid}/statut")
async def facture_statut(request: Request, fid: int, db: Session = Depends(get_db)):
    data = await form_dict(request)
    try:
        f = services.set_facture_statut(db, fid, data.get("statut", ""))
    except ValidationError as e:
        flash(request, e.errors[0], "danger")
        return redirect(f"/factures/{fid}")
    if not f:
        return render(request, "404.html", db, status_code=404)
    flash(request, f"Facture {f.numero} : statut « {f.statut} ».")
    return redirect(f"/factures/{fid}")


@app.post("/factures/{fid}/payer")
def facture_pay(request: Request, fid: int, db: Session = Depends(get_db)):
    f = services.mark_paid(db, fid)
    if not f:
        return render(request, "404.html", db, status_code=404)
    flash(request, f"Facture {f.numero} marquée comme payée.")
    return redirect(f"/factures/{fid}")


@app.post("/factures/{fid}/supprimer")
def facture_delete(request: Request, fid: int, db: Session = Depends(get_db)):
    ok = services.delete_facture(db, fid)
    flash(request, "Facture supprimée." if ok else "Facture introuvable.", "success" if ok else "danger")
    return redirect("/factures")


@app.get("/factures/{fid}/pdf")
def facture_pdf(fid: int, db: Session = Depends(get_db)):
    f = services.get_facture(db, fid)
    if not f:
        return Response("Facture introuvable.", status_code=404)
    pdf = generate_invoice_pdf(f, services.get_parametres(db))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{quote(f.numero)}.pdf"'})
