# admin/backup_questions.py
import sys
import os
import json
import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import Question

def backup_questions():
    """Backup all questions to JSON file"""
    
    with app.app_context():
        questions = Question.query.all()
        
        if not questions:
            print("❌ No questions to backup!")
            return
        
        # Convert to dict
        data = []
        for q in questions:
            data.append({
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
                'success_rate': q.success_rate
            })
        
        # Create filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'backup/questions_backup_{timestamp}.json'
        
        # Create backup directory if not exists
        os.makedirs('backup', exist_ok=True)
        
        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Backed up {len(data)} questions to {filename}")

def restore_from_backup(filename):
    """Restore questions from backup file"""
    
    from models import db
    
    with app.app_context():
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Clear existing
        Question.query.delete()
        
        # Restore
        for item in data:
            q = Question(
                id=item['id'],
                category=item['category'],
                level=item['level'],
                difficulty=item['difficulty'],
                question_text=item['question'],
                option_a=item['options'][0],
                option_b=item['options'][1],
                option_c=item['options'][2],
                option_d=item['options'][3],
                correct_answer=item['correct'],
                explanation=item['explanation'],
                points=item['points'],
                time_limit=item['time_limit'],
                times_used=item['times_used'],
                success_rate=item['success_rate']
            )
            db.session.add(q)
        
        db.session.commit()
        print(f"✅ Restored {len(data)} questions from {filename}")

if __name__ == '__main__':
    print("📦 QUESTION BACKUP TOOL")
    print("1. Backup questions")
    print("2. Restore from backup")
    
    choice = input("\nChoose option (1 or 2): ")
    
    if choice == '1':
        backup_questions()
    elif choice == '2':
        filename = input("Enter backup filename: ")
        restore_from_backup(filename)
    else:
        print("❌ Invalid choice")