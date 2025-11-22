# Database Cleanup Guide

This guide provides instructions for cleaning the email client database.

## Database Location

The database is located at:

```
~/.email_client/email_client.db
```

On macOS/Linux, this expands to:

```
/Users/your_username/.email_client/email_client.db
```

## Automated Cleanup Script

Use the provided `clean_database.py` script:

### Delete All Accounts

```bash
python clean_database.py --accounts
```

### Delete All Data (keeps structure)

```bash
python clean_database.py --all
```

### Delete Entire Database File

```bash
python clean_database.py --full
```

## Manual SQL Commands

You can also use SQLite directly to clean the database.

### 1. Connect to the Database

**Old Database:**

```bash
sqlite3 ~/.email_desktop_client/data/email_client.db
```

**New Database:**

```bash
sqlite3 ~/.email_client/email_client.db
```

### 2. View Current Accounts

**Old Database:**

```sql
SELECT account_id, email_address, display_name, provider FROM accounts;
```

**New Database:**

```sql
SELECT id, email_address, display_name, provider FROM accounts;
```

### 3. Delete a Specific Account

**Old Database:**

```sql
-- First, delete related data
DELETE FROM emails WHERE account_id = 1;
DELETE FROM folders WHERE account_id = 1;
DELETE FROM attachments WHERE email_id IN (SELECT email_id FROM emails WHERE account_id = 1);
DELETE FROM tokens WHERE account_id = 1;

-- Then delete the account
DELETE FROM accounts WHERE account_id = 1;

-- Commit changes
COMMIT;
```

**New Database:**

```sql
-- First, delete related data
DELETE FROM emails WHERE account_id = 1;
DELETE FROM folders WHERE account_id = 1;
DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE account_id = 1);
DELETE FROM tokens WHERE account_id = 1;

-- Then delete the account
DELETE FROM accounts WHERE id = 1;

-- Commit changes
COMMIT;
```

### 4. Delete Account by Email Address

**Old Database:**

```sql
-- Find the account ID first
SELECT account_id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com';

-- Then delete
DELETE FROM emails WHERE account_id = (SELECT account_id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM folders WHERE account_id = (SELECT account_id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM tokens WHERE account_id = (SELECT account_id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com';
COMMIT;
```

**New Database:**

```sql
-- Find the account ID first
SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com';

-- Then delete
DELETE FROM emails WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM folders WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM tokens WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com');
DELETE FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com';
COMMIT;
```

### 5. Delete All Accounts

```sql
-- Delete in order to respect foreign key constraints
DELETE FROM emails;
DELETE FROM folders;
DELETE FROM attachments;
DELETE FROM tokens;
DELETE FROM accounts;
COMMIT;
```

### 6. Delete All Data (Reset Database)

```sql
DELETE FROM accounts;
DELETE FROM folders;
DELETE FROM emails;
DELETE FROM attachments;
DELETE FROM settings;
DELETE FROM tokens;
COMMIT;
```

### 7. Delete Entire Database Files

Exit SQLite and delete the files:

```bash
# Exit SQLite
.exit

# Delete old database files
rm ~/.email_desktop_client/data/email_client.db
rm ~/.email_desktop_client/data/email_client.db-wal 2>/dev/null
rm ~/.email_desktop_client/data/email_client.db-shm 2>/dev/null

# Delete new database files
rm ~/.email_client/email_client.db
rm ~/.email_client/email_client.db-wal 2>/dev/null
rm ~/.email_client/email_client.db-shm 2>/dev/null
```

## Quick One-Liner Commands

### Delete All Accounts (Bash)

```bash
sqlite3 ~/.email_client/email_client.db "DELETE FROM emails; DELETE FROM folders; DELETE FROM tokens; DELETE FROM accounts;"
```

### Delete Specific Account by Email (Bash)

```bash
sqlite3 ~/.email_client/email_client.db "DELETE FROM emails WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com'); DELETE FROM folders WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com'); DELETE FROM tokens WHERE account_id = (SELECT id FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com'); DELETE FROM accounts WHERE email_address = 'niteshsingh1357@gmail.com';"
```

### Delete Entire Database (Bash)

```bash
rm ~/.email_client/email_client.db ~/.email_client/email_client.db-wal ~/.email_client/email_client.db-shm 2>/dev/null
```

## Verify Cleanup

After cleanup, verify the databases are empty:

**Old Database:**

```bash
sqlite3 ~/.email_desktop_client/data/email_client.db "SELECT COUNT(*) FROM accounts;"
```

**New Database:**

```bash
sqlite3 ~/.email_client/email_client.db "SELECT COUNT(*) FROM accounts;"
```

Both should return `0`.

## Notes

- The database uses foreign key constraints with `ON DELETE CASCADE`, so deleting an account should automatically delete related folders, emails, and tokens.
- However, it's safer to delete in the order shown above to avoid constraint violations.
- The database will be automatically recreated with the correct schema when you run the application again.
- Make sure the application is not running when you delete the database file.
