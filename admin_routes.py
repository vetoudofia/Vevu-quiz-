# admin_routes.py
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import uuid
from datetime import datetime, timedelta
from models import db, User, Question, Transaction, GameSession, Appeal, ActivityLog
from config import Config
from sqlalchemy import func

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


# NEW: Real-time stats endpoint
@admin_bp.route('/stats/realtime', methods=['GET'])
@admin_required
def get_realtime_stats():
    """Get real-time active users and game stats"""
    
    # Active users (online in last 5 minutes)
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)
    active_users = User.query.filter(
        User.last_activity >= five_min_ago,
        User.is_online == True
    ).count()
    
    # Games in progress
    games_in_progress = GameSession.query.filter(
        GameSession.status.in_(['waiting', 'active'])
    ).all()
    
    # Count by game type
    game_counts = {
        'quick': 0,
        'level': 0,
        'battle': 0,
        'onevone': 0,
        'golden': 0
    }
    
    for game in games_in_progress:
        if game.game_type in game_counts:
            game_counts[game.game_type] += 1
    
    # Top active players (currently playing)
    top_players = User.query.filter(
        User.current_game_id.isnot(None),
        User.is_online == True
    ).limit(5).all()
    
    top_players_data = []
    for player in top_players:
        game = GameSession.query.get(player.current_game_id)
        time_ago = datetime.utcnow() - (player.current_session_start or datetime.utcnow())
        minutes = int(time_ago.total_seconds() / 60)
        
        top_players_data.append({
            'id': player.id,
            'name': f"{player.first_name} {player.last_name}".strip() or player.email,
            'gameType': player.current_game_type or 'Unknown',
            'timeAgo': f"{minutes} min ago" if minutes > 0 else "Just now"
        })
    
    # Recent activity (last 10 actions)
    recent = ActivityLog.query.order_by(
        ActivityLog.created_at.desc()
    ).limit(10).all()
    
    recent_data = []
    for log in recent:
        user = User.query.get(log.user_id) if log.user_id else None
        recent_data.append({
            'user': user.first_name if user else 'System',
            'action': log.action,
            'type': log.details.get('type') if log.details else 'info',
            'time': log.created_at.strftime('%H:%M'),
            'details': log.details
        })
    
    return jsonify({
        'activeUsers': active_users,
        'games': game_counts,
        'topPlayers': top_players_data,
        'recentActivity': recent_data
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
            'is_online': u.is_online,  # NEW
            'current_game_type': u.current_game_type,  # NEW
            'last_activity': u.last_activity.isoformat() if u.last_activity else None,  # NEW
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'last_login': u.last_login.isoformat() if u.last_login else None
        } for u in users.items],
        'total': users.total,
        'page': page,
        'pages': users.pages
    }), 200


# ... rest of your existing admin routes remain the same ...
# (get_user, get_user_stats, get_user_games, get_user_transactions,
#  adjust_user_balance, freeze_user, unfreeze_user, etc.)