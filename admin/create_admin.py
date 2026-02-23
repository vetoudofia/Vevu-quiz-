# admin/create_admin.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app
from models import db, User
import bcrypt
import uuid
import getpass

def create_admin():
    """Create admin user"""
    
    with app.app_context():
        print("=" * 60)
        print("👑 CREATE ADMIN USER")
        print("=" * 60)
        
        email = input("\n📧 Admin email: ")
        password = getpass.getpass("🔑 Admin password: ")
        confirm = getpass.getpass("🔑 Confirm password: ")
        
        if password != confirm:
            print("\n❌ Passwords do not match!")
            return
        
        if len(password) < 6:
            print("\n❌ Password must be at least 6 characters!")
            return
        
        # Check if admin exists
        existing = User.query.filter_by(email=email).first()
        if existing:
            print("\n❌ User with this email already exists!")
            return
        
        # Create admin
        admin = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            first_name='Admin',
            last_name='User',
            balance=0,
            is_verified=True,
            is_active=True,
            role='admin'  # You'd need to add this field to User model
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"\n✅ Admin user {email} created successfully!")
        print("=" * 60)

if __name__ == '__main__':
    create_admin()