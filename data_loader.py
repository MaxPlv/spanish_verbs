import csv
import random
from typing import Dict, List, Optional


class VerbDataLoader:
    """Класс для загрузки и работы с данными глаголов из CSV"""

    def __init__(self, csv_file: str):
        self.csv_file = csv_file
        self.verbs: List[Dict] = []
        self.tenses: List[str] = []
        self.load_data()

    def load_data(self):
        """Загрузка данных из CSV файла"""
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.verbs = list(reader)

        # Определяем доступные времена из заголовков
        if self.verbs:
            # Получаем все ключи, которые содержат времена
            tense_keys = [key for key in self.verbs[0].keys() if '__' in key]
            # Извлекаем уникальные названия времён
            tenses_set = set()
            for key in tense_keys:
                tense_name = key.split('__')[0]
                tenses_set.add(tense_name)
            self.tenses = sorted(list(tenses_set))

    def get_random_verb(self) -> Dict:
        """Получить случайный глагол"""
        return random.choice(self.verbs)

    def get_verb_by_infinitivo(self, infinitivo: str) -> Optional[Dict]:
        """Получить глагол по инфинитиву"""
        for verb in self.verbs:
            if verb['infinitivo'] == infinitivo:
                return verb
        return None

    def get_tenses(self) -> List[str]:
        """Получить список всех времён"""
        return self.tenses

    def get_tense_forms(self, verb_data: Dict, tense: str) -> List[str]:
        """
        Получить все формы глагола для указанного времени
        Возвращает список форм: [1s, 2s, 3s, 1p, 2p, 3p]
        """
        forms = []
        for person in ['1s', '2s', '3s', '1p', '2p', '3p']:
            key = f"{tense}__{person}"
            forms.append(verb_data.get(key, '—'))
        return forms

    def get_all_verbs(self) -> List[Dict]:
        """Получить все глаголы"""
        return self.verbs

    def get_random_translations(self, exclude: str, count: int = 3) -> List[str]:
        """
        Получить случайные переводы, исключая указанный
        Используется для генерации вариантов ответов в квизах
        """
        available = [v['translation_ru'] for v in self.verbs if v['translation_ru'] != exclude]
        return random.sample(available, min(count, len(available)))

    def get_random_infinitivos(self, exclude: str, count: int = 3) -> List[str]:
        """
        Получить случайные инфинитивы, исключая указанный
        Используется для генерации вариантов ответов в квизах
        """
        available = [v['infinitivo'] for v in self.verbs if v['infinitivo'] != exclude]
        return random.sample(available, min(count, len(available)))
