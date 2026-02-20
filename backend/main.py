from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://citrus_user:cU8UT6UD58ysf91SJgznlKjVxY2P0ZFu@dpg-d6cees1r0fns73bc2ri0-a/citrus_export')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
CORS(app, supports_credentials=True)

# ============== DATABASE MODELS ==============

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='exporter')  # exporter, admin, forwarder
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    shipments = db.relationship('Shipment', backref='exporter', lazy=True)
    
    def get_id(self):
        return self.id

class Shipment(db.Model):
    __tablename__ = 'shipments'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tracking_number = db.Column(db.String(20), unique=True, nullable=False)
    exporter_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Shipment details
    exporter_name = db.Column(db.String(100), nullable=False)
    importer_name = db.Column(db.String(100), nullable=False)
    product = db.Column(db.String(50), nullable=False)
    quantity_cartons = db.Column(db.Integer, nullable=False)
    destination_country = db.Column(db.String(100), nullable=False)
    port_of_loading = db.Column(db.String(50), default='Cape Town')
    vessel_name = db.Column(db.String(100))
    
    # Status
    status = db.Column(db.String(50), default='created')  # created, in_transit, arrived, delivered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tracking_events = db.relationship('TrackingEvent', backref='shipment', lazy=True, order_by='TrackingEvent.timestamp.desc()')
    documents = db.relationship('Document', backref='shipment', lazy=True)

class TrackingEvent(db.Model):
    __tablename__ = 'tracking_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id = db.Column(db.String(36), db.ForeignKey('shipments.id'), nullable=False)
    
    event_type = db.Column(db.String(50), nullable=False)  # location_update, temperature_alert, status_change
    location = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    temperature = db.Column(db.Float)  # For reefer monitoring
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id = db.Column(db.String(36), db.ForeignKey('shipments.id'), nullable=False)
    
    doc_type = db.Column(db.String(50), nullable=False)  # commercial_invoice, packing_list, bill_of_lading
    document_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='generated')  # generated, sent, signed
    content = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============== AUTHENTICATION ==============

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.route('/')
def root():
    return jsonify({
        "message": "Citrus Export AI API - TMS Edition",
        "version": "2.0.0",
        "status": "running",
        "database": "connected"
    })

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if user exists
    existing = User.query.filter_by(email=data.get('email')).first()
    if existing:
        return jsonify({"error": "Email already registered"}), 400
    
    # Create new user
    hashed_pw = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    new_user = User(
        email=data.get('email'),
        password_hash=hashed_pw,
        company_name=data.get('company_name'),
        role='exporter'
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        "message": "Registration successful",
        "user_id": new_user.id,
        "company": new_user.company_name
    }), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    user = User.query.filter_by(email=data.get('email')).first()
    
    if not user or not bcrypt.check_password_hash(user.password_hash, data.get('password')):
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403
    
    login_user(user)
    
    return jsonify({
        "message": "Login successful",
        "user_id": user.id,
        "email": user.email,
        "company": user.company_name,
        "role": user.role
    })

@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logout successful"})

@app.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    return jsonify({
        "user_id": current_user.id,
        "email": current_user.email,
        "company": current_user.company_name,
        "role": current_user.role
    })

# ============== SHIPMENTS ==============

@app.route('/shipments/', methods=['POST'])
@login_required
def create_shipment():
    data = request.get_json()
    
    tracking_number = f"CIT-{uuid.uuid4().hex[:8].upper()}"
    
    new_shipment = Shipment(
        id=str(uuid.uuid4()),
        tracking_number=tracking_number,
        exporter_id=current_user.id,
        exporter_name=data.get('exporter_name'),
        importer_name=data.get('importer_name'),
        product=data.get('product'),
        quantity_cartons=data.get('quantity_cartons'),
        destination_country=data.get('destination_country'),
        port_of_loading=data.get('port_of_loading', 'Cape Town'),
        vessel_name=data.get('vessel_name'),
        status='created'
    )
    
    db.session.add(new_shipment)
    db.session.commit()
    
    # Add initial tracking event
    initial_event = TrackingEvent(
        id=str(uuid.uuid4()),
        shipment_id=new_shipment.id,
        event_type='status_change',
        location=new_shipment.port_of_loading,
        description=f'Shipment created at {new_shipment.port_of_loading}',
        latitude=-33.9249,  # Cape Town coordinates (demo)
        longitude=18.4241
    )
    db.session.add(initial_event)
    db.session.commit()
    
    return jsonify({
        "id": new_shipment.id,
        "tracking_number": new_shipment.tracking_number,
        "status": new_shipment.status,
        "created_at": new_shipment.created_at.isoformat()
    }), 201

@app.route('/shipments/', methods=['GET'])
@login_required
def get_shipments():
    # Exporters see only their shipments, admins see all
    if current_user.role == 'admin':
        shipments = Shipment.query.all()
    else:
        shipments = Shipment.query.filter_by(exporter_id=current_user.id).all()
    
    return jsonify([{
        "id": s.id,
        "tracking_number": s.tracking_number,
        "exporter_name": s.exporter_name,
        "importer_name": s.importer_name,
        "product": s.product,
        "quantity_cartons": s.quantity_cartons,
        "destination_country": s.destination_country,
        "status": s.status,
        "created_at": s.created_at.isoformat()
    } for s in shipments])

