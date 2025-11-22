"""
Database cleanup utility script.

This script helps clean up the email client database by:
- Listing all accounts
- Deleting specific accounts by email
- Resetting the entire database (use with caution)
"""
import sys
import sqlite3
from pathlib import Path
from email_client.config import load_env, SQLITE_DB_PATH
from email_client.storage.db import get_connection, init_db
import config  # Old config module


def list_accounts():
    """List all accounts in the database (checks both old and new database systems)."""
    print("\nChecking new database system...")
    load_env()
    
    # Check new database system
    new_db_path = SQLITE_DB_PATH
    accounts = []
    
    if new_db_path.exists():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email_address, display_name, provider FROM accounts")
            rows = cursor.fetchall()
            for row in rows:
                account_info = {
                    'id': row['id'],
                    'email': row['email_address'],
                    'display_name': row['display_name'] or '(no name)',
                    'provider': row['provider'],
                    'db_type': 'new'
                }
                accounts.append(account_info)
        finally:
            conn.close()
    
    # Check old database system
    print("Checking old database system...")
    old_db_path = config.DB_PATH
    if old_db_path.exists():
        try:
            conn = sqlite3.connect(old_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT account_id, email_address, display_name, provider FROM accounts")
            rows = cursor.fetchall()
            for row in rows:
                account_info = {
                    'id': row['account_id'],
                    'email': row['email_address'],
                    'display_name': row['display_name'] or '(no name)',
                    'provider': row['provider'],
                    'db_type': 'old'
                }
                accounts.append(account_info)
            conn.close()
        except Exception as e:
            print(f"  Could not read old database: {e}")
    
    if not accounts:
        print("No accounts found in either database.")
        return []
    
    print("\nAccounts in database:")
    print("-" * 70)
    for account_info in accounts:
        db_type = account_info.get('db_type', 'unknown')
        print(f"ID: {account_info['id']} | Email: {account_info['email']} | "
              f"Name: {account_info['display_name']} | Provider: {account_info['provider']} | "
              f"DB: {db_type}")
    print("-" * 70)
    return accounts


def delete_account_by_email(email: str):
    """Delete an account by email address (checks both old and new database systems)."""
    load_env()
    deleted = False
    
    # Try new database system
    new_db_path = SQLITE_DB_PATH
    if new_db_path.exists():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, display_name FROM accounts WHERE email_address = ?", (email,))
            row = cursor.fetchone()
            
            if row:
                account_id = row['id']
                display_name = row['display_name'] or email
                cursor.execute("DELETE FROM accounts WHERE email_address = ?", (email,))
                conn.commit()
                print(f"\n✓ Successfully deleted from new database: {display_name} ({email})")
                print(f"  Account ID: {account_id}")
                deleted = True
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error deleting from new database: {str(e)}")
        finally:
            conn.close()
    
    # Try old database system
    old_db_path = config.DB_PATH
    if old_db_path.exists():
        try:
            conn = sqlite3.connect(old_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT account_id, display_name FROM accounts WHERE email_address = ?", (email,))
            row = cursor.fetchone()
            
            if row:
                account_id = row['account_id']
                display_name = row['display_name'] or email
                cursor.execute("DELETE FROM accounts WHERE email_address = ?", (email,))
                conn.commit()
                print(f"\n✓ Successfully deleted from old database: {display_name} ({email})")
                print(f"  Account ID: {account_id}")
                deleted = True
            conn.close()
        except Exception as e:
            print(f"\n✗ Error deleting from old database: {str(e)}")
    
    if not deleted:
        print(f"\nAccount with email '{email}' not found in either database.")
        return False
    
    print(f"  Related folders, emails, and attachments have been removed.")
    return True


def reset_database():
    """Reset the entire database (deletes all data)."""
    load_env()
    
    print("\n⚠ WARNING: This will delete ALL accounts, emails, folders, and settings!")
    print(f"Database location: {SQLITE_DB_PATH}")
    
    response = input("\nAre you sure you want to reset the database? (yes/no): ")
    if response.lower() != 'yes':
        print("Operation cancelled.")
        return False
    
    try:
        # Close any existing connections by deleting and recreating
        if SQLITE_DB_PATH.exists():
            SQLITE_DB_PATH.unlink()
            print(f"\n✓ Deleted existing database: {SQLITE_DB_PATH}")
        
        # Reinitialize database
        init_db()
        print(f"✓ Created new database: {SQLITE_DB_PATH}")
        print("\nDatabase has been reset. You can now add accounts fresh.")
        return True
    except Exception as e:
        print(f"\n✗ Error resetting database: {str(e)}")
        return False


def main():
    """Main function for database cleanup."""
    if len(sys.argv) < 2:
        print("Database Cleanup Utility")
        print("=" * 60)
        print("\nUsage:")
        print("  python cleanup_db.py list                    - List all accounts")
        print("  python cleanup_db.py delete <email>          - Delete account by email")
        print("  python cleanup_db.py reset                   - Reset entire database")
        print("\nExamples:")
        print("  python cleanup_db.py list")
        print("  python cleanup_db.py delete user@example.com")
        print("  python cleanup_db.py reset")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'list':
        list_accounts()
    
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("Error: Please provide an email address to delete.")
            print("Usage: python cleanup_db.py delete <email>")
            return
        email = sys.argv[2]
        delete_account_by_email(email)
    
    elif command == 'reset':
        reset_database()
    
    else:
        print(f"Unknown command: {command}")
        print("Use 'list', 'delete', or 'reset'")


if __name__ == "__main__":
    main()

