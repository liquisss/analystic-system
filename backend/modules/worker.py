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

                # Прогресс
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
    finished = pyqtSignal(str)  # JSON результат
    error    = pyqtSignal(str)  # JSON ошибки
    progress = pyqtSignal(str)  # JSON прогресса

    def __init__(self, documents, settings):
        super().__init__()
        self.documents = documents
        self.settings  = settings

    def run(self):
        try:
            from modules.natasha_processor import process_document, clean_text, split_into_chunks

            results = []
            total = len(self.documents)

            for i, raw in enumerate(self.documents):
                if raw.get('error'):
                    continue

                # Сообщаем прогресс в JS
                self.progress.emit(json.dumps({
                    "action":  "natasha_progress",
                    "current": i + 1,
                    "total":   total,
                    "name":    raw['name'],
                }))

                from modules.natasha_processor import process_document
                result = process_document(raw, self.settings)
                results.append(result)

            final = {
                'documents':    results,
                'total_tokens': sum(r['tokens_count'] for r in results),
                'total_docs':   len(results),
            }
            self.finished.emit(json.dumps(final))

        except Exception as e:
            traceback.print_exc()
            self.error.emit(json.dumps({"error": str(e)}))


class BERTopicWorker(QThread):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, natasha_data, settings):
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

            self.finished.emit(json.dumps(result))

        except Exception as e:
            traceback.print_exc()
            self.error.emit(json.dumps({"error": str(e)}))

