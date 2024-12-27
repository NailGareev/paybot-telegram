import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


# Функция для создания базы данных и таблиц
def create_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            phone_number TEXT,
            card_number TEXT,
            cvv TEXT,
            expiration_date TEXT,
            balance INTEGER
        )
    ''')
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            amount INTEGER,
            date TEXT,
            time TEXT,
            FOREIGN KEY(sender_id) REFERENCES users(user_id),
            FOREIGN KEY(receiver_id) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    conn.close()


# Функция для генерации данных карты
def generate_card_details():
    card_number = "552255" + "".join([str(random.randint(0, 9)) for _ in range(10)])
    cvv = str(random.randint(100, 999))
    expiration_date = (datetime.now() + timedelta(days=365)).strftime("%m/%y")
    return card_number, cvv, expiration_date


# Функция для сохранения данных пользователя в базе данных
def save_user_data(user_id, username, phone_number, card_number, cvv, expiration_date, balance=10000):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, phone_number, card_number, cvv, expiration_date, balance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, phone_number, card_number, cvv, expiration_date, balance))
    conn.commit()
    conn.close()


# Функция для получения данных пользователя из базы данных
def get_user_data(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone_number, card_number, cvv, expiration_date, balance FROM users WHERE user_id = ?',
                   (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data


# Функция для получения пользователя по номеру телефона
def get_user_by_phone(phone_number):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, balance FROM users WHERE phone_number = ?', (phone_number,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data


# Функция для обновления баланса пользователя
def update_user_balance(user_id, new_balance):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()
    conn.close()


# Функция для сохранения транзакции
def save_transaction(sender_id, receiver_id, amount):
    date = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H:%M:%S")
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (sender_id, receiver_id, amount, date, time)
        VALUES (?, ?, ?, ?, ?)
    ''', (sender_id, receiver_id, amount, date, time))
    conn.commit()
    conn.close()


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    if user_data:
        phone_number = user_data[0]
        keyboard = [
            [KeyboardButton("Информация об аккаунте")],
            [KeyboardButton("Получить данные карты")],
            [KeyboardButton("Перевод")],
            [KeyboardButton("История транзакций")]
        ]
    else:
        keyboard = [
            [KeyboardButton("Регистрация", request_contact=True)]
        ]

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    context.user_data['previous_keyboard'] = keyboard  # Сохраняем текущую клавиатуру
    await update.message.reply_text(
        "Добро пожаловать!",
        reply_markup=reply_markup)


# Обработчик команды "История транзакций"
async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Получаем все транзакции, где пользователь может быть как отправителем, так и получателем
    cursor.execute(''' 
        SELECT amount, date, time, phone_number, sender_id, receiver_id
        FROM transactions
        JOIN users ON (transactions.sender_id = users.user_id OR transactions.receiver_id = users.user_id)
        WHERE sender_id = ? OR receiver_id = ?
        ORDER BY date DESC, time DESC
    ''', (user_id, user_id))

    transactions = cursor.fetchall()
    conn.close()

    if transactions:
        history_message = "История транзакций:\n"
        seen_transactions = set()  # Храним уникальные транзакции для предотвращения повторов
        for transaction in transactions:
            amount, date, time, phone_number, sender_id, receiver_id = transaction
            if (sender_id, receiver_id, amount, date, time) not in seen_transactions:
                seen_transactions.add((sender_id, receiver_id, amount, date, time))
                if sender_id == user_id:
                    # Это транзакция отправителя
                    receiver_data = get_user_data(receiver_id)
                    if receiver_data:
                        receiver_phone = receiver_data[0]
                        history_message += f"Дата: {date} Время: {time} Сумма: {amount} тенге Получатель: {receiver_phone}\n"
                else:
                    # Это транзакция получателя
                    sender_data = get_user_data(sender_id)
                    if sender_data:
                        sender_phone = sender_data[0]
                        history_message += f"Дата: {date} Время: {time} Сумма: {amount} тенге Отправитель: {sender_phone}\n"

        await update.message.reply_text(history_message)
    else:
        await update.message.reply_text("У вас нет истории транзакций.")


# Обработчик регистрации (получение номера телефона)
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        user_id = update.message.from_user.id
        username = update.message.from_user.username
        save_user_data(user_id, username, phone_number, '', '', '', 10000)

        await update.message.reply_text(
            f"Вы успешно зарегистрированы!\nНомер телефона: {phone_number}")

        # После регистрации обновляем клавиатуру
        await start(update, context)
    else:
        await update.message.reply_text("Пожалуйста, отправьте свой номер телефона, нажав кнопку 'Отправить номер'.")


