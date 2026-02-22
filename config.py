# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database - using Supabase PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # Redis for rate limiting (optional)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # Security Settings
    BCRYPT_LOG_ROUNDS = 12
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate Limiting
    RATE_LIMIT_DEFAULT = "100 per hour"
    RATE_LIMIT_LOGIN = "5 per minute"
    RATE_LIMIT_REGISTER = "3 per hour"
    RATE_LIMIT_SPIN = "10 per day"
    RATE_LIMIT_GAME_CREATE = "10 per hour"
    
    # Account Security
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    
    # Platform Settings
    PLATFORM_FEE = 0.10  # 10%
    WELCOME_BONUS = 30.00  # ₦30
    MIN_DEPOSIT = 50
    MIN_STAKE = 10
    MAX_STAKE = 100000
    MIN_WITHDRAWAL = 500
    MAX_WITHDRAWAL = 5000000
    
    # Spin Wheel
    FREE_SPINS_DAILY = 10
    SPIN_COST = 50
    
    # Frontend
    FRONTEND_URL = os.environ.get('FRONTEND_URL') or 'http://localhost:19000'
    
    # CORS
    CORS_ORIGINS = [FRONTEND_URL]
    
    # Supabase (optional - for extra features)
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
    SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
    SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET')
    
    # Paystack Payment Gateway (NO STRIPE)
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')