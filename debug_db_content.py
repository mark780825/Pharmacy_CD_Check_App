import sqlite3
import os
import sys

# Force utf-8 printing for console
sys.stdout.reconfigure(encoding='utf-8')

DB_NAME = 'pharmacy.db'

def count_records(db_path, label):
    if not os.path.exists(db_path):
        print(f"[{label}] File not found: {db_path}")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute("SELECT count(*) FROM prescription_drugs WHERE status='已領'")
        count = cur.fetchone()[0]
        print(f"[{label}] Picked Records: {count}")
        conn.close()
    except Exception as e:
        print(f"[{label}] Error: {e}")

def check_content():
    print("=== Checking DB Content ===")
    
    # Check Local
    if os.path.exists(DB_NAME):
        count_records(DB_NAME, "LOCAL")
    else:
        print("[LOCAL] pharmacy.db not found")

    # Check Shared
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.execute("SELECT value FROM settings WHERE key='transfer_dest'")
        row = cur.fetchone()
        conn.close()
        
        if row:
            raw_path = row[0]
            target_db = os.path.join(raw_path, 'pharmacy.db')
            count_records(target_db, "SHARED")
        else:
            print("[SHARED] No setting found")
            
    except Exception as e:
        print(f"[ERROR] Failed checking shared: {e}")

if __name__ == "__main__":
    check_content()
