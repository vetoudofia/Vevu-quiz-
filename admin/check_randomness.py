# admin/check_randomness.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import Question
from question_service import question_service
from collections import Counter

def check_randomness():
    """Check if questions are truly random"""
    
    with app.app_context():
        total = Question.query.count()
        print("=" * 60)
        print("🎲 QUESTION RANDOMNESS TEST")
        print("=" * 60)
        print(f"\n📊 Total questions in database: {total}")
        
        if total == 0:
            print("\n❌ No questions found! Run seed_questions.py first.")
            return
        
        # Test 1: Same game - no repeats
        print("\n🔍 TEST 1: Same game - No repeats")
        user_id = 'test-user-1'
        questions = question_service.get_questions_for_game(
            user_id=user_id,
            level='quick',
            count=10,
            avoid_recent=False
        )
        
        question_ids = [q['id'] for q in questions]
        unique_ids = len(set(question_ids))
        
        print(f"   • Questions selected: {len(questions)}")
        print(f"   • Unique questions: {unique_ids}")
        print(f"   • Repeats: {'✅ NONE' if unique_ids == len(questions) else '❌ FOUND'}")
        
        # Test 2: Option shuffling
        print("\n🔍 TEST 2: Option shuffling")
        if questions:
            first_q = questions[0]
            original_options = first_q['options']
            print(f"   • Original order: {original_options}")
            
            # Shuffle same question multiple times
            from models import Question as QuestionModel
            db_question = QuestionModel.query.get(first_q['id'])
            
            shuffles = []
            for i in range(10):
                shuffled = question_service._shuffle_question(db_question)
                shuffles.append(shuffled['options'][0])
            
            # Count first positions
            first_positions = Counter(shuffles)
            print(f"   • First option distribution (10 shuffles):")
            for opt, count in first_positions.most_common():
                short_opt = opt[:20] + "..." if len(opt) > 20 else opt
                print(f"      - {short_opt}: {count} times")
        
        # Test 3: Cross-game repeats
        print("\n🔍 TEST 3: Cross-game repeats (50 games)")
        user_id = 'test-user-2'
        all_seen = []
        
        for i in range(50):
            qs = question_service.get_questions_for_game(
                user_id=user_id,
                level='quick',
                count=10,
                avoid_recent=True
            )
            for q in qs:
                all_seen.append(q['id'])
        
        total_seen = len(all_seen)
        unique_seen = len(set(all_seen))
        repeat_rate = ((total_seen - unique_seen) / total_seen) * 100
        
        print(f"   • Total questions seen: {total_seen}")
        print(f"   • Unique questions seen: {unique_seen}")
        print(f"   • Repeat rate: {repeat_rate:.1f}%")
        
        print("\n" + "=" * 60)
        if repeat_rate < 20:
            print("✅ RANDOMNESS TEST PASSED!")
        else:
            print("⚠️ High repeat rate detected")
        print("=" * 60)

if __name__ == '__main__':
    check_randomness()