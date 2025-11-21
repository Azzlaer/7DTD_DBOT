"""
Discord webhook file monitor - GUI
Creates a PyQt5 GUI that tails a text log file and sends messages to a Discord webhook
when it detects chat lines in the specified format.

Features:
- Detect platforms (Xbox_, PSN_, Steam_)
- Sends formatted messages to a webhook using a template with placeholders
  {platform} {user} {message}
- Config stored in config.ini (auto-created with defaults if missing)
- GUI allows customizing webhook, template, file path and starting/stopping the monitor
- No maximize button, small polished UI with zombie emoji

Dependencies:
pip install PyQt5 requests

Run: python monitor_webhook_gui.py
"""

import sys
import os
import time
import re
import configparser
import threading
import requests
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

CONFIG_FILE = "config.ini"
DEFAULT_CONFIG = {
    'general': {
        'log_file': 'E:/Steam/steamapps/common/7 Days to Die Dedicated Server/logs/server_log.txt',
        'webhook_url': '',
        'message_template': "🧟 {platform} — **{user}**: {message}",
        'poll_interval': '1'
    }
}

CHAT_LINE_RE = re.compile(r"Chat \(from '([^']+)'(?:,.*?)\): '([^']+)': (.+)$")


class TailWorker(QtCore.QThread):
    new_chat = QtCore.pyqtSignal(str, str, str)
    log = QtCore.pyqtSignal(str)

    def __init__(self, filepath, poll_interval=1, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.poll_interval = float(poll_interval)
        self._running = False

    def run(self):
        self._running = True
        try:
            self.log.emit(f"Iniciando vigilancia de: {self.filepath}")
            with open(self.filepath, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(0, os.SEEK_END)

                while self._running:
                    line = f.readline()
                    if not line:
                        time.sleep(self.poll_interval)
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    self.log.emit(f"Linea detectada: {line}")

                    m = CHAT_LINE_RE.search(line)
                    if m:
                        platform_id = m.group(1)
                        user = m.group(2)
                        message = m.group(3).strip(" '\"")
                        self.log.emit(f"Chat parseado -> platform: {platform_id}, user: {user}, message: {message}")
                        self.new_chat.emit(platform_id, user, message)

        except FileNotFoundError:
            self.log.emit(f"El archivo no fue encontrado: {self.filepath}")
        except Exception as e:
            self.log.emit(f"Error en TailWorker: {e}")

    def stop(self):
        self._running = False
        self.wait(2000)


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Webhook Chat Watcher 🧟')
        self.setWindowIcon(QtGui.QIcon())
        self.setFixedSize(720, 520)

        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowMaximizeButtonHint)

        self.config = configparser.ConfigParser()
        self.load_or_create_config()

        self.tail_worker = None

        self.build_ui()
        self.load_settings_to_ui()

    def build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        top_row = QtWidgets.QHBoxLayout()
        self.file_edit = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton('Examinar...')
        browse_btn.clicked.connect(self.browse_file)
        top_row.addWidget(QtWidgets.QLabel('Archivo de log:'))
        top_row.addWidget(self.file_edit)
        top_row.addWidget(browse_btn)
        layout.addLayout(top_row)

        wh_row = QtWidgets.QHBoxLayout()
        self.webhook_edit = QtWidgets.QLineEdit()
        wh_row.addWidget(QtWidgets.QLabel('Webhook de Discord:'))
        wh_row.addWidget(self.webhook_edit)
        test_wh_btn = QtWidgets.QPushButton('Probar Webhook')
        test_wh_btn.clicked.connect(self.test_webhook)
        wh_row.addWidget(test_wh_btn)
        layout.addLayout(wh_row)

        templ_label = QtWidgets.QLabel('Plantilla de mensaje (usa {platform} {user} {message}):')
        layout.addWidget(templ_label)
        self.template_edit = QtWidgets.QPlainTextEdit()
        self.template_edit.setMaximumHeight(90)
        layout.addWidget(self.template_edit)

        btn_row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton('Iniciar vigilancia')
        self.start_btn.clicked.connect(self.toggle_watch)
        save_btn = QtWidgets.QPushButton('Guardar configuración')
        save_btn.clicked.connect(self.save_settings_from_ui)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        layout.addWidget(QtWidgets.QLabel('Registro de la aplicación:'))
        self.app_log = QtWidgets.QPlainTextEdit()
        self.app_log.setReadOnly(True)
        layout.addWidget(self.app_log)

    def browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Selecciona archivo de log', os.getcwd(), "Text files (*.txt *.log);;All files (*)")
        if path:
            self.file_edit.setText(path)

    def load_or_create_config(self):
        if not os.path.exists(CONFIG_FILE):
            cfg = configparser.ConfigParser()
            cfg.read_dict(DEFAULT_CONFIG)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                cfg.write(f)
            self.config = cfg
        else:
            self.config.read(CONFIG_FILE, encoding='utf-8')

    def load_settings_to_ui(self):
        gen = self.config['general']
        self.file_edit.setText(gen.get('log_file', ''))
        self.webhook_edit.setText(gen.get('webhook_url', ''))
        self.template_edit.setPlainText(gen.get('message_template', DEFAULT_CONFIG['general']['message_template']))

    def save_settings_from_ui(self):
        if 'general' not in self.config:
            self.config['general'] = {}
        self.config['general']['log_file'] = self.file_edit.text()
        self.config['general']['webhook_url'] = self.webhook_edit.text()
        self.config['general']['message_template'] = self.template_edit.toPlainText()
        self.config['general']['poll_interval'] = self.config['general'].get('poll_interval', '1')
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            self.config.write(f)
        self.append_log('Configuración guardada.')

    def append_log(self, text):
        ts = QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')
        self.app_log.appendPlainText(f"[{ts}] {text}")

    def toggle_watch(self):
        if self.tail_worker and self.tail_worker.isRunning():
            self.stop_watching()
        else:
            self.start_watching()

    def start_watching(self):
        filepath = self.file_edit.text()
        if not filepath or not os.path.exists(filepath):
            self.append_log('Ruta de archivo inválida o no existe.')
            return
        poll = float(self.config['general'].get('poll_interval', '1'))
        self.tail_worker = TailWorker(filepath, poll_interval=poll)
        self.tail_worker.new_chat.connect(self.on_new_chat)
        self.tail_worker.log.connect(self.append_log)
        self.tail_worker.start()
        self.start_btn.setText('Detener vigilancia')
        self.append_log('Vigilancia iniciada.')

    def stop_watching(self):
        if self.tail_worker:
            self.tail_worker.stop()
            self.tail_worker = None
            self.start_btn.setText('Iniciar vigilancia')
            self.append_log('Vigilancia detenida.')

    def on_new_chat(self, platform_id, user, message):
        platform_label = platform_id
        if platform_id.startswith('Xbox_'):
            platform_label = 'Xbox'
        elif platform_id.startswith('PSN_'):
            platform_label = 'PSN'
        elif platform_id.startswith('Steam_'):
            platform_label = 'Steam'

        template = self.template_edit.toPlainText() or DEFAULT_CONFIG['general']['message_template']
        content = (
            template.replace('{platform}', platform_label)
                    .replace('{user}', user)
                    .replace('{message}', message)
        )

        self.append_log(f"Preparando envío: {content}")

        webhook = self.webhook_edit.text().strip()
        if webhook:
            success, resp_text = self.post_webhook(webhook, content)
            if success:
                self.append_log('Mensaje enviado correctamente al webhook.')
            else:
                self.append_log(f'Error al enviar webhook: {resp_text}')
        else:
            self.append_log('Webhook vacío — no se envió el mensaje.')

    def post_webhook(self, webhook_url, content):
        try:
            r = requests.post(webhook_url, json={"content": content}, timeout=8)
            if r.status_code in (200, 204):
                return True, ''
            else:
                return False, f"HTTP {r.status_code} - {r.text}"
        except Exception as e:
            return False, str(e)

    def test_webhook(self):
        webhook = self.webhook_edit.text().strip()
        if not webhook:
            self.append_log('Introduce un webhook para probar.')
            return
        text = '🔔 Prueba de webhook desde Webhook Chat Watcher 🧟'
        ok, resp = self.post_webhook(webhook, text)
        if ok:
            self.append_log('Prueba de webhook enviada correctamente.')
        else:
            self.append_log(f'Error en prueba de webhook: {resp}')

    def closeEvent(self, event):
        if self.tail_worker:
            self.tail_worker.stop()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
