from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

shipments_db = []
documents_db = []

@app.route('/')
def root():
    return jsonify({
        "message": "Citrus Export AI API",
        "version": "0.1.0",
        "status": "running"
    })

@app.route('/shipments/', methods=['POST'])
def create_shipment():
    data = request.get_json()
    
    shipment_id = str(uuid.uuid4())[:8]
    tracking_number = f"CIT-{shipment_id.upper()}"
    
    new_shipment = {
        "exporter_name": data.get('exporter_name'),
        "importer_name": data.get('importer_name'),
        "product": data.get('product'),
        "quantity_cartons": data.get('quantity_cartons'),
        "destination_country": data.get('destination_country'),
        "port_of_loading": data.get('port_of_loading', 'Cape Town'),
        "vessel_name": data.get('vessel_name'),
        "id": shipment_id,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "tracking_number": tracking_number
    }
    
    shipments_db.append(new_shipment)
    return jsonify(new_shipment)

@app.route('/shipments/', methods=['GET'])
def get_shipments():
    return jsonify(shipments_db)

@app.route('/shipments/<shipment_id>', methods=['GET'])
def get_shipment(shipment_id):
    for s in shipments_db:
        if s['id'] == shipment_id:
            return jsonify(s)
    return jsonify({"error": "Shipment not found"}), 404

@app.route('/documents/commercial-invoice/', methods=['POST'])
def generate_invoice():
    shipment_id = request.args.get('shipment_id')
    
    shipment = None
    for s in shipments_db:
        if s['id'] == shipment_id:
            shipment = s
            break
    
    if not shipment:
        return jsonify({"error": "Shipment not found"}), 404
    
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
        "exporter": shipment['exporter_name'],
        "importer": shipment['importer_name'],
        "product": shipment['product'],
        "quantity": shipment['quantity_cartons'],
        "destination": shipment['destination_country'],
        "status": "generated",
        "content": {
            "header": "COMMERCIAL INVOICE",
            "invoice_to": shipment['importer_name'],
            "ship_to": shipment['importer_name'],
            "from": shipment['exporter_name'],
            "description": f"Fresh {shipment['product']} - {shipment['quantity_cartons']} cartons",
            "origin": "South Africa",
            "hs_code": hs_codes.get(shipment['product'].lower(), "0805.10")
        }
    }
    
    documents_db.append(document)
    return jsonify(document)

@app.route('/documents/', methods=['GET'])
def get_documents():
    return jsonify(documents_db)

@app.route('/track/<tracking_number>', methods=['GET'])
def track_shipment(tracking_number):
    for s in shipments_db:
        if s['tracking_number'] == tracking_number:
            return jsonify({
                "tracking_number": tracking_number,
                "status": s['status'],
                "location": "In transit",
                "last_update": datetime.now().isoformat(),
                "history": [
                    {"status": "created", "time": s['created_at']},
                    {"status": "documentation_complete", "time": datetime.now().isoformat()},
                    {"status": "in_transit", "time": datetime.now().isoformat()}
                ]
            })
    return jsonify({"error": "Tracking number not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
