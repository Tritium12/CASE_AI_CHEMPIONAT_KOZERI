import sys
import ctypes
import re
import webbrowser
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLineEdit, QTextEdit,
                               QListWidget, QLabel, QGraphicsDropShadowEffect,
                               QProgressBar, QStatusBar, QListWidgetItem)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QFont
# Для правильного отображения иконки на панели задач Windows
myappid = 'mycompany.myproduct.subproduct.version'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
# Импортируем функцию из нашего бэкенда
from rag1 import ask_rag


# ==========================================
# ПОТОК ДЛЯ ВЫПОЛНЕНИЯ RAG (Чтобы окно не зависало)
# ==========================================
myappid = 'mycompany.myproduct.subproduct.version'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


# ==========================================
# ПОТОК ДЛЯ ВЫПОЛНЕНИЯ RAG (Чтобы окно не зависало)
# ==========================================
class RAGWorker(QThread):
    # Теперь сигнал передает два аргумента: строку и список
    finished = Signal(str, list)
    error = Signal(str)

    def __init__(self, question):
        super().__init__()
        self.question = question

    def run(self):
        try:
            # Вызываем функцию из бэкенда, получаем ответ и ссылки
            answer, sources = ask_rag(self.question)
            self.finished.emit(answer, sources)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Поисковый ИИ-агент")
        self.resize(1300, 850)

        # Иконка
        # self.setWindowIcon(QIcon('icon.ico'))

        # Градиентный фон
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #0a0a0a, stop:1 #0f1a2c);
            }
        """)

        # Главный виджет и компоновка
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ==========================================
        # ЛЕВАЯ ПАНЕЛЬ (История вопросов)
        # ==========================================
        history_container = QWidget()
        history_container.setFixedWidth(300)
        history_layout = QVBoxLayout(history_container)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(10)

        # Заголовок и кнопка очистки
        header_layout = QHBoxLayout()
        history_label = QLabel("История вопросов")
        history_label.setStyleSheet("color: #90caf9; font-size: 16px; font-weight: bold;")

        self.btn_clear_history = QPushButton("Очистить")
        self.btn_clear_history.setCursor(Qt.PointingHandCursor)
        self.btn_clear_history.setStyleSheet("""
            QPushButton { color: #f44336; background: transparent; border: none; font-size: 12px; }
            QPushButton:hover { text-decoration: underline; }
        """)
        self.btn_clear_history.clicked.connect(self.clear_history)

        header_layout.addWidget(history_label)
        header_layout.addWidget(self.btn_clear_history, alignment=Qt.AlignRight)
        history_layout.addLayout(header_layout)

        # Список истории
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #0e1624; color: #d0d8e8;
                border: 1px solid #1e3a5f; border-radius: 10px; padding: 5px; font-size: 14px;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #1e3a5f; border-radius: 5px; }
            QListWidget::item:hover { background-color: #1e3a5f; color: #ffffff; }
            QListWidget::item:selected { background-color: #0d47a1; color: #ffffff; }
        """)
        self.history_list.itemClicked.connect(self.on_history_click)
        history_layout.addWidget(self.history_list)

        # ==========================================
        # ПРАВАЯ ПАНЕЛЬ (Основной интерфейс)
        # ==========================================
        main_container = QWidget()
        layout = QVBoxLayout(main_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # 1. Быстрые вопросы (Чипсы)
        chips_layout = QHBoxLayout()
        chips = ["Военная кафедра", "Виды стипендий", "Как получить стипендию"]
        for text in chips:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a5f; color: #90caf9; border: 1px solid #2196F3;
                    border-radius: 15px; padding: 8px 15px; font-size: 13px;
                }
                QPushButton:hover { background-color: #2196F3; color: white; }
            """)
            btn.clicked.connect(lambda checked, t=text: self.question_input.setText(t))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        # 2. Поле ввода
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Введите ваш вопрос...")
        self.question_input.setStyleSheet("""
            QLineEdit {
                padding: 18px; border-radius: 12px; background-color: #121b2b; 
                color: #e0e0e0; font-size: 18px; border: 2px solid #1e3a5f;
            }
            QLineEdit:focus { border: 2px solid #2196F3; background-color: #162338; }
        """)
        self.question_input.returnPressed.connect(self.ask_agent)
        layout.addWidget(self.question_input)

        # 3. Кнопка "Спросить" + Индикатор загрузки
        btn_layout = QHBoxLayout()
        self.btn_ask = QPushButton("СПРОСИТЬ")
        self.btn_ask.setCursor(Qt.PointingHandCursor)
        self.btn_ask.setStyleSheet("""
            QPushButton {
                background-color: #0d47a1; color: #ffffff; padding: 18px;
                border-radius: 12px; font-weight: bold; font-size: 18px;
                letter-spacing: 2px; border: 1px solid #1e88e5;
            }
            QPushButton:hover { background-color: #1565c0; border: 1px solid #42a5f5; }
            QPushButton:pressed { background-color: #0a3d91; padding-top: 20px; padding-bottom: 16px; }
            QPushButton:disabled { background-color: #333; color: #888; border: 1px solid #444; }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(33, 150, 243, 180))
        shadow.setOffset(0, 0)
        self.btn_ask.setGraphicsEffect(shadow)
        self.btn_ask.clicked.connect(self.ask_agent)
        btn_layout.addWidget(self.btn_ask)

        # Крутящийся индикатор (скрыт по умолчанию)
        self.spinner = QProgressBar()
        self.spinner.setRange(0, 0)
        self.spinner.setFixedSize(100, 5)
        self.spinner.setStyleSheet("""
            QProgressBar { border: none; background: #1e3a5f; border-radius: 2px; }
            QProgressBar::chunk { background: #2196F3; border-radius: 2px; }
        """)
        self.spinner.hide()
        btn_layout.addWidget(self.spinner)
        layout.addLayout(btn_layout)

        # 4. Поле ответа
        self.answer_output = QTextEdit()
        self.answer_output.setReadOnly(True)
        self.answer_output.setStyleSheet("""
            QTextEdit {
                background-color: #0e1624; color: #d0d8e8; padding: 25px; 
                border-radius: 12px; font-size: 16px; border: 1px solid #1e3a5f;
            }
            QScrollBar:vertical { border: none; background: #0e1624; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #1e3a5f; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #2196F3; }
        """)
        layout.addWidget(self.answer_output)

        # 5. Кнопка "Копировать"
        self.btn_copy = QPushButton("📋 Копировать ответ")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton { background: transparent; color: #90caf9; border: 1px solid #1e3a5f; border-radius: 8px; padding: 8px; }
            QPushButton:hover { background: #1e3a5f; color: white; }
        """)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.btn_copy, alignment=Qt.AlignRight)

        # 6. Блок источников
        sources_label = QLabel("Источники")
        sources_label.setStyleSheet("color: #90caf9; font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(sources_label)

        self.sources_list = QListWidget()
        self.sources_list.setMaximumHeight(100)
        self.sources_list.setStyleSheet("""
            QListWidget {
                background-color: #0e1624; color: #2196F3;
                border: 1px solid #1e3a5f; border-radius: 8px; padding: 5px;
            }
            QListWidget::item { padding: 5px; }
            QListWidget::item:hover { background-color: #1e3a5f; }
        """)
        self.sources_list.itemClicked.connect(self.open_url)
        layout.addWidget(self.sources_list)

        # Добавляем панели в главное окно
        main_layout.addWidget(history_container)
        main_layout.addWidget(main_container)

        # 7. Статус-бар (внизу окна)
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("color: #64b5f6; background: #0a0a0a; font-size: 12px;")
        self.setStatusBar(self.status_bar)
        self.update_status("Готов к работе", "ChromaDB", 0)

    def update_status(self, status, db_status, found_count):
        self.status_bar.showMessage(f"Статус: {status}  |  База: {db_status}  |  Найдено: {found_count}")

    def clear_history(self):
        self.history_list.clear()
        self.update_status("История очищена", "ChromaDB", 0)

    def on_history_click(self, item):
        self.question_input.setText(item.text())
        self.question_input.setFocus()

    def open_url(self, item):
        webbrowser.open(item.text())

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.answer_output.toPlainText())
        self.update_status("Скопировано в буфер", "ChromaDB", 0)
        self.btn_copy.setText("✅ Скопировано!")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("📋 Копировать ответ"))

    def ask_agent(self):
        question = self.question_input.text().strip()
        if not question:
            return

        # Добавляем в историю (без дублей)
        items = self.history_list.findItems(question, Qt.MatchExactly)
        if not items:
            self.history_list.insertItem(0, question)

        # Включаем индикатор загрузки
        self.btn_ask.setEnabled(False)
        self.btn_ask.setText("ИЩУ...")
        self.spinner.show()
        self.answer_output.setHtml(
            "<i style='color: #2196F3;'>Агент изучает базу данных... (это займет несколько секунд)</i>")
        self.update_status("Выполняется поиск...", "ChromaDB", 0)

        # ЗАПУСКАЕМ ПОТОК
        self.worker = RAGWorker(question)
        self.worker.finished.connect(self.display_real_answer)
        self.worker.error.connect(self.display_error)
        self.worker.start()

    def display_real_answer(self, answer_text, sources):
        # ==========================================
        # ЖЕСТКАЯ ОЧИСТКА ТЕКСТА ОТ ССЫЛОК
        # ==========================================
        clean_text = answer_text

        # 1. Удаляем сноски в квадратных скобках, например [1], [2]
        clean_text = re.sub(r'\[\d+\]', '', clean_text)

        # 2. Удаляем сами ссылки (http, https, www) и всё, что после них до пробела
        clean_text = re.sub(r'https?://\S+|www\.\S+', '', clean_text)

        # 3. Удаляем "хвосты" от ссылок, если они остались (например, "://" или просто домены)
        clean_text = re.sub(r'://\S*', '', clean_text)

        # 4. Убираем лишние пробелы, которые могли образоваться после удаления ссылок
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # 5. Убираем висящие точки или запятые в конце текста
        clean_text = re.sub(r'[\s.,;]+$', '', clean_text)

        # 6. Выводим очищенный ответ
        self.answer_output.setHtml(f"<p style='color: #e0e0e0;'>{clean_text}</p>")

        # 7. Заполняем поле источников из списка, который пришел из бэкенда
        self.sources_list.clear()


        unique_sources = []
        for src in sources:
            if src not in unique_sources:
                unique_sources.append(src)

        for src in unique_sources:

            display_src = src if src.startswith('http') else f"http://{src}"
            item = QListWidgetItem(display_src)
            item.setToolTip("Нажмите, чтобы открыть в браузере")
            self.sources_list.addItem(item)

        # 8. Выключаем индикатор
        self.btn_ask.setEnabled(True)
        self.btn_ask.setText("СПРОСИТЬ")
        self.spinner.hide()
        self.update_status("Готов к работе", "ChromaDB", len(unique_sources))


    def display_error(self, error_message):
        self.answer_output.setHtml(f"<p style='color: red;'>Произошла ошибка: {error_message}</p>")
        self.btn_ask.setEnabled(True)
        self.btn_ask.setText("СПРОСИТЬ")
        self.spinner.hide()
        self.update_status("Ошибка", "ChromaDB", 0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())