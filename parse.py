#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер пьесы: docx -> data/play.json

Превращает драматургический текст в структуру:
  meta  — заголовок, список ролей с числом реплик
  units — плоский список блоков в порядке чтения:
          {type: act|scene|line|stage|song|meta, ...}

Решает засады формата «Волки и овцы»:
  - разнобой в написании имён (Анфуса/Анфиса, Мурзавецкий/Мурзовецкий…)  -> канон-словарь
  - ремарки под видом реплик (Входит X, Уходят)                         -> тип stage
  - два разделителя реплики: точка и двоеточие
  - ремарки внутри реплики (в скобках)                                  -> поле action, скрывается при заучивании
  - хоровые реплики (Павлин и Влас хором:, Все:, Голоса:)               -> speaker с флагом chorus
"""
import re
import json
import sys
import unicodedata
from pathlib import Path
from docx import Document

ROOT = Path(__file__).parent
DOCX = ROOT / "data" / "play.docx"
OUT = ROOT / "data" / "play.json"

# ---- Канонические имена ролей -------------------------------------------------
# ключ = каноничное имя; значения = все встречающиеся варианты написания (в нижнем регистре)
CANON = {
    "Мурзавецкая": ["мурзавецкая", "мурзавуцкая", "мурзовецкая"],
    "Мурзавецкий": ["мурзавецкий", "мурзовецкий", "мурзавуцкий", "аполлон", "аполон", "апполон"],
    "Купавина":    ["купавина"],
    "Лыняев":      ["лыняев"],
    "Беркутов":    ["беркутов"],
    "Чугунов":     ["чугунов"],
    "Глафира":     ["глафира"],
    "Горецкий":    ["горецкий"],
    "Павлин":      ["павлин"],
    "Анфуса":      ["анфуса", "анфиса"],
    "Влас":        ["влас"],
    "Подрядчик":   ["подрядчик", "подрячик"],
    "Маляр":       ["маляр"],
    "Столяр":      ["столяр"],
    "Староста":    ["староста"],
    "Садовник":    ["садовник"],
    "1-й Крестьянин": ["1-й крестьянин", "1 крестьянин", "первый крестьянин"],
    "2-й Крестьянин": ["2-й крестьянин", "2 крестьянин", "второй крестьянин"],
    "Все":         ["все"],
    "Голоса":      ["голоса"],
    "Лакей":       ["лакей", "лакеи"],
}
# обратный индекс: вариант -> канон
VAR2CANON = {}
for canon, variants in CANON.items():
    for v in variants:
        VAR2CANON[v] = canon

# слова, с которых начинается ремарка-действие, а не имя говорящего
STAGE_STARTS = (
    "входит", "входят", "уходит", "уходят", "проходка", "выходит", "выходят",
    "садятся", "садится", "встаёт", "встает", "занавес", "все уходят",
)

ROMAN_ACT = re.compile(r"^(Действие|ДЕЙСТВИЕ)\b", re.I)
SCENE = re.compile(r"^(Явление|ЯВЛЕНИЕ)\b", re.I)

# «Имя (ремарка) . текст»  или  «Имя: текст»
# имя = 1-3 слова с большой буквы (или «1-й Крестьянин»)
SPEAKER_RE = re.compile(
    r"^\s*"
    r"(?P<name>(?:\d+-?[йяео]?\s+)?[А-ЯЁ][а-яё]+(?:\s+(?:и\s+)?[А-ЯЁ][а-яё]+){0,3})"
    r"\s*(?P<paren>\([^)]*\)\s*)?"
    r"\s*(?P<sep>[.:])\s*"
    r"(?P<text>.*)$"
)

# несколько говорящих: «Павлин и Влас хором», «Павлин, Влас»
CHORUS_SPLIT = re.compile(r"\s+и\s+|,\s*|\s+хором", re.I)


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def resolve_speaker(raw: str):
    """Вернуть (canon_name|None, chorus_bool, display_raw). None если это не роль (ремарка/шум)."""
    raw_clean = re.sub(r"\bхором\b", "", raw, flags=re.I).strip(" ,")
    low = raw_clean.lower().strip()

    # прямое совпадение
    if low in VAR2CANON:
        return VAR2CANON[low], False, raw_clean

    # хоровая: разбить на части, если все части — известные роли
    parts = [p.strip() for p in CHORUS_SPLIT.split(raw_clean) if p.strip()]
    if len(parts) >= 2:
        canons = [VAR2CANON.get(p.lower()) for p in parts]
        if all(canons):
            label = " и ".join(dict.fromkeys(canons))  # уникальные, сохраняя порядок
            return label, True, raw_clean

    # одно слово с большой буквы, которого нет в каноне, но начинается не с ремарки —
    # считаем неизвестной ролью (сохраняем как есть, чтобы не терять реплику)
    if len(parts) == 1 and re.match(r"^[А-ЯЁ][а-яё]+$", parts[0]):
        return parts[0], False, raw_clean

    return None, False, raw_clean


def is_stage_start(name: str) -> bool:
    low = name.lower()
    return any(low.startswith(w) for w in STAGE_STARTS)


def parse():
    doc = Document(DOCX)
    paras = [norm(p.text) for p in doc.paragraphs]
    paras = [p for p in paras if p]

    units = []
    act = None
    scene = None
    title = None
    in_song = False
    song_lines = []

    for i, p in enumerate(paras):
        # заголовок пьесы / автор — первые строки до первого «Действие»
        if act is None and ROMAN_ACT.match(p) is None and SCENE.match(p) is None:
            low = p.lower()
            if low.startswith("текст песни"):
                in_song = True
                continue
            if in_song:
                # песня идёт до строки «Действие первое»
                song_lines.append(p)
                continue
            if title is None and ("островский" not in low and "комедия" not in low
                                  and "имя/роль" not in low and "волки и овцы" not in low):
                pass
            units.append({"type": "meta", "text": p})
            continue

        if ROMAN_ACT.match(p):
            if in_song and song_lines:
                units.append({"type": "song", "lines": song_lines})
                song_lines = []
                in_song = False
            act = p
            scene = None
            units.append({"type": "act", "title": p})
            continue

        if SCENE.match(p):
            scene = p
            units.append({"type": "scene", "title": p, "act": act})
            continue

        m = SPEAKER_RE.match(p)
        if m:
            name = m.group("name").strip()
            if is_stage_start(name):
                units.append({"type": "stage", "text": p, "act": act, "scene": scene})
                continue
            canon, chorus, raw = resolve_speaker(name)
            if canon is None:
                units.append({"type": "stage", "text": p, "act": act, "scene": scene})
                continue
            action = (m.group("paren") or "").strip()
            action = action[1:-1].strip() if action.startswith("(") else action
            # ремарки внутри текста реплики вытащим отдельно, но текст оставим целым
            inline_actions = re.findall(r"\(([^)]*)\)", m.group("text"))
            units.append({
                "type": "line",
                "speaker": canon,
                "speaker_raw": raw,
                "chorus": chorus,
                "action": action,                 # ремарка перед репликой
                "inline_actions": inline_actions,  # ремарки внутри
                "text": m.group("text").strip(),
                "act": act,
                "scene": scene,
            })
            continue

        # не структура и не реплика -> ремарка/народная сцена (показываем подсказкой)
        units.append({"type": "stage", "text": p, "act": act, "scene": scene})

    if in_song and song_lines:
        units.append({"type": "song", "lines": song_lines})

    # --- статистика по ролям ---
    roles = {}
    for u in units:
        if u["type"] == "line" and not u["chorus"]:
            roles[u["speaker"]] = roles.get(u["speaker"], 0) + 1
    roles_sorted = sorted(roles.items(), key=lambda kv: -kv[1])

    # --- метаданные сцен: участники, число реплик, превью, счётчик по ролям ---
    # проходим по units, для каждого scene смотрим блок реплик до следующего scene
    scene_idxs = [i for i, u in enumerate(units) if u["type"] == "scene"]
    for si, start in enumerate(scene_idxs):
        end = scene_idxs[si + 1] if si + 1 < len(scene_idxs) else len(units)
        block = units[start + 1:end]
        participants = []           # порядок появления, уникально
        per_role = {}               # роль -> сколько её реплик в сцене
        preview = ""
        for b in block:
            if b["type"] != "line":
                continue
            # хоровую разложим на участников для присутствия
            names = b["speaker"].split(" и ") if b["chorus"] else [b["speaker"]]
            for nm in names:
                if nm not in participants:
                    participants.append(nm)
                per_role[nm] = per_role.get(nm, 0) + 1
            if not preview:
                preview = f'{b["speaker"]}: {b["text"]}'
        u = units[start]
        u["participants"] = participants
        u["per_role"] = per_role
        u["n_lines"] = sum(1 for b in block if b["type"] == "line")
        u["preview"] = preview[:90]

    meta = {
        "title": "Волки и овцы (расширенная версия)",
        "author": "А. Н. Островский",
        "roles": [{"name": n, "lines": c} for n, c in roles_sorted],
        "total_units": len(units),
        "total_lines": sum(1 for u in units if u["type"] == "line"),
    }

    OUT.write_text(json.dumps({"meta": meta, "units": units}, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    # --- отчёт в консоль для проверки ---
    print(f"Юнитов: {len(units)}  |  реплик: {meta['total_lines']}")
    print("Роли (реплик):")
    for r in meta["roles"]:
        print(f"  {r['lines']:4}  {r['name']}")
    # неизвестные говорящие (не из канона) — их стоит глазами проверить
    known = set(CANON.keys())
    unknown = sorted({u["speaker"] for u in units
                      if u["type"] == "line" and not u["chorus"] and u["speaker"] not in known})
    if unknown:
        print("\nНеизвестные роли (проверь, не опечатка ли):", ", ".join(unknown))
    n_stage = sum(1 for u in units if u["type"] == "stage")
    print(f"\nРемарок/сцен.указаний: {n_stage}")
    print(f"JSON сохранён: {OUT}")


if __name__ == "__main__":
    parse()
