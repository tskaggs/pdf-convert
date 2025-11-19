#!/usr/bin/env python3
"""
Seed script to create initial admin user and API token
"""
import sys
from database import init_db, create_user, create_api_token, get_user_by_username

def seed_admin():
    """Create an admin user if it doesn't exist"""
    # Initialize database
    init_db()
    
    # Default admin credentials
    admin_username = "admin"
    admin_email = "admin@example.com"
    admin_password = "admin123"  # Change this in production!
    
    # Check if admin already exists
    existing_user = get_user_by_username(admin_username)
    if existing_user:
        print(f"Admin user '{admin_username}' already exists!")
        print(f"User ID: {existing_user['id']}")
        return existing_user['id']
    
    # Create admin user
    try:
        user_id = create_user(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            is_admin=True
        )
        print(f"✓ Admin user created successfully!")
        print(f"  Username: {admin_username}")
        print(f"  Email: {admin_email}")
        print(f"  Password: {admin_password}")
        print(f"  User ID: {user_id}")
        
        # Create an initial API token
        token = create_api_token(user_id, "Initial Admin Token")
        print(f"\n✓ API Token created:")
        print(f"  Token: {token}")
        print(f"\n⚠️  IMPORTANT: Save this token securely! It won't be shown again.")
        print(f"\nYou can now use this token to authenticate API requests:")
        print(f'  curl -X POST "http://localhost:8000/convert" \\')
        print(f'       -H "Authorization: Bearer {token}" \\')
        print(f'       -F "file=@document.pdf" \\')
        print(f'       -F "output_format=png"')
        
        return user_id
    except ValueError as e:
        print(f"Error creating admin user: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Seeding database with admin user...")
    seed_admin()
    print("\n✓ Seeding complete!")

