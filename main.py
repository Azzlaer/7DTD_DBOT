import sys
import os
import time
import re
import configparser
import requests
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

# -----------------------
# ARCHIVOS IMPORTANTES
# -----------------------
CONFIG_FILE = "config.ini"
ERROR_LOG = "bot_error.log"

DEFAULT_CONFIG = {
    'general': {
        'log_file': '',
        'webhook_url': '',
        'message_template': "🧟 {platform} — **{user}**: {message}",
        'poll_interval': '1'
    }
}

# ======================================================
#   REGEX DEFINITIVO PARA EL CHAT DE 7 DAYS TO DIE
# ======================================================
# Ejemplo:
# 2025-11-21T04:23:26 1717.059 INF Chat (from 'Steam_76561198093711528', entity id '1278', to 'Global'): 'Azzlaer': se
CHAT_LINE_RE = re.compile(
    r"Chat\s*\(.*?'(?P<platform>[^']+)'.*?\)\s*:\s*'(?P<user>[^']+)'\s*:\s*(?P<msg>.*)$",
    re.IGNORECASE
)


# -----------------------
#   LOG DE ERRORES
# -----------------------
def write_error_log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


# ======================================================
#   SISTEMA DE LECTURA EN TIEMPO REAL (TAIL)
# ======================================================
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
            self.log.emit(f"📄 Vigilando archivo: {self.filepath}")

            with open(self.filepath, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)

                while self._running:
                    line = f.readline()
                    if not line:
                        time.sleep(self.poll_interval)
                        continue

                    line = line.strip()
                    if not line:
                        continue

                    self.log.emit(f"[RAW] {line}")

                    # Procesar chat
                    m = CHAT_LINE_RE.search(line)
                    if m:
                        platform_id = m.group("platform")
                        user = m.group("user")
                        message = m.group("msg").strip()

                        self.log.emit(f"🎯 Chat detectado — {platform_id} | {user} | {message}")
                        self.new_chat.emit(platform_id, user, message)

        except Exception as e:
            err = f"❌ Error en TailWorker: {e}"
            write_error_log(err)
            self.log.emit(err)

    def stop(self):
        self._running = False
        self.wait(2000)


