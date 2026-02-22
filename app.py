from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import uuid
import hashlib
import re

app = Flask(__name__)
CORS(app)

# In-memory storage (temporary)
users = []
games = []

# Helper functions
def hash_password(password):
    """Simple hash for demo - will use bcrypt later"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    pattern = r'^\+?[\d\s-]{10,}$'
    return re.match(pattern, phone) is not None

@app.route('/')
def home():
    return jsonify({
        'message': '🎉 VEV QUIZER API is running!',
        'status': 'online',
        'version': '1.0.0',
        'endpoints': [
            '/health',
            '/api/auth/register',
            '/api/auth/login',
            '/api/user/profile',
            '/api/games'
        ]
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/test')
def test():
    return jsonify({
        'success': True,
        'message': 'API connection successful'
    })

# ==================== AUTH ENDPOINTS ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user with ₦30 welcome bonus"""
    
    # Get data from request
    data = request.json
    
    # Validate required fields
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Check if email or phone provided
    if not data.get('email') and not data.get('phone'):
        return jsonify({'error': 'Email or phone required'}), 400
    
    # Validate email if provided
    if data.get('email') and not validate_email(data['email']):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Validate phone if provided
    if data.get('phone') and not validate_phone(data['phone']):
        return jsonify({'error': 'Invalid phone format'}), 400
    
    # Validate password
    if not data.get('password'):
        return jsonify({'error': 'Password required'}), 400
    
    if len(data['password']) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if user already exists
    for user in users:
        if data.get('email') and user['email'] == data['email']:
            return jsonify({'error': 'Email already registered'}), 400
        if data.get('phone') and user['phone'] == data['phone']:
            return jsonify({'error': 'Phone already registered'}), 400
    
    # Create new user with ₦30 welcome bonus
    new_user = {
        'id': str(uuid.uuid4()),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'password': hash_password(data['password']),
        'first_name': data.get('first_name', ''),
        'last_name': data.get('last_name', ''),
        'balance': 30.00,  # ₦30 welcome bonus
        'total_earned': 30.00,
        'free_spins': 10,
        'badge': 'bronze',
        'games_played': 0,
        'wins': 0,
        'created_at': datetime.now().isoformat(),
        'last_login': None
    }
    
    # Save user (temporary - in memory)
    users.append(new_user)
    
    # Remove password from response
    user_response = new_user.copy()
    del user_response['password']
    
    return jsonify({
        'success': True,
        'message': 'Registration successful! You received ₦30 welcome bonus.',
        'user': user_response
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    identifier = data.get('email') or data.get('phone')
    password = data.get('password')
    
    if not identifier or not password:
        return jsonify({'error': 'Email/phone and password required'}), 400
    
    # Find user
    found_user = None
    for user in users:
        if user['email'] == identifier or user['phone'] == identifier:
            found_user = user
            break
    
    if not found_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check password
    if found_user['password'] != hash_password(password):
        return jsonify({'error': 'Invalid password'}), 401
    
    # Update last login
    found_user['last_login'] = datetime.now().isoformat()
    
    # Remove password from response
    user_response = found_user.copy()
    del user_response['password']
    
    # Generate simple token (in production, use JWT)
    token = str(uuid.uuid4())
    
    return jsonify({
        'success': True,
        'token': token,
        'user': user_response
    }), 200

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users (for testing only)"""
    # Remove passwords from response
    safe_users = []
    for user in users:
        user_copy = user.copy()
        del user_copy['password']
        safe_users.append(user_copy)
    
    return jsonify({
        'users': safe_users,
        'count': len(safe_users)
    })

@app.route('/api/games', methods=['GET'])
def get_games():
    return jsonify({
        'games': games,
        'count': len(games)
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 VEV QUIZER BACKEND STARTING...")
    print("=" * 50)
    print("\n✅ Server running on: http://localhost:5000")
    print("✅ Test endpoint: http://localhost:5000/api/test")
    print("✅ Register endpoint: http://localhost:5000/api/auth/register")
    print("✅ Login endpoint: http://localhost:5000/api/auth/login")
    print("\n📝 Test users will be stored in memory")
    print(" Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
   
# Store device ID with login
device_id = request.headers.get('X-Device-ID')
if device_id:
    user.last_device = device_id
    user.last_ip = request.remote_addr
    
# Track failed attempts
failed_attempts = redis.get(f"failed_login:{email}")
if failed_attempts and int(failed_attempts) >= 5:
    return jsonify({'error': 'Account locked. Try again in 15 minutes'}), 429
    
 # Send OTP for registration
otp = generate_otp()
send_email(email, f"Your verification code is: {otp}")
# User must verify before playing 
