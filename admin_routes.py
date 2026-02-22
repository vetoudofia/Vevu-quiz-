# admin_routes.py
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import uuid
from datetime import datetime, timedelta
from models import db, User, Question, Transaction, GameSession, Appeal
from config import Config

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Admin decorator to protect routes
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'No token provided'}), 401
        
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
                
            request.admin_id = payload['user_id']
            
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated


# Dashboard Statistics
@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats():
    """Get admin dashboard statistics"""
    
    # User stats
    total_users = User.query.count()
    active_today = User.query.filter(
        User.last_login >= datetime.utcnow() - timedelta(days=1)
    ).count()
    
    # Question stats
    total_questions = Question.query.count()
    
    # Game stats
    total_games = GameSession.query.count()
    games_today = GameSession.query.filter(
        GameSession.created_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    
    # Appeal stats
    pending_appeals = Appeal.query.filter_by(status='pending').count()
    
    # Transaction stats
    total_deposits = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        type='deposit', status='completed'
    ).scalar() or 0
    
    total_withdrawals = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        type='withdraw', status='completed'
    ).scalar() or 0
    
    total_revenue = db.session.query(db.func.sum(Transaction.fee)).filter_by(
        status='completed'
    ).scalar() or 0
    
    pending_withdrawals = Transaction.query.filter_by(
        type='withdraw', status='pending'
    ).count()
    
    return jsonify({
        'users': {
            'total': total_users,
            'active_today': active_today
        },
        'questions': {
            'total': total_questions
        },
        'games': {
            'total': total_games,
            'today': games_today
        },
        'appeals': {
            'pending': pending_appeals
        },
        'financial': {
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'total_revenue': float(total_revenue),
            'pending_withdrawals': pending_withdrawals
        }
    }), 200


# User Management
@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users with pagination"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            db.or_(
                User.email.ilike(f'%{search}%'),
                User.phone.ilike(f'%{search}%'),
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%')
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'users': [{
            'id': u.id,
            'email': u.email,
            'phone': u.phone,
            'name': f"{u.first_name} {u.last_name}".strip(),
            'balance': u.balance,
            'badge': u.badge,
            'games_played': u.games_played,
            'wins': u.wins,
            'role': u.role,
            'is_verified': u.is_verified,
            'is_active': u.is_active,
            'is_frozen': u.is_frozen,
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users.items],
        'total': users.total,
        'page': page,
        'pages': users.pages
    }), 200


@admin_bp.route('/users/<user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Get single user details"""
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200


@admin_bp.route('/users/<user_id>/stats', methods=['GET'])
@admin_required
def get_user_stats(user_id):
    """Get user statistics"""
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Calculate win rate
    win_rate = (user.wins / user.games_played * 100) if user.games_played > 0 else 0
    
    return jsonify({
        'win_rate': round(win_rate, 2),
        'avg_score': 0,  # Would need to calculate from game history
        'total_staked': 0,  # Would need to calculate from transactions
        'total_won': user.total_earned
    }), 200


@admin_bp.route('/users/<user_id>/games', methods=['GET'])
@admin_required
def get_user_games(user_id):
    """Get user game history"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    games = GameSession.query.filter_by(
        created_by=user_id
    ).order_by(
        GameSession.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'games': [{
            'id': g.id,
            'game_code': g.game_code,
            'game_type': g.game_type,
            'status': g.status,
            'stake': g.stake,
            'result': 'win' if g.winner_id == user_id else 'loss',
            'created_at': g.created_at.isoformat() if g.created_at else None
        } for g in games.items],
        'total': games.total,
        'page': page,
        'pages': games.pages
    }), 200


@admin_bp.route('/users/<user_id>/transactions', methods=['GET'])
@admin_required
def get_user_transactions(user_id):
    """Get user transactions"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'transactions': [t.to_dict() for t in transactions.items],
        'total': transactions.total,
        'page': page,
        'pages': transactions.pages
    }), 200


