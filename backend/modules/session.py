import os
import json
import uuid
import shutil
from datetime import datetime

TEMP_DIR = os.path.join(os.path.dirname(__file__), '..', 'temp')


class Session:
    def __init__(self):
        self.session_id = uuid.uuid4().hex[:8]
        self.root = os.path.join(TEMP_DIR, f"session_{self.session_id}")

        # Создаём папки для каждого этапа
        self.raw_dir = os.path.join(self.root, 'raw')
        self.natasha_dir = os.path.join(self.root, 'natasha')
        self.bertopic_dir = os.path.join(self.root, 'bertopic')

        for d in [self.raw_dir, self.natasha_dir, self.bertopic_dir]:
            os.makedirs(d, exist_ok=True)

        print(f"[Session] создана: {self.session_id}")

    def save_raw(self, name: str, data: dict):
        """Сохраняет сырой текст документа"""
        path = os.path.join(self.raw_dir, f"{name}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_raw_all(self) -> list[dict]:
        """Читает все сырые документы"""
        results = []
        for fname in os.listdir(self.raw_dir):
            if fname.endswith('.json'):
                with open(os.path.join(self.raw_dir, fname), encoding='utf-8') as f:
                    results.append(json.load(f))
        return results

    def save_natasha(self, data: dict):
        path = os.path.join(self.natasha_dir, 'processed.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_natasha(self) -> dict:
        path = os.path.join(self.natasha_dir, 'processed.json')
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def save_bertopic(self, data: dict):
        path = os.path.join(self.bertopic_dir, 'topics.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_bertopic(self) -> dict:
        path = os.path.join(self.bertopic_dir, 'topics.json')
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def cleanup(self):
        """Удаляет временные файлы сессии"""
        shutil.rmtree(self.root, ignore_errors=True)
        print(f"[Session] очищена: {self.session_id}")


def cleanup_old_sessions(max_age_hours: int = 24):
    """Удаляет сессии старше N часов — вызывать при старте"""
    if not os.path.exists(TEMP_DIR):
        return
    now = datetime.now().timestamp()
    for name in os.listdir(TEMP_DIR):
        path = os.path.join(TEMP_DIR, name)
        age_hours = (now - os.path.getmtime(path)) / 3600
        if age_hours > max_age_hours:
            shutil.rmtree(path, ignore_errors=True)
            print(f"[Session] удалена старая сессия: {name}")