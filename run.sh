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
echo ""
echo "  🎭 Репетитор роли запущен"
echo "  ────────────────────────────────"
echo "  На этом Маке:   http://localhost:$PORT"
[ -n "$IP" ] && echo "  С телефона:     http://$IP:$PORT   (телефон в той же Wi-Fi)"
echo "  Останов: Ctrl+C"
echo ""
python3 server.py