@admin_bp.route('/users/<user_id>/balance', methods=['POST'])
@admin_required
def adjust_user_balance(user_id):
    """Adjust user balance (add/deduct)"""
    
    data = request.json
    amount = data.get('amount')
    action = data.get('action')  # 'add' or 'deduct'
    reason = data.get('reason', 'Admin adjustment')
    
    if not amount or not action:
        return jsonify({'error': 'Amount and action required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if action == 'add':
        user.balance += amount
    elif action == 'deduct':
        if user.balance < amount:
            return jsonify({'error': 'Insufficient balance'}), 400
        user.balance -= amount
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    # Record admin transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        reference=f"ADMIN-{uuid.uuid4().hex[:8].upper()}",
        type='admin_adjustment',
        amount=amount,
        status='completed',
        # FIXED: Changed from 'metadata' to 'transaction_metadata'
        transaction_metadata={'action': action, 'reason': reason, 'admin_id': request.admin_id}
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_balance': user.balance,
        'message': f'Balance {action}ed by ₦{amount}'
    }), 200


@admin_bp.route('/users/<user_id>/freeze', methods=['POST'])
@admin_required
def freeze_user(user_id):
    """Freeze a user account"""
    
    data = request.json
    reason = data.get('reason', 'No reason provided')
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.is_frozen:
        return jsonify({'error': 'User already frozen'}), 400
    
    user.is_frozen = True
    user.frozen_reason = reason
    user.frozen_at = datetime.utcnow()
    user.frozen_by = request.admin_id
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'User {user.email} has been frozen',
        'user': user.to_dict()
    }), 200


@admin_bp.route('/users/<user_id>/unfreeze', methods=['POST'])
@admin_required
def unfreeze_user(user_id):
    """Unfreeze a user account"""
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if not user.is_frozen:
        return jsonify({'error': 'User is not frozen'}), 400
    
    user.is_frozen = False
    user.frozen_reason = None
    user.frozen_at = None
    user.frozen_by = None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'User {user.email} has been unfrozen',
        'user': user.to_dict()
    }), 200


# Question Management
@admin_bp.route('/questions', methods=['GET'])
@admin_required
def get_questions():
    """Get all questions"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    level = request.args.get('level')
    
    query = Question.query
    
    if level and level != 'all':
        query = query.filter_by(level=level)
    
    questions = query.order_by(Question.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'questions': [{
            'id': q.id,
            'category': q.category,
            'level': q.level,
            'difficulty': q.difficulty,
            'question': q.question_text,
            'options': [q.option_a, q.option_b, q.option_c, q.option_d],
            'correct': q.correct_answer,
            'explanation': q.explanation,
            'points': q.points,
            'time_limit': q.time_limit,
            'times_used': q.times_used,
            'success_rate': q.success_rate,
            'is_active': q.is_active
        } for q in questions.items],
        'total': questions.total,
        'page': page,
        'pages': questions.pages
    }), 200


@admin_bp.route('/questions', methods=['POST'])
@admin_required
def create_question():
    """Create a new question"""
    
    data = request.json
    
    required = ['category', 'level', 'question', 'options', 'correct']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    question = Question(
        id=str(uuid.uuid4()),
        category=data['category'],
        level=data['level'],
        difficulty=data.get('difficulty', 1),
        question_text=data['question'],
        option_a=data['options'][0],
        option_b=data['options'][1],
        option_c=data['options'][2],
        option_d=data['options'][3],
        correct_answer=data['correct'],
        explanation=data.get('explanation', ''),
        points=data.get('points', 10),
        time_limit=data.get('time_limit', 10)
    )
    
    db.session.add(question)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Question created',
        'question_id': question.id
    }), 201


@admin_bp.route('/questions/<question_id>', methods=['PUT'])
@admin_required
def update_question(question_id):
    """Update a question"""
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    data = request.json
    
    if 'category' in data:
        question.category = data['category']
    if 'level' in data:
        question.level = data['level']
    if 'difficulty' in data:
        question.difficulty = data['difficulty']
    if 'question' in data:
        question.question_text = data['question']
    if 'options' in data:
        question.option_a = data['options'][0]
        question.option_b = data['options'][1]
        question.option_c = data['options'][2]
        question.option_d = data['options'][3]
    if 'correct' in data:
        question.correct_answer = data['correct']
    if 'explanation' in data:
        question.explanation = data['explanation']
    if 'points' in data:
        question.points = data['points']
    if 'time_limit' in data:
        question.time_limit = data['time_limit']
    if 'is_active' in data:
        question.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Question updated'}), 200


@admin_bp.route('/questions/<question_id>', methods=['DELETE'])
@admin_required
def delete_question(question_id):
    """Delete a question"""
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    db.session.delete(question)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Question deleted'}), 200


# Transaction Management
@admin_bp.route('/transactions', methods=['GET'])
@admin_required
def get_transactions():
    """Get all transactions"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status', 'all')
    t_type = request.args.get('type', 'all')
    
    query = Transaction.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    if t_type != 'all':
        query = query.filter_by(type=t_type)
    
    transactions = query.order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'transactions': [{
            'id': t.id,
            'reference': t.reference,
            'user_id': t.user_id,
            'type': t.type,
            'amount': t.amount,
            'fee': t.fee,
            'status': t.status,
            'created_at': t.created_at.isoformat() if t.created_at else None
        } for t in transactions.items],
        'total': transactions.total,
        'page': page,
        'pages': transactions.pages
    }), 200


