# auth.py
from flask import Blueprint, request, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt
import uuid
import re
import jwt
import pyotp
from datetime import datetime, timedelta
from models import db, User
from config import Config

auth_bp = Blueprint('auth', __name__)

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=Config.REDIS_URL
)

# Helper functions
def hash_password(password):
    salt = bcrypt.gensalt(rounds=Config.BCRYPT_LOG_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + Config.JWT_ACCESS_TOKEN_EXPIRES,
        'iat': datetime.utcnow(),
        'jti': str(uuid.uuid4())
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')

def generate_refresh_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + Config.JWT_REFRESH_TOKEN_EXPIRES,
        'iat': datetime.utcnow(),
        'type': 'refresh'
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')

def validate_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    pattern = r'^\+?[\d\s-]{10,}$'
    return re.match(pattern, phone) is not None

def generate_otp():
    import random
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def generate_referral_code():
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)

def get_device_id():
    return request.headers.get('X-Device-ID', 'unknown')


@auth_bp.route('/register', methods=['POST'])
@limiter.limit(Config.RATE_LIMIT_REGISTER)
def register():
    """Register new user with ₦30 welcome bonus"""
    
    data = request.json
    ip = get_client_ip()
    device_id = get_device_id()
    
    # Validation
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if not data.get('password'):
        return jsonify({'error': 'Password required'}), 400
    
    if len(data['password']) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    has_email = data.get('email')
    has_phone = data.get('phone')
    
    if not has_email and not has_phone:
        return jsonify({'error': 'Email or phone required'}), 400
    
    if has_email and not validate_email(has_email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    if has_phone and not validate_phone(has_phone):
        return jsonify({'error': 'Invalid phone format'}), 400
    
    # Check if user exists
    if has_email:
        existing = User.query.filter_by(email=has_email).first()
        if existing:
            return jsonify({'error': 'Email already registered'}), 400
    
    if has_phone:
        existing = User.query.filter_by(phone=has_phone).first()
        if existing:
            return jsonify({'error': 'Phone already registered'}), 400
    
    # Create verification token
    verification_token = generate_otp()
    
    # Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=has_email,
        phone=has_phone,
        password_hash=hash_password(data['password']),
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', ''),
        balance=Config.WELCOME_BONUS,
        total_earned=Config.WELCOME_BONUS,
        free_spins=Config.FREE_SPINS_DAILY,
        badge='bronze',
        referral_code=generate_referral_code(),
        verification_token=verification_token,
        last_login_ip=ip,
        last_device_id=device_id,
        created_at=datetime.utcnow()
    )
    
    # Handle referral
    if data.get('referral_code'):
        referrer = User.query.filter_by(referral_code=data['referral_code']).first()
        if referrer:
            new_user.referred_by = referrer.id
    
    db.session.add(new_user)
    db.session.commit()
    
    # In production, send verification email/SMS here
    # send_verification_email(new_user.email, verification_token)
    
    # Generate tokens
    token = generate_token(new_user.id)
    refresh_token = generate_refresh_token(new_user.id)
    
    return jsonify({
        'success': True,
        'message': f'Registration successful! You received ₦{Config.WELCOME_BONUS} welcome bonus.',
        'token': token,
        'refresh_token': refresh_token,
        'user': new_user.to_dict()
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit(Config.RATE_LIMIT_LOGIN)
def login():
    """Login user with rate limiting and lockout protection"""
    
    data = request.json
    ip = get_client_ip()
    device_id = get_device_id()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    identifier = data.get('email') or data.get('phone')
    password = data.get('password')
    
    if not identifier or not password:
        return jsonify({'error': 'Email/phone and password required'}), 400
    
    # Find user
    user = None
    if '@' in identifier:
        user = User.query.filter_by(email=identifier).first()
    else:
        user = User.query.filter_by(phone=identifier).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        minutes_left = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        return jsonify({
            'error': f'Account locked. Try again in {minutes_left} minutes'
        }), 403
    
    # Check password
    if not check_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1
        
        # Lock account if too many failures
        if user.failed_login_attempts >= Config.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=Config.LOGIN_LOCKOUT_MINUTES)
            db.session.commit()
            return jsonify({
                'error': f'Too many failed attempts. Account locked for {Config.LOGIN_LOCKOUT_MINUTES} minutes'
            }), 403
        
        db.session.commit()
        return jsonify({'error': 'Invalid password'}), 401
    
    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    user.last_login_ip = ip
    user.last_device_id = device_id
    
    db.session.commit()
    
    # Generate tokens
    token = generate_token(user.id)
    refresh_token = generate_refresh_token(user.id)
    
    return jsonify({
        'success': True,
        'token': token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Get new access token using refresh token"""
    
    data = request.json
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400
    
    try:
        payload = jwt.decode(refresh_token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401
        
        user_id = payload['user_id']
        new_token = generate_token(user_id)
        
        return jsonify({
            'success': True,
            'token': new_token
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid refresh token'}), 401


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    """Verify email with token"""
    
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        return jsonify({'error': 'Invalid verification token'}), 404
    
    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Email verified successfully'
    }), 200


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Send password reset OTP"""
    
    data = request.json
    identifier = data.get('email') or data.get('phone')
    
    if not identifier:
        return jsonify({'error': 'Email or phone required'}), 400
    
    # Find user
    user = None
    if '@' in identifier:
        user = User.query.filter_by(email=identifier).first()
    else:
        user = User.query.filter_by(phone=identifier).first()
    
    if not user:
        # Don't reveal that user doesn't exist (security)
        return jsonify({'success': True, 'message': 'If account exists, OTP will be sent'}), 200
    
    # Generate OTP
    otp = generate_otp()
    user.verification_token = otp
    db.session.commit()
    
    # In production, send OTP via email/SMS
    # send_otp_email(user.email, otp)
    # send_otp_sms(user.phone, otp)
    
    return jsonify({
        'success': True,
        'message': 'OTP sent successfully',
        'user_id': user.id
    }), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with OTP"""
    
    data = request.json
    user_id = data.get('user_id')
    otp = data.get('otp')
    new_password = data.get('new_password')
    
    if not all([user_id, otp, new_password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    user = User.query.get(user_id)
    if not user or user.verification_token != otp:
        return jsonify({'error': 'Invalid OTP'}), 400
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.verification_token = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Password reset successful'
    }), 200


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.json
        
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'avatar' in data:
            user.avatar = data['avatar']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401


@auth_bp.route('/admin/login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    """Special login endpoint for admins with extra security"""
    
    data = request.json
    email = data.get('email')
    password = data.get('password')
    admin_key = data.get('admin_key')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    # Verify admin secret key (from .env)
    if admin_key != os.environ.get('ADMIN_SECRET_KEY'):
        return jsonify({'error': 'Invalid admin credentials'}), 401
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({'error': 'Admin not found'}), 404
    
    # Check if user has admin role
    if user.role != 'admin':
        return jsonify({'error': 'Not authorized as admin'}), 403
    
    # Check password
    if not check_password(password, user.password_hash):
        return jsonify({'error': 'Invalid password'}), 401
    
    # Generate admin token (longer expiry - 8 hours)
    admin_token = jwt.encode({
        'user_id': user.id,
        'email': user.email,
        'role': 'admin',
        'exp': datetime.utcnow() + timedelta(hours=8),
        'iat': datetime.utcnow()
    }, Config.JWT_SECRET_KEY, algorithm='HS256')
    
    # Log admin login
    print(f"🔐 Admin login: {email} at {datetime.utcnow()}")
    
    return jsonify({
        'success': True,
        'message': 'Admin login successful',
        'token': admin_token,
        'admin': {
            'id': user.id,
            'email': user.email,
            'name': f"{user.first_name} {user.last_name}".strip() or user.email,
            'role': user.role
        }
    }), 200


@auth_bp.route('/admin/verify', methods=['GET'])
def verify_admin_token():
    """Verify if a token is a valid admin token"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided', 'valid': False}), 401
    
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        
        if payload.get('role') != 'admin':
            return jsonify({'valid': False, 'error': 'Not an admin token'}), 403
        
        user = User.query.get(payload['user_id'])
        if not user or user.role != 'admin':
            return jsonify({'valid': False, 'error': 'Admin not found'}), 404
        
        return jsonify({
            'valid': True,
            'admin': {
                'id': user.id,
                'email': user.email,
                'name': f"{user.first_name} {user.last_name}".strip() or user.email
            }
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'valid': False, 'error': 'Invalid token'}), 401