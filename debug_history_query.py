import sqlite3
import os
import sys

# Force utf-8 printing
sys.stdout.reconfigure(encoding='utf-8')

DB_NAME = 'pharmacy.db'

def get_shared_path():
    try:
        conn = sqlite3.connect(DB_NAME)
        row = conn.execute("SELECT value FROM settings WHERE key='transfer_dest'").fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None

def debug_query():
    path = get_shared_path()
    if not path:
        print("[ERROR] No shared path found in settings.")
        return
        
    db_path = os.path.join(path, 'pharmacy.db')
    print(f"[INFO] Using DB: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Dump Actual Patient Data
    print("\n=== RAW DATA INSPECTION ===")
    cur = conn.execute("SELECT id, patient_name, patient_id FROM prescriptions")
    p_map = {}
    for r in cur:
        # Check for hidden characters
        pid_repr = repr(r['patient_id'])
        print(f"ID: {r['id']}, Name: {r['patient_name']}, PID: {r['patient_id']} (Repr: {pid_repr})")
        p_map[r['id']] = r['patient_id']

    # 2. Simulate User Query
    print("\n=== SIMULATING QUERY ===")
    start_date = '2020/09/16' # Hypothesis: Slashes break SQLite date()
    end_date = '2025/12/15'
    q_val = 'B200592990' # User's query from screenshot
    
    sql = '''
        SELECT 
            pd.id as pd_id, pd.picked_at, pd.drug_code,
            p.patient_name, p.patient_id
        FROM prescription_drugs pd
        JOIN prescriptions p ON pd.prescription_id = p.id
        WHERE pd.status = '已領'
        AND date(pd.picked_at) BETWEEN ? AND ?
        AND p.patient_id LIKE ?
    '''
    
    params = [start_date, end_date, f"%{q_val}%"]
    
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    print(f"\n[RESULT] Matched Rows: {len(rows)}")
    for r in rows:
        print(dict(r))

    if len(rows) == 0:
        print("\n[DIAGNOSIS] Query returned 0 rows. Checking why...")
        # Check components
        # A. Check Date
        print("Checking Date Range matches:")
        cur = conn.execute("SELECT picked_at, date(picked_at) as d FROM prescription_drugs WHERE status='已領'")
        for r in cur:
            print(f"  PickedAt: {r['picked_at']} -> Date: {r['d']} (InRange? {start_date <= r['d'] <= end_date})")
        
        # B. Check Patient ID Match logic
        print("Checking LIKE match:")
        term = f"%{q_val}%"
        for pid in p_map.values():
            # Python check
            is_match = q_val in pid
            print(f"  PID '{pid}' contains '{q_val}'? {is_match}")


    conn.close()

if __name__ == "__main__":
    debug_query()
