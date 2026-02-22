# quiz.py
from flask import Blueprint, request, jsonify
import uuid
import random
from datetime import datetime
from models import db, User, GameSession, Transaction, Question
from config import Config
from question_service import question_service
from functools import wraps
import jwt

quiz_bp = Blueprint('quiz', __name__)

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
def generate_game_code():
    import random
    import string
    return 'VEV' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def calculate_platform_fee(amount):
    return amount * Config.PLATFORM_FEE


# ==================== QUICK PLAY ====================

@quiz_bp.route('/quick/start', methods=['POST'])
@token_required
def quick_play_start(current_user):
    """Start quick play with randomized questions"""
    
    # Check balance (Quick play stake = ₦100)
    stake = 100
    if current_user.balance < stake:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Get randomized questions from database
    questions = Question.query.filter_by(
        level='quick',
        is_active=True
    ).order_by(db.func.random()).limit(10).all()
    
    if len(questions) < 10:
        return jsonify({'error': 'Not enough questions available'}), 500
    
    # Shuffle options for each question
    shuffled_questions = []
    question_map = {}
    
    for q in questions:
        # Shuffle options
        options = [q.option_a, q.option_b, q.option_c, q.option_d]
        correct_idx = q.correct_answer
        
        # Create pairs and shuffle
        pairs = list(enumerate(options))
        random.shuffle(pairs)
        
        # Reconstruct
        shuffled_options = [opt for _, opt in pairs]
        new_correct = next(i for i, (idx, _) in enumerate(pairs) if idx == correct_idx)
        
        # Store mapping
        question_map[q.id] = {
            'correct': correct_idx,
            'shuffled': new_correct
        }
        
        # Add to response
        shuffled_questions.append({
            'id': q.id,
            'category': q.category,
            'question': q.question_text,
            'options': shuffled_options,
            'time_limit': q.time_limit,
            'points': q.points
        })
    
    # Create game session
    game_id = str(uuid.uuid4())
    game_code = generate_game_code()
    
    game = GameSession(
        id=game_id,
        game_code=game_code,
        game_type='quick',
        status='active',
        stake=stake,
        platform_fee=calculate_platform_fee(stake * 3),
        total_pot=stake * 3,
        total_questions=10,
        time_per_question=10,
        created_by=current_user.id,
        question_data=question_map,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow()
    )
    db.session.add(game)
    
    # Deduct stake
    current_user.balance -= stake
    
    # Record transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        game_id=game_id,
        reference=f"STAKE-{game_code}",
        type='stake',
        amount=stake,
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'game_code': game_code,
        'questions': shuffled_questions,
        'time_limit': 60,
        'stake': stake,
        'multiplier': 3
    }), 200


@quiz_bp.route('/quick/submit', methods=['POST'])
@token_required
def quick_play_submit(current_user):
    """Submit quick play answers"""
    
    data = request.json
    game_id = data.get('game_id')
    user_answers = data.get('answers')
    
    if not game_id or not user_answers:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get game
    game = GameSession.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if game.created_by != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    question_map = game.question_data or {}
    
    # Score answers
    score = 0
    results = []
    
    for ans in user_answers:
        q_id = ans['question_id']
        user_choice = ans['answer_index']
        
        # Get original correct answer
        question = Question.query.get(q_id)
        if not question:
            continue
            
        is_correct = (user_choice == question.correct_answer)
        if is_correct:
            score += 1
            question.update_stats(True)
        else:
            question.update_stats(False)
        
        results.append({
            'question_id': q_id,
            'question': question.question_text,
            'user_answer': user_choice,
            'correct': question.correct_answer,
            'is_correct': is_correct
        })
    
    # Determine win (all correct for quick play)
    won = (score == 10)
    prize = 0
    
    if won:
        gross_win = game.stake * 3
        fee = calculate_platform_fee(gross_win)
        prize = gross_win - fee
        
        # Update user balance
        current_user.balance += prize
        current_user.total_earned += prize
        current_user.wins += 1
        
        # Record win transaction
        win_transaction = Transaction(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            game_id=game_id,
            reference=f"WIN-{game.game_code}",
            type='win',
            amount=prize,
            fee=fee,
            status='completed'
        )
        db.session.add(win_transaction)
    
    # Update game
    game.status = 'completed'
    game.completed_at = datetime.utcnow()
    if won:
        game.winner_id = current_user.id
    
    # Update user games played
    current_user.games_played += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'score': score,
        'total': 10,
        'won': won,
        'prize': prize,
        'game_code': game.game_code,
        'results': results
    }), 200


