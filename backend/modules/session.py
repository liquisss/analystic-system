import os
import json
import uuid
import shutil
from datetime import datetime

TEMP_DIR = os.path.join(os.path.dirname(__file__), '..', 'temp')


class Session:
    def __init__(self):
        self.session_id = uuid.uuid4().hex[:8]
        self.root        = os.path.join(TEMP_DIR, f"session_{self.session_id}")
        self.raw_dir     = os.path.join(self.root, 'raw')
        self.natasha_dir = os.path.join(self.root, 'natasha')
        self.bertopic_dir = os.path.join(self.root, 'bertopic')
        for d in [self.raw_dir, self.natasha_dir, self.bertopic_dir]:
            os.makedirs(d, exist_ok=True)
        print(f"[Session] создана: {self.session_id}")

    def save_raw(self, name: str, data: dict):
        """Обычный файл — отдельный JSON."""
        path = os.path.join(self.raw_dir, f"{name}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_raw_dataset(self, documents: list):
        """
        Датасет из CSV/XLSX — один JSONL файл.
        Намного быстрее чем 6000 отдельных json.
        """
        path = os.path.join(self.raw_dir, '_dataset.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')
        print(f"[Session] датасет сохранён: {len(documents)} документов → _dataset.jsonl")

    def load_raw_all(self) -> list[dict]:
        """Читает JSONL датасет + обычные JSON файлы."""
        results = []

        # JSONL датасет (приоритет — загружаем первым)
        dataset_path = os.path.join(self.raw_dir, '_dataset.jsonl')
        if os.path.exists(dataset_path):
            with open(dataset_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        results.append(json.loads(line))
            print(f"[Session] датасет загружен: {len(results)} документов")

        # Обычные файлы
        for fname in os.listdir(self.raw_dir):
            if fname.endswith('.json'):
                with open(os.path.join(self.raw_dir, fname), encoding='utf-8') as f:
                    results.append(json.load(f))

        return results

    def save_natasha(self, data: dict):
        """JSONL для документов — не держим всё в памяти."""
        docs = data.get('documents', [])
        meta = {k: v for k, v in data.items() if k != 'documents'}

        with open(os.path.join(self.natasha_dir, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)

        with open(os.path.join(self.natasha_dir, 'documents.jsonl'), 'w', encoding='utf-8') as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        print(f"[Session] natasha сохранена: {len(docs)} документов")

    def load_natasha(self) -> dict:
        path_meta = os.path.join(self.natasha_dir, 'meta.json')
        path_docs = os.path.join(self.natasha_dir, 'documents.jsonl')
        path_old  = os.path.join(self.natasha_dir, 'processed.json')

        # Обратная совместимость со старым форматом
        if os.path.exists(path_old) and not os.path.exists(path_docs):
            with open(path_old, encoding='utf-8') as f:
                return json.load(f)

        with open(path_meta, encoding='utf-8') as f:
            meta = json.load(f)

        docs = []
        with open(path_docs, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))

        return {**meta, 'documents': docs}

    def save_bertopic(self, data: dict):
        path = os.path.join(self.bertopic_dir, 'topics.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_bertopic(self) -> dict:
        path = os.path.join(self.bertopic_dir, 'topics.json')
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)
        print(f"[Session] очищена: {self.session_id}")


def cleanup_old_sessions(max_age_hours: int = 24):
    if not os.path.exists(TEMP_DIR):
        return
    now = datetime.now().timestamp()
    for name in os.listdir(TEMP_DIR):
        path = os.path.join(TEMP_DIR, name)
        age_hours = (now - os.path.getmtime(path)) / 3600
        if age_hours > max_age_hours:
            shutil.rmtree(path, ignore_errors=True)
            print(f"[Session] удалена старая сессия: {name}")
