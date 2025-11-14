import random
from typing import Dict, List


class QuizGenerator:
    """Класс для генерации квизов"""

    def __init__(self, data_loader):
        self.data_loader = data_loader

    def generate_translation_quiz(self, verb_data: Dict) -> List[str]:
        """
        Генерация квиза №1: инфинитив → перевод
        Возвращает список из 4 вариантов (1 правильный + 3 неправильных)
        """
        correct = verb_data['translation_ru']
        wrong = self.data_loader.get_random_translations(exclude=correct, count=3)

        options = [correct] + wrong
        random.shuffle(options)

        return options

    def generate_infinitivo_quiz(self, verb_data: Dict) -> List[str]:
        """
        Генерация квиза №2: перевод → инфинитив
        Возвращает список из 4 вариантов (1 правильный + 3 неправильных)
        """
        correct = verb_data['infinitivo']
        wrong = self.data_loader.get_random_infinitivos(exclude=correct, count=3)

        options = [correct] + wrong
        random.shuffle(options)

        return options
