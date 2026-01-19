import sqlite3
import os
import sys

# Force utf-8 printing for console
sys.stdout.reconfigure(encoding='utf-8')

DB_NAME = 'pharmacy.db'

def get_local_db():
    return sqlite3.connect(DB_NAME)

def check_path():
    print("=== Debugging DB Path Resolution ===")
    
    # 1. Read Raw Setting
    try:
        conn = get_local_db()
        cur = conn.execute("SELECT value FROM settings WHERE key='transfer_dest'")
        row = cur.fetchone()
        conn.close()
        
        if not row:
            print("[INFO] No 'transfer_dest' setting found in local DB.")
            return
            
        raw_path = row[0]
        print(f"[INFO] Raw Path from DB: {repr(raw_path)}")
        print(f"[INFO] Printed Path: {raw_path}")
        
    except Exception as e:
        print(f"[ERROR] Failed to read local DB: {e}")
        return

    # 2. Check Existence
    try:
        exists = os.path.exists(raw_path)
        print(f"[TEST] os.path.exists(path): {exists}")
        
        is_dir = os.path.isdir(raw_path)
        print(f"[TEST] os.path.isdir(path): {is_dir}")
        
        if exists and is_dir:
            target_db = os.path.join(raw_path, 'pharmacy.db')
            print(f"[INFO] Target DB file: {target_db}")
            print(f"[TEST] Target DB exists? {os.path.exists(target_db)}")
        else:
            print("[WARN] Path does not exist or is not a directory!")
            
    except Exception as e:
        print(f"[ERROR] Path check failed: {e}")

if __name__ == "__main__":
    check_path()
