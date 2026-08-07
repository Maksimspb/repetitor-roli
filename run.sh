#!/bin/bash
# Запуск репетитора роли. Открывается на Маке и с телефона по Wi-Fi.
cd "$(dirname "$0")" || exit 1

# пересобрать данные, если пьеса менялась
if [ data/play.docx -nt data/play.json ]; then
  echo "Пьеса изменилась — пересобираю data/play.json…"
  python3 parse.py || exit 1
fi

PORT=8777
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)

# Распознавание речи (Whisper) — если установлен 3.11-venv. Надёжная замена
# браузерному Web Speech. Работает только на этом Маке (для проверки текста за столом).
ASR=""
if [ -x .venv-asr/bin/python ]; then
  .venv-asr/bin/python asr_server.py >/tmp/asr.log 2>&1 &
  ASR=$!
  trap "kill $ASR 2>/dev/null" EXIT
  ASR_NOTE="  Распознавание: Whisper на :8788 (первый запуск качает модель, см. /tmp/asr.log)"
else
  ASR_NOTE="  Распознавание: браузерное (Web Speech). Для точного Whisper: см. README → Проверка речи"
fi

echo ""
echo "  🎭 Репетитор роли запущен"
echo "  ────────────────────────────────"
echo "  На этом Маке:   http://localhost:$PORT"
[ -n "$IP" ] && echo "  С телефона:     http://$IP:$PORT   (телефон в той же Wi-Fi)"
echo "$ASR_NOTE"
echo "  Останов: Ctrl+C"
echo ""
python3 server.py