@admin_bp.route('/transactions/stats', methods=['GET'])
@admin_required
def get_transaction_stats():
    """Get transaction statistics"""
    
    total_deposits = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        type='deposit', status='completed'
    ).scalar() or 0
    
    total_withdrawals = db.session.query(db.func.sum(Transaction.amount)).filter_by(
        type='withdraw', status='completed'
    ).scalar() or 0
    
    pending_count = Transaction.query.filter_by(
        type='withdraw', status='pending'
    ).count()
    
    total_revenue = db.session.query(db.func.sum(Transaction.fee)).filter_by(
        status='completed'
    ).scalar() or 0
    
    return jsonify({
        'total_deposits': float(total_deposits),
        'total_withdrawals': float(total_withdrawals),
        'pending_count': pending_count,
        'total_revenue': float(total_revenue)
    }), 200


@admin_bp.route('/transactions/<transaction_id>/process', methods=['POST'])
@admin_required
def process_transaction(transaction_id):
    """Process a pending transaction (for withdrawals)"""
    
    data = request.json
    action = data.get('action')  # 'approve' or 'reject'
    note = data.get('note', '')
    
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    if transaction.type != 'withdraw':
        return jsonify({'error': 'Only withdrawals can be processed'}), 400
    
    if transaction.status != 'pending':
        return jsonify({'error': 'Transaction already processed'}), 400
    
    if action == 'approve':
        transaction.status = 'completed'
        transaction.processed_at = datetime.utcnow()
        message = 'Withdrawal approved'
        
    elif action == 'reject':
        transaction.status = 'failed'
        transaction.processed_at = datetime.utcnow()
        
        # Refund the user
        user = User.query.get(transaction.user_id)
        if user:
            user.balance += transaction.amount
        
        message = 'Withdrawal rejected and refunded'
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    # Add note to metadata
    if not transaction.transaction_metadata:
        transaction.transaction_metadata = {}
    transaction.transaction_metadata['admin_note'] = note
    transaction.transaction_metadata['processed_by'] = request.admin_id
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': message}), 200


# Appeals Management
@admin_bp.route('/appeals', methods=['GET'])
@admin_required
def get_appeals():
    """Get all appeals"""
    
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Appeal.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    appeals = query.order_by(
        Appeal.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'appeals': [{
            'id': a.id,
            'user_id': a.user_id,
            'user_email': a.user.email,
            'user_name': f"{a.user.first_name} {a.user.last_name}".strip(),
            'reason': a.reason,
            'message': a.message,
            'status': a.status,
            'admin_notes': a.admin_notes,
            'created_at': a.created_at.isoformat(),
            'reviewed_at': a.reviewed_at.isoformat() if a.reviewed_at else None
        } for a in appeals.items],
        'total': appeals.total,
        'page': page,
        'pages': appeals.pages
    }), 200


@admin_bp.route('/appeals/<appeal_id>/review', methods=['POST'])
@admin_required
def review_appeal(appeal_id):
    """Review an appeal"""
    
    data = request.json
    action = data.get('action')  # approve, reject
    notes = data.get('notes', '')
    
    appeal = Appeal.query.get(appeal_id)
    if not appeal:
        return jsonify({'error': 'Appeal not found'}), 404
    
    if appeal.status != 'pending':
        return jsonify({'error': 'Appeal already reviewed'}), 400
    
    appeal.status = 'approved' if action == 'approve' else 'rejected'
    appeal.admin_notes = notes
    appeal.reviewed_by = request.admin_id
    appeal.reviewed_at = datetime.utcnow()
    
    # If approved, unfreeze the user
    if action == 'approve':
        user = User.query.get(appeal.user_id)
        if user:
            user.is_frozen = False
            user.frozen_reason = None
            user.frozen_at = None
            user.frozen_by = None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Appeal {action}d successfully'
    }), 200