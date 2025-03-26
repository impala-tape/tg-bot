import os
import logging
import httpx
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from database import create_db, save_client_config, get_tariffs
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
WG_SERVICE_URL = os.getenv('WG_SERVICE_URL', "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class PurchaseState(StatesGroup):
    choosing_tariff = State()
    payment_confirmation = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await create_db()
    
    welcome_text = (
        "🔐 VPN Bot - Secure Connection\n\n"
        "Available tariffs:\n"
        "1. Basic - $5.99 (30 days)\n"
        "2. Pro - $9.99 (30 days)\n"
        "3. Premium - $14.99 (60 days)"
    )
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🛒 Buy VPN")],
            [types.KeyboardButton(text="📁 My Config")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(F.text == "🛒 Buy VPN")
async def purchase_start(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tariffs")
    tariffs = cursor.fetchall()
    conn.close()
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=f"{t[1]} - ${t[2]}")] for t in tariffs],
        resize_keyboard=True
    )
    
    await message.answer("Select tariff:", reply_markup=keyboard)
    await state.set_state(PurchaseState.choosing_tariff)

@dp.message(PurchaseState.choosing_tariff)
async def process_tariff(message: types.Message, state: FSMContext):
    tariff_name = message.text.split(' - ')[0]
    
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tariffs WHERE name=?", (tariff_name,))
    tariff = cursor.fetchone()
    conn.close()
    
    if not tariff:
        await message.answer("Invalid tariff selected")
        await state.clear()
        return
    
    await state.update_data(tariff_id=tariff[0], days=tariff[3])
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="✅ Confirm Payment")]],
        resize_keyboard=True
    )
    
    await message.answer(
        f"Please confirm payment for {tariff_name} (${tariff[2]})",
        reply_markup=keyboard
    )
    await state.set_state(PurchaseState.payment_confirmation)

@dp.message(PurchaseState.payment_confirmation, F.text == "✅ Confirm Payment")
async def process_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    try:
        # Генерируем тестовый конфиг прямо в боте
        expiry_date = (datetime.now() + timedelta(days=data['days'])).strftime("%Y-%m-%d")
        ip_suffix = message.from_user.id % 254 + 1
        
        config = f"""[Interface]
PrivateKey = 00000000000000000000000000000000000000000000
Address = 10.0.0.{ip_suffix}/24
DNS = 8.8.8.8

[Peer]
PublicKey = 00000000000000000000000000000000000000000000
PresharedKey = 00000000000000000000000000000000000000000000
AllowedIPs = 0.0.0.0/0
Endpoint = example.com:51820
PersistentKeepalive = 25
"""
        
        config_data = {
            "config": config,
            "ip_address": f"10.0.0.{ip_suffix}",
            "private_key": "00000000000000000000000000000000000000000000",
            "public_key": "00000000000000000000000000000000000000000000",
            "preshared_key": "00000000000000000000000000000000000000000000",
            "expiry_date": expiry_date
        }
        
        await save_client_config(message.from_user.id, config_data)
        
        await message.answer_document(
            types.BufferedInputFile(
                config.encode('utf-8'),
                filename=f"wg_{message.from_user.id}.conf"
            ),
            caption="⚠️ ТЕСТОВЫЙ КОНФИГ (не рабочий)\n\n"
                   f"Действителен до: {expiry_date}\n"
                   "Это демо-версия без реального VPN-доступа"
        )
        
        await message.answer(
            "✅ Тестовый конфиг создан!\n"
            "Функционал в режиме тестирования\n\n"
            "Для реальной работы нужно:\n"
            "1. Развернуть WireGuard сервер\n"
            "2. Настроить микросервис генерации конфигов",
            reply_markup=ReplyKeyboardRemove()
        )
        
    except Exception as e:
        await message.answer(
            "⚠️ Произошла ошибка при генерации конфига",
            reply_markup=ReplyKeyboardRemove()
        )
        logging.error(f"Config generation error: {str(e)}")
    
    await state.clear()

if __name__ == "__main__":
    dp.run_polling(bot)