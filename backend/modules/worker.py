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
            total = len(self.paths)

            for i, path in enumerate(self.paths):
                print(f"[Loader] загружаем: {path}")
                result = load_file(path)
                print(f"[Loader] результат: name={result.get('name')}, "
                      f"is_dataset={result.get('is_dataset')}, "
                      f"error={result.get('error')}")

                self.progress.emit(json.dumps({
                    "action": "file_loading_progress",
                    "current": i + 1,
                    "total": total,
                    "name": result['name'],
                }))

                if result.get('is_dataset'):
                    if result.get('missing_cols'):
                        print(f"[Loader] missing_cols: {result.get('columns')}")
                        loaded.append({
                            "name": result['name'],
                            "ext": result['ext'],
                            "size": 0,
                            "error": None,
                            "is_dataset": True,
                            "missing_cols": True,
                            "columns": result.get('columns', []),
                        })
                        continue

                    docs = result.get('documents', [])
                    print(f"[Loader] датасет: {len(docs)} документов, сохраняем...")
                    self.session.save_raw_dataset(docs)
                    print(f"[Loader] датасет сохранён")

                    loaded.append({
                        "name": result['name'],
                        "ext": result['ext'],
                        "size": 0,  # у датасета нет размера в байтах
                        "error": None,
                        "is_dataset": True,
                        "doc_count": len(docs),
                    })
                    continue

                # Обычный файл
                if not result.get('error'):
                    safe_name = result['name'].replace('.', '_')
                    self.session.save_raw(safe_name, result)
                    print(f"[Loader] файл сохранён: {result['name']}")

                loaded.append({
                    "name": result['name'],
                    "ext": result['ext'],
                    "size": len(result.get('text', '')),
                    "error": result.get('error'),
                    "is_dataset": False,
                })

            self.finished.emit(json.dumps({
                "action": "files_selected",
                "files": loaded,
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
        super().__init__()
        self.documents     = documents
        self.settings      = settings
        self.thesaurus_raw = thesaurus_raw

    def run(self):
        try:
            from modules.natasha_processor import process_document, build_thesaurus_lookup

            total = len(self.documents)
            print(f"[NatashaWorker] запуск: {total} документов")

            if total == 0:
                self.finished.emit(json.dumps({
                    'documents': [], 'total_tokens': 0,
                    'total_docs': 0, 'thesaurus_applied': False,
                    'thesaurus_entries': 0, 'fast_mode': False,
                }))
                return

            has_fast = any(d.get('fast_mode') for d in self.documents)
            print(f"[NatashaWorker] fast_mode={has_fast}")

            self.progress.emit(json.dumps({
                "action": "natasha_progress",
                "current": 0,
                "total": total,
                "name": "Инициализация...",
                "fast_mode": has_fast,
            }))

            thesaurus_lookup = None
            if self.thesaurus_raw and isinstance(self.thesaurus_raw, dict) \
                    and len(self.thesaurus_raw) > 0:
                thesaurus_lookup = build_thesaurus_lookup(self.thesaurus_raw)

            results = []
            report_every = 50 if total > 200 else 1

            for i, raw in enumerate(self.documents):
                if raw.get('error'):
                    print(f"[NatashaWorker] пропуск {raw.get('name')} — ошибка")
                    continue

                if i % report_every == 0 or i == total - 1:
                    display = (
                        f"обработано {i + 1}/{total}"
                        if raw.get('fast_mode')
                        else raw.get('name', f'doc_{i}')
                    )
                    self.progress.emit(json.dumps({
                        "action": "natasha_progress",
                        "current": i + 1,
                        "total": total,
                        "name": display,
                        "fast_mode": raw.get('fast_mode', False),
                    }))

                try:
                    result = process_document(raw, self.settings, thesaurus_lookup)
                    results.append(result)
                except Exception as doc_err:
                    print(f"[NatashaWorker] ошибка документа {raw.get('name')}: {doc_err}")
                    traceback.print_exc()
                    continue

            print(f"[NatashaWorker] готово: {len(results)} документов")

            final = {
                'documents': results,
                'total_tokens': sum(r['tokens_count'] for r in results),
                'total_docs': len(results),
                'thesaurus_applied': thesaurus_lookup is not None,
                'thesaurus_entries': len(self.thesaurus_raw) if self.thesaurus_raw else 0,
                'fast_mode': has_fast,
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
