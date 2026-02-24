# wallet.py
from flask import Blueprint, request, jsonify
import uuid
import random
import string
import requests
from datetime import datetime, timedelta
from models import db, User, Transaction
from config import Config
from functools import wraps
import jwt

wallet_bp = Blueprint('wallet', __name__)

# Token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.get(payload['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

# Helper functions
def generate_reference(prefix='TXN'):
    """Generate unique transaction reference"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{timestamp}-{random_str}"


def get_paystack_balance():
    """Get Paystack balance"""
    try:
        headers = {
            'Authorization': f'Bearer {Config.PAYSTACK_SECRET_KEY}'
        }
        response = requests.get('https://api.paystack.co/balance', headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data['status'] and data['data']:
                # Paystack returns balance in kobo, convert to naira
                return data['data'][0]['balance'] / 100
        # Fallback to 1,000,000 if API fails
        return 1000000
    except Exception as e:
        print(f"Error getting Paystack balance: {e}")
        return 1000000


def notify_admin_low_balance(user, amount, available_balance):
    """Send notification to admin about low balance"""
    # Log the alert
    print(f"⚠️ LOW BALANCE ALERT: User {user.email} requested ₦{amount}, available ₦{available_balance}")
    
    # In production, you would:
    # 1. Send email to admin
    # 2. Create in-app notification
    # 3. Send SMS
    
    # Create notification in database (you need to create Notification model)
    try:
        # Example: Save to a notifications table
        notification = {
            'id': str(uuid.uuid4()),
            'type': 'low_balance_alert',
            'user_id': user.id,
            'user_email': user.email,
            'user_name': f"{user.first_name} {user.last_name}".strip(),
            'amount_requested': amount,
            'available_balance': available_balance,
            'created_at': datetime.utcnow().isoformat(),
            'read': False
        }
        # Save to database - implement based on your schema
        # db.session.add(notification)
        # db.session.commit()
    except Exception as e:
        print(f"Error saving notification: {e}")


# ==================== BALANCE & TRANSACTIONS ====================

@wallet_bp.route('/balance', methods=['GET'])
@token_required
def get_balance(current_user):
    """Get user balance"""
    
    return jsonify({
        'success': True,
        'balance': current_user.balance,
        'currency': 'NGN'
    }), 200


@wallet_bp.route('/transactions', methods=['GET'])
@token_required
def get_transactions(current_user):
    """Get user transaction history"""
    
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    t_type = request.args.get('type', 'all')
    
    # Build query
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    if t_type != 'all':
        query = query.filter_by(type=t_type)
    
    # Paginate
    transactions = query.order_by(
        Transaction.created_at.desc()
    ).paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'success': True,
        'transactions': [t.to_dict() for t in transactions.items],
        'total': transactions.total,
        'page': page,
        'pages': transactions.pages
    }), 200


# ==================== DEPOSITS ====================

@wallet_bp.route('/deposit/initialize', methods=['POST'])
@token_required
def initialize_deposit(current_user):
    """Initialize a deposit with Paystack"""
    
    data = request.json
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'card')
    
    if not amount:
        return jsonify({'error': 'Amount required'}), 400
    
    # Validate amount
    if amount < Config.MIN_DEPOSIT:
        return jsonify({'error': f'Minimum deposit is ₦{Config.MIN_DEPOSIT}'}), 400
    
    # Generate reference
    reference = generate_reference('DEP')
    
    # Create transaction record
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        reference=reference,
        type='deposit',
        amount=amount,
        status='pending',
        payment_method=payment_method,
        created_at=datetime.utcnow()
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    # Initialize Paystack transaction
    headers = {
        'Authorization': f'Bearer {Config.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'email': current_user.email,
        'amount': int(amount * 100),  # Paystack uses kobo
        'reference': reference,
        'callback_url': f"{Config.FRONTEND_URL}/wallet/verify"
    }
    
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['status']:
                return jsonify({
                    'success': True,
                    'message': 'Deposit initialized',
                    'reference': reference,
                    'authorization_url': data['data']['authorization_url'],
                    'access_code': data['data']['access_code']
                }), 200
            else:
                return jsonify({'error': 'Payment initialization failed'}), 400
        else:
            return jsonify({'error': 'Payment gateway error'}), 500
            
    except Exception as e:
        return jsonify({'error': 'Payment service unavailable'}), 503


@wallet_bp.route('/deposit/verify', methods=['POST'])
@token_required
def verify_deposit(current_user):
    """Verify and complete deposit"""
    
    data = request.json
    reference = data.get('reference')
    
    if not reference:
        return jsonify({'error': 'Reference required'}), 400
    
    # Verify with Paystack
    headers = {
        'Authorization': f'Bearer {Config.PAYSTACK_SECRET_KEY}'
    }
    
    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] and data['data']['status'] == 'success':
                
                # Find transaction
                transaction = Transaction.query.filter_by(reference=reference).first()
                
                if not transaction:
                    return jsonify({'error': 'Transaction not found'}), 404
                
                if transaction.status != 'pending':
                    return jsonify({'error': 'Transaction already processed'}), 400
                
                # Update transaction
                transaction.status = 'completed'
                transaction.processed_at = datetime.utcnow()
                
                # Update user balance
                current_user.balance += transaction.amount
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Deposit successful',
                    'amount': transaction.amount,
                    'new_balance': current_user.balance
                }), 200
            else:
                return jsonify({'error': 'Payment verification failed'}), 400
        else:
            return jsonify({'error': 'Verification service error'}), 500
            
    except Exception as e:
        return jsonify({'error': 'Verification service unavailable'}), 503


# ==================== WITHDRAWALS ====================

@wallet_bp.route('/withdraw/initialize', methods=['POST'])
@token_required
def initialize_withdrawal(current_user):
    """Initialize a withdrawal with balance check"""
    
    data = request.json
    amount = data.get('amount')
    bank_code = data.get('bank_code')
    account_number = data.get('account_number')
    account_name = data.get('account_name')
    
    if not all([amount, bank_code, account_number, account_name]):
        return jsonify({'error': 'All withdrawal details required'}), 400
    
    # Validate amount
    if amount < Config.MIN_WITHDRAWAL:
        return jsonify({'error': f'Minimum withdrawal is ₦{Config.MIN_WITHDRAWAL}'}), 400
    
    if amount > Config.MAX_WITHDRAWAL:
        return jsonify({'error': f'Maximum withdrawal is ₦{Config.MAX_WITHDRAWAL}'}), 400
    
    # Check user balance
    if current_user.balance < amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Check Paystack balance
    paystack_balance = get_paystack_balance()
    
    # Generate reference
    reference = generate_reference('WDR')
    
    # Determine processing time based on Paystack balance
    if amount > paystack_balance:
        processing_days = 3
        message = "Your withdrawal request will be processed in 3 working days due to high demand. We'll notify you when completed."
        
        # Notify admin
        notify_admin_low_balance(current_user, amount, paystack_balance)
    else:
        processing_days = 1
        message = "Your withdrawal will be processed within 24 hours"
    
    # Calculate estimated completion
    estimated_completion = datetime.utcnow() + timedelta(days=processing_days)
    
    # Create transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        reference=reference,
        type='withdraw',
        amount=amount,
        status='pending',
        payment_method='bank_transfer',
        transaction_metadata={
            'bank_code': bank_code,
            'account_number': account_number,
            'account_name': account_name,
            'processing_days': processing_days,
            'estimated_completion': estimated_completion.isoformat(),
            'paystack_balance_at_request': paystack_balance
        },
        created_at=datetime.utcnow()
    )
    
    db.session.add(transaction)
    
    # Hold the amount (deduct from balance)
    current_user.balance -= amount
    current_user.total_withdrawn = (current_user.total_withdrawn or 0) + amount
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': message,
        'reference': reference,
        'amount': amount,
        'status': 'pending',
        'processing_days': processing_days,
        'estimated_completion': estimated_completion.isoformat()
    }), 200


@wallet_bp.route('/withdraw/status/<reference>', methods=['GET'])
@token_required
def withdrawal_status(current_user, reference):
    """Check withdrawal status"""
    
    transaction = Transaction.query.filter_by(
        reference=reference,
        user_id=current_user.id
    ).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    # Get processing info
    processing_days = 1
    estimated_completion = None
    
    if transaction.transaction_metadata:
        processing_days = transaction.transaction_metadata.get('processing_days', 1)
        estimated_completion = transaction.transaction_metadata.get('estimated_completion')
    
    return jsonify({
        'success': True,
        'reference': reference,
        'status': transaction.status,
        'amount': transaction.amount,
        'processing_days': processing_days,
        'estimated_completion': estimated_completion,
        'created_at': transaction.created_at.isoformat() if transaction.created_at else None,
        'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
    }), 200


# ==================== BANKS ====================

@wallet_bp.route('/banks', methods=['GET'])
def get_banks():
    """Get list of banks from Paystack"""
    
    headers = {
        'Authorization': f'Bearer {Config.PAYSTACK_SECRET_KEY}'
    }
    
    try:
        response = requests.get(
            'https://api.paystack.co/bank',
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['status']:
                banks = [{
                    'code': bank['code'],
                    'name': bank['name']
                } for bank in data['data']]
                
                return jsonify({
                    'success': True,
                    'banks': banks
                }), 200
            else:
                return jsonify({'error': 'Failed to fetch banks'}), 400
        else:
            return jsonify({'error': 'Bank service error'}), 500
            
    except Exception as e:
        # Fallback to static bank list if Paystack fails
        fallback_banks = [
            {'code': '044', 'name': 'Access Bank'},
            {'code': '011', 'name': 'First Bank'},
            {'code': '058', 'name': 'Guaranty Trust Bank'},
            {'code': '032', 'name': 'Union Bank'},
            {'code': '033', 'name': 'United Bank for Africa'},
            {'code': '057', 'name': 'Zenith Bank'}
        ]
        
        return jsonify({
            'success': True,
            'banks': fallback_banks,
            'note': 'Using fallback bank list'
        }), 200


# ==================== PAYMENT WEBHOOKS ====================

@wallet_bp.route('/webhook/paystack', methods=['POST'])
def paystack_webhook():
    """Handle Paystack webhook"""
    
    data = request.json
    event = data.get('event')
    webhook_data = data.get('data', {})
    
    # Verify webhook signature (implement signature verification)
    # signature = request.headers.get('x-paystack-signature')
    
    if event == 'charge.success':
        reference = webhook_data.get('reference')
        
        # Find and update transaction
        transaction = Transaction.query.filter_by(reference=reference).first()
        if transaction and transaction.status == 'pending':
            transaction.status = 'completed'
            transaction.processed_at = datetime.utcnow()
            
            # Update user balance
            user = User.query.get(transaction.user_id)
            if user:
                user.balance += transaction.amount
            
            db.session.commit()
    
    return jsonify({'status': 'success'}), 200