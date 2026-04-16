# migrate.py - Database upgrade script for SchoolOS Phase 2
# Run this BEFORE replacing app.py to keep your data safe!

import sqlite3
import shutil
import os
from datetime import datetime

def main():
    print("=" * 50)
    print("SCHOOLOS DATABASE MIGRATION")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists("schoolos.db"):
        print("❌ No existing database found (schoolos.db)")
        print("ℹ️  This is OK if you're doing fresh install")
        return
    
    # Create backup
    backup_name = f"schoolos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    print(f"📦 Creating backup: {backup_name}")
    shutil.copy2("schoolos.db", backup_name)
    print("✅ Backup created!")
    
    # Connect to database
    conn = sqlite3.connect("schoolos.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get list of existing tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cur.fetchall()]
    print(f"\n📊 Found tables: {existing_tables}")
    
    # Upgrade schools table
    if 'schools' in existing_tables:
        print("\n🔄 Upgrading schools table...")
        try:
            cur.execute("ALTER TABLE schools ADD COLUMN is_active INTEGER DEFAULT 1")
            print("   ✅ Added is_active column")
        except sqlite3.OperationalError:
            print("   ℹ️  is_active already exists")
        
        try:
            cur.execute("ALTER TABLE schools ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
            print("   ✅ Added created_at column")
        except sqlite3.OperationalError:
            print("   ℹ️  created_at already exists")
    
    # Upgrade students table
    if 'students' in existing_tables:
        print("\n🔄 Upgrading students table...")
        try:
            cur.execute("ALTER TABLE students ADD COLUMN is_active INTEGER DEFAULT 1")
            print("   ✅ Added is_active column")
        except sqlite3.OperationalError:
            print("   ℹ️  is_active already exists")
    
    # Upgrade care_logs table
    if 'care_logs' in existing_tables:
        print("\n🔄 Upgrading care_logs table...")
        new_columns = [
            ('type', 'TEXT'),
            ('sub_type', 'TEXT'),
            ('status', 'TEXT'),
            ('start_time', 'TEXT'),
            ('end_time', 'TEXT'),
            ('recorded_by', 'TEXT')
        ]
        for col_name, col_type in new_columns:
            try:
                cur.execute(f"ALTER TABLE care_logs ADD COLUMN {col_name} {col_type}")
                print(f"   ✅ Added {col_name}")
            except sqlite3.OperationalError:
                print(f"   ℹ️  {col_name} already exists")
    
    # Create audit_logs table (NEW)
    print("\n🔄 Creating audit_logs table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id TEXT,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            performed_by TEXT,
            performed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ audit_logs ready")
    
    # Create admin_config table (NEW)
    print("\n🔄 Creating admin_config table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    # Add default admin password if not exists
    cur.execute("SELECT 1 FROM admin_config WHERE key='admin_password_hash'")
    if not cur.fetchone():
        try:
            import bcrypt
            hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            cur.execute("INSERT INTO admin_config VALUES (?, ?)", 
                       ("admin_password_hash", hashed))
            print("   ✅ Default admin created (password: admin123)")
        except ImportError:
            print("   ⚠️  bcrypt not installed - run: pip install bcrypt")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("🎉 MIGRATION COMPLETE!")
    print("=" * 50)
    print(f"📁 Your data is safe in: {backup_name}")
    print("\nNext steps:")
    print("1. Replace your app.py with Phase 2 code")
    print("2. Run: streamlit run app.py")

if __name__ == "__main__":
    main()
