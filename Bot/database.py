import sqlite3
import logging
from datetime import datetime

def create_db():
    """Создание таблиц и начальных данных (синхронная версия)"""
    try:
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        
        # Таблица с тарифами
        cursor.execute('''CREATE TABLE IF NOT EXISTS tariffs
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL UNIQUE,
                         price REAL NOT NULL,
                         duration_days INTEGER NOT NULL)''')
        
        # Таблица с клиентами
        cursor.execute('''CREATE TABLE IF NOT EXISTS clients
                        (user_id INTEGER NOT NULL,
                         config TEXT NOT NULL,
                         end_date TEXT NOT NULL,
                         PRIMARY KEY(user_id, end_date))''')
        
        # Добавляем тестовые тарифы

        
        cursor.execute("SELECT COUNT(*) FROM tariffs")
        if cursor.fetchone()[0] == 0:
            tariffs = [
                ('1 Day', 1.99, 'day'),
                ('1 Month', 5.99, 'month'),
                ('1 Year', 49.99, 'year')
            ]
        cursor.executemany(
            "INSERT INTO tariffs (name, price, period_type) VALUES (?, ?, ?)",
            tariffs
        )
        
        conn.commit()
        logging.info("Database initialized successfully")
        
    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        raise
    finally:
        if conn:
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
                     (user_id, config, end_date)
                     VALUES (?, ?, ?)''',
                  (user_id, config_data['config'], config_data['expiry_date']))
    conn.commit()
    conn.close()