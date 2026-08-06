#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пред-рендер реплик пьесы в аудио (edge-tts, Microsoft Neural — бесплатно, без ключа).
Каждому персонажу — свой тембр (из 2 голосов + сдвиги высоты/темпа = «труппа»).
Результат: audio/<id>.mp3 + audio/index.json. Приложение играет их вместо системного голоса,
Service Worker кэширует → работает офлайн (в машине).

Запуск (из venv с edge-tts):
    .venv-tts/bin/python build_audio.py            # все реплики
    .venv-tts/bin/python build_audio.py --role Лыняев   # только реплики партнёров Лыняева
    .venv-tts/bin/python build_audio.py --limit 40      # первые N (проба)
Инкрементально: уже готовые файлы пропускаются.
"""
import asyncio, json, re, argparse, sys
from pathlib import Path
import edge_tts

ROOT = Path(__file__).parent
PLAY = ROOT / "data" / "play.json"
OUT = ROOT / "audio"
OUT.mkdir(exist_ok=True)

SVET = "ru-RU-SvetlanaNeural"   # женский нейро
DMIT = "ru-RU-DmitryNeural"     # мужской нейро

# персонаж -> (голос, темп, высота). Сдвиги дают разные тембры из двух голосов.
VOICE_MAP = {
    "Мурзавецкая": (SVET, "-8%",  "-8Hz"),   # властная, пожилая
    "Купавина":    (SVET, "+0%",  "+12Hz"),  # молодая
    "Глафира":     (SVET, "+0%",  "+0Hz"),
    "Анфуса":      (SVET, "-8%",  "-3Hz"),    # приживалка, комична
    "Лыняев":      (DMIT, "+0%",  "+0Hz"),
    "Беркутов":    (DMIT, "-5%",  "-6Hz"),    # солидный
    "Чугунов":     (DMIT, "-6%",  "-10Hz"),   # вкрадчивый
    "Мурзавецкий": (DMIT, "+8%",  "+14Hz"),   # молодой шалопай
    "Горецкий":    (DMIT, "+3%",  "+8Hz"),
    "Павлин":      (DMIT, "-3%",  "+4Hz"),    # чинный слуга
    "Влас":        (DMIT, "+0%",  "+2Hz"),
}
FEMALE = {"Мурзавецкая", "Купавина", "Глафира", "Анфуса"}


def voice_for(speaker: str):
    name = speaker.split(" и ")[0]  # хоровая — по первому
    if name in VOICE_MAP:
        return VOICE_MAP[name]
    return (SVET, "+0%", "+0Hz") if name in FEMALE else (DMIT, "+0%", "+0Hz")


def clean(text: str) -> str:
    return re.sub(r"\([^)]*\)", " ", text).replace("…", "...").strip()


async def synth(sem, line, force):
    out = OUT / f"{line['id']}.mp3"
    if out.exists() and not force:
        return ("skip", line["id"])
    text = clean(line["text"])
    if not text:
        return ("empty", line["id"])
    voice, rate, pitch = voice_for(line["speaker"])
    async with sem:
        try:
            com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await com.save(str(out))
            return ("ok", line["id"])
        except Exception as e:
            return ("err", f"{line['id']}: {e}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="только реплики партнёров этой роли (не её собственные)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    data = json.loads(PLAY.read_text(encoding="utf-8"))
    units = data["units"]
    lines = [u for u in units if u["type"] == "line"]

    if args.role:
        # партнёрские реплики = все, кроме реплик самой роли, в сценах где роль есть
        scenes = [i for i, u in enumerate(units) if u["type"] == "scene"]
        keep_ids = set()
        for si, s in enumerate(scenes):
            e = scenes[si + 1] if si + 1 < len(scenes) else len(units)
            block = units[s + 1:e]
            speakers = {b["speaker"] for b in block if b["type"] == "line"}
            if args.role in speakers:
                for b in block:
                    if b["type"] == "line" and b["speaker"] != args.role:
                        keep_ids.add(b["id"])
        lines = [l for l in lines if l["id"] in keep_ids]

    if args.limit:
        lines = lines[:args.limit]

    print(f"К озвучке: {len(lines)} реплик, потоков: {args.concurrency}")
    sem = asyncio.Semaphore(args.concurrency)
    done = {"ok": 0, "skip": 0, "empty": 0, "err": 0}
    errors = []
    tasks = [synth(sem, l, args.force) for l in lines]
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        status, info = await coro
        done[status] = done.get(status, 0) + 1
        if status == "err":
            errors.append(info)
        if i % 25 == 0 or i == len(lines):
            print(f"  {i}/{len(lines)}  ok={done['ok']} skip={done['skip']} err={done['err']}")

    # индекс: id -> файл (для приложения)
    idx = {str(l["id"]): f"audio/{l['id']}.mp3"
           for l in [u for u in units if u["type"] == "line"]
           if (OUT / f"{l['id']}.mp3").exists()}
    (OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    print(f"\nГотово: ok={done['ok']} skip={done['skip']} empty={done['empty']} err={done['err']}")
    print(f"Всего файлов в индексе: {len(idx)}  →  audio/index.json")
    if errors:
        print("Ошибки:", *errors[:5], sep="\n  ")


if __name__ == "__main__":
    asyncio.run(main())
