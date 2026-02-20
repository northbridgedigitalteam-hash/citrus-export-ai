from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import jwt
import os
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://citrus_user:cU8UT6UD58ysf91SJgznlKjVxY2P0ZFu@dpg-d6cees1r0fns73bc2ri0-a/citrus_export'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(50), primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    contact_phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False)
    tracking_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Exporter info
    exporter_name = db.Column(db.String(100), nullable=False)
    exporter_id = db.Column(db.String(50))
    
    # Importer info
    importer_name = db.Column(db.String(100), nullable=False)
    importer_address = db.Column(db.Text)
    
    # Product details
    product = db.Column(db.String(50), nullable=False)
    variety = db.Column(db.String(50))
    quantity_cartons = db.Column(db.Integer, nullable=False)
    weight_kg = db.Column(db.Float)
    
    # Shipping details
    destination_country = db.Column(db.String(100), nullable=False)
    destination_port = db.Column(db.String(100))
    port_of_loading = db.Column(db.String(100), default='Cape Town')
    vessel_name = db.Column(db.String(100))
    container_number = db.Column(db.String(20))
    reefer_temperature = db.Column(db.Float, default=0.5)
    
    # Status
    status = db.Column(db.String(50), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # GPS Tracking (demo data for now)
    current_lat = db.Column(db.Float)
    current_lng = db.Column(db.Float)
    current_location = db.Column(db.String(200))
    last_gps_update = db.Column(db.DateTime)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.String(50), primary_key=True)
    shipment_id = db.Column(db.String(50), db.ForeignKey('shipments.id'), nullable=False)
    doc_type = db.Column(db.String(50), nullable=False)
    doc_number = db.Column(db.String(50))
    status = db.Column(db.String(50), default='generated')
    content = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper functions
def generate_id():
    return str(uuid.uuid4())[:8]

def generate_tracking():
    return f"CIT-{str(uuid.uuid4())[:8].upper()}"

def token_required(f):
    def decorator(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'User not found'}), 401
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(current_user, *args, **kwargs)
    decorator.__name__ = f.__name__
    return decorator

# Routes
@app.route('/')
def root():
    return jsonify({
        "message": "Citrus Export AI API - Production",
        "version": "1.0.0",
        "status": "running",
        "database": "connected"
    })

# Auth Routes
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    new_user = User(
        id=generate_id(),
        email=data['email'],
        password_hash=hashed_password,
        company_name=data['company_name'],
        contact_phone=data.get('contact_phone')
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user_id': new_user.id
    }), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, app.config['SECRET_KEY'])
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'company_name': user.company_name
        }
    })

# Shipment Routes
@app.route('/shipments/', methods=['POST'])
@token_required
def create_shipment(current_user):
    data = request.get_json()
    
    shipment = Shipment(
        id=generate_id(),
        user_id=current_user.id,
        tracking_number=generate_tracking(),
        exporter_name=data.get('exporter_name', current_user.company_name),
        exporter_id=data.get('exporter_id'),
        importer_name=data['importer_name'],
        importer_address=data.get('importer_address'),
        product=data['product'],
        variety=data.get('variety'),
        quantity_cartons=data['quantity_cartons'],
        weight_kg=data.get('weight_kg'),
        destination_country=data['destination_country'],
        destination_port=data.get('destination_port'),
        port_of_loading=data.get('port_of_loading', 'Cape Town'),
        vessel_name=data.get('vessel_name'),
        container_number=data.get('container_number'),
        reefer_temperature=data.get('reefer_temperature', 0.5),
        status='created',
        # Demo GPS data (Cape Town coordinates)
        current_lat=-33.9249,
        current_lng=18.4241,
        current_location='Cape Town Harbour, South Africa',
        last_gps_update=datetime.utcnow()
    )
    
    db.session.add(shipment)
    db.session.commit()
    
    return jsonify({
        'id': shipment.id,
        'tracking_number': shipment.tracking_number,
        'status': shipment.status,
        'message': 'Shipment created successfully'
    }), 201

@app.route('/shipments/', methods=['GET'])
@token_required
def get_shipments(current_user):
    shipments = Shipment.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': s.id,
        'tracking_number': s.tracking_number,
        'exporter_name': s.exporter_name,
        'importer_name': s.importer_name,
        'product': s.product,
        'quantity_cartons': s.quantity_cartons,
        'destination_country': s.destination_country,
        'status': s.status,
        'created_at': s.created_at.isoformat(),
        'current_location': s.current_location,
        'reefer_temperature': s.reefer_temperature
    } for s in shipments])