# ==================== LEVEL QUIZ ====================

@quiz_bp.route('/level/levels', methods=['GET'])
def get_levels():
    """Get available levels"""
    
    levels = {
        'good': {
            'name': 'Good',
            'questions': 45,
            'required': 40,
            'multiplier': 2.5,
            'time_per_question': 10
        },
        'smart': {
            'name': 'Smart',
            'questions': 65,
            'required': 58,
            'multiplier': 4.5,
            'time_per_question': 10
        },
        'best': {
            'name': 'Best',
            'questions': 85,
            'required': 73,
            'multiplier': 6.5,
            'time_per_question': 10
        }
    }
    
    return jsonify({'levels': levels}), 200


@quiz_bp.route('/level/start', methods=['POST'])
@token_required
def level_quiz_start(current_user):
    """Start level quiz with dynamic questions"""
    
    data = request.json
    level = data.get('level')
    stake = data.get('stake')
    
    if not level or not stake:
        return jsonify({'error': 'Level and stake required'}), 400
    
    # Validate stake
    if stake < Config.MIN_STAKE:
        return jsonify({'error': f'Minimum stake is ₦{Config.MIN_STAKE}'}), 400
    
    if stake > Config.MAX_STAKE:
        return jsonify({'error': f'Maximum stake is ₦{Config.MAX_STAKE}'}), 400
    
    if current_user.balance < stake:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Level config
    level_config = {
        'good': {'questions': 45, 'required': 40, 'multiplier': 2.5},
        'smart': {'questions': 65, 'required': 58, 'multiplier': 4.5},
        'best': {'questions': 85, 'required': 73, 'multiplier': 6.5}
    }
    
    config = level_config.get(level)
    if not config:
        return jsonify({'error': 'Invalid level'}), 400
    
    # Get questions from database
    questions = Question.query.filter_by(
        level=level,
        is_active=True
    ).order_by(db.func.random()).limit(config['questions']).all()
    
    if len(questions) < config['questions']:
        return jsonify({'error': 'Not enough questions available'}), 500
    
    # Shuffle options for each question
    shuffled_questions = []
    question_map = {}
    
    for q in questions:
        # Shuffle options
        options = [q.option_a, q.option_b, q.option_c, q.option_d]
        correct_idx = q.correct_answer
        
        pairs = list(enumerate(options))
        random.shuffle(pairs)
        
        shuffled_options = [opt for _, opt in pairs]
        new_correct = next(i for i, (idx, _) in enumerate(pairs) if idx == correct_idx)
        
        question_map[q.id] = {
            'correct': correct_idx,
            'shuffled': new_correct
        }
        
        shuffled_questions.append({
            'id': q.id,
            'category': q.category,
            'question': q.question_text,
            'options': shuffled_options,
            'time_limit': q.time_limit,
            'points': q.points
        })
    
    # Create game
    game_id = str(uuid.uuid4())
    game_code = generate_game_code()
    
    game = GameSession(
        id=game_id,
        game_code=game_code,
        game_type='level',
        level=level,
        status='active',
        stake=stake,
        platform_fee=calculate_platform_fee(stake * config['multiplier']),
        total_pot=stake * config['multiplier'],
        total_questions=config['questions'],
        required_correct=config['required'],
        time_per_question=10,
        created_by=current_user.id,
        question_data=question_map,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow()
    )
    db.session.add(game)
    
    # Deduct stake
    current_user.balance -= stake
    
    # Record transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        game_id=game_id,
        reference=f"STAKE-{game_code}",
        type='stake',
        amount=stake,
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'game_code': game_code,
        'questions': shuffled_questions,
        'required_correct': config['required'],
        'total_questions': config['questions'],
        'time_limit': config['questions'] * 10,
        'stake': stake,
        'multiplier': config['multiplier']
    }), 200