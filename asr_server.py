#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальный сервер распознавания речи (faster-whisper) — надёжная замена
браузерному Web Speech, который постоянно отваливается.

Приложение пишет реплику через MediaRecorder и шлёт аудио POST-ом сюда;
сервер прогоняет Whisper и возвращает {text}. Работает офлайн, приватно.

Запуск (из 3.11-venv с faster-whisper):
    .venv-asr/bin/python asr_server.py
Порт 8788. Модель по умолчанию 'small' (хороша для русского). Сменить:
    ASR_MODEL=base .venv-asr/bin/python asr_server.py
"""
import os, json, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_NAME = os.environ.get("ASR_MODEL", "small")
PORT = int(os.environ.get("ASR_PORT", "8788"))
_model = None


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def ext_for(ctype: str) -> str:
    c = (ctype or "").lower()
    for key, e in (("mp4", ".mp4"), ("webm", ".webm"), ("ogg", ".ogg"),
                   ("wav", ".wav"), ("mpeg", ".mp3"), ("aac", ".aac")):
        if key in c:
            return e
    return ".webm"


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path.startswith("/asr/health"):
            self._json({"ok": True, "model": MODEL_NAME, "ready": _model is not None})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/asr"):
            self._json({"error": "not found"}, 404); return
        n = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(n) if n else b""
        if not data:
            self._json({"text": ""}); return
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext_for(self.headers.get("Content-Type")), delete=False) as f:
                f.write(data); path = f.name
            segs, _ = get_model().transcribe(path, language="ru", beam_size=1, vad_filter=True)
            text = " ".join(s.text.strip() for s in segs).strip()
            self._json({"text": text})
        except Exception as e:
            self._json({"text": "", "error": str(e)}, 200)
        finally:
            if path:
                try: os.unlink(path)
                except OSError: pass

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"ASR (faster-whisper '{MODEL_NAME}') на http://127.0.0.1:{PORT}")
    print("Загружаю модель (первый раз качает веса)…")
    get_model()
    print("Модель готова. Жду запись реплик.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
