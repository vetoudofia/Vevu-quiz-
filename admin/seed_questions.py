# admin/seed_questions.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import db, Question
import uuid
import random

def seed_questions():
    """Seed database with sample questions"""
    
    with app.app_context():
        # Check if questions already exist
        existing = Question.query.count()
        if existing > 0:
            print(f"\n⚠️  Database already has {existing} questions.")
            choice = input("Add more? (yes/no): ")
            if choice.lower() != 'yes':
                print("❌ Seeding cancelled")
                return
        
        print("=" * 60)
        print("🌱 SEEDING QUESTIONS DATABASE")
        print("=" * 60)
        
        # Categories and levels
        categories = [
            'Geography', 'History', 'Science', 'Sports', 'Entertainment',
            'Art', 'Technology', 'Literature', 'Music', 'General Knowledge',
            'Politics', 'Economics', 'Biology', 'Physics', 'Chemistry',
            'Mathematics', 'Computer Science', 'Mythology', 'Philosophy', 'Religion'
        ]
        
        levels = ['quick', 'good', 'smart', 'best']
        
        # Generate questions
        questions = []
        total_to_create = 1000  # Start with 1000, can increase later
        
        print(f"\n📝 Generating {total_to_create} questions...")
        
        for i in range(total_to_create):
            category = random.choice(categories)
            level = random.choice(levels)
            difficulty = random.randint(1, 5)
            
            # Create question
            q = {
                'id': str(uuid.uuid4()),
                'category': category,
                'level': level,
                'difficulty': difficulty,
                'question_text': f"Sample {category} question #{i+1}?",
                'option_a': f"Option A for question {i+1}",
                'option_b': f"Option B for question {i+1}",
                'option_c': f"Option C for question {i+1}",
                'option_d': f"Option D for question {i+1}",
                'correct_answer': random.randint(0, 3),
                'explanation': f"This is the explanation for question {i+1}",
                'points': 10,
                'time_limit': 10,
                'is_active': True,
                'times_used': 0,
                'correct_count': 0,
                'wrong_count': 0,
                'success_rate': 0.0
            }
            questions.append(q)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"   • Generated {i + 1} questions...")
        
        # Insert in batches
        print("\n💾 Inserting into database...")
        batch_size = 100
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i+batch_size]
            db.session.bulk_insert_mappings(Question, batch)
            db.session.commit()
            print(f"   • Inserted {i + len(batch)} questions...")
        
        # Verify
        final_count = Question.query.count()
        print(f"\n✅ Successfully seeded {final_count} questions!")
        
        # Show distribution
        by_level = db.session.query(
            Question.level, db.func.count()
        ).group_by(Question.level).all()
        
        print("\n📊 Distribution:")
        for level, count in by_level:
            print(f"   • {level}: {count} questions")
        
        print("\n" + "=" * 60)

def seed_from_csv(csv_file):
    """Seed from CSV file (for bulk import)"""
    
    import csv
    
    with app.app_context():
        print(f"\n📂 Importing from {csv_file}...")
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            questions = []
            
            for row in reader:
                q = {
                    'id': str(uuid.uuid4()),
                    'category': row['category'],
                    'level': row['level'],
                    'difficulty': int(row.get('difficulty', 1)),
                    'question_text': row['question'],
                    'option_a': row['option_a'],
                    'option_b': row['option_b'],
                    'option_c': row['option_c'],
                    'option_d': row['option_d'],
                    'correct_answer': int(row['correct']),
                    'explanation': row.get('explanation', ''),
                    'points': int(row.get('points', 10)),
                    'time_limit': int(row.get('time_limit', 10))
                }
                questions.append(q)
            
            # Insert in batches
            batch_size = 100
            for i in range(0, len(questions), batch_size):
                batch = questions[i:i+batch_size]
                db.session.bulk_insert_mappings(Question, batch)
                db.session.commit()
                print(f"   • Imported {i + len(batch)} questions...")
        
        print(f"\n✅ Imported {len(questions)} questions from CSV!")

if __name__ == '__main__':
    print("\n🌱 QUESTION SEEDING TOOL")
    print("1. Generate sample questions")
    print("2. Import from CSV")
    
    choice = input("\nChoose option (1 or 2): ")
    
    if choice == '1':
        seed_questions()
    elif choice == '2':
        csv_file = input("Enter CSV filename: ")
        seed_from_csv(csv_file)
    else:
        print("❌ Invalid choice")