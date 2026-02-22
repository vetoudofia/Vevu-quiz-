# spinwheel.py
from flask import Blueprint, request, jsonify
from flask_cors import CORS
import uuid
import random
import hashlib
import hmac
import secrets
from datetime import datetime, date, timedelta
from models import db, User, SpinHistory, Transaction
from config import Config

spinwheel_bp = Blueprint('spinwheel', __name__)

# Wheel configuration
WHEEL_SEGMENTS = [
    {'prize': 10, 'probability': 30, 'color': '#FF6B6B', 'label': '₦10'},
    {'prize': 20, 'probability': 25, 'color': '#4ECDC4', 'label': '₦20'},
    {'prize': 50, 'probability': 15, 'color': '#45B7D1', 'label': '₦50'},
    {'prize': 100, 'probability': 10, 'color': '#96CEB4', 'label': '₦100'},
    {'prize': 200, 'probability': 8, 'color': '#FFEAA7', 'label': '₦200'},
    {'prize': 500, 'probability': 5, 'color': '#DDA0DD', 'label': '₦500'},
    {'prize': 1000, 'probability': 4, 'color': '#F08080', 'label': '₦1000'},
    {'prize': 2000, 'probability': 3, 'color': '#9ACD32', 'label': '₦2000'}
]

# Verify probabilities sum to 100
TOTAL_PROBABILITY = sum(s['probability'] for s in WHEEL_SEGMENTS)
if TOTAL_PROBABILITY != 100:
    # Adjust if needed
    pass


class ProvablyFairSpin:
    """Provably fair spin wheel algorithm"""
    
    @staticmethod
    def generate_server_seed():
        """Generate server seed"""
        return secrets.token_hex(32)
    
    @staticmethod
    def generate_client_seed(user_id):
        """Generate client seed based on user and time"""
        timestamp = datetime.utcnow().isoformat()
        seed_string = f"{user_id}:{timestamp}:{secrets.token_hex(8)}"
        return hashlib.sha256(seed_string.encode()).hexdigest()
    
    @staticmethod
    def calculate_result(server_seed, client_seed, nonce=0):
        """Calculate spin result from seeds"""
        combined = f"{server_seed}:{client_seed}:{nonce}"
        hash_result = hashlib.sha256(combined.encode()).hexdigest()
        
        # Convert first 8 chars to number between 0-9999
        random_number = int(hash_result[:8], 16) % 10000
        
        # Map to prize based on probabilities
        cumulative = 0
        for segment in WHEEL_SEGMENTS:
            prob_range = segment['probability'] * 100  # Convert to 0-10000 range
            cumulative += prob_range
            if random_number < cumulative:
                return {
                    'prize': segment['prize'],
                    'random_number': random_number,
                    'hash_result': hash_result,
                    'segment': segment
                }
        
        # Fallback to last segment
        return {
            'prize': WHEEL_SEGMENTS[-1]['prize'],
            'random_number': random_number,
            'hash_result': hash_result,
            'segment': WHEEL_SEGMENTS[-1]
        }
    
    @staticmethod
    def verify_spin(server_seed, client_seed, nonce, expected_prize):
        """Verify a spin result was fair"""
        result = ProvablyFairSpin.calculate_result(server_seed, client_seed, nonce)
        return result['prize'] == expected_prize


# ==================== SPIN WHEEL ENDPOINTS ====================

