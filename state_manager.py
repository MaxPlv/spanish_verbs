import sqlite3
from typing import List, Optional
from datetime import datetime


class StateManager:
    """Класс для управления состоянием пользователей в SQLite"""

    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT
            )
        ''')

        # Таблица глаголов дня
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verb_of_day (
                user_id INTEGER PRIMARY KEY,
                infinitivo TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Таблица отправленных времён
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_tenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tense TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        conn.commit()
        conn.close()

    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        conn.close()
        return result is not None

    def create_user(self, user_id: int):
        """Создание нового пользователя"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)',
            (user_id, datetime.now().isoformat())
        )

        conn.commit()
        conn.close()

    def get_all_users(self) -> List[int]:
        """Получить список всех пользователей"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('SELECT user_id FROM users')
        users = [row[0] for row in cursor.fetchall()]

        conn.close()
        return users

    def set_verb_of_the_day(self, user_id: int, infinitivo: str):
        """Установить глагол дня для пользователя"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()

        # Проверяем, есть ли уже глагол на сегодня
        cursor.execute(
            'SELECT date FROM verb_of_day WHERE user_id = ?',
            (user_id,)
        )
        result = cursor.fetchone()

        if result and result[0] == today:
            # Глагол на сегодня уже есть, не обновляем
            conn.close()
            return

        # Устанавливаем новый глагол дня
        cursor.execute(
            'INSERT OR REPLACE INTO verb_of_day (user_id, infinitivo, date) VALUES (?, ?, ?)',
            (user_id, infinitivo, today)
        )

        # Очищаем отправленные времена для нового дня
        cursor.execute(
            'DELETE FROM sent_tenses WHERE user_id = ? AND date != ?',
            (user_id, today)
        )

        conn.commit()
        conn.close()

    def get_current_verb(self, user_id: int) -> Optional[str]:
        """Получить текущий глагол дня для пользователя"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()

        cursor.execute(
            'SELECT infinitivo FROM verb_of_day WHERE user_id = ? AND date = ?',
            (user_id, today)
        )
        result = cursor.fetchone()

        conn.close()
        return result[0] if result else None

    def get_sent_tenses(self, user_id: int) -> List[str]:
        """Получить список отправленных времён для пользователя на сегодня"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()

        cursor.execute(
            'SELECT tense FROM sent_tenses WHERE user_id = ? AND date = ?',
            (user_id, today)
        )
        tenses = [row[0] for row in cursor.fetchall()]

        conn.close()
        return tenses

    def mark_tense_sent(self, user_id: int, tense: str):
        """Отметить время как отправленное"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()

        cursor.execute(
            'INSERT INTO sent_tenses (user_id, tense, date) VALUES (?, ?, ?)',
            (user_id, tense, today)
        )

        conn.commit()
        conn.close()

    def reset_daily_progress(self, user_id: int):
        """Сброс ежедневного прогресса (для тестирования)"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM verb_of_day WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM sent_tenses WHERE user_id = ?', (user_id,))

        conn.commit()
        conn.close()
