from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app import models, database, crud, schemas
from app.database import engine, get_db
from app.utils.pdf_gen import generate_invoice_pdf

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FroidPro")

# Templates & Static
templates = Jinja2Templates(directory="app/templates")
if not os.path.exists("app/static"):
    os.makedirs("app/static")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    kpis = crud.get_dashboard_kpis(db)
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context=kpis
    )

# --- Clients ---
@app.get("/clients", response_class=HTMLResponse)
async def list_clients(request: Request, db: Session = Depends(get_db)):
    clients = crud.get_clients(db)
    return templates.TemplateResponse(
        request=request, 
        name="clients/list.html", 
        context={"clients": clients}
    )

@app.get("/clients/create", response_class=HTMLResponse)
async def create_client_form(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="clients/form.html"
    )

@app.post("/clients/create")
async def create_client(
    nom: str = Form(...),
    adresse: str = Form(None),
    telephone: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    client_in = schemas.ClientCreate(nom=nom, adresse=adresse, telephone=telephone, email=email)
    crud.create_client(db, client_in)
    return RedirectResponse(url="/clients", status_code=303)

@app.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_detail(request: Request, client_id: int, db: Session = Depends(get_db)):
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return templates.TemplateResponse(
        request=request, 
        name="clients/detail.html", 
        context={"client": client}
    )

# --- Interventions ---
@app.get("/interventions", response_class=HTMLResponse)
async def list_interventions(request: Request, db: Session = Depends(get_db)):
    interventions = crud.get_interventions(db)
    return templates.TemplateResponse(
        request=request, 
        name="interventions/list.html", 
        context={"interventions": interventions}
    )

@app.post("/interventions/create")
async def create_intervention(
    client_id: int = Form(...),
    date_prevue: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    int_in = schemas.InterventionCreate(client_id=client_id, date_prevue=date_prevue, description=description)
    crud.create_intervention(db, int_in)
    return RedirectResponse(url=f"/clients/{client_id}", status_code=303)

@app.post("/interventions/{intervention_id}/finish")
async def finish_intervention(intervention_id: int, db: Session = Depends(get_db)):
    crud.update_intervention_status(db, intervention_id, "TERMINE")
    return RedirectResponse(url="/interventions", status_code=303)

# --- Invoices & Articles ---
@app.get("/articles", response_class=HTMLResponse)
async def list_articles(request: Request, db: Session = Depends(get_db)):
    articles = crud.get_articles(db)
    return templates.TemplateResponse(
        request=request, 
        name="invoices/articles.html", 
        context={"articles": articles}
    )

@app.post("/articles/create")
async def create_article(
    libelle: str = Form(...),
    prix_unitaire_ht: float = Form(...),
    taux_tva: float = Form(20.0),
    db: Session = Depends(get_db)
):
    art_in = schemas.ArticleCreate(libelle=libelle, prix_unitaire_ht=prix_unitaire_ht, taux_tva=taux_tva)
    crud.create_article(db, art_in)
    return RedirectResponse(url="/articles", status_code=303)

@app.get("/api/articles/search")
async def search_articles(q: str = "", db: Session = Depends(get_db)):
    articles = crud.get_articles(db, q=q)
    return articles

@app.get("/invoices/{facture_id}", response_class=HTMLResponse)
async def invoice_detail(request: Request, facture_id: int, db: Session = Depends(get_db)):
    facture = crud.get_facture(db, facture_id)
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return templates.TemplateResponse(
        request=request, 
        name="invoices/detail.html", 
        context={"facture": facture}
    )

@app.post("/invoices/from-intervention/{intervention_id}")
async def create_invoice_from_int(intervention_id: int, db: Session = Depends(get_db)):
    intervention = crud.get_intervention(db, intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")
    
    lignes = [
        schemas.LigneFactureCreate(libelle=f"Intervention: {intervention.description or 'Maintenance'}", quantite=1, prix_unitaire_ht=0, taux_tva=20)
    ]
    facture = crud.create_facture_from_intervention(db, intervention_id, lignes)
    return RedirectResponse(url=f"/invoices/{facture.id}", status_code=303)

@app.post("/invoices/{facture_id}/toggle-payment")
async def toggle_payment(facture_id: int, db: Session = Depends(get_db)):
    crud.toggle_facture_payment(db, facture_id)
    return RedirectResponse(url="/", status_code=303)

@app.get("/invoices/{facture_id}/pdf")
async def get_invoice_pdf(facture_id: int, db: Session = Depends(get_db)):
    facture = crud.get_facture(db, facture_id)
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    
    pdf_path = f"temp_invoice_{facture_id}.pdf"
    generate_invoice_pdf(facture, pdf_path)
    
    return FileResponse(pdf_path, filename=f"Facture_{facture.numero}.pdf", media_type="application/pdf")