# Обработчик команды "Получить данные карты"
async def get_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    if user_data:
        card_number = user_data[1]
        if card_number:
            phone_number, card_number, cvv, expiration_date, balance = user_data
            await update.message.reply_text(
                f"Номер карты: {card_number}\nCVV: {cvv}\nСрок действия: {expiration_date}\nБаланс: {balance} тенге")
        else:
            keyboard = [[KeyboardButton("Создать карту")], [KeyboardButton("Назад")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
            await update.message.reply_text("У вас нет карты. Пожалуйста, создайте карту, нажав 'Создать карту'.",
                                            reply_markup=reply_markup)
    else:
        await update.message.reply_text("Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь, нажав 'Регистрация'.")


# Обработчик создания карты
async def create_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    if user_data:
        card_number, cvv, expiration_date = generate_card_details()
        save_user_data(user_id, user_data[1], user_data[0], card_number, cvv, expiration_date, user_data[4])
        await update.message.reply_text(
            f"Ваша новая карта создана!\nНомер карты: {card_number}\nCVV: {cvv}\nСрок действия: {expiration_date}"
        )

        # Возвращаем предыдущую клавиатуру
        previous_keyboard = context.user_data.get('previous_keyboard', [])
        reply_markup = ReplyKeyboardMarkup(previous_keyboard, one_time_keyboard=False)
        await update.message.reply_text("Вы вернулись в меню", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь сначала.")


# Обработчик кнопки "Назад"
async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    previous_keyboard = context.user_data.get('previous_keyboard', [])
    reply_markup = ReplyKeyboardMarkup(previous_keyboard, one_time_keyboard=False)
    await update.message.reply_text("Вы вернулись в меню", reply_markup=reply_markup)


# Обработчик текстовых сообщений (для кнопок)
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id

    # Если пользователь вводит номер телефона для перевода
    if 'action' in context.user_data and context.user_data['action'] == 'transfer':
        if not context.user_data.get('receiver_phone'):  # Если номер телефона получателя еще не введен
            # Проверяем, существует ли такой номер телефона в базе данных
            receiver_data = get_user_by_phone(text)
            if receiver_data:
                context.user_data['receiver_phone'] = text
                await update.message.reply_text(f"Номер телефона {text} найден. Введите сумму для перевода:")
            else:
                await update.message.reply_text(
                    "Пользователь с таким номером телефона не найден. Пожалуйста, попробуйте снова.")
        else:
            # Пользователь вводит сумму перевода
            receiver_phone = context.user_data['receiver_phone']
            sender_data = get_user_data(user_id)
            if sender_data:
                balance = sender_data[4]
                try:
                    amount = int(text)
                    if amount <= 0:
                        await update.message.reply_text("Сумма перевода должна быть больше нуля.")
                    elif amount > balance:
                        await update.message.reply_text("У вас недостаточно средств для перевода.")
                    else:
                        # Выполняем перевод
                        receiver_data = get_user_by_phone(receiver_phone)
                        if receiver_data:
                            receiver_id = receiver_data[0]
                            # Обновляем балансы
                            update_user_balance(user_id, balance - amount)
                            receiver_balance = receiver_data[1]
                            update_user_balance(receiver_id, receiver_balance + amount)

                            # Сохраняем транзакцию
                            save_transaction(user_id, receiver_id, amount)

                            # Уведомляем получателя
                            receiver_user_data = get_user_data(receiver_id)
                            if receiver_user_data:
                                receiver_phone_number = receiver_user_data[0]
                                # Отправляем сообщение получателю
                                application = context.application
                                await application.bot.send_message(receiver_id,
                                                                   f"Вам поступило {amount} тенге от {sender_data[0]}.")
                            await update.message.reply_text(
                                f"Перевод {amount} тенге на номер {receiver_phone} успешно выполнен.")
                            # Сбросим данные перевода
                            context.user_data['action'] = None
                            context.user_data['receiver_phone'] = None

                            # Возвращаем пользователя в меню
                            previous_keyboard = context.user_data.get('previous_keyboard', [])
                            reply_markup = ReplyKeyboardMarkup(previous_keyboard, one_time_keyboard=False)
                            await update.message.reply_text("Вы вернулись в меню", reply_markup=reply_markup)

                except ValueError:
                    await update.message.reply_text("Пожалуйста, введите корректную сумму.")

    elif text == "Информация об аккаунте":
        user_data = get_user_data(user_id)
        if user_data:
            phone_number, _, _, _, balance = user_data
            await update.message.reply_text(
                f"Информация об аккаунте\nНомер телефона: {phone_number}\nБаланс карты: {balance} тенге"
            )
        else:
            await update.message.reply_text(
                "Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь, нажав 'Регистрация'.")

    elif text == "Получить данные карты":
        await get_card(update, context)

    elif text == "Перевод":
        keyboard = [
            [KeyboardButton("Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
        await update.message.reply_text("Введите номер телефона получателя:", reply_markup=reply_markup)
        context.user_data['action'] = 'transfer'

    elif text == "История транзакций":
        await transaction_history(update, context)

    elif text == "Назад":
        await go_back(update, context)

    elif text == "Создать карту":
        await create_card(update, context)

    else:
        await update.message.reply_text("Неизвестная команда. Используйте доступные кнопки.")


# Основная функция для запуска бота
def main():
    create_db()

    token = '8025238812:AAFI2A3xTeIi2d_uwdGWNeINqBkwXJr9Rq8'

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, register))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    application.run_polling()


if __name__ == '__main__':
    main()
