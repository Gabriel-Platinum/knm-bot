import telebot
import datetime
import calendar
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton,InputMediaPhoto
import bcrypt

# --- Пользователи ---
from db import (
    get_all_users,
    get_user_by_username,
    get_user_by_id,
    get_admin_by_username,
    add_user_to_db,
    update_username,
    update_password,
    delete_user_from_db,
    link_telegram_id,
)

# --- Значки пользователя ---
from db import (
    get_user_badges,
    get_user_badges_by_telegram_id,
    get_badge_status,
    update_badge_status,
    update_badge_date,
    delete_user_badge,
    add_existing_badge_to_user,
    get_badge_name_by_id
)

# --- Все значки ---
from db import get_all_badges


from config import BOT_TOKEN, ADMIN_USERNAME, ADMIN_PASSWORD_HASH

bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {}  

#ДЕФОЛТ ПАНЕЛЬ

@bot.message_handler(commands=['start'])
def start(message):
    greeting = (
        "Привет! Я бот для проекта \"Aus vielen ein Ganzes\" 🌟\n\n"
        "Здесь ты можешь отслеживать свою активность по проекту.\n\n"
        "С помощью данных тебе нужно выполнить вход, а дальше ты получишь доступ к:\n"
        "1. Количеству полученных значков и сколько ещё нужно донабрать\n"
        "2. Сколько значков ожидают получения\n"
        "3. Сколько осталось дней до конца текущего квартала\n"
        "4. Какие именно значки ты получил (название, дата получения, статус - получен/не получен)\n"
        "5. К кому можно обратиться за получением наклейки (значка)\n"
        "6. К кому можно обратиться (кураторы проекта)\n"
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    login_button = types.KeyboardButton("Войти")
    markup.add(login_button)

    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    
    
#логин юзера
@bot.message_handler(func=lambda m: m.text == "Войти")
def ask_username(message):
    bot.send_message(message.chat.id, "Введите ваш логин:")
    bot.register_next_step_handler(message, get_username)

def get_username(message):
    username = message.text.strip().lower()  
    user = get_user_by_username(username)
    if user is None:
        bot.send_message(message.chat.id, "❌ Пользователь не найден. Попробуйте снова.")
        return
    
    bot.send_message(message.chat.id, "Введите пароль:")
    bot.register_next_step_handler(message, login_user, username)
    

def login_user(message, username):
    password = message.text.strip()
    user = get_user_by_username(username.lower())  

    if user is None:
        bot.send_message(message.chat.id, "❌ Пользователь с таким логином не найден.")
        return

    user_id, user_username, stored_password, tg_id = user
    current_tg_id = message.from_user.id

    if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
        if tg_id:
            if tg_id != current_tg_id:
                bot.send_message(
                    message.chat.id,
                    "🚫 Этот аккаунт уже привязан к другому Telegram-профилю."
                )
                return
        else:
            link_telegram_id(user_id, current_tg_id)

        user_sessions[message.chat.id] = user_id

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Зарегистрированные значки", callback_data="badges_received"),
            InlineKeyboardButton("Ожидающие получения", callback_data="badges_pending"),
            InlineKeyboardButton("Остаток дней", callback_data="days_remaining"),
            InlineKeyboardButton("Все значки", callback_data="all_badges"),
            InlineKeyboardButton("Где получить наклейку", callback_data="get_sticker")
        )

        bot.send_message(message.chat.id, "✅ Вход выполнен успешно!", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуйте снова.")

        
#ФУНКЦИИ ЮЗЕРА

# Полученные значки
@bot.callback_query_handler(func=lambda call: call.data == "badges_received")
def show_badges(call):
    user_id = user_sessions.get(call.message.chat.id)

    if not user_id:
        bot.send_message(call.message.chat.id, "Пожалуйста, войдите в систему.")
        return

    badges = get_user_badges(user_id)

    if not badges:
        bot.send_message(call.message.chat.id, "У вас пока нет значков.")
        return

    for badge in badges:
        id, name, image_path, status, date_received = badge
        status_text = "✅ Получен" if status == "получен" else "Ожидает получения"

        
        date_text = f"📅 {date_received}" if date_received else "📅 Дата не указана"

        caption = f"🏅 *{name}*\n статус: {status_text}\n дата регистрации значка: {date_text}"
        print(f"Image Path: {image_path}")  # Выводим путь к картинке для дебага
        try:
            with open(image_path, 'rb') as photo:
                bot.send_photo(call.message.chat.id, photo, caption=caption, parse_mode="Markdown")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"{name}\n{status_text}\n{date_text}\n(⚠️ ошибка загрузки изображения)")


