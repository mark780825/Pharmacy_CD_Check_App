import sqlite3
DB_NAME = 'pharmacy.db'

def migrate():
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute('ALTER TABLE prescriptions ADD COLUMN chronic_seq TEXT')
        print("Added chronic_seq")
    except Exception as e:
        print(f"chronic_seq might exist: {e}")
        
    try:
        conn.execute('ALTER TABLE prescriptions ADD COLUMN chronic_total TEXT')
        print("Added chronic_total")
    except Exception as e:
        print(f"chronic_total might exist: {e}")
    conn.close()

if __name__ == '__main__':
    migrate()
