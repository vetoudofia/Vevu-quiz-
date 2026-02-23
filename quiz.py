# quiz.py
from flask import Blueprint, request, jsonify
import uuid
import random
from datetime import datetime
from models import db, User, GameSession, Transaction, Question, ActivityLog
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
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        player_count=1
    )
    db.session.add(game)
    
    # Update user online status
    current_user.is_online = True
    current_user.current_game_id = game_id
    current_user.current_game_type = 'quick'
    current_user.current_session_start = datetime.utcnow()
    current_user.last_activity = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='game_start',
        details={'game_type': 'quick', 'game_id': game_id, 'stake': stake}
    )
    db.session.add(activity)
    
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
        
        # Log win activity
        activity = ActivityLog(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            action='win',
            details={'game_type': 'quick', 'game_id': game_id, 'amount': prize}
        )
        db.session.add(activity)
    
    # Update game
    game.status = 'completed'
    game.completed_at = datetime.utcnow()
    if won:
        game.winner_id = current_user.id
    
    # Clear user's current game
    current_user.current_game_id = None
    current_user.current_game_type = None
    current_user.current_session_start = None
    current_user.last_activity = datetime.utcnow()
    
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
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        player_count=1
    )
    db.session.add(game)
    
    # Update user online status
    current_user.is_online = True
    current_user.current_game_id = game_id
    current_user.current_game_type = 'level'
    current_user.current_session_start = datetime.utcnow()
    current_user.last_activity = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='game_start',
        details={'game_type': 'level', 'level': level, 'game_id': game_id, 'stake': stake}
    )
    db.session.add(activity)
    
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


# ==================== BATTLE QUIZ ====================

@quiz_bp.route('/battle/available', methods=['GET'])
@token_required
def get_available_battles(current_user):
    """Get available battle games"""
    
    games = GameSession.query.filter_by(
        game_type='battle',
        status='waiting'
    ).limit(20).all()
    
    return jsonify({
        'games': [g.to_dict() for g in games]
    }), 200


@quiz_bp.route('/battle/create', methods=['POST'])
@token_required
def create_battle(current_user):
    """Create a battle game"""
    
    data = request.json
    stake = data.get('stake')
    max_players = data.get('max_players', 3)
    
    if not stake:
        return jsonify({'error': 'Stake amount required'}), 400
    
    if current_user.balance < stake:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Create battle game
    game_id = str(uuid.uuid4())
    game_code = generate_game_code()
    
    game = GameSession(
        id=game_id,
        game_code=game_code,
        game_type='battle',
        status='waiting',
        stake=stake,
        platform_fee=calculate_platform_fee(stake * max_players),
        total_pot=stake * max_players,
        max_players=max_players,
        current_players=1,
        total_questions=50,
        time_per_question=10,
        created_by=current_user.id,
        player_count=1,
        created_at=datetime.utcnow()
    )
    
    db.session.add(game)
    
    # Update user online status
    current_user.is_online = True
    current_user.current_game_id = game_id
    current_user.current_game_type = 'battle'
    current_user.current_session_start = datetime.utcnow()
    current_user.last_activity = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='game_created',
        details={'game_type': 'battle', 'game_id': game_id, 'stake': stake, 'max_players': max_players}
    )
    db.session.add(activity)
    
    # Deduct stake
    current_user.balance -= stake
    
    # Record transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        game_id=game_id,
        reference=f"BATTLE-{game_code}",
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
        'stake': stake,
        'max_players': max_players
    }), 201


@quiz_bp.route('/battle/join', methods=['POST'])
@token_required
def join_battle(current_user):
    """Join a battle game"""
    
    data = request.json
    game_id = data.get('game_id')
    
    if not game_id:
        return jsonify({'error': 'Game ID required'}), 400
    
    game = GameSession.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    if game.status != 'waiting':
        return jsonify({'error': 'Game already started'}), 400
    
    if game.current_players >= game.max_players:
        return jsonify({'error': 'Game is full'}), 400
    
    if current_user.balance < game.stake:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Join game
    game.current_players += 1
    game.player_count += 1
    
    # Update user online status
    current_user.is_online = True
    current_user.current_game_id = game_id
    current_user.current_game_type = 'battle'
    current_user.current_session_start = datetime.utcnow()
    current_user.last_activity = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='game_joined',
        details={'game_type': 'battle', 'game_id': game_id, 'stake': game.stake}
    )
    db.session.add(activity)
    
    # Deduct stake
    current_user.balance -= game.stake
    
    # Record transaction
    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        game_id=game_id,
        reference=f"JOIN-{game.game_code}-{current_user.id[:8]}",
        type='stake',
        amount=game.stake,
        status='completed'
    )
    db.session.add(transaction)
    db.session.commit()
    
    # Check if game is ready to start
    if game.current_players >= game.max_players:
        game.status = 'ready'
        db.session.commit()
    
    return jsonify({
        'success': True,
        'game_id': game.id,
        'game_code': game.game_code,
        'current_players': game.current_players,
        'max_players': game.max_players
    }), 200


@quiz_bp.route('/battle/quit', methods=['POST'])
@token_required
def quit_battle(current_user):
    """Quit a battle game (stake lost)"""
    
    data = request.json
    game_id = data.get('game_id')
    
    if not game_id:
        return jsonify({'error': 'Game ID required'}), 400
    
    game = GameSession.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    # Update game
    game.current_players -= 1
    
    # Clear user's current game
    current_user.current_game_id = None
    current_user.current_game_type = None
    current_user.current_session_start = None
    current_user.last_activity = datetime.utcnow()
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='game_quit',
        details={'game_type': 'battle', 'game_id': game_id}
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'You have quit the game. Your stake has been lost.'
    }), 200


# ==================== 1V1 QUIZ ====================

@quiz_bp.route('/1v1/online', methods=['GET'])
@token_required
def get_online_players(current_user):
    """Get online players for 1v1"""
    
    # Get users who are online and not in a game
    online_players = User.query.filter(
        User.is_online == True,
        User.id != current_user.id,
        User.current_game_id == None
    ).limit(20).all()
    
    players_data = [{
        'id': p.id,
        'username': f"{p.first_name} {p.last_name}".strip() or p.email,
        'wins': p.wins,
        'rank': 0  # Calculate rank based on wins
    } for p in online_players]
    
    return jsonify({'users': players_data}), 200


@quiz_bp.route('/1v1/invite', methods=['POST'])
@token_required
def send_1v1_invite(current_user):
    """Send 1v1 game invite"""
    
    data = request.json
    opponent_id = data.get('opponent_id')
    stake = data.get('stake')
    
    if not opponent_id or not stake:
        return jsonify({'error': 'Opponent and stake required'}), 400
    
    # Validate stake
    if stake < Config.MIN_STAKE:
        return jsonify({'error': f'Minimum stake is ₦{Config.MIN_STAKE}'}), 400
    
    if stake > Config.MAX_STAKE:
        return jsonify({'error': f'Maximum stake is ₦{Config.MAX_STAKE}'}), 400
    
    # Check balance
    if current_user.balance < stake:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Create invite (in production, store in database)
    invite_id = str(uuid.uuid4())
    
    # Log activity
    activity = ActivityLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        action='invite_sent',
        details={'opponent_id': opponent_id, 'stake': stake}
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'invite_id': invite_id,
        'message': 'Invite sent successfully'
    }), 200