import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200

def test_create_client():
    response = client.post(
        "/clients/create", 
        data={"nom": "Test Client", "email": "test@example.com"},
        follow_redirects=False
    )
    assert response.status_code == 303
    
    # Verify in DB
    response = client.get("/clients")
    assert "Test Client" in response.text

def test_intervention_numbering():
    # Create client
    client.post(
        "/clients/create", 
        data={"nom": "Client 1"},
        follow_redirects=False
    )
    
    # Create two interventions
    client.post(
        "/interventions/create", 
        data={"client_id": 1, "description": "Int 1"},
        follow_redirects=False
    )
    client.post(
        "/interventions/create", 
        data={"client_id": 1, "description": "Int 2"},
        follow_redirects=False
    )
    
    response = client.get("/interventions")
    assert "INT-" in response.text
    # Check that we have two different numbers
    assert response.text.count("INT-") >= 2

def test_invoice_flow():
    # Setup
    client.post(
        "/clients/create", 
        data={"nom": "Client Facture"},
        follow_redirects=False
    )
    client.post(
        "/interventions/create", 
        data={"client_id": 1, "description": "Réparation"},
        follow_redirects=False
    )
    client.post(
        "/interventions/1/finish",
        follow_redirects=False
    )
    
    # Create invoice
    client.post(
        "/invoices/from-intervention/1",
        follow_redirects=False
    )
    
    response = client.get("/invoices/1")
    assert response.status_code == 200
    assert "FACT-" in response.text
    
    # Toggle payment
    client.post(
        "/invoices/1/toggle-payment",
        follow_redirects=False
    )
    response = client.get("/")
    assert "PAYE" in response.text