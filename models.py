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
    free_spins = db.Column(db.Integer, default=10)
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
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Question(db.Model):
    __tablename__ = 'questions'
    
    __table_args__ = (
        db.Index('idx_question_level', 'level'),
        db.Index('idx_question_category', 'category'),
        db.Index('idx_question_difficulty', 'difficulty'),
        db.Index('idx_question_active', 'is_active'),
        db.Index('idx_question_usage', 'times_used'),
    )
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Categorization
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(50))
    level = db.Column(db.String(20), nullable=False)
    difficulty = db.Column(db.Integer, default=1)
    
    # Question content
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.Integer, nullable=False)
    
    # Additional fields
    explanation = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    points = db.Column(db.Integer, default=10)
    time_limit = db.Column(db.Integer, default=10)
    
    # Statistics
    times_used = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    wrong_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    def update_stats(self, was_correct):
        self.times_used += 1
        if was_correct:
            self.correct_count += 1
        else:
            self.wrong_count += 1
        self.success_rate = (self.correct_count / self.times_used) * 100 if self.times_used > 0 else 0
    
    def to_dict(self, include_answer=False):
        data = {
            'id': self.id,
            'category': self.category,
            'subcategory': self.subcategory,
            'level': self.level,
            'difficulty': self.difficulty,
            'question': self.question_text,
            'options': [self.option_a, self.option_b, self.option_c, self.option_d],
            'time_limit': self.time_limit,
            'points': self.points,
            'image_url': self.image_url
        }
        if include_answer:
            data['correct'] = self.correct_answer
            data['explanation'] = self.explanation
        return data


class GameSession(db.Model):
    __tablename__ = 'game_sessions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_code = db.Column(db.String(20), unique=True, nullable=False)
    game_type = db.Column(db.String(20), nullable=False)
    level = db.Column(db.String(20))
    status = db.Column(db.String(20), default='waiting')
    
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
    
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    
    metadata = db.Column(db.JSON)
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
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='appeals')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])


class QuestionCategory(db.Model):
    __tablename__ = 'question_categories'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    question_count = db.Column(db.Integer, default=0)
    icon = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)