#ожидающие значки
@bot.callback_query_handler(func=lambda call: call.data == "badges_pending")
def handle_pending_badges(call):
    user_id = call.from_user.id
    badges = get_user_badges_by_telegram_id(user_id)

    if not badges:
        return bot.send_message(call.message.chat.id, "У вас нет значков.")
    for badge in badges:
     print(f"[DEBUG] Значок: {badge[0]}, Статус: '{badge[2]}'")

    # Фильтруем только те значки, у которых статус "не получен"
    pending_badges = [badge for badge in badges if badge[2] == "не получен"]

    if not pending_badges:
        return bot.send_message(call.message.chat.id, "У вас нет ожидающих значков. 🎉")

    media_group = []

    for name, image_path, status, date_received in pending_badges[:10]:  # до 10 штук — лимит Telegram
        status_text = "⏳ Ожидает получения"
        date_text = f"📅 Дата регистрации значка: {date_received}"  
        caption = f"🏷 *{name}*\nСтатус: {status_text}\n{date_text}"

        image_file_path = image_path
        
        try:
            with open(image_file_path, 'rb') as img:
                media = InputMediaPhoto(img.read(), caption=caption, parse_mode="Markdown")
                media_group.append(media)
        except FileNotFoundError:
            bot.send_message(call.message.chat.id, f"⚠️ Картинка не найдена для значка: {name}")

    if media_group:
        bot.send_media_group(call.message.chat.id, media_group)

# Остаток дней
@bot.callback_query_handler(func=lambda call: call.data == "days_remaining")
def handle_remaining_days(call):
    def get_days_until_end_of_quarter():
        today = datetime.date.today()
        year = today.year
        month = today.month

        # Определяем конец квартала по текущему месяцу
        if 5 <= month <= 7:  # май-июль
            end_month = 7
        elif 8 <= month <= 10:  # август-октябрь
            end_month = 10
        elif month == 11 or month == 12 or month == 1:  # ноябрь-январь
            if month == 1:
                year -= 1  # январь — относится к кварталу ноябрь-январь
            end_month = 1
        else:  # февраль-апрель
            end_month = 4

        # Определяем последний день месяца с учетом количества дней
        if end_month == 1:
            end_date = datetime.date(year + 1, 1, calendar.monthrange(year + 1, 1)[1])
        else:
            end_date = datetime.date(year, end_month, calendar.monthrange(year, end_month)[1])

        remaining_days = (end_date - today).days
        return remaining_days

    days_remaining = get_days_until_end_of_quarter()
    weeks = days_remaining // 7
    days = days_remaining % 7

    message = f"📅 До конца квартала осталось {days_remaining} дней\n" \
              f"🗓️ Это примерно {weeks} недель и {days} дней."

    bot.send_message(call.message.chat.id, message)

# все значки
@bot.callback_query_handler(func=lambda call: call.data == "all_badges")
def handle_all_badges(call):
    badges = get_all_badges()

    if not badges:
        bot.send_message(call.message.chat.id, "Значки не найдены.")
        return

    for _, name, image_path in badges:
        caption = f"🏅 *{name}*"
        try:
            with open(image_path, 'rb') as img:
                bot.send_photo(call.message.chat.id, img, caption=caption, parse_mode="Markdown")
        except FileNotFoundError:
            bot.send_message(call.message.chat.id, f"⚠️ Картинка не найдена: {name}")
        
