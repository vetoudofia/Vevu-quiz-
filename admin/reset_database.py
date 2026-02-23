# admin/reset_database.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import db, Question, User, GameSession, Transaction, SpinHistory

def reset_database(tables=None):
    """Reset database tables"""
    
    with app.app_context():
        print("=" * 60)
        print("⚠️  DATABASE RESET TOOL")
        print("=" * 60)
        print("\nTables that will be affected:")
        print("   1. questions")
        print("   2. users")
        print("   3. game_sessions")
        print("   4. transactions")
        print("   5. spin_history")
        print("\n⚠️  THIS ACTION CANNOT BE UNDONE!")
        
        confirm = input("\nType 'RESET' to confirm: ")
        
        if confirm != 'RESET':
            print("\n❌ Reset cancelled.")
            return
        
        # Delete in correct order (respect foreign keys)
        print("\n🔄 Resetting database...")
        
        # Delete child tables first
        count = SpinHistory.query.delete()
        print(f"   • Deleted {count} spin history records")
        
        count = Transaction.query.delete()
        print(f"   • Deleted {count} transactions")
        
        count = GameSession.query.delete()
        print(f"   • Deleted {count} game sessions")
        
        # Delete main tables
        count = Question.query.delete()
        print(f"   • Deleted {count} questions")
        
        count = User.query.filter_by(email != 'admin@vevquizer.com').delete()
        print(f"   • Deleted {count} users (admin kept)")
        
        # Commit changes
        db.session.commit()
        
        print("\n✅ Database reset complete!")
        print("\nNext steps:")
        print("   1. Run seed_questions.py to add questions")
        print("   2. Run create_admin.py if needed")
        print("\n" + "=" * 60)

if __name__ == '__main__':
    print("\n⚠️  WARNING: This will delete ALL data!")
    choice = input("Continue? (yes/no): ")
    if choice.lower() == 'yes':
        reset_database()
    else:
        print("❌ Reset cancelled")