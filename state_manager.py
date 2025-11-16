import sqlite3
from typing import List, Optional
from datetime import datetime
from contextlib import contextmanager


class StateManager:
    """Класс для управления состоянием пользователей в SQLite"""

    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для безопасной работы с соединением БД"""
        conn = sqlite3.connect(self.db_file, timeout=10.0)
        conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging для лучшей конкурентности
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Инициализация базы данных"""
        with self._get_connection() as conn:
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

    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result is not None

    def create_user(self, user_id: int):
        """Создание нового пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)',
                (user_id, datetime.now().isoformat())
            )

    def get_all_users(self) -> List[int]:
        """Получить список всех пользователей"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            users = [row[0] for row in cursor.fetchall()]
            return users

    def set_verb_of_the_day(self, user_id: int, infinitivo: str):
        """Установить глагол дня для пользователя"""
        with self._get_connection() as conn:
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

    def get_current_verb(self, user_id: int) -> Optional[str]:
        """Получить текущий глагол дня для пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()

            cursor.execute(
                'SELECT infinitivo FROM verb_of_day WHERE user_id = ? AND date = ?',
                (user_id, today)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def get_sent_tenses(self, user_id: int) -> List[str]:
        """Получить список отправленных времён для пользователя на сегодня"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()

            cursor.execute(
                'SELECT tense FROM sent_tenses WHERE user_id = ? AND date = ?',
                (user_id, today)
            )
            tenses = [row[0] for row in cursor.fetchall()]
            return tenses

    def mark_tense_sent(self, user_id: int, tense: str):
        """Отметить время как отправленное"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()

            cursor.execute(
                'INSERT INTO sent_tenses (user_id, tense, date) VALUES (?, ?, ?)',
                (user_id, tense, today)
            )

    def reset_daily_progress(self, user_id: int):
        """Сброс ежедневного прогресса (для тестирования)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM verb_of_day WHERE user_id = ?', (user_id,))
            cursor.execute('DELETE FROM sent_tenses WHERE user_id = ?', (user_id,))

    def reset_sent_tenses(self, user_id: int):
        """Сброс отправленных времён для пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()
            cursor.execute('DELETE FROM sent_tenses WHERE user_id = ? AND date = ?', (user_id, today))
