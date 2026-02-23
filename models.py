# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    avatar = db.Column(db.String(500))
    
    # Balance & Stats
    balance = db.Column(db.Float, default=0.0)
    total_earned = db.Column(db.Float, default=0.0)
    total_withdrawn = db.Column(db.Float, default=0.0)
    games_played = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    
    # Badge & Spins
    badge = db.Column(db.String(20), default='bronze')
    free_spins = db.Column(db.Integer, default=1)  # Changed from 10 to 1
    last_spin_reset = db.Column(db.Date)
    
    # Referral
    referral_code = db.Column(db.String(20), unique=True)
    referred_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Security
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    last_device_id = db.Column(db.String(255))
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(255))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    kyc_status = db.Column(db.String(20), default='pending')
    role = db.Column(db.String(20), default='user')
    
    # Online/Activity Tracking - NEW FIELDS
    is_online = db.Column(db.Boolean, default=False)
    last_activity = db.Column(db.DateTime)
    current_game_id = db.Column(db.String(36), db.ForeignKey('game_sessions.id'), nullable=True)
    current_game_type = db.Column(db.String(20))
    current_session_start = db.Column(db.DateTime)
    
    # Freeze/Appeal System
    is_frozen = db.Column(db.Boolean, default=False)
    frozen_reason = db.Column(db.String(500))
    frozen_at = db.Column(db.DateTime)
    frozen_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    appeal_message = db.Column(db.Text)
    appeal_status = db.Column(db.String(20), default='none')
    appeal_submitted_at = db.Column(db.DateTime)
    appeal_reviewed_at = db.Column(db.DateTime)
    appeal_reviewed_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    appeal_response = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    games = db.relationship('GameSession', backref='player', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    spins = db.relationship('SpinHistory', backref='user', lazy=True)
    appeals = db.relationship('Appeal', backref='user', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'avatar': self.avatar,
            'balance': self.balance,
            'total_earned': self.total_earned,
            'badge': self.badge,
            'free_spins': self.free_spins,
            'games_played': self.games_played,
            'wins': self.wins,
            'is_verified': self.is_verified,
            'kyc_status': self.kyc_status,
            'role': self.role,
            'is_frozen': self.is_frozen,
            'is_online': self.is_online,  # NEW
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,  # NEW
            'current_game_type': self.current_game_type,  # NEW
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class GameSession(db.Model):
    __tablename__ = 'game_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_code = db.Column(db.String(20), unique=True, nullable=False)
    game_type = db.Column(db.String(20), nullable=False)  # quick, level, battle, 1v1, golden
    level = db.Column(db.String(20))
    status = db.Column(db.String(20), default='waiting')  # waiting, active, completed, quit
    
    stake = db.Column(db.Float, default=0.0)
    platform_fee = db.Column(db.Float, default=0.0)
    total_pot = db.Column(db.Float, default=0.0)
    
    max_players = db.Column(db.Integer, default=1)
    current_players = db.Column(db.Integer, default=1)
    
    total_questions = db.Column(db.Integer)
    required_correct = db.Column(db.Integer)
    time_per_question = db.Column(db.Integer, default=10)
    
    question_data = db.Column(db.JSON)
    
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    winner_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Game timing - UPDATED
    started_at = db.Column(db.DateTime)  # When game actually starts
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Player tracking
    player_count = db.Column(db.Integer, default=1)  # Track current players
    players_data = db.Column(db.JSON)  # Store player info and scores
    
    def to_dict(self):
        return {
            'id': self.id,
            'game_code': self.game_code,
            'game_type': self.game_type,
            'level': self.level,
            'status': self.status,
            'stake': self.stake,
            'total_pot': self.total_pot,
            'max_players': self.max_players,
            'current_players': self.current_players,
            'player_count': self.player_count,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reference = db.Column(db.String(100), unique=True, nullable=False)
    
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')
    
    payment_method = db.Column(db.String(50))
    game_id = db.Column(db.String(36), db.ForeignKey('game_sessions.id'))
    
    transaction_metadata = db.Column(db.JSON)
    
    ip_address = db.Column(db.String(45))
    device_id = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'type': self.type,
            'amount': self.amount,
            'fee': self.fee,
            'net': self.amount - self.fee,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SpinHistory(db.Model):
    __tablename__ = 'spin_history'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount_won = db.Column(db.Float, nullable=False)
    used_free_spin = db.Column(db.Boolean, default=True)
    spin_cost = db.Column(db.Float, default=0)
    
    server_seed = db.Column(db.String(255))
    client_seed = db.Column(db.String(255))
    nonce = db.Column(db.Integer)
    hash_result = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount_won,
            'used_free_spin': self.used_free_spin,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Appeal(db.Model):
    __tablename__ = 'appeals'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='appeals')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # login, logout, game_start, game_end, win, stake
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id])