# ======================================================
#   INTERFAZ GRAFICA
# ======================================================
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Webhook Chat Watcher 🧟")
        self.setFixedSize(720, 520)

        self.config = configparser.ConfigParser()
        self.load_or_create_config()

        self.tail_worker = None

        self.build_ui()
        self.load_settings_to_ui()

    # -----------------------
    #   UI
    # -----------------------
    def build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # --- ARCHIVO LOG ---
        top = QtWidgets.QHBoxLayout()
        self.file_edit = QtWidgets.QLineEdit()
        btn_browse = QtWidgets.QPushButton("Examinar…")
        btn_browse.clicked.connect(self.browse_file)

        top.addWidget(QtWidgets.QLabel("Archivo de log:"))
        top.addWidget(self.file_edit)
        top.addWidget(btn_browse)
        layout.addLayout(top)

        # --- WEBHOOK ---
        wh = QtWidgets.QHBoxLayout()
        self.webhook_edit = QtWidgets.QLineEdit()

        wh.addWidget(QtWidgets.QLabel("Webhook de Discord:"))
        wh.addWidget(self.webhook_edit)

        btn_test = QtWidgets.QPushButton("Probar Webhook")
        btn_test.clicked.connect(self.test_webhook)
        wh.addWidget(btn_test)

        layout.addLayout(wh)

        # --- PLANTILLA ---
        layout.addWidget(QtWidgets.QLabel("Plantilla del mensaje:"))
        self.template_edit = QtWidgets.QPlainTextEdit()
        self.template_edit.setMaximumHeight(90)
        layout.addWidget(self.template_edit)

        # --- BOTONES ---
        row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Iniciar vigilancia")
        self.start_btn.clicked.connect(self.toggle_watch)

        btn_save = QtWidgets.QPushButton("Guardar configuración")
        btn_save.clicked.connect(self.save_settings_from_ui)

        row.addWidget(self.start_btn)
        row.addWidget(btn_save)
        layout.addLayout(row)

        # --- LOG ---
        layout.addWidget(QtWidgets.QLabel("Registro de la aplicación:"))
        self.app_log = QtWidgets.QPlainTextEdit()
        self.app_log.setReadOnly(True)
        layout.addWidget(self.app_log)

    # -----------------------
    #  FILE SELECTION
    # -----------------------
    def browse_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Selecciona archivo de log", os.getcwd(),
            "Logs (*.txt *.log);;Todos (*.*)"
        )
        if path:
            self.file_edit.setText(path)

    # -----------------------
    #   CONFIG
    # -----------------------
    def load_or_create_config(self):
        if not os.path.exists(CONFIG_FILE):
            cfg = configparser.ConfigParser()
            cfg.read_dict(DEFAULT_CONFIG)

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                cfg.write(f)

            self.config = cfg
        else:
            self.config.read(CONFIG_FILE, encoding="utf-8")

    def load_settings_to_ui(self):
        g = self.config["general"]
        self.file_edit.setText(g.get("log_file", ""))
        self.webhook_edit.setText(g.get("webhook_url", ""))
        self.template_edit.setPlainText(
            g.get("message_template", DEFAULT_CONFIG["general"]["message_template"])
        )

    def save_settings_from_ui(self):
        g = self.config.setdefault("general", {})
        g["log_file"] = self.file_edit.text()
        g["webhook_url"] = self.webhook_edit.text()
        g["message_template"] = self.template_edit.toPlainText()
        g["poll_interval"] = g.get("poll_interval", "1")

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self.config.write(f)

        self.append_log("💾 Configuración guardada.")

    # -----------------------
    #   LOG UI
    # -----------------------
    def append_log(self, text):
        ts = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.app_log.appendPlainText(f"[{ts}] {text}")

    # -----------------------
    #   CONTROL DE THREAD
    # -----------------------
    def toggle_watch(self):
        if self.tail_worker and self.tail_worker.isRunning():
            self.stop_watching()
        else:
            self.start_watching()

    def start_watching(self):
        filepath = self.file_edit.text()

        if not filepath or not os.path.exists(filepath):
            self.append_log("❌ Archivo de log inválido o no existe.")
            return

        poll = float(self.config["general"].get("poll_interval", "1"))

        self.tail_worker = TailWorker(filepath, poll)
        self.tail_worker.log.connect(self.append_log)
        self.tail_worker.new_chat.connect(self.on_new_chat)
        self.tail_worker.start()

        self.start_btn.setText("Detener vigilancia")
        self.append_log("🟢 Vigilancia iniciada.")

    def stop_watching(self):
        if self.tail_worker:
            self.tail_worker.stop()
            self.tail_worker = None

        self.start_btn.setText("Iniciar vigilancia")
        self.append_log("🔴 Vigilancia detenida.")

    # -----------------------
    #   PROCESAR CHAT
    # -----------------------
    def on_new_chat(self, platform_id, user, message):
        platform = platform_id

        if platform.startswith("Steam_"):
            platform = "Steam"
        elif platform.startswith("Xbox_"):
            platform = "Xbox"
        elif platform.startswith("PSN_"):
            platform = "PSN"

        template = self.template_edit.toPlainText()
        content = (
            template.replace("{platform}", platform)
                    .replace("{user}", user)
                    .replace("{message}", message)
        )

        self.append_log(f"➡ Enviando mensaje: {content}")

        webhook = self.webhook_edit.text().strip()
        if webhook:
            ok, resp = self.post_webhook(webhook, content)
            if ok:
                self.append_log("✅ Mensaje enviado al webhook.")
            else:
                self.append_log(f"❌ Error al enviar webhook: {resp}")
                write_error_log(resp)
        else:
            self.append_log("⚠ Webhook vacío — mensaje no enviado.")

    # -----------------------
    #   ENVIAR WEBHOOK
    # -----------------------
    def post_webhook(self, webhook_url, content):
        try:
            r = requests.post(webhook_url, json={"content": content}, timeout=8)
            if r.status_code in (200, 204):
                return True, ""
            return False, f"HTTP {r.status_code} - {r.text}"
        except Exception as e:
            write_error_log(str(e))
            return False, str(e)

    # -----------------------
    #   TEST WEBHOOK
    # -----------------------
    def test_webhook(self):
        url = self.webhook_edit.text().strip()
        if not url:
            self.append_log("⚠ Debes ingresar un webhook.")
            return

        ok, resp = self.post_webhook(url, "🔔 Mensaje de prueba desde el bot 🧟")
        if ok:
            self.append_log("🟢 Webhook funcionando.")
        else:
            self.append_log(f"❌ Error en webhook: {resp}")

    # -----------------------
    #   CERRAR APP
    # -----------------------
    def closeEvent(self, event):
        if self.tail_worker:
            self.tail_worker.stop()
        event.accept()


# -----------------------
#   MAIN
# -----------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
