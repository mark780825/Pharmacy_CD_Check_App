import sqlite3
import os

try:
    if not os.path.exists('pharmacy.db'):
        print("Local pharmacy.db not found.")
    else:
        conn = sqlite3.connect('pharmacy.db')
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cur.fetchone():
            print("Settings table not found.")
        else:
            cur = conn.execute("SELECT value FROM settings WHERE key='transfer_dest'")
            res = cur.fetchone()
            print(f"Transfer Dest: {res[0] if res else 'Not Set'}")
        conn.close()
except Exception as e:
    print(f"Error: {e}")
