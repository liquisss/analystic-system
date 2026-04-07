import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl
from bridge import Bridge

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SemanticAnalyzer")
        self.setMinimumSize(1280, 800)

        # Создаём мост
        self.bridge = Bridge()
        self.channel = QWebChannel()
        self.channel.registerObject("backend", self.bridge)

        self.view = QWebEngineView()
        self.view.page().setWebChannel(self.channel)
        self.view.load(QUrl("http://localhost:5173"))
        self.setCentralWidget(self.view)

    def closeEvent(self, event):
        """Вызывается когда пользователь закрывает окно"""
        self.bridge.session.cleanup()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())