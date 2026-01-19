import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SQLITE_DB = 'pharmacy.db'
POSTGRES_URL = os.getenv('DATABASE_URL')

def get_sqlite_conn():
    return sqlite3.connect(SQLITE_DB)

def get_postgres_conn():
    return psycopg2.connect(POSTGRES_URL)

def create_tables(pg_conn):
    cur = pg_conn.cursor()
    
    # 1. Create Tables (Adapted for Postgres)
    # Note: SQLite 'TEXT' matches Postgres 'TEXT', but 'TIMESTAMP' usage might need care.
    # Postgres uses SERIAL for autoincrement.
    
    print("Creating tables in Postgres...")
    
    # settings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            value TEXT
        );
    """)
    
    # medical_institutions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medical_institutions (
            code TEXT PRIMARY KEY, 
            name TEXT
        );
    """)
    
    # departments
    cur.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            code TEXT PRIMARY KEY, 
            name TEXT
        );
    """)
    
    # controlled_drugs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS controlled_drugs (
            nh_code TEXT PRIMARY KEY, 
            product_code TEXT, 
            name TEXT, 
            barcode TEXT, 
            level TEXT
        );
    """)
    
    # prescriptions
    # 'id INTEGER PRIMARY KEY AUTOINCREMENT' -> 'id SERIAL PRIMARY KEY'
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id SERIAL PRIMARY KEY, 
            patient_name TEXT, 
            patient_id TEXT, 
            visit_date TEXT, 
            visit_seq TEXT, 
            institution_code TEXT, 
            dept_code TEXT, 
            chronic_seq TEXT, 
            chronic_total TEXT,
            status TEXT DEFAULT '未提領', 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # prescription_drugs
    # Foreign key references prescriptions(id)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prescription_drugs (
            id SERIAL PRIMARY KEY, 
            prescription_id INTEGER REFERENCES prescriptions(id) ON DELETE CASCADE, 
            drug_code TEXT, 
            total_qty REAL, 
            picked_qty REAL DEFAULT 0, 
            picked_by TEXT, 
            picked_at TIMESTAMP, 
            modified_by TEXT, 
            modified_at TIMESTAMP, 
            status TEXT DEFAULT '未領'
        );
    """)
    
    pg_conn.commit()
    print("Tables created.")

def migrate_data():
    if not os.path.exists(SQLITE_DB):
        print("Local pharmacy.db not found. Skipping data migration.")
        return

    lite_conn = get_sqlite_conn()
    pg_conn = get_postgres_conn()
    
    create_tables(pg_conn)
    
    pg_cur = pg_conn.cursor()
    lite_cur = lite_conn.cursor()
    
    # --- Settings ---
    lite_cur.execute("SELECT * FROM settings")
    rows = lite_cur.fetchall()
    if rows:
        execute_values(pg_cur, "INSERT INTO settings (key, value) VALUES %s ON CONFLICT (key) DO NOTHING", rows)
        print(f"Migrated {len(rows)} settings.")

    # --- Medical Institutions ---
    lite_cur.execute("SELECT * FROM medical_institutions")
    rows = lite_cur.fetchall()
    if rows:
        execute_values(pg_cur, "INSERT INTO medical_institutions (code, name) VALUES %s ON CONFLICT (code) DO NOTHING", rows)
        print(f"Migrated {len(rows)} institutions.")

    # --- Departments ---
    lite_cur.execute("SELECT * FROM departments")
    rows = lite_cur.fetchall()
    if rows:
        execute_values(pg_cur, "INSERT INTO departments (code, name) VALUES %s ON CONFLICT (code) DO NOTHING", rows)
        print(f"Migrated {len(rows)} departments.")

    # --- Controlled Drugs ---
    lite_cur.execute("SELECT * FROM controlled_drugs")
    rows = lite_cur.fetchall()
    if rows:
        execute_values(pg_cur, "INSERT INTO controlled_drugs (nh_code, product_code, name, barcode, level) VALUES %s ON CONFLICT (nh_code) DO NOTHING", rows)
        print(f"Migrated {len(rows)} controlled drugs.")

    # --- Prescriptions & Drugs ---
    # Since IDs are SERIAL in Postgres, we want to preserve the original IDs if possible to keep relationships.
    # However, 'id' columns in Postgres can be explicitly inserted.
    
    print("Migrating Prescriptions...")
    lite_cur.execute("SELECT id, patient_name, patient_id, visit_date, visit_seq, institution_code, dept_code, chronic_seq, chronic_total, status, created_at FROM prescriptions")
    prescriptions = lite_cur.fetchall()
    
    for p in prescriptions:
        # Check if exists
        pg_cur.execute("SELECT id FROM prescriptions WHERE id = %s", (p[0],))
        if not pg_cur.fetchone():
            pg_cur.execute("""
                INSERT INTO prescriptions (id, patient_name, patient_id, visit_date, visit_seq, institution_code, dept_code, chronic_seq, chronic_total, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, p)
            
    # Reset sequence
    pg_cur.execute("SELECT setval('prescriptions_id_seq', (SELECT MAX(id) FROM prescriptions));")
    print(f"Migrated {len(prescriptions)} prescriptions.")

    print("Migrating Prescription Drugs...")
    # Check if modified_by columns exist in SQLite (might be missing in old DBs)
    lite_cur.execute("PRAGMA table_info(prescription_drugs)")
    cols = [r[1] for r in lite_cur.fetchall()]
    
    has_modified = 'modified_by' in cols
    
    if has_modified:
        lite_cur.execute("SELECT id, prescription_id, drug_code, total_qty, picked_qty, picked_by, picked_at, status, modified_by, modified_at FROM prescription_drugs")
    else:
        # Fallback for old schema
        lite_cur.execute("SELECT id, prescription_id, drug_code, total_qty, picked_qty, picked_by, picked_at, status FROM prescription_drugs")
        
    p_drugs = lite_cur.fetchall()
    
    for d in p_drugs:
        pg_cur.execute("SELECT id FROM prescription_drugs WHERE id = %s", (d[0],))
        if not pg_cur.fetchone():
            if has_modified:
                pg_cur.execute("""
                    INSERT INTO prescription_drugs (id, prescription_id, drug_code, total_qty, picked_qty, picked_by, picked_at, status, modified_by, modified_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, d)
            else:
                 pg_cur.execute("""
                    INSERT INTO prescription_drugs (id, prescription_id, drug_code, total_qty, picked_qty, picked_by, picked_at, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, d)

    pg_cur.execute("SELECT setval('prescription_drugs_id_seq', (SELECT MAX(id) FROM prescription_drugs));")
    print(f"Migrated {len(p_drugs)} prescription drugs.")
    
    pg_conn.commit()
    print("Migration Complete!")
    pg_conn.close()
    lite_conn.close()

if __name__ == '__main__':
    try:
        migrate_data()
    except Exception as e:
        print(f"Migration Failed: {e}")