# Где получить наклейку
@bot.callback_query_handler(func=lambda call: call.data == "get_sticker")
def handle_get_sticker(call):
    text = "🎉 Наклейку вы можете получить в любое субботнее мероприятие у куратора!"
    bot.send_message(call.message.chat.id, text)
    
#   ФУНКЦИИ АДМИНА

admin_sessions = set()
admin_login_temp = {}  # временно храним логины, чтобы знать к какому пользователю относится пароль

#вход админа
@bot.message_handler(commands=['admin'])
def admin_login_start(message):
    bot.send_message(message.chat.id, "Введите логин администратора:")
    bot.register_next_step_handler(message, get_admin_login)

def get_admin_login(message):
    username = message.text.strip().lower()  # 👈 Приводим к нижнему регистру
    admin_data = get_admin_by_username(username)

    if admin_data:
        stored_username, stored_hash = admin_data
        admin_login_temp[message.chat.id] = (stored_username, stored_hash)
        bot.send_message(message.chat.id, "Введите пароль:")
        bot.register_next_step_handler(message, get_admin_password)
    else:
        bot.send_message(message.chat.id, "❌ Неверный логин. Попробуйте снова.")



def get_admin_password(message):
    user_id = message.chat.id
    password = message.text.strip()

    if user_id in admin_login_temp:
        username, stored_hash = admin_login_temp[user_id]

        
        username = username.lower()

        if bcrypt.checkpw(password.encode(), stored_hash.encode()):
            admin_sessions.add(message.from_user.id)
            bot.send_message(message.chat.id, f"✅ Администратор *{username}* успешно вошёл.", parse_mode="Markdown")
            send_admin_menu(message.chat.id)
        else:
            bot.send_message(message.chat.id, "❌ Неверный пароль.")
        
        del admin_login_temp[user_id]
    else:
        bot.send_message(message.chat.id, "Произошла ошибка. Начните снова с команды /admin.")

        
# панель админа       
def send_admin_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📋 Посмотреть всех участников", "🔍 Найти участника по логину")
    markup.add("➕ Добавить пользователя") 
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)
    
    
    
# добавление пользователя у админа
user_states = {}

@bot.message_handler(func=lambda message: message.text == "➕ Добавить пользователя")
def ask_for_login(message):
    if message.from_user.id not in admin_sessions:
        return bot.send_message(message.chat.id, "Вы не авторизованы как админ.")
    
    bot.send_message(
        message.chat.id,
        "Введите логин нового пользователя (или отправьте 'идинахуй' для отмены действия):"
    )
    user_states[message.chat.id] = {"action": "waiting_for_login"}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("action") == "waiting_for_login")
