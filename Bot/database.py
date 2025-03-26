import sqlite3
from datetime import datetime

async def create_db():
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS tariffs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      price REAL NOT NULL,
                      duration_days INTEGER NOT NULL)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients
                     (user_id INTEGER PRIMARY KEY,
                      ip_address TEXT,
                      public_key TEXT,
                      private_key TEXT,
                      preshared_key TEXT,
                      config TEXT,
                      start_date TIMESTAMP,
                      end_date TIMESTAMP)''')
    
    # Тестовые тарифы
    if not cursor.execute("SELECT COUNT(*) FROM tariffs").fetchone()[0]:
        cursor.executemany(
            "INSERT INTO tariffs (name, price, duration_days) VALUES (?, ?, ?)",
            [('Basic', 5.99, 30), ('Pro', 9.99, 30), ('Premium', 14.99, 60)]
        )
    
    conn.commit()
    conn.close()

async def get_tariffs():
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tariffs")
    data = cursor.fetchall()
    conn.close()
    return data

async def save_client_config(user_id: int, config_data: dict):
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    
    cursor.execute('''INSERT OR REPLACE INTO clients 
                     (user_id, ip_address, public_key, private_key, preshared_key, config, start_date, end_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, 
                   config_data['ip_address'], 
                   config_data['public_key'],
                   config_data['private_key'], 
                   config_data['preshared_key'],
                   config_data['config'], 
                   datetime.now().isoformat(),
                   config_data['expiry_date']))
    
    conn.commit()
    conn.close()