@app.route('/shipments/<shipment_id>', methods=['GET'])
@token_required
def get_shipment(current_user, shipment_id):
    shipment = Shipment.query.filter_by(id=shipment_id, user_id=current_user.id).first()
    if not shipment:
        return jsonify({'error': 'Shipment not found'}), 404
    
    return jsonify({
        'id': shipment.id,
        'tracking_number': shipment.tracking_number,
        'exporter_name': shipment.exporter_name,
        'importer_name': shipment.importer_name,
        'product': shipment.product,
        'variety': shipment.variety,
        'quantity_cartons': shipment.quantity_cartons,
        'weight_kg': shipment.weight_kg,
        'destination_country': shipment.destination_country,
        'destination_port': shipment.destination_port,
        'port_of_loading': shipment.port_of_loading,
        'vessel_name': shipment.vessel_name,
        'container_number': shipment.container_number,
        'reefer_temperature': shipment.reefer_temperature,
        'status': shipment.status,
        'created_at': shipment.created_at.isoformat(),
        'current_location': shipment.current_location,
        'current_lat': shipment.current_lat,
        'current_lng': shipment.current_lng,
        'last_gps_update': shipment.last_gps_update.isoformat() if shipment.last_gps_update else None
    })

# GPS Tracking Route
@app.route('/shipments/<shipment_id>/location', methods=['GET'])
@token_required
def get_shipment_location(current_user, shipment_id):
    shipment = Shipment.query.filter_by(id=shipment_id, user_id=current_user.id).first()
    if not shipment:
        return jsonify({'error': 'Shipment not found'}), 404
    
    # Demo: Simulate movement (in real app, this comes from GPS device)
    return jsonify({
        'shipment_id': shipment_id,
        'tracking_number': shipment.tracking_number,
        'current_location': shipment.current_location,
        'coordinates': {
            'lat': shipment.current_lat,
            'lng': shipment.current_lng
        },
        'reefer_temperature': shipment.reefer_temperature,
        'last_update': shipment.last_gps_update.isoformat() if shipment.last_gps_update else None,
        'status': 'in_transit'
    })

# Public Tracking (no login required)
@app.route('/track/<tracking_number>', methods=['GET'])
def track_public(tracking_number):
    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
    if not shipment:
        return jsonify({'error': 'Tracking number not found'}), 404
    
    return jsonify({
        'tracking_number': shipment.tracking_number,
        'status': shipment.status,
        'current_location': shipment.current_location,
        'coordinates': {
            'lat': shipment.current_lat,
            'lng': shipment.current_lng
        },
        'reefer_temperature': shipment.reefer_temperature,
        'product': shipment.product,
        'destination_country': shipment.destination_country,
        'last_update': shipment.last_gps_update.isoformat() if shipment.last_gps_update else None
    })

# Document Generation
@app.route('/documents/commercial-invoice/', methods=['POST'])
@token_required
def generate_invoice(current_user):
    shipment_id = request.args.get('shipment_id')
    shipment = Shipment.query.filter_by(id=shipment_id, user_id=current_user.id).first()
    
    if not shipment:
        return jsonify({'error': 'Shipment not found'}), 404
    
    doc_id = generate_id()
    invoice_number = f"INV-{doc_id.upper()}"
    
    hs_codes = {
        "oranges": "0805.10",
        "mandarins": "0805.21",
        "lemons": "0805.50",
        "grapefruit": "0805.40"
    }
    
    content = {
        "header": "COMMERCIAL INVOICE",
        "invoice_number": invoice_number,
        "date": datetime.utcnow().isoformat(),
        "exporter": shipment.exporter_name,
        "importer": shipment.importer_name,
        "product": f"{shipment.variety} {shipment.product}" if shipment.variety else shipment.product,
        "quantity": f"{shipment.quantity_cartons} cartons",
        "weight": f"{shipment.weight_kg} kg" if shipment.weight_kg else "N/A",
        "destination": f"{shipment.destination_port}, {shipment.destination_country}",
        "origin": f"{shipment.port_of_loading}, South Africa",
        "hs_code": hs_codes.get(shipment.product.lower(), "0805.10"),
        "container": shipment.container_number,
        "vessel": shipment.vessel_name
    }
    
    document = Document(
        id=doc_id,
        shipment_id=shipment_id,
        doc_type='commercial_invoice',
        doc_number=invoice_number,
        content=content
    )
    
    db.session.add(document)
    db.session.commit()
    
    return jsonify({
        'id': document.id,
        'invoice_number': invoice_number,
        'type': 'commercial_invoice',
        'status': 'generated',
        'content': content
    })

# Initialize database
@app.route('/init-db', methods=['POST'])
def init_db():
    try:
        db.create_all()
        return jsonify({'message': 'Database initialized successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