def ask_for_password(message):
    if message.text.strip().lower() == "идинахуй":
        user_states.pop(message.chat.id, None)
        return bot.send_message(message.chat.id, "❌ Добавление пользователя отменено.")

    username = message.text.strip().lower()  # 👈 логин в нижнем регистре
    if get_user_by_username(username):
        bot.send_message(message.chat.id, "⚠️ Пользователь с таким логином уже существует. Введите другой логин:")
        return 
    
    user_states[message.chat.id] = {"action": "waiting_for_password", "username": username}
    bot.send_message(
        message.chat.id,
        "Введите пароль для нового пользователя (или отправьте 'идинахуй' для отмены действия):"
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get("action") == "waiting_for_password")
def add_user(message):
    if message.text.strip().lower() == "идинахуй":
        user_states.pop(message.chat.id, None)
        return bot.send_message(message.chat.id, "❌ Добавление пользователя отменено.")

    password = message.text.strip().lower()  # 👈 пароль тоже в нижнем регистре
    username = user_states[message.chat.id]["username"]
    success = add_user_to_db(username, password)

    if success:
        bot.send_message(message.chat.id, f"✅ Пользователь *{username}* успешно добавлен!", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Ошибка при добавлении пользователя.")
    
    user_states.pop(message.chat.id, None)


    
# Показываем всех пользователей как кнопки
@bot.message_handler(func=lambda message: message.text == "📋 Посмотреть всех участников")
def view_all_users(message):
    if message.from_user.id not in admin_sessions:
        return bot.send_message(message.chat.id, "Вы не авторизованы как админ.")

    users = get_all_users()
    if not users:
        return bot.send_message(message.chat.id, "Пользователей пока нет.")

    markup = types.InlineKeyboardMarkup()
    for user_id, username in users:
        markup.add(types.InlineKeyboardButton(text=username, callback_data=f"view_user_{user_id}"))

    bot.send_message(message.chat.id, "Список участников:", reply_markup=markup)
    
# Обрабатываем нажатие на кнопку пользователя
@bot.callback_query_handler(func=lambda call: call.data.startswith("view_user_"))
def handle_user_click(call):
    user_id = int(call.data.split("_")[-1])
    user = get_user_by_id(user_id)  
    if not user:
        return bot.send_message(call.message.chat.id, "❌ Пользователь не найден.")

    username, hashed_password, tg_id= user[1], user[2], user[3]

    
    badges = get_user_badges(user_id)

    
    if badges:
        badges_text = "\n".join([f"🏅 {badge_name} — {status} (Дата: {date_received})" for _, badge_name, _, status, date_received in badges])
    else:
        badges_text = "Нет значков."

   
    text = (
        f"👤 Пользователь:\n"
        f"Ник: <b>{username}</b>\n"
        f"Хэшированный пароль: <b>{hashed_password}</b>\n"
        f"Telegram id: <b>{tg_id}</b>\n"
        f"Количество значков: <b>{len(badges)}</b>\n\n"
        f"🎖️ Значки:\n{badges_text}"
    )

    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data=f"edit_user_{user_id}"))
    markup.add(InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data=f"delete_user_{user_id}"))
    markup.add(InlineKeyboardButton(text="🎖️ Редактировать значки", callback_data=f"edit_badges_{user_id}"))
    markup.add(InlineKeyboardButton(text="➕ Добавить значок", callback_data=f"add_badge_{user_id}"))

    bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
# значки - кнопки для редактирования
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_badges_"))
def handle_edit_badges(call):
    user_id = int(call.data.split("_")[-1])
    badges = get_user_badges(user_id)

    if not badges:
        return bot.send_message(call.message.chat.id, "У пользователя нет значков.")

    markup = InlineKeyboardMarkup()
    for badge in badges:
        badge_id, badge_name, _, status, _ = badge
        markup.add(
            InlineKeyboardButton(
                text=f"{badge_name} ({status})",
                callback_data=f"editbadge|{user_id}|{badge_id}"
            )
        )

    bot.send_message(call.message.chat.id, "Выберите значок для редактирования:", reply_markup=markup)


#редактирование значка
@bot.callback_query_handler(func=lambda call: call.data.startswith("editbadge|"))
def handle_single_badge_edit(call):
    parts = call.data.split("|")
    user_id = int(parts[1])
    badge_id = int(parts[2])
    
    

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✏️ Изменить статус", callback_data=f"change_status|{user_id}|{badge_id}"),
        InlineKeyboardButton("📅 Изменить дату", callback_data=f"change_date|{user_id}|{badge_id}"),
        InlineKeyboardButton("🗑️ Удалить значок", callback_data=f"delete_badge|{user_id}|{badge_id}")
    )

    bot.send_message(call.message.chat.id, f"Выбран значок ID {badge_id}. Что вы хотите изменить?", reply_markup=markup)


