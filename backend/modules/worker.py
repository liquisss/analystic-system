from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
import json
import traceback


class FileLoaderWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, paths, session):
        super().__init__()
        self.paths   = paths
        self.session = session

    def run(self):
        try:
            from modules.loader import load_file
            loaded = []
            total  = len(self.paths)

            for i, path in enumerate(self.paths):
                result = load_file(path)

                self.progress.emit(json.dumps({
                    "action":  "file_loading_progress",
                    "current": i + 1,
                    "total":   total,
                    "name":    result['name'],
                }))

                if not result['error']:
                    safe_name = result['name'].replace('.', '_')
                    self.session.save_raw(safe_name, result)
                    print(f"[Loader] загружен: {result['name']} ({len(result['text'])} символов)")

                loaded.append({
                    "name":  result['name'],
                    "ext":   result['ext'],
                    "size":  len(result['text']),
                    "error": result['error']
                })

            self.finished.emit(json.dumps({
                "action": "files_selected",
                "files":  loaded
            }))

        except Exception as e:
            traceback.print_exc()
            self.error.emit(json.dumps({"error": str(e)}))


class NatashaWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, documents: list, settings: dict,
                 thesaurus_raw: Optional[dict] = None):
        """
        documents     — список raw-документов из session.load_raw_all()
        settings      — настройки Natasha из UI (без ключа 'thesaurus')
        thesaurus_raw — { "канон": ["вариант1", ...] } или None
        """
        super().__init__()
        self.documents     = documents
        self.settings      = settings
        self.thesaurus_raw = thesaurus_raw

    def run(self):
        try:
            from modules.natasha_processor import (
                process_document,
                build_thesaurus_lookup,
            )

            total = len(self.documents)

            # Строим lookup тезауруса один раз (дорогая операция — лемматизация синонимов)
            thesaurus_lookup = None
            if self.thesaurus_raw and isinstance(self.thesaurus_raw, dict) \
                    and len(self.thesaurus_raw) > 0:
                print(f"[NatashaWorker] строим тезаурус: {len(self.thesaurus_raw)} записей")
                thesaurus_lookup = build_thesaurus_lookup(self.thesaurus_raw)

            results = []

            for i, raw in enumerate(self.documents):
                if raw.get('error'):
                    print(f"[NatashaWorker] пропуск {raw.get('name','?')} — ошибка загрузки")
                    continue

                self.progress.emit(json.dumps({
                    "action":  "natasha_progress",
                    "current": i + 1,
                    "total":   total,
                    "name":    raw['name'],
                }))

                # process_document возвращает text_raw + text_clean оба поля
                result = process_document(raw, self.settings, thesaurus_lookup)
                results.append(result)

            final = {
                'documents':         results,
                'total_tokens':      sum(r['tokens_count'] for r in results),
                'total_docs':        len(results),
                'thesaurus_applied': thesaurus_lookup is not None,
                'thesaurus_entries': len(self.thesaurus_raw) if self.thesaurus_raw else 0,
            }
            self.finished.emit(json.dumps(final, ensure_ascii=False))

        except Exception as e:
            traceback.print_exc()
            self.error.emit(json.dumps({"error": str(e)}))


class BERTopicWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, natasha_data: dict, settings: dict):
        super().__init__()
        self.natasha_data = natasha_data
        self.settings     = settings

    def run(self):
        try:
            self.progress.emit(json.dumps({
                "action": "bertopic_progress",
                "stage":  "Загрузка embedding модели..."
            }))

            from modules.bertopic_processor import run_bertopic, build_vosviewer_json
            result   = run_bertopic(self.settings, self.natasha_data)
            vos_data = build_vosviewer_json(result)
            result['vos_data'] = vos_data

            self.finished.emit(json.dumps(result, ensure_ascii=False))

        except Exception as e:
            traceback.print_exc()
            self.error.emit(json.dumps({"error": str(e)}))
