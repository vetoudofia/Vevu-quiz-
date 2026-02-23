# admin/question_stats.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import Question, db

def show_stats():
    """Show detailed question statistics"""
    
    with app.app_context():
        total = Question.query.count()
        
        if total == 0:
            print("\n❌ No questions found! Run seed_questions.py first.")
            return
        
        # Basic counts
        by_level = db.session.query(
            Question.level, db.func.count()
        ).group_by(Question.level).all()
        
        by_category = db.session.query(
            Question.category, db.func.count()
        ).group_by(Question.category).all()
        
        by_difficulty = db.session.query(
            Question.difficulty, db.func.count()
        ).group_by(Question.difficulty).all()
        
        # Most used questions
        most_used = Question.query.order_by(
            Question.times_used.desc()
        ).limit(5).all()
        
        # Success rates
        high_success = Question.query.filter(
            Question.times_used > 10,
            Question.success_rate > 80
        ).count()
        
        low_success = Question.query.filter(
            Question.times_used > 10,
            Question.success_rate < 30
        ).count()
        
        # Print report
        print("=" * 60)
        print("📊 QUESTION DATABASE STATISTICS")
        print("=" * 60)
        print(f"\n📁 Total Questions: {total}")
        
        print("\n📊 By Level:")
        for level, count in by_level:
            percentage = (count / total) * 100
            print(f"   • {level.upper()}: {count} ({percentage:.1f}%)")
        
        print("\n📚 By Category (Top 5):")
        for cat, count in sorted(by_category, key=lambda x: x[1], reverse=True)[:5]:
            print(f"   • {cat}: {count}")
        
        print("\n⚡ By Difficulty:")
        for diff, count in sorted(by_difficulty):
            print(f"   • Level {diff}: {count}")
        
        print("\n📈 Usage Stats:")
        print(f"   • Most used question: {most_used[0].id if most_used else 'N/A'}")
        print(f"   • Questions with >80% success: {high_success}")
        print(f"   • Questions with <30% success: {low_success}")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    show_stats()