#изменение даты регистраиции
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_date"))
def handle_change_date_prompt(call):
    try:
        _, user_id, badge_id = call.data.split("|")
        user_id = int(user_id)
        badge_id = int(badge_id)

        # Сохраняем временные данные
        bot.send_message(call.message.chat.id, "Введите новую дату для значка в формате ГГГГ-ММ-ДД:")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, lambda msg: update_date_step(msg, user_id, badge_id))

    except Exception as e:
        print(f"Ошибка при запросе даты: {e}")
        bot.send_message(call.message.chat.id, "Произошла ошибка при обработке запроса.")
        
    def update_date_step(message, user_id, badge_id):
     date_text = message.text.strip()

     # Проверим формат даты
     try:
         datetime.datetime.strptime(date_text, "%Y-%m-%d")
     except ValueError:
         return bot.send_message(message.chat.id, "❌ Неверный формат даты. Попробуйте снова (ГГГГ-ММ-ДД).")

     # Обновляем дату в базе
     update_badge_date(user_id, badge_id, date_text)
     bot.send_message(message.chat.id, f"📅 Дата значка успешно обновлена на {date_text}.")



#изменение статуса
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_status"))
def handle_change_status(call):
    try:
        _, user_id, badge_id = call.data.split("|")
        user_id = int(user_id)
        badge_id = int(badge_id)

        # Получаем текущий статус
        current_status = get_badge_status(user_id, badge_id)
        if not current_status:
            return bot.answer_callback_query(call.id, "Значок не найден.")

        # Меняем статус
        new_status = "не получен" if current_status == "получен" else "получен"
        update_badge_status(user_id, badge_id, new_status)

        bot.answer_callback_query(call.id, "Статус обновлён.")
        bot.send_message(call.message.chat.id, f"Статус значка изменён на <b>{new_status}</b>.", parse_mode="HTML")

    except Exception as e:
        print(f"Ошибка при смене статуса: {e}")
        bot.answer_callback_query(call.id, "Ошибка при смене статуса.")

#удаление значка
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_badge"))
def handle_delete_badge(call):
    try:
        _, user_id, badge_id = call.data.split("|")
        user_id = int(user_id)
        badge_id = int(badge_id)

        # Удаляем значок
        delete_user_badge(user_id, badge_id)

        bot.send_message(call.message.chat.id, "✅ Значок успешно удалён.")
        
        # (опционально) можно вернуть обновлённый список значков

    except Exception as e:
        print(f"Ошибка при удалении значка: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка при удалении значка.")


#добавление значка к пользователю
@bot.callback_query_handler(func=lambda call: call.data.startswith("add_badge_"))
def handle_add_badge_start(call):
    user_id = int(call.data.split("_")[-1])
    badges = get_all_badges()

    if not badges:
        bot.send_message(call.message.chat.id, "❌ Нет доступных значков для добавления.")
        return

    markup = InlineKeyboardMarkup()
    for badge_id, badge_name, _ in badges:
        callback_data = f"select_badge|{user_id}|{badge_id}"
        markup.add(InlineKeyboardButton(text=badge_name, callback_data=callback_data))

    bot.send_message(call.message.chat.id, f"Выберите значок для добавления пользователю ID {user_id}:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_badge|"))
def handle_select_badge(call):
    try:
        _, user_id, badge_id = call.data.split("|")
        user_id = int(user_id)
        badge_id = int(badge_id)

        status = "не получен"
        date_received = datetime.datetime.now()
        add_existing_badge_to_user(user_id, badge_id, status, date_received)

        # Получаем имя значка по ID
        badge_name = get_badge_name_by_id(badge_id)  # напиши эту функцию если нет

        bot.send_message(call.message.chat.id, f"✅ Значок '{badge_name}' добавлен пользователю.")
    except Exception as e:
        print(f"Ошибка при добавлении значка: {e}")
        bot.send_message(call.message.chat.id, "❌ Произошла ошибка при добавлении значка.")





#редактирование юзера
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_user_"))
def edit_user_menu(call):
    user_id = int(call.data.split("_")[2])
    user = get_user_by_id(user_id)

    if not user:
        return bot.send_message(call.message.chat.id, "❌ Пользователь не найден.")

    username = user[1]  
    

    # кнопки для редактирования
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✏️ Изменить логин", callback_data=f"change_username_{user_id}"),
        InlineKeyboardButton("🔒 Изменить пароль", callback_data=f"change_password_{user_id}")
    )
    markup.row(
        InlineKeyboardButton("🗑️ Удалить пользователя", callback_data=f"delete_user_{user_id}")
    )
    

    text = f"👤 Редактирование пользователя {username}:\n\n"
    bot.send_message(call.message.chat.id, text, reply_markup=markup)