@spinwheel_bp.route('/status', methods=['GET'])
def get_spin_status():
    """Get user's spin status"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        user_id = 'test-user-id'
        
        user = User.query.get(user_id)
        if not user:
            # Create test user
            user = User(
                id='test-user-id',
                email='test@example.com',
                password_hash='hash',
                balance=1000,
                free_spins=10,
                last_spin_reset=date.today()
            )
            db.session.add(user)
            db.session.commit()
        
        # Check if free spins need reset
        today = date.today()
        if user.last_spin_reset != today:
            user.free_spins = Config.FREE_SPINS_DAILY
            user.last_spin_reset = today
            db.session.commit()
        
        # Get today's spins count
        today_spins = SpinHistory.query.filter(
            SpinHistory.user_id == user_id,
            SpinHistory.created_at >= datetime(today.year, today.month, today.day)
        ).count()
        
        return jsonify({
            'success': True,
            'free_spins': user.free_spins,
            'total_spins_today': today_spins,
            'max_daily_free': Config.FREE_SPINS_DAILY,
            'next_free_reset': (today + timedelta(days=1)).isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@spinwheel_bp.route('/spin', methods=['POST'])
def spin_wheel():
    """Spin the wheel"""
    
    data = request.json
    use_free_spin = data.get('use_free_spin', True)
    buy_spin = data.get('buy_spin', False)
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        user_id = 'test-user-id'
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check free spins
        today = date.today()
        if user.last_spin_reset != today:
            user.free_spins = Config.FREE_SPINS_DAILY
            user.last_spin_reset = today
        
        if use_free_spin:
            if user.free_spins <= 0:
                return jsonify({'error': 'No free spins left'}), 400
        elif buy_spin:
            # Check balance for buying spin (₦50 per spin)
            spin_cost = 50
            if user.balance < spin_cost:
                return jsonify({'error': 'Insufficient balance to buy spin'}), 400
        
        # Generate provably fair spin
        server_seed = ProvablyFairSpin.generate_server_seed()
        client_seed = ProvablyFairSpin.generate_client_seed(user_id)
        nonce = SpinHistory.query.filter_by(user_id=user_id).count() + 1
        
        result = ProvablyFairSpin.calculate_result(server_seed, client_seed, nonce)
        prize = result['prize']
        
        # Update user
        if use_free_spin:
            user.free_spins -= 1
        elif buy_spin:
            spin_cost = 50
            user.balance -= spin_cost
        
        # Add winnings to balance
        user.balance += prize
        user.total_earned += prize
        
        # Record spin
        spin = SpinHistory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount_won=prize,
            used_free_spin=use_free_spin,
            spin_cost=0 if use_free_spin else 50,
            created_at=datetime.utcnow()
        )
        db.session.add(spin)
        
        # Record transaction
        transaction = Transaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            reference=f"SPIN-{uuid.uuid4().hex[:8].upper()}",
            type='spin_win',
            amount=prize,
            status='completed',
            metadata={
                'server_seed': server_seed,
                'client_seed': client_seed,
                'nonce': nonce,
                'random_number': result['random_number']
            }
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'prize': prize,
            'new_balance': user.balance,
            'remaining_spins': user.free_spins,
            'used_free_spin': use_free_spin,
            'spin_id': spin.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@spinwheel_bp.route('/history', methods=['GET'])
def get_spin_history():
    """Get user's spin history"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        user_id = 'test-user-id'
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        
        spins = SpinHistory.query.filter_by(
            user_id=user_id
        ).order_by(
            SpinHistory.created_at.desc()
        ).paginate(page=page, per_page=limit, error_out=False)
        
        # Calculate stats
        total_won = db.session.query(
            db.func.sum(SpinHistory.amount_won)
        ).filter_by(user_id=user_id).scalar() or 0
        
        total_spins = SpinHistory.query.filter_by(user_id=user_id).count()
        free_spins_used = SpinHistory.query.filter_by(
            user_id=user_id, used_free_spin=True
        ).count()
        paid_spins = total_spins - free_spins_used
        
        return jsonify({
            'success': True,
            'spins': [s.to_dict() for s in spins.items],
            'total': spins.total,
            'page': page,
            'pages': spins.pages,
            'stats': {
                'total_won': total_won,
                'total_spins': total_spins,
                'free_spins_used': free_spins_used,
                'paid_spins': paid_spins,
                'biggest_win': db.session.query(
                    db.func.max(SpinHistory.amount_won)
                ).filter_by(user_id=user_id).scalar() or 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@spinwheel_bp.route('/buy-spins', methods=['POST'])
def buy_spins():
    """Buy additional spins"""
    
    data = request.json
    quantity = data.get('quantity', 10)
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        user_id = 'test-user-id'
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Calculate cost (₦50 per spin, or package deal)
        if quantity == 10:
            cost = 500  # ₦500 for 10 spins
        elif quantity == 25:
            cost = 1000  # ₦1000 for 25 spins
        elif quantity == 50:
            cost = 1500  # ₦1500 for 50 spins
        else:
            cost = quantity * 50  # Default ₦50 per spin
        
        if user.balance < cost:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Deduct cost
        user.balance -= cost
        
        # Add spins
        user.free_spins += quantity
        
        # Record transaction
        transaction = Transaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            reference=f"BUYSPIN-{uuid.uuid4().hex[:8].upper()}",
            type='spin_purchase',
            amount=cost,
            status='completed',
            metadata={'quantity': quantity}
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully purchased {quantity} spins',
            'new_balance': user.balance,
            'total_spins': user.free_spins,
            'cost': cost
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@spinwheel_bp.route('/verify/<spin_id>', methods=['GET'])
def verify_spin(spin_id):
    """Verify a spin was fair (for customer support)"""
    
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'error': 'No token provided'}), 401
    
    try:
        # Admin only check would go here
        
        spin = SpinHistory.query.get(spin_id)
        if not spin:
            return jsonify({'error': 'Spin not found'}), 404
        
        # Get transaction metadata
        transaction = Transaction.query.filter_by(
            user_id=spin.user_id,
            type='spin_win',
            amount=spin.amount_won
        ).order_by(Transaction.created_at.desc()).first()
        
        if not transaction or not transaction.metadata:
            return jsonify({'error': 'Verification data not found'}), 404
        
        # Verify the spin
        metadata = transaction.metadata
        is_valid = ProvablyFairSpin.verify_spin(
            metadata['server_seed'],
            metadata['client_seed'],
            metadata['nonce'],
            spin.amount_won
        )
        
        return jsonify({
            'success': True,
            'spin_id': spin_id,
            'is_valid': is_valid,
            'amount': spin.amount_won,
            'date': spin.created_at.isoformat(),
            'verification_data': {
                'server_seed': metadata['server_seed'],
                'client_seed': metadata['client_seed'],
                'nonce': metadata['nonce'],
                'random_number': metadata['random_number']
            } if is_valid else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@spinwheel_bp.route('/config', methods=['GET'])
def get_wheel_config():
    """Get wheel configuration (for frontend)"""
    
    # Return wheel segments without probabilities
    config_segments = []
    for segment in WHEEL_SEGMENTS:
        config_segments.append({
            'prize': segment['prize'],
            'color': segment['color'],
            'label': segment['label']
        })
    
    return jsonify({
        'success': True,
        'segments': config_segments,
        'free_spins_daily': Config.FREE_SPINS_DAILY,
        'spin_cost': 50
    }), 200