import logging
import os
import sys
from datetime import time, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz
from dotenv import load_dotenv

from data_loader import VerbDataLoader
from state_manager import StateManager
from quiz_generator import QuizGenerator

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TIMEZONE = pytz.timezone('Europe/Moscow')  # Измените на ваш часовой пояс


class SpanishVerbBot:
    def __init__(self):
        self.data_loader = VerbDataLoader('verbs.csv')
        self.state_manager = StateManager('bot_state.db')
        self.quiz_generator = QuizGenerator(self.data_loader)
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id

        # Инициализация пользователя
        if not self.state_manager.user_exists(user_id):
            self.state_manager.create_user(user_id)
            await update.message.reply_text(
                "¡Hola! 👋\n\n"
                "Я помогу тебе учить испанские глаголы!\n\n"
                "Каждый день в 09:00 я буду выбирать новый глагол дня.\n"
                "Затем в течение дня ты получишь:\n"
                "- Квизы на перевод (в 10:00 и 11:00)\n"
                "- Все формы глагола по временам (начиная с 13:00, каждый час)\n\n"
                "Используй /status чтобы узнать текущий глагол дня."
            )
        else:
            await update.message.reply_text(
                "С возвращением! 👋\n\n"
                "Используй /status чтобы узнать текущий глагол дня."
            )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user_id = update.effective_user.id

        if not self.state_manager.user_exists(user_id):
            await update.message.reply_text(
                "Используй /start чтобы начать!"
            )
            return

        current_verb = self.state_manager.get_current_verb(user_id)

        if current_verb:
            verb_data = self.data_loader.get_verb_by_infinitivo(current_verb)
            if verb_data:
                await update.message.reply_text(
                    f"📚 Глагол дня:\n\n"
                    f"🇪🇸 {verb_data['infinitivo']}\n"
                    f"🇷🇺 {verb_data['translation_ru']}"
                )
        else:
            await update.message.reply_text(
                "Глагол дня ещё не выбран. Жди утреннего сообщения в 09:00!"
            )

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда для прохождения дневного флоу с интервалом 1 минута"""
        user_id = update.effective_user.id

        if not self.state_manager.user_exists(user_id):
            self.state_manager.create_user(user_id)

        await update.message.reply_text(
            "🧪 Запускаю тестовый дневной флоу!\n\n"
            "Ты получишь:\n"
            "- Глагол дня (сейчас)\n"
            "- Квиз №1 (через 1 минуту)\n"
            "- Квиз №2 (через 2 минуты)\n"
            "- Времена глаголов (с 3-й минуты, каждую минуту)"
        )

        # Сбрасываем состояние времен для пользователя
        self.state_manager.reset_sent_tenses(user_id)

        # Отправляем глагол дня немедленно
        await self.send_verb_of_the_day(user_id)

        # Планируем задачи с интервалом 1 минута
        now = datetime.now(TIMEZONE)

        # Квиз №1 через 1 минуту
        self.scheduler.add_job(
            self.send_quiz_1,
            DateTrigger(run_date=now + timedelta(minutes=1), timezone=TIMEZONE),
            args=[user_id],
            id=f"test_quiz1_{user_id}",
            replace_existing=True
        )

        # Квиз №2 через 2 минуты
        self.scheduler.add_job(
            self.send_quiz_2,
            DateTrigger(run_date=now + timedelta(minutes=2), timezone=TIMEZONE),
            args=[user_id],
            id=f"test_quiz2_{user_id}",
            replace_existing=True
        )

        # Времена глаголов - начиная с 3-й минуты, каждую минуту
        # Получаем количество доступных времен
        all_tenses = self.data_loader.get_tenses()
        for i, _ in enumerate(all_tenses):
            self.scheduler.add_job(
                self.send_next_tense,
                DateTrigger(run_date=now + timedelta(minutes=3 + i), timezone=TIMEZONE),
                args=[user_id],
                id=f"test_tense_{user_id}_{i}",
                replace_existing=True
            )

        logger.info(f"Test flow scheduled for user {user_id}")

    async def send_verb_of_the_day(self, user_id: int):
        """Отправка глагола дня (09:00)"""
        try:
            # Выбираем случайный глагол
            verb_data = self.data_loader.get_random_verb()

            # Сохраняем глагол дня для пользователя
            self.state_manager.set_verb_of_the_day(user_id, verb_data['infinitivo'])

            # Отправляем сообщение
            await self.application.bot.send_message(
                chat_id=user_id,
                text=f"📚 Глагол дня:\n\n🇪🇸 {verb_data['infinitivo']} — 🇷🇺 {verb_data['translation_ru']}"
            )

            logger.info(f"Sent verb of the day to user {user_id}: {verb_data['infinitivo']}")
        except Exception as e:
            logger.error(f"Error sending verb of the day to user {user_id}: {e}")

    async def send_quiz_1(self, user_id: int):
        """Отправка квиза №1: инфинитив → перевод (10:00)"""
        try:
            current_verb = self.state_manager.get_current_verb(user_id)
            if not current_verb:
                return

            verb_data = self.data_loader.get_verb_by_infinitivo(current_verb)
            if not verb_data:
                return

            # Генерируем квиз
            options = self.quiz_generator.generate_translation_quiz(verb_data)
            correct_answer = verb_data['translation_ru']

            # Создаём кнопки
            keyboard = []
            for option in options:
                callback_data = f"q1_{user_id}_{option == correct_answer}_{correct_answer}"
                keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.application.bot.send_message(
                chat_id=user_id,
                text=f"🎯 Квиз №1\n\nГлагол: {verb_data['infinitivo']}\nВыбери верный перевод:",
                reply_markup=reply_markup
            )

            logger.info(f"Sent quiz 1 to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending quiz 1 to user {user_id}: {e}")

    async def send_quiz_2(self, user_id: int):
        """Отправка квиза №2: перевод → инфинитив (11:00)"""
        try:
            current_verb = self.state_manager.get_current_verb(user_id)
            if not current_verb:
                return

            verb_data = self.data_loader.get_verb_by_infinitivo(current_verb)
            if not verb_data:
                return

            # Генерируем квиз
            options = self.quiz_generator.generate_infinitivo_quiz(verb_data)
            correct_answer = verb_data['infinitivo']

            # Создаём кнопки
            keyboard = []
            for option in options:
                callback_data = f"q2_{user_id}_{option == correct_answer}_{correct_answer}"
                keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.application.bot.send_message(
                chat_id=user_id,
                text=f"🎯 Квиз №2\n\nЗначение: {verb_data['translation_ru']}\nВыбери правильный инфинитив:",
                reply_markup=reply_markup
            )

            logger.info(f"Sent quiz 2 to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending quiz 2 to user {user_id}: {e}")

    async def send_next_tense(self, user_id: int):
        """Отправка следующего времени (начиная с 13:00, каждый час)"""
        try:
            current_verb = self.state_manager.get_current_verb(user_id)
            if not current_verb:
                return

            verb_data = self.data_loader.get_verb_by_infinitivo(current_verb)
            if not verb_data:
                return

            # Получаем список уже отправленных времён
            sent_tenses = self.state_manager.get_sent_tenses(user_id)

            # Получаем все доступные времена
            all_tenses = self.data_loader.get_tenses()

            # Находим следующее время
            next_tense = None
            for tense in all_tenses:
                if tense not in sent_tenses:
                    next_tense = tense
                    break

            if not next_tense:
                # Все времена уже отправлены
                return

            # Получаем формы для этого времени
            forms = self.data_loader.get_tense_forms(verb_data, next_tense)

            # Форматируем сообщение
            message = f"📖 {next_tense}\n\n"
            pronouns = ['yo', 'tú', 'él/ella', 'nosotros', 'vosotros', 'ellos/ellas']
            for pronoun, form in zip(pronouns, forms):
                message += f"{pronoun} — {form}\n"

            await self.application.bot.send_message(
                chat_id=user_id,
                text=message
            )

            # Отмечаем время как отправленное
            self.state_manager.mark_tense_sent(user_id, next_tense)

            logger.info(f"Sent tense {next_tense} to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending tense to user {user_id}: {e}")

    async def handle_quiz_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ответов на квизы"""
        query = update.callback_query
        await query.answer()

        try:
            # Валидация callback data
            data = query.data.split('_')

            # Проверяем минимальную длину (quiz_type, user_id, is_correct, correct_answer)
            if len(data) < 4:
                logger.warning(f"Invalid callback data format: {query.data}")
                await query.answer("Неверный формат данных", show_alert=True)
                return

            # Извлекаем и валидируем компоненты
            quiz_type = data[0]

            # Валидация типа квиза
            if quiz_type not in ['q1', 'q2']:
                logger.warning(f"Invalid quiz type: {quiz_type}")
                await query.answer("Неверный тип квиза", show_alert=True)
                return

            # Валидация user_id
            try:
                target_user_id = int(data[1])
            except ValueError:
                logger.warning(f"Invalid user_id in callback data: {data[1]}")
                await query.answer("Неверный формат данных", show_alert=True)
                return

            # Валидация is_correct
            if data[2] not in ['True', 'False']:
                logger.warning(f"Invalid is_correct value: {data[2]}")
                await query.answer("Неверный формат данных", show_alert=True)
                return

            is_correct = data[2] == 'True'
            correct_answer = '_'.join(data[3:])

            # Валидация correct_answer
            if not correct_answer or len(correct_answer) > 200:
                logger.warning(f"Invalid correct_answer: {correct_answer}")
                await query.answer("Неверный формат данных", show_alert=True)
                return

            # Проверяем, что пользователь отвечает на свой квиз
            if query.from_user.id != target_user_id:
                await query.answer("Это не твой квиз!", show_alert=True)
                return

            if is_correct:
                await query.edit_message_text(
                    text=query.message.text + f"\n\n✅ Верно!"
                )
            else:
                await query.edit_message_text(
                    text=query.message.text + f"\n\n❌ Неверно. Правильный ответ: {correct_answer}"
                )
        except Exception as e:
            logger.error(f"Error handling quiz callback: {e}")
            await query.answer("Произошла ошибка при обработке ответа", show_alert=True)

    def schedule_jobs(self):
        """Настройка расписания задач"""
        # Получаем всех пользователей
        users = self.state_manager.get_all_users()

        for user_id in users:
            # 09:00 - Глагол дня
            self.scheduler.add_job(
                self.send_verb_of_the_day,
                CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
                args=[user_id],
                id=f"verb_of_day_{user_id}",
                replace_existing=True
            )

            # 10:00 - Квиз №1
            self.scheduler.add_job(
                self.send_quiz_1,
                CronTrigger(hour=10, minute=0, timezone=TIMEZONE),
                args=[user_id],
                id=f"quiz1_{user_id}",
                replace_existing=True
            )

            # 11:00 - Квиз №2
            self.scheduler.add_job(
                self.send_quiz_2,
                CronTrigger(hour=11, minute=0, timezone=TIMEZONE),
                args=[user_id],
                id=f"quiz2_{user_id}",
                replace_existing=True
            )

            # 13:00-23:00 - Времена глаголов (каждый час)
            for hour in range(13, 24):
                self.scheduler.add_job(
                    self.send_next_tense,
                    CronTrigger(hour=hour, minute=0, timezone=TIMEZONE),
                    args=[user_id],
                    id=f"tense_{user_id}_{hour}",
                    replace_existing=True
                )

    def add_user_schedule(self, user_id: int):
        """Добавление расписания для нового пользователя"""
        # 09:00 - Глагол дня
        self.scheduler.add_job(
            self.send_verb_of_the_day,
            CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
            args=[user_id],
            id=f"verb_of_day_{user_id}",
            replace_existing=True
        )

        # 10:00 - Квиз №1
        self.scheduler.add_job(
            self.send_quiz_1,
            CronTrigger(hour=10, minute=0, timezone=TIMEZONE),
            args=[user_id],
            id=f"quiz1_{user_id}",
            replace_existing=True
        )

        # 11:00 - Квиз №2
        self.scheduler.add_job(
            self.send_quiz_2,
            CronTrigger(hour=11, minute=0, timezone=TIMEZONE),
            args=[user_id],
            id=f"quiz2_{user_id}",
            replace_existing=True
        )

        # 13:00-23:00 - Времена глаголов (каждый час)
        for hour in range(13, 24):
            self.scheduler.add_job(
                self.send_next_tense,
                CronTrigger(hour=hour, minute=0, timezone=TIMEZONE),
                args=[user_id],
                id=f"tense_{user_id}_{hour}",
                replace_existing=True
            )

    async def post_init(self, application: Application):
        """Инициализация после запуска бота"""
        self.application = application
        self.schedule_jobs()
        self.scheduler.start()
        logger.info("Bot initialized and scheduler started")

    def run(self):
        """Запуск бота"""
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
            logger.error("Please set TELEGRAM_BOT_TOKEN in your .env file or environment")
            sys.exit(1)

        try:
            # Создаём приложение
            application = Application.builder().token(TELEGRAM_TOKEN).post_init(self.post_init).build()

            # Добавляем обработчики
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CommandHandler("status", self.status_command))
            application.add_handler(CommandHandler("test", self.test_command))
            application.add_handler(CallbackQueryHandler(self.handle_quiz_callback))

            # Запускаем бота
            logger.info("Starting bot...")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            sys.exit(1)


if __name__ == '__main__':
    bot = SpanishVerbBot()
    bot.run()