#изменение логина 
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_username_"))
def ask_new_username(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "Введите новый логин:")
    bot.register_next_step_handler(msg, process_new_username, user_id)
def process_new_username(message, user_id):
    new_username = message.text.strip()

    if not new_username:
        bot.send_message(message.chat.id, "❌ Логин не может быть пустым.")
        return

    update_username(user_id, new_username)
    bot.send_message(message.chat.id, f"✅ Логин успешно обновлён на: {new_username}")
    
#изменение пароля 
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_password_"))
def ask_new_password(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "Введите новый пароль:")
    bot.register_next_step_handler(msg, process_new_password, user_id)

def process_new_password(message, user_id):
    new_password = message.text.strip()

    if not new_password:
        bot.send_message(message.chat.id, "❌ Пароль не может быть пустым.")
        return

    # Хэшируем пароль
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

    update_password(user_id, hashed_password)
    bot.send_message(message.chat.id, "✅ Пароль успешно обновлён.")

#удаление пользователя точно???
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_user_"))
def delete_user_handler(call):
    user_id = int(call.data.split("_")[2])

    # Подтверждение удаления
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_delete_{user_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")
    )
    bot.send_message(call.message.chat.id, f"Вы уверены, что хотите удалить пользователя с ID {user_id}?", reply_markup=markup)
#точно, брат
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_"))
def confirm_delete_user(call):
    user_id = int(call.data.split("_")[2])

    delete_user_from_db(user_id)
    bot.send_message(call.message.chat.id, f"🗑️ Пользователь с ID {user_id} был удалён.")
#отмена, брат
@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete(call):
    bot.send_message(call.message.chat.id, "❌ Удаление отменено.")






#нахождение по логину
@bot.message_handler(func=lambda message: message.text == "🔍 Найти участника по логину")
def search_user_by_login_prompt(message):
    if message.from_user.id not in admin_sessions:
        return bot.send_message(message.chat.id, "Вы не авторизованы как админ.")
    
    bot.send_message(message.chat.id, "Введите логин пользователя:")
    bot.register_next_step_handler(message, search_user_by_login)

def search_user_by_login(message):
    username = message.text.strip().lower()  # 👈 логин приводим к нижнему регистру
    user = get_user_by_username(username)
    
    if user:
        user_id, username, hashed_password, tg_id = user[0], user[1], user[2],user[3]
        badges = get_user_badges_by_telegram_id(tg_id)

        if badges:
            badges_text = "\n".join([f"🏅 {badge_name} — {status} (Дата: {date_received})" for badge_name, _, status, date_received in badges])
        else:
            badges_text = "Нет значков."

        text = (
            f"👤 Пользователь:\n"
            f"Ник: <b>{username}</b>\n"
            f"Хэшированный пароль: <b>{hashed_password}</b>\n"
            f"Telegram id: <b>{tg_id}</b>\n"
            f"Количество значков: <b>{len(badges)}</b>\n\n"
            f"🎖️ Значки:\n{badges_text}"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data=f"edit_user_{user_id}"))
        markup.add(InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data=f"delete_user_{user_id}"))
        markup.add(InlineKeyboardButton(text="🎖️ Редактировать значки", callback_data=f"edit_badges_{user_id}"))
        markup.add(InlineKeyboardButton(text="➕ Добавить значок", callback_data=f"add_badge_{user_id}"))

        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ Пользователь с таким логином не найден. Попробуйте ещё раз.")



@bot.callback_query_handler(func=lambda call: True)
def debug_callback(call):
    print(f"CALLBACK DATA: {call.data}")


bot.polling(none_stop=True)
