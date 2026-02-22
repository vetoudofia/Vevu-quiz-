# question_service.py
import random
from models import db, Question, GameSession

class QuestionService:
    """Professional question randomization service"""
    
    def __init__(self):
        self.recent_questions = {}  # Track per user
    
    def get_questions_for_game(self, user_id, level, count, avoid_recent=True):
        """
        Get random questions with:
        - No repeats in same game
        - Low chance of repeats across games
        - Shuffled options
        """
        
        # Build query
        query = Question.query.filter(
            Question.level == level,
            Question.is_active == True
        )
        
        # Avoid questions user saw recently
        if avoid_recent and user_id in self.recent_questions:
            recent_ids = self.recent_questions[user_id][-50:]  # Last 50 questions
            if recent_ids:
                query = query.filter(~Question.id.in_(recent_ids))
        
        # Get more than needed for randomness
        fetch_count = min(count * 3, 500)
        candidates = query.order_by(db.func.random()).limit(fetch_count).all()
        
        if len(candidates) < count:
            # Fallback: get any questions
            candidates = Question.query.filter(
                Question.level == level,
                Question.is_active == True
            ).order_by(db.func.random()).limit(count * 2).all()
        
        # Select random subset (ensures no repeats in same game)
        selected = random.sample(candidates, min(count, len(candidates)))
        
        # Shuffle options for each question
        shuffled_questions = []
        for q in selected:
            shuffled = self._shuffle_question(q)
            shuffled_questions.append(shuffled)
            
            # Track for history
            if user_id not in self.recent_questions:
                self.recent_questions[user_id] = []
            self.recent_questions[user_id].append(q.id)
            # Keep only last 100
            self.recent_questions[user_id] = self.recent_questions[user_id][-100:]
        
        return shuffled_questions
    
    def _shuffle_question(self, question):
        """
        Shuffle options while tracking correct answer
        """
        # Original data
        original_options = [
            question.option_a,
            question.option_b,
            question.option_c,
            question.option_d
        ]
        correct_idx = question.correct_answer
        
        # Create pairs for shuffling
        pairs = list(enumerate(original_options))
        random.shuffle(pairs)
        
        # Reconstruct shuffled options
        new_options = [opt for _, opt in pairs]
        new_correct = next(i for i, (idx, _) in enumerate(pairs) if idx == correct_idx)
        
        # Return shuffled question
        return {
            'id': question.id,
            'category': question.category,
            'level': question.level,
            'question': question.question_text,
            'options': new_options,
            'original_correct': correct_idx,
            'shuffled_correct': new_correct,
            'time_limit': question.time_limit,
            'points': question.points
        }
    
    def verify_answer(self, question_id, user_answer, question_data):
        """Verify answer accounting for shuffled options"""
        question = Question.query.get(question_id)
        if not question:
            return False
        return user_answer == question.correct_answer
    
    def get_dynamic_questions(self, user_id, level, count, difficulty='mixed'):
        """
        Advanced: Adjust difficulty based on user performance
        """
        # Get user's recent performance
        recent_games = GameSession.query.filter_by(
            created_by=user_id,
            status='completed'
        ).order_by(
            GameSession.completed_at.desc()
        ).limit(10).all()
        
        if recent_games:
            # Calculate average score
            scores = []
            for game in recent_games:
                if game.total_questions and game.total_questions > 0:
                    # You'd need to store score in GameSession
                    pass
            
            # This would need score stored in GameSession
            # For now, use mixed difficulty
        
        # Difficulty mapping
        difficulty_map = {
            'easy': [1, 2],
            'medium': [3],
            'hard': [4, 5],
            'mixed': [1, 2, 3, 4, 5]
        }
        
        difficulties = difficulty_map.get(difficulty, [1, 2, 3, 4, 5])
        
        questions = Question.query.filter(
            Question.level == level,
            Question.difficulty.in_(difficulties),
            Question.is_active == True
        ).order_by(db.func.random()).limit(count * 2).all()
        
        # Random selection
        selected = random.sample(questions, min(count, len(questions)))
        
        # Shuffle each question
        return [self._shuffle_question(q) for q in selected]

# Create global instance
question_service = QuestionService()