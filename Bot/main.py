import os
import logging
import sqlite3
import signal
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from database import create_db, save_client_config, get_tariffs
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta

import logging
from logging.handlers import RotatingFileHandler

# Настройка логирования
def setup_logging():
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            RotatingFileHandler(
                'bot.log',
                maxBytes=5*1024*1024,  # 5 MB
                backupCount=3,
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )
    
    # Уровень логирования для aiogram
    logging.getLogger('aiogram').setLevel(logging.WARNING)

# Вызов функции настройки в начале
setup_logging()


load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class PurchaseState(StatesGroup):
    choosing_tariff = State()
    payment_confirmation = State()

def get_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🛒 Buy VPN")],
            [types.KeyboardButton(text="📁 My Config")]
        ],
        resize_keyboard=True
    )

def get_back_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="⬅️ Back")]],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🔐 VPN Bot - Secure Connection\n\n"
        "Available tariffs:\n"
        "1. 1 Day - $1.99\n"
        "2. 1 Month - $5.99\n"
        "3. 1 Year - $49.99",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🛒 Buy VPN")
async def purchase_start(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tariffs")
    tariffs = cursor.fetchall()
    conn.close()
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=f"{t[1]} - ${t[2]}")] for t in tariffs] + 
                  [[types.KeyboardButton(text="⬅️ Back")]],
        resize_keyboard=True
    )
    
    await message.answer("Select tariff:", reply_markup=keyboard)
    await state.set_state(PurchaseState.choosing_tariff)

@dp.message(F.text == "📁 My Config")
async def show_user_configs(message: types.Message):
    try:
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT config, end_date FROM clients 
                         WHERE user_id = ? ORDER BY end_date DESC''',
                     (message.from_user.id,))
        configs = cursor.fetchall()
        conn.close()

        if not configs:
            await message.answer("You have no active configurations", reply_markup=get_main_keyboard())
            return

        for config_data in configs:
            config_text, expiry_date = config_data
            try:
                expiry_date = datetime.strptime(expiry_date.split('T')[0], "%Y-%m-%d")
                await message.answer_document(
                    types.BufferedInputFile(
                        config_text.encode('utf-8'),
                        filename=f"wg_config_{expiry_date.date()}.conf"
                    ),
                    caption=f"Valid until: {expiry_date.strftime('%d.%m.%Y')}",
                    reply_markup=get_back_keyboard()
                )
            except Exception as e:
                logging.error(f"Config processing error: {str(e)}")
                await message.answer("Error processing config", reply_markup=get_back_keyboard())

    except Exception as e:
        logging.error(f"Error showing configs: {str(e)}")
        await message.answer("Error loading configurations", reply_markup=get_main_keyboard())

@dp.message(F.text == "⬅️ Back")
async def handle_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Main menu:", reply_markup=get_main_keyboard())

@dp.message(PurchaseState.choosing_tariff)
async def process_tariff(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Back":
        await handle_back(message, state)
        return

    tariff_name = message.text.split(' - ')[0]
    conn = sqlite3.connect('vpn.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, price, period_type FROM tariffs WHERE name=?", (tariff_name,))
    tariff = cursor.fetchone()
    conn.close()
    
    if not tariff:
        await message.answer("Invalid tariff selected", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    await state.update_data(tariff_id=tariff[0], price=tariff[1], period_type=tariff[2])
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Confirm Payment")],
            [types.KeyboardButton(text="⬅️ Back")]
        ],
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
        conn = sqlite3.connect('vpn.db')
        cursor = conn.cursor()
        cursor.execute("SELECT period_type FROM tariffs WHERE id = ?", (data['tariff_id'],))
        period_type = cursor.fetchone()[0]
        conn.close()

        purchase_date = datetime.now()
        expiry_date = calculate_expiry_date(purchase_date, period_type)

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
            "private_key": "0"*44,
            "public_key": "0"*44,
            "preshared_key": "0"*44,
            "expiry_date": expiry_date.isoformat()
        }
        
        await save_client_config(message.from_user.id, config_data)
        
        await message.answer_document(
            types.BufferedInputFile(
                config.encode('utf-8'),
                filename=f"wg_{message.from_user.id}.conf"
            ),
            caption=f"⚠️ TEST CONFIG (non-working)\nValid until: {expiry_date.strftime('%Y-%m-%d')}",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logging.error(f"Config generation error: {str(e)}", exc_info=True)
        await message.answer("Error generating config", reply_markup=get_main_keyboard())
    
    await state.clear()

def calculate_expiry_date(start_date: datetime, period_type: int) -> datetime:
    """Рассчитывает дату окончания по типу периода"""
    match period_type:
        case 1:  # День
            return start_date + timedelta(days=1)
        case 2:  # Месяц
            return start_date + relativedelta(months=1, day=start_date.day)
        case 3:  # Год
            return start_date + relativedelta(years=1)
        case _:
            raise ValueError(f"Unknown period type: {period_type}")

async def shutdown(bot: Bot):
    await bot.session.close()
    print("\nBot stopped")

async def main():
    # Инициализация БД в отдельном потоке
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_db)
    
    # Остальная логика
    try:
        loop.add_signal_handler(
            signal.SIGINT,
            lambda: asyncio.create_task(shutdown(bot))
        )
    except NotImplementedError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    
    try:
        print("Bot started. Press Ctrl+C to stop.")
        await dp.start_polling(bot)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nGraceful shutdown...")
    finally:
        await shutdown(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")