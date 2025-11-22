#!/usr/bin/env python3
"""
Script to clean the email client database.

This script can:
1. Delete all accounts (keeps database structure)
2. Delete all data (keeps database structure)
3. Delete the entire database file

Uses the new database system:
- Database: ~/.email_client/email_client.db

Usage:
    python clean_database.py --accounts    # Delete all accounts
    python clean_database.py --all         # Delete all data
    python clean_database.py --full        # Delete entire database file
    python clean_database.py --email EMAIL # Delete specific account by email
"""

import sys
import argparse
from pathlib import Path
import sqlite3
import time

# Import config to get database paths
sys.path.insert(0, str(Path(__file__).parent))

# Database path (used by email_client.storage.db)
try:
    from email_client.config import SQLITE_DB_PATH, load_env
    load_env()
    DB_PATH = SQLITE_DB_PATH
except ImportError:
    DB_PATH = Path.home() / ".email_client" / "email_client.db"


def _clean_database(db_path: Path, db_name: str):
    """Helper to clean a specific database"""
    if not db_path.exists():
        print(f"  {db_name}: Database does not exist. Skipping.")
        return 0
    
    # Wait a bit and retry if database is locked
    max_retries = 5
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            cursor = conn.cursor()
            
            # Get count before deletion (new system uses 'id' not 'account_id')
            cursor.execute("SELECT COUNT(*) FROM accounts")
            count = cursor.fetchone()[0]
            
            if count == 0:
                conn.close()
                print(f"  {db_name}: No accounts to delete.")
                return 0
            
            print(f"  {db_name}: Found {count} account(s) to delete.")
            
            # Delete related data first (foreign key constraints)
            cursor.execute("DELETE FROM emails")
            cursor.execute("DELETE FROM folders")
            cursor.execute("DELETE FROM attachments")
            
            # Try to delete from tokens table
            try:
                cursor.execute("DELETE FROM tokens")
            except sqlite3.OperationalError:
                pass  # Table doesn't exist, that's okay
            
            # Delete accounts
            cursor.execute("DELETE FROM accounts")
            
            # Commit changes
            conn.commit()
            conn.close()
            
            print(f"  {db_name}: ✓ Successfully deleted {count} account(s) and all related data.")
            return count
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(f"  {db_name}: Database locked, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"  {db_name}: ✗ Error: {e}")
                return 0
        except sqlite3.Error as e:
            print(f"  {db_name}: ✗ Error: {e}")
            return 0
    
    return 0


def delete_all_accounts():
    """Delete all accounts from the database"""
    print("Cleaning accounts from database...")
    print(f"Database: {DB_PATH}")
    print()
    
    total = _clean_database(DB_PATH, "Database")
    
    if total == 0:
        print("\nNo accounts found in database.")
    else:
        print(f"\n✓ Total: Deleted {total} account(s).")


def delete_all_data():
    """Delete all data from all tables (keeps structure)"""
    print("Deleting all data from database...")
    print(f"Database: {DB_PATH}")
    
    if not DB_PATH.exists():
        print("Database does not exist. Skipping.")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        total_deleted = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute(f"DELETE FROM {table}")
                    total_deleted += count
                    print(f"  Deleted {count} row(s) from {table}")
            except sqlite3.OperationalError:
                pass  # Table might not exist or be locked
        
        conn.commit()
        conn.close()
        print(f"✓ Deleted {total_deleted} total rows.")
        
    except sqlite3.Error as e:
        print(f"✗ Error: {e}")


def delete_database_file():
    """Delete the entire database file"""
    print("Deleting database file...")
    print(f"Database: {DB_PATH}")
    
    if not DB_PATH.exists():
        print("Database does not exist. Skipping.")
        return
    
    # Also delete WAL and SHM files if they exist
    wal_file = DB_PATH.with_suffix('.db-wal')
    shm_file = DB_PATH.with_suffix('.db-shm')
    
    try:
        DB_PATH.unlink()
        print("✓ Deleted database file")
        
        if wal_file.exists():
            wal_file.unlink()
            print("✓ Deleted WAL file")
        
        if shm_file.exists():
            shm_file.unlink()
            print("✓ Deleted SHM file")
        
        print("\n✓ Database removed. It will be recreated on next run.")
    except Exception as e:
        print(f"✗ Error deleting database: {e}")


def delete_account_by_email(email: str):
    """Delete a specific account by email address"""
    print(f"Deleting account: {email}")
    print(f"Database: {DB_PATH}")
    print()
    
    if not DB_PATH.exists():
        print("Database does not exist. Skipping.")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        
        # Find account (new system uses 'id' not 'account_id')
        cursor.execute("SELECT id FROM accounts WHERE email_address = ?", (email,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            print("Account not found.")
            return
        
        account_id = result[0]
        print(f"Found account (ID: {account_id})")
        
        # Delete related data
        cursor.execute("DELETE FROM emails WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM folders WHERE account_id = ?", (account_id,))
        cursor.execute("DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (account_id,))
        
        # Try to delete from tokens table
        try:
            cursor.execute("DELETE FROM tokens WHERE account_id = ?", (account_id,))
        except sqlite3.OperationalError:
            pass
        
        # Delete account
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        
        conn.commit()
        conn.close()
        print("✓ Account deleted successfully.")
        
    except sqlite3.Error as e:
        print(f"✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Clean the email client database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clean_database.py --accounts    # Delete all accounts
  python clean_database.py --all         # Delete all data
  python clean_database.py --full        # Delete entire database file
        """
    )
    
    parser.add_argument(
        '--accounts',
        action='store_true',
        help='Delete all accounts (and related data)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Delete all data from all tables'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Delete the entire database file'
    )
    parser.add_argument(
        '--email',
        type=str,
        help='Delete a specific account by email address'
    )
    
    args = parser.parse_args()
    
    if not any([args.accounts, args.all, args.full, args.email]):
        parser.print_help()
        print("\n⚠  No action specified. Use --accounts, --all, --full, or --email EMAIL")
        sys.exit(1)
    
    if args.email:
        response = input(f"⚠  This will delete the account '{args.email}' and all related data. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        delete_account_by_email(args.email)
    elif args.full:
        response = input("⚠  This will delete the entire database files. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        delete_database_file()
    elif args.all:
        response = input("⚠  This will delete all data from all tables. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        delete_all_data()
    elif args.accounts:
        response = input("⚠  This will delete all accounts and related data. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
        delete_all_accounts()
    
    print("\n✓ Done!")


if __name__ == '__main__':
    main()

