"""FroidPro V2 : application FastAPI + Jinja2 (Bootstrap 5)."""
import json
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import models, services
from app.database import get_db, init_db
from app.services import ValidationError
from app.utils.pdf_gen import generate_invoice_pdf

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
MAX_LOGO = 2 * 1024 * 1024
LOGO_TYPES = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FroidPro", lifespan=lifespan)
import os  # noqa: E402
app.add_middleware(SessionMiddleware, secret_key=os.getenv("FROIDPRO_SECRET", "dev-change-me-" + "froidpro"),
                   same_site="lax")
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
    ctx.update(request=request, p=services.get_parametres(db), flashes=flashes, path=request.url.path)
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
    return render(request, "clients/detail.html", db, c=c, factures=factures, interventions=itvs)


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