@app.route('/shipments/<shipment_id>', methods=['GET'])
@login_required
def get_shipment(shipment_id):
    shipment = Shipment.query.get_or_404(shipment_id)
    
    # Check permission
    if current_user.role != 'admin' and shipment.exporter_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    
    # Get latest tracking
    latest_tracking = TrackingEvent.query.filter_by(shipment_id=shipment_id).order_by(TrackingEvent.timestamp.desc()).first()
    
    return jsonify({
        "id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "exporter_name": shipment.exporter_name,
        "importer_name": shipment.importer_name,
        "product": shipment.product,
        "quantity_cartons": shipment.quantity_cartons,
        "destination_country": shipment.destination_country,
        "port_of_loading": shipment.port_of_loading,
        "vessel_name": shipment.vessel_name,
        "status": shipment.status,
        "created_at": shipment.created_at.isoformat(),
        "current_location": {
            "lat": latest_tracking.latitude if latest_tracking else None,
            "lng": latest_tracking.longitude if latest_tracking else None,
            "temperature": latest_tracking.temperature if latest_tracking else None
        }
    })

# ============== TRACKING & GPS ==============

@app.route('/track/<tracking_number>', methods=['GET'])
def track_shipment(tracking_number):
    # Public tracking (no login required)
    shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
    
    if not shipment:
        return jsonify({"error": "Tracking number not found"}), 404
    
    events = TrackingEvent.query.filter_by(shipment_id=shipment.id).order_by(TrackingEvent.timestamp.desc()).all()
    
    return jsonify({
        "tracking_number": shipment.tracking_number,
        "status": shipment.status,
        "product": shipment.product,
        "destination": shipment.destination_country,
        "current_location": {
            "lat": events[0].latitude if events else None,
            "lng": events[0].longitude if events else None,
            "temperature": events[0].temperature if events else None
        },
        "history": [{
            "event_type": e.event_type,
            "location": e.location,
            "latitude": e.latitude,
            "longitude": e.longitude,
            "temperature": e.temperature,
            "description": e.description,
            "timestamp": e.timestamp.isoformat()
        } for e in events]
    })

@app.route('/shipments/<shipment_id>/tracking', methods=['POST'])
@login_required
def add_tracking_event(shipment_id):
    # Add GPS/temperature update (simulated for now)
    data = request.get_json()
    
    shipment = Shipment.query.get_or_404(shipment_id)
    
    # Check permission
    if current_user.role != 'admin' and shipment.exporter_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    
    new_event = TrackingEvent(
        id=str(uuid.uuid4()),
        shipment_id=shipment_id,
        event_type=data.get('event_type', 'location_update'),
        location=data.get('location'),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        temperature=data.get('temperature'),
        description=data.get('description')
    )
    
    db.session.add(new_event)
    db.session.commit()
    
    return jsonify({
        "message": "Tracking event added",
        "event_id": new_event.id
    }), 201

# ============== DOCUMENTS ==============

@app.route('/documents/commercial-invoice/', methods=['POST'])
@login_required
def generate_invoice():
    shipment_id = request.args.get('shipment_id')
    shipment = Shipment.query.get_or_404(shipment_id)
    
    # Check permission
    if current_user.role != 'admin' and shipment.exporter_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    
    doc_id = str(uuid.uuid4())
    invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
    
    hs_codes = {
        "oranges": "0805.10",
        "mandarins": "0805.21",
        "lemons": "0805.50",
        "grapefruit": "0805.40"
    }
    
    document = Document(
        id=doc_id,
        shipment_id=shipment_id,
        doc_type='commercial_invoice',
        document_number=invoice_number,
        content={
            "header": "COMMERCIAL INVOICE",
            "invoice_number": invoice_number,
            "date": datetime.now().isoformat(),
            "exporter": shipment.exporter_name,
            "importer": shipment.importer_name,
            "product": shipment.product,
            "quantity": shipment.quantity_cartons,
            "destination": shipment.destination_country,
            "origin": "South Africa",
            "hs_code": hs_codes.get(shipment.product.lower(), "0805.10")
        }
    )
    
    db.session.add(document)
    db.session.commit()
    
    return jsonify({
        "id": document.id,
        "document_number": document.document_number,
        "type": document.doc_type,
        "status": document.status,
        "content": document.content
    })

@app.route('/shipments/<shipment_id>/documents', methods=['GET'])
@login_required
def get_shipment_documents(shipment_id):
    shipment = Shipment.query.get_or_404(shipment_id)
    
    # Check permission
    if current_user.role != 'admin' and shipment.exporter_id != current_user.id:
        return jsonify({"error": "Access denied"}), 403
    
    documents = Document.query.filter_by(shipment_id=shipment_id).all()
    
    return jsonify([{
        "id": d.id,
        "document_number": d.document_number,
        "type": d.doc_type,
        "status": d.status,
        "created_at": d.created_at.isoformat()
    } for d in documents])

# ============== ADMIN ROUTES ==============

@app.route('/admin/users', methods=['GET'])
@login_required
def get_all_users():
    if current_user.role != 'admin':
        return jsonify({"error": "Admin access required"}), 403
    
    users = User.query.all()
    return jsonify([{
        "id": u.id,
        "email": u.email,
        "company": u.company_name,
        "role": u.role,
        "created_at": u.created_at.isoformat()
    } for u in users])

# ============== DATABASE INIT ==============

@app.route('/init-db', methods=['POST'])
def init_database():
    # Create tables (run this once)
    try:
        db.create_all()
        return jsonify({"message": "Database initialized successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
