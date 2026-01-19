import sqlite3
import os
import sys

# Force utf-8 printing for console
sys.stdout.reconfigure(encoding='utf-8')

DB_NAME = 'pharmacy.db'

def inspect_shared():
    print("=== Inspecting Shared DB Records ===")
    
    # 1. Get Path
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.execute("SELECT value FROM settings WHERE key='transfer_dest'")
        row = cur.fetchone()
        conn.close()
        
        if not row:
            print("No shared path set locally.")
            return

        raw_path = row[0]
        db_path = os.path.join(raw_path, 'pharmacy.db')
        print(f"Target DB: {db_path}")
        
    except Exception as e:
        print(f"Error reading setting: {e}")
        return

    # 2. Dump Data
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        print("\n--- Prescriptions (Pending/Done) ---")
        cur = conn.execute("SELECT id, patient_name, visit_date, status, created_at FROM prescriptions LIMIT 5")
        for r in cur.fetchall():
            print(f"ID: {r['id']}, Name: {r['patient_name']}, Date: {r['visit_date']}, Status: {r['status']}, Created: {r['created_at']}")
            
        print("\n--- Picked Drugs (History) ---")
        cur = conn.execute("SELECT id, prescription_id, drug_code, picked_at, status FROM prescription_drugs WHERE status='已領'")
        for r in cur.fetchall():
            print(f"ID: {r['id']}, P_ID: {r['prescription_id']}, Code: {r['drug_code']}, PickedAt: {r['picked_at']}, Status: {r['status']}")
            
        conn.close()
    except Exception as e:
        print(f"Error reading shared DB: {e}")

if __name__ == "__main__":
    inspect_shared()
