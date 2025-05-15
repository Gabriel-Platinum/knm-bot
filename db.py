import pymysql
from config import DB_CONFIG
import bcrypt

def connect_db():
    return pymysql.connect(**DB_CONFIG)

def link_telegram_id(user_id, telegram_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET telegram_id = %s
                WHERE id = %s AND telegram_id IS NULL
            """, (telegram_id, user_id))
            conn.commit()
    finally:
        conn.close()

               
def get_user_badges_by_telegram_id(telegram_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.name, b.image_path, ub.status, ub.date_received
                FROM users u
                JOIN user_badges ub ON u.id = ub.user_id
                JOIN badges b ON ub.badge_id = b.id
                WHERE u.telegram_id = %s
            """, (telegram_id,))
            return cursor.fetchall()
    finally:
        conn.close()


        
def get_user_badges(user_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.id, b.name, b.image_path, ub.status, ub.date_received
                FROM user_badges ub
                JOIN badges b ON ub.badge_id = b.id
                WHERE ub.user_id = %s
            """, (user_id,))
            return cursor.fetchall()
    finally:
        conn.close()

def get_badge_status(user_id, badge_id):
    connection = connect_db()
    with connection.cursor() as cursor:
        sql = "SELECT status FROM user_badges WHERE user_id = %s AND badge_id = %s"
        cursor.execute(sql, (user_id, badge_id))
        result = cursor.fetchone()
    connection.close()
    return result[0] if result else None

def update_badge_status(user_id, badge_id, new_status):
    connection = connect_db()
    with connection.cursor() as cursor:
        sql = "UPDATE user_badges SET status = %s WHERE user_id = %s AND badge_id = %s"
        cursor.execute(sql, (new_status, user_id, badge_id))
    connection.commit()
    connection.close()

def update_badge_date(user_id, badge_id, new_date):
    connection = connect_db()
    with connection.cursor() as cursor:
        sql = "UPDATE user_badges SET date_received = %s WHERE user_id = %s AND badge_id = %s"
        cursor.execute(sql, (new_date, user_id, badge_id))
    connection.commit()
    connection.close()

def delete_user_badge(user_id, badge_id):
    connection = connect_db()
    with connection.cursor() as cursor:
        sql = "DELETE FROM user_badges WHERE user_id = %s AND badge_id = %s"
        cursor.execute(sql, (user_id, badge_id))
    connection.commit()
    connection.close()


def get_all_badges():
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name, image_path FROM badges")
            badges = cursor.fetchall()
        return badges
    finally:
        connection.close()

      
def get_all_users():
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username FROM users")
            return cursor.fetchall() 
    finally:
        conn.close()


def get_user_by_username(username):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, password, telegram_id FROM users WHERE username = %s
            """, (username,))
            return cursor.fetchone()
    finally:
        conn.close()



def get_admin_by_username(username):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, password_hash FROM admins WHERE username = %s", (username,))
            return cursor.fetchone()  # вернёт (id, password_hash) или None
    finally:
        conn.close()
        
def add_user_to_db(username, password):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            # Сначала проверяем, есть ли уже пользователь с таким username
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone() is not None:
                return False  # Пользователь уже существует

            # Если нет — хэшируем пароль и добавляем
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, password_hash)
            )
            conn.commit()
            return True  # Успешно добавлен
    finally:
        conn.close()

def delete_user_from_db(user_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            # Удалим сначала все связанные записи из других таблиц (если есть связи по foreign key)
            cursor.execute("DELETE FROM user_badges WHERE user_id = %s", (user_id,))
            # Затем саму запись из users
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, password, telegram_id FROM users WHERE id=%s", (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()
        
def update_username(user_id, new_username):
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE users SET username = %s WHERE id = %s"
            cursor.execute(sql, (new_username, user_id))
        connection.commit()
    finally:
        connection.close()

def update_password(user_id, hashed_password):
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            sql = "UPDATE users SET password = %s WHERE id = %s"
            cursor.execute(sql, (hashed_password, user_id))
        connection.commit()
    finally:
        connection.close()
        
def add_existing_badge_to_user(user_id, badge_id, status, date_received):
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            # Проверяем, есть ли уже такой значок у пользователя
            cursor.execute(
                "SELECT * FROM user_badges WHERE user_id = %s AND badge_id = %s",
                (user_id, badge_id)
            )
            existing = cursor.fetchone()

            if existing:
                # Можно здесь обновить, если хочешь перезаписать
                raise ValueError("У пользователя уже есть этот значок.")

            # Добавляем новую запись
            cursor.execute(
                "INSERT INTO user_badges (user_id, badge_id, status, date_received) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, badge_id, status, date_received)
            )
            connection.commit()
    finally:
        connection.close()
        
def get_badge_name_by_id(badge_id):
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM badges WHERE id = %s", (badge_id,))
            result = cursor.fetchone()
            if result:
                return result[0]  # т.к. fetchone() возвращает кортеж
            else:
                return "Неизвестный значок"
    except Exception as e:
        print(f"Ошибка при получении названия значка: {e}")
        return "Ошибка"
    finally:
        connection.close()



