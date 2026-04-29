from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QFileDialog
import json
import os
from modules.loader import load_file
from modules.session import Session, cleanup_old_sessions
from modules.worker import NatashaWorker, BERTopicWorker, FileLoaderWorker
from modules.report_generator import generate_report
from modules.bertopic_processor import build_vosviewer_json
import shutil

class Bridge(QObject):
    result_ready   = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        cleanup_old_sessions()
        self.session = Session()
        self._natasha_worker  = None
        self._bertopic_worker = None
        self._file_worker     = None

    @pyqtSlot()
    def open_file_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            None, "Выберите документы", "",
            "Документы (*.pdf *.docx *.txt *.csv)"
        )
        if not paths:
            self.result_ready.emit(json.dumps({
                "action": "files_selected", "files": []
            }))
            return

        self.result_ready.emit(json.dumps({
            "action": "file_loading_started",
            "total":  len(paths)
        }))

        self._file_worker = FileLoaderWorker(paths, self.session)

        def on_progress(data):
            self.result_ready.emit(data)

        def on_finished(data):
            self.result_ready.emit(data)

        def on_error(data):
            err = json.loads(data)
            self.error_occurred.emit(json.dumps({
                "action": "files_selected",
                "error":  err['error']
            }))

        self._file_worker.progress.connect(on_progress)
        self._file_worker.finished.connect(on_finished)
        self._file_worker.error.connect(on_error)
        self._file_worker.start()

    @pyqtSlot(str)
    def run_natasha(self, settings_json: str):
        """
        settings_json может содержать ключ 'thesaurus':
            { ..., "thesaurus": { "евросоюз": ["ес", "eu"], ... } }
        или 'thesaurus': null если тезаурус не задан.

        Тезаурус извлекается ДО передачи settings в NatashaWorker,
        чтобы worker получил чистые настройки, а тезаурус передаётся отдельно.
        """
        try:
            settings      = json.loads(settings_json)
            # Извлекаем тезаурус — он не нужен внутри Natasha-настроек
            thesaurus_raw = settings.pop('thesaurus', None)
            documents     = self.session.load_raw_all()

            if not documents:
                self.error_occurred.emit(json.dumps({
                    "action": "natasha_done",
                    "error":  "Нет загруженных документов"
                }))
                return

            thesaurus_entries = len(thesaurus_raw) if thesaurus_raw else 0
            print(f"[Bridge] Natasha: {len(documents)} документов, "
                  f"тезаурус: {thesaurus_entries} записей")

            self._natasha_worker = NatashaWorker(
                documents, settings, thesaurus_raw=thesaurus_raw
            )

            def on_progress(data):
                self.result_ready.emit(json.dumps({
                    **json.loads(data),
                    "action": "natasha_progress"
                }))

            def on_finished(data):
                result = json.loads(data)
                self.session.save_natasha(result)
                self.result_ready.emit(json.dumps({
                    "action":            "natasha_done",
                    "total_docs":        result['total_docs'],
                    "total_tokens":      result['total_tokens'],
                    "thesaurus_applied": result.get('thesaurus_applied', False),
                    "thesaurus_entries": result.get('thesaurus_entries', 0),
                    # Статистика для PageNatasha (только числа)
                    "documents": [
                        {
                            "name":           d['name'],
                            "tokens_count":   d['tokens_count'],
                            "chunks_count":   d['chunks_count'],
                            "entities_count": len(d.get('entities', [])),
                            "dates_count":    len(d.get('dates', [])),
                        }
                        for d in result['documents']
                    ],
                    # Полные данные для TopicDetailModal (NER-бейджи)
                    "natasha_documents": [
                        {
                            "name":         d['name'],
                            "tokens_count": d['tokens_count'],
                            "chunks_count": d['chunks_count'],
                            "entities":     d.get('entities', []),
                            "dates":        d.get('dates', []),
                        }
                        for d in result['documents']
                    ],
                }))

            def on_error(data):
                err = json.loads(data)
                self.error_occurred.emit(json.dumps({
                    "action": "natasha_done",
                    "error":  err['error']
                }))

            self._natasha_worker.progress.connect(on_progress)
            self._natasha_worker.finished.connect(on_finished)
            self._natasha_worker.error.connect(on_error)
            self._natasha_worker.start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(json.dumps({
                "action": "natasha_done", "error": str(e)
            }))

    @pyqtSlot(str)
    def run_bertopic_analysis(self, settings_json: str):
        try:
            settings     = json.loads(settings_json)
            natasha_data = self.session.load_natasha()

            print(f"[Bridge] BERTopic запуск")
            self._bertopic_worker = BERTopicWorker(natasha_data, settings)

            def on_progress(data):
                self.result_ready.emit(json.dumps({
                    **json.loads(data),
                    "action": "bertopic_progress"
                }))

            def on_finished(data):
                result = json.loads(data)

                vos_data = build_vosviewer_json(result)
                result_to_save = {k: v for k, v in result.items() if k != 'topic_embeddings'}
                self.session.save_bertopic(result_to_save)

                vos_path = os.path.join(self.session.bertopic_dir, 'vosviewer.json')
                with open(vos_path, 'w', encoding='utf-8') as f:
                    json.dump(vos_data, f, ensure_ascii=False, indent=2)

                # Даты из Natasha → привязываем к doc_topics
                doc_dates = {}
                for doc in natasha_data.get('documents', []):
                    dates = doc.get('dates', [])
                    if dates:
                        first = dates[0].get('text', {})
                        if isinstance(first, dict) and 'year' in first:
                            year  = first.get('year', '')
                            month = first.get('month')
                            day   = first.get('day')
                            date_str = str(year)
                            if month: date_str += f"-{month:02d}"
                            if day:   date_str += f"-{day:02d}"
                            doc_dates[doc['name']] = date_str

                doc_topics_with_dates = []
                for dt in result.get('doc_topics', []):
                    entry = dict(dt)
                    entry['date'] = doc_dates.get(dt['name'], None)
                    doc_topics_with_dates.append(entry)

                has_dates = any(d['date'] for d in doc_topics_with_dates)
                print(f"[Bridge] документов с датами: "
                      f"{sum(1 for d in doc_topics_with_dates if d['date'])}"
                      f"/{len(doc_topics_with_dates)}")

                self.result_ready.emit(json.dumps({
                    "action":      "bertopic_done",
                    "topics":      result['topics'],
                    "total_docs":  result['total_docs'],
                    "noise_pct":   result['noise_pct'],
                    "coherence":   result['coherence'],
                    "noise_count": result['noise_count'],
                    "vos_data":    vos_data,
                    "doc_topics":  doc_topics_with_dates,
                    "has_dates":   has_dates,
                }))

            def on_error(data):
                err = json.loads(data)
                self.error_occurred.emit(json.dumps({
                    "action": "bertopic_done",
                    "error":  err['error']
                }))

            self._bertopic_worker.progress.connect(on_progress)
            self._bertopic_worker.finished.connect(on_finished)
            self._bertopic_worker.error.connect(on_error)
            self._bertopic_worker.start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(json.dumps({
                "action": "bertopic_done", "error": str(e)
            }))

    @pyqtSlot(str)
    def generate_pdf_report(self, params_json: str):
        try:
            params        = json.loads(params_json)
            sections      = params.get('sections', {})
            bertopic_data = self.session.load_bertopic()
            output_path   = os.path.join(self.session.root, 'report.pdf')

            generate_report(bertopic_data, sections, output_path)

            self.result_ready.emit(json.dumps({
                "action": "report_done",
                "path":   output_path,
            }))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(json.dumps({
                "action": "report_done",
                "error":  str(e)
            }))

    @pyqtSlot(str)
    def save_file_dialog(self, source_path: str):
        dest_path, _ = QFileDialog.getSaveFileName(
            None,
            "Сохранить отчёт",
            "SemanticAnalyzer_report.pdf",
            "PDF файлы (*.pdf)"
        )
        if dest_path:
            shutil.copy2(source_path, dest_path)
            self.result_ready.emit(json.dumps({
                "action": "file_saved",
                "path":   dest_path,
            }))
