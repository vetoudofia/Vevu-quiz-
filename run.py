# run.py - Main entry point for VEV QUIZER Backend
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Import config
from config import Config

# Import database
from models import db

# Import blueprints
from auth import auth_bp
from quiz import quiz_bp
from wallet import wallet_bp
from spinwheel import spinwheel_bp
from admin_routes import admin_bp

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
CORS(app, origins=[
    "http://localhost:19000",                    # Local frontend dev
    "http://localhost:19001",                     # Local admin dev
    "exp://localhost:19000",                       # Local Expo Go frontend
    "exp://localhost:19001",                        # Local Expo Go admin
    "https://vev-squizer-backend.onrender.com"      # Your Render URL
], supports_credentials=True)

db.init_app(app)
migrate = Migrate(app, db)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(quiz_bp, url_prefix='/api/quiz')
app.register_blueprint(wallet_bp, url_prefix='/api/wallet')
app.register_blueprint(spinwheel_bp, url_prefix='/api/wheel')
app.register_blueprint(admin_bp)

# Root endpoint
@app.route('/')
def index():
    return jsonify({
        'name': 'VEV QUIZER API',
        'version': '1.0.0',
        'status': 'running',
        'environment': os.getenv('FLASK_ENV', 'production'),
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': {
            'auth': '/api/auth',
            'quiz': '/api/quiz',
            'wallet': '/api/wallet',
            'wheel': '/api/wheel',
            'admin': '/api/admin',
            'version': '/api/version'
        }
    })

# Health check
@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'connected'
    })

# Version endpoint for app updates
@app.route('/api/version', methods=['GET'])
def get_version():
    """Get latest app version for update checks"""
    return jsonify({
        'version': '1.0.1',           # Change this when you release updates
        'force': False,                 # True for critical updates
        'message': 'New features and bug fixes available!'
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({'error': 'Rate limit exceeded. Please slow down.'}), 429

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# CLI command to create database
@app.cli.command('init-db')
def init_db():
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print('✅ Database tables created!')

# CLI command to create admin user
@app.cli.command('create-admin')
def create_admin():
    """Create admin user"""
    from models import User
    import bcrypt
    import uuid
    
    email = input('Admin email: ')
    password = input('Admin password: ')
    
    admin = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        first_name='Admin',
        last_name='User',
        balance=0,
        is_verified=True,
        is_active=True,
        role='admin'
    )
    db.session.add(admin)
    db.session.commit()
    print(f'✅ Admin user {email} created!')

# Run the app
if __name__ == '__main__':
    print("=" * 60)
    print("🎉 VEV QUIZER BACKEND - RUNNING")
    print("=" * 60)
    print(f"\n📁 Environment: {os.getenv('FLASK_ENV', 'production')}")
    print(f"\n🌐 Endpoints:")
    print(f"   • Main API: http://localhost:5000")
    print(f"   • Health: http://localhost:5000/health")
    print(f"   • Version: http://localhost:5000/api/version")
    print(f"\n🚀 Starting server...\n")
    
    app.run(host='0.0.0.0', port=5000)