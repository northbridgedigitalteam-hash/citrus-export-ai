from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

app = FastAPI()

shipments_db = []

class ShipmentCreate(BaseModel):
    exporter_name: str
    importer_name: str
    product: str
    quantity_cartons: int
    destination_country: str

class Shipment(BaseModel):
    exporter_name: str
    importer_name: str
    product: str
    quantity_cartons: int
    destination_country: str
    id: str
    status: str
    created_at: str
    tracking_number: str

@app.get("/")
def root():
    return {"message": "Citrus Export AI API"}

@app.post("/shipments/")
def create(s: ShipmentCreate):
    sid = str(uuid.uuid4())[:8]
    track = f"CIT-{sid.upper()}"
    new = Shipment(
        exporter_name=s.exporter_name,
        importer_name=s.importer_name,
        product=s.product,
        quantity_cartons=s.quantity_cartons,
        destination_country=s.destination_country,
        id=sid,
        status="created",
        created_at=datetime.now().isoformat(),
        tracking_number=track
    )
    shipments_db.append(new)
    return new

@app.get("/shipments/")
def list_all():
    return shipments_db

@app.get("/track/{track_num}")
def track(track_num: str):
    for s in shipments_db:
        if s.tracking_number == track_num:
            return {"tracking_number": track_num, "status": s.status}
    return {"error": "Not found"}
