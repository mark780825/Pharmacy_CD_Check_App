import sqlite3
DB_NAME = 'pharmacy.db'

def migrate():
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute('ALTER TABLE prescription_drugs ADD COLUMN modified_by TEXT')
        print("Added modified_by")
    except Exception as e:
        print(f"modified_by might exist: {e}")
        
    try:
        conn.execute('ALTER TABLE prescription_drugs ADD COLUMN modified_at TIMESTAMP')
        print("Added modified_at")
    except Exception as e:
        print(f"modified_at might exist: {e}")
    conn.close()

if __name__ == '__main__':
    migrate()
