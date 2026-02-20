from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

app = FastAPI(title="Citrus Export AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

shipments_db = []
documents_db = []


class ShipmentCreate(BaseModel):
    exporter_name: str
    importer_name: str
    product: str
    quantity_cartons: int
    destination_country: str
    port_of_loading: str = "Cape Town"
    vessel_name: Optional[str] = None


class Shipment(BaseModel):
    exporter_name: str
    importer_name: str
    product: str
    quantity_cartons: int
    destination_country: str
    port_of_loading: str
    vessel_name: Optional[str]
    id: str
    status: str
    created_at: datetime
    tracking_number: str


@app.get("/")
def read_root():
    return {
        "message": "Citrus Export AI API",
        "version": "0.1.0",
        "status": "running"
    }


@app.post("/shipments/")
def create_shipment(shipment: ShipmentCreate):
    shipment_id = str(uuid.uuid4())[:8]
    tracking_number = f"CIT-{shipment_id.upper()}"
    
    new_shipment = Shipment(
        exporter_name=shipment.exporter_name,
        importer_name=shipment.importer_name,
        product=shipment.product,
        quantity_cartons=shipment.quantity_cartons,
        destination_country=shipment.destination_country,
        port_of_loading=shipment.port_of_loading,
        vessel_name=shipment.vessel_name,
        id=shipment_id,
        status="created",
        created_at=datetime.now(),
        tracking_number=tracking_number
    )
    
    shipments_db.append(new_shipment)
    return new_shipment


@app.get("/shipments/")
def get_shipments():
    return shipments_db


@app.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str):
    for s in shipments_db:
        if s.id == shipment_id:
            return s
    raise HTTPException(status_code=404, detail="Shipment not found")


@app.post("/documents/commercial-invoice/")
def generate_commercial_invoice(shipment_id: str):
    shipment = None
    for s in shipments_db:
        if s.id == shipment_id:
            shipment = s
            break
    
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    doc_id = str(uuid.uuid4())[:8]
    invoice_number = f"INV-{doc_id.upper()}"
    
    hs_codes = {
        "oranges": "0805.10",
        "mandarins": "0805.21",
        "lemons": "0805.50",
        "grapefruit": "0805.40"
    }
    
    document = {
        "id": doc_id,
        "shipment_id": shipment_id,
        "type": "commercial_invoice",
        "invoice_number": invoice_number,
        "date": datetime.now().isoformat(),
        "exporter": shipment.exporter_name,
        "importer": shipment.importer_name,
        "product": shipment.product,
        "quantity": shipment.quantity_cartons,
        "destination": shipment.destination_country,
        "status": "generated",
        "content": {
            "header": "COMMERCIAL INVOICE",
            "invoice_to": shipment.importer_name,
            "ship_to": shipment.importer_name,
            "from": shipment.exporter_name,
            "description": f"Fresh {shipment.product} - {shipment.quantity_cartons} cartons",
            "origin": "South Africa",
            "hs_code": hs_codes.get(shipment.product.lower(), "0805.10")
        }
    }
    
    documents_db.append(document)
    return document


@app.get("/documents/")
def get_documents():
    return documents_db


@app.get("/track/{tracking_number}")
def track_shipment(tracking_number: str):
    for s in shipments_db:
        if s.tracking_number == tracking_number:
            return {
                "tracking_number": tracking_number,
                "status": s.status,
                "location": "In transit",
                "last_update": datetime.now().isoformat(),
                "history": [
                    {"status": "created", "time": s.created_at.isoformat()},
                    {"status": "documentation_complete", "time": datetime.now().isoformat()},
                    {"status": "in_transit", "time": datetime.now().isoformat()}
                ]
            }
    raise HTTPException(status_code=404, detail="Tracking number not found")
