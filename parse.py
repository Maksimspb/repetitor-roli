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
# «про что явление» — пишется руками, парсер только подставляет
NOTES = ROOT / "data" / "scene_notes.json"

# ---- Канонические имена ролей -------------------------------------------------
# ключ = каноничное имя; значения = все встречающиеся варианты написания (в нижнем регистре)
CANON = {
    "Мурзавецкая": ["мурзавецкая", "мурзавуцкая", "мурзовецкая"],
    "Мурзавецкий": ["мурзавецкий", "мурзовецкий", "мурзавуцкий", "аполлон", "аполон", "апполон"],
    "Купавина":    ["купавина"],
    "Лыняев":      ["лыняев"],
    "Беркутов":    ["беркутов"],
    "Чугунов":     ["чугунов"],
    # В этой адаптации две Глафиры — их играют разные актрисы, и роли надо
    # репетировать порознь. В docx вторая подписана «Глафира2» / «Глафира 2»,
    # первая — просто «Глафира»: Глафира 1 это всё, что не Глафира 2.
    "Глафира 1":   ["глафира", "глафира1", "глафира 1"],
    "Глафира 2":   ["глафира2", "глафира 2"],
    "Горецкий":    ["горецкий"],
    "Павлин":      ["павлин", "павли"],   # «Павли и Влас хором» — опечатка в исходнике
    "Анфуса":      ["анфуса", "анфиса"],
    "Влас":        ["влас"],
    "Подрядчик":   ["подрядчик", "подрячик"],
    "Маляр":       ["маляр"],
    "Столяр":      ["столяр"],
    "Староста":    ["староста"],
    "Садовник":    ["садовник"],
    "1-й Крестьянин": ["1-й крестьянин", "1 крестьянин", "первый крестьянин", "крестьянин 1"],
    "2-й Крестьянин": ["2-й крестьянин", "2 крестьянин", "второй крестьянин", "крестьянин 2", "2"],
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
    r"(?P<name>(?:\d+-?[йяео]?\s+)?[А-ЯЁ][а-яё]+\s*\d?"
    r"(?:\s+(?:и\s+)?[А-ЯЁ][а-яё]+\s*\d?){0,3}(?:\s+и\s+\d)?)"   # «Крестьянин 1 и 2»
    r"\s*(?:хором)?"                                              # «Павлин и Влас хором:»
    r"\s*(?P<paren>\([^)]*\)\s*)?"
    r"\s*(?P<sep>[.:])\s*"
    r"(?P<text>.*)$"
)

# несколько говорящих: «Павлин и Влас хором», «Павлин, Влас»
CHORUS_SPLIT = re.compile(r"\s+и\s+|,\s*|\s+хором", re.I)

# В исходном docx часть реплик слиплась в один абзац:
#   «…мерси! (Целует у нее руку.)  Мурзавецкая . Поди спать!»
# Настоящую склейку от простого упоминания фамилии в тексте
# («Наш общий знакомый, Мурзавецкий. Проводите меня») отличает разделитель:
# пробел ПЕРЕД точкой либо двоеточие — так набран этот файл.
_NAMES = "|".join(re.escape(v) for v in sorted(
    {v.capitalize() for v in VAR2CANON} | set(CANON), key=len, reverse=True))
#
# Признак склейки — имя в ИМЕНИТЕЛЬНОМ падеже (то есть ровно так, как оно
# написано в каноне) сразу после конца предыдущей фразы. По фамилии в этой
# пьесе почти не обращаются, а когда упоминают — падеж косвенный
# («у Лыняева», «с Мурзавецким»), и под правило это не попадает.
# Требование «после конца фразы» отсекает приложения внутри предложения:
# «Наш общий знакомый, Мурзавецкий. Проводите меня» — тут перед именем запятая.
# Отчество после имени — значит это обращение, а не подпись: «Глафира Алексеевна».
_PATRON = r"(?![А-ЯЁ][а-яё]+(?:вна|чна|ична|ович|евич|ич)\b)"
_WHO = (r"(?:" + _NAMES + r")(?:\s+и\s+(?:" + _NAMES + r"))?"   # в т.ч. хоровое «Анфуса и Анфиса»
        r"(?:\s*\([^)]*\))?")                                   # необязательная ремарка

# Разделитель после имени бывает потерян совсем: «…шутка… Глафира Ну вот я не спала…».
GLUE_RE = re.compile(
    r"(?<=[.!?…»)])\s+"
    r"(" + _WHO + r")(?:\s*[.:]\s*|\s+)"
    + _PATRON + r"(?=[А-ЯЁ«])"
)

# Абзац начинается с имени, но без точки и двоеточия: «Анфиса Я по водочке скучаю!»
NOSEP_SPEAKER = re.compile(r"^\s*(" + _WHO + r")\s+" + _PATRON + r"(?=[А-ЯЁ«])")


# Реплики, у которых в docx потеряна подпись: абзац начинается сразу с ремарки,
# и по тексту говорящего не вывести. Единственный случай на всю пьесу — по смыслу
# сцены это Мурзавецкая (она вызвала Лыняева поручением, он ей и отвечает).
# Установлено исполнителем роли, а не догадкой парсера.
MANUAL_SPEAKER = {
    "(Лыняеву.)  А кабы не поручение": "Мурзавецкая",
    # Абзац без подписи между двумя репликами племянника: по правилу «продолжение
    # предыдущего» вышел бы Мурзавецкий, но он тут же отвечает «ма тант, ваших слов
    # не понимаю» — значит говорила тётка.
    "Долго ты меня будешь мучить да срамить": "Мурзавецкая",
}

# Абзац без подписи, который на самом деле — продолжение речи предыдущего
# говорящего: в docx длинные реплики разбиты на абзацы, и подпись стоит только
# у первого. Отличаем от настоящей ремарки: ремарка описывает действие в третьем
# лице, речь — от первого или второго.
STAGE_VERBS = re.compile(
    r"\b(уход|входит|входят|садит|встаёт|встает|занавес|играют|подходит|"
    r"обнимает|целует|показывает|берёт|берет|подаёт|подает|бросает)\w*", re.I)
# служебные начала ремарок и заголовков
STAGE_OPEN = re.compile(
    r"^\s*(Входит|Входят|Уходит|Уходят|Те же|Из |За |Слышен|Слышны|Показываются|"
    r"Показывается|Декорация|Лица|СЦЕНА|Сцена|Проходка|Занавес|Вбегает|Садятся|Садится)")
ROLE_START = re.compile(r"^\s*(?:" + _NAMES + r")\b")


def is_continuation(p: str) -> bool:
    """Абзац без подписи: это прямая речь или всё-таки ремарка?

    Опора на то, как ремарки устроены в этом файле: они либо перечисляют
    участников явления, либо начинаются с имени роли («Купавина пишет.»),
    либо со служебного слова («Входит…», «За сценой…», «Те же…»).
    Всё остальное с буквами — речь.
    """
    t = (p or "").strip()
    if not t or not re.search(r"[А-Яа-яЁё]", t):
        return False
    if re.match(r"^\s*\(.*\)\s*$", t):            # целиком в скобках — ремарка
        return False
    if is_stage_start(t) or STAGE_OPEN.match(t):
        return False
    bare = re.sub(r"\([^)]*\)", " ", t)             # ремарки внутри речи не считаются
    if STAGE_VERBS.search(bare):
        return False
    words = re.findall(r"[А-Яа-яЁё]+", bare)
    if not words:
        return False
    caps = [w for w in words if w[:1].isupper()]
    # список участников / заголовок — но в них не бывает вопросов и восклицаний,
    # а «Анфуса Тихоновна!.. Поезжайте на лошадях Мишеля!» — это обращение
    if (len(caps) >= 2 and len(caps) / len(words) > 0.6
            and not re.search(r"[?!]", bare)):
        return False
    m = ROLE_START.match(t)
    if m:
        rest = t[m.end():].lstrip()
        # «Анфуса Тихоновна!..» — это обращение, а не ремарка про Анфусу
        if not re.match(r"^[А-ЯЁ][а-яё]+(?:вна|чна|ична|ович|евич|ич)", rest):
            return False
    return True


def strip_orphan_action(text: str):
    """«Открывает сумку и вынимает деньги.)  Вот извольте!» — в docx у ремарки
    потеряна открывающая скобка. Вернуть (ремарка, чистый текст)."""
    m = re.match(r"^\s*([^()]{3,}?)\)\s+(?=\S)", text)
    if m:
        return m.group(1).strip().rstrip("."), text[m.end():].strip()
    return "", text


def manual_line(p: str):
    """Вернуть (speaker, action, text) для реплики с потерянной подписью."""
    for prefix, who in MANUAL_SPEAKER.items():
        if p.startswith(prefix):
            m = re.match(r"^\s*\(([^)]*)\)\s*(.*)$", p, re.S)
            action = m.group(1).strip().rstrip(".") if m else ""
            return who, action, (m.group(2).strip() if m else p)
    return None, "", p


def split_glued(p: str):
    """Разбить абзац, в котором слиплись несколько реплик разных персонажей.

    Режем только то, что само является репликой. Иначе под нож попадают
    ремарки и списки участников явления, где имена стоят рядом по делу:
    «Входит Анфуса . Анфиса.» или «Лыняев , Глафира , Анфуса . Анфиса.»
    """
    m = SPEAKER_RE.match(p or "") or NOSEP_SPEAKER.match(p or "")
    if m:
        name = (m.groupdict().get("name") or m.group(1)).strip()
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
        if is_stage_start(name) or resolve_speaker(name)[0] is None:
            return [p]
        # дальше начинается текст самой реплики: у полного шаблона это конец
        # разделителя, у шаблона без разделителя — конец имени
        head = m.end("sep") if "sep" in m.groupdict() else m.end()
    elif is_continuation(p):
        head = 0            # продолжение речи тоже бывает склеено со следующей репликой
    else:
        return [p]
    cuts = [g.start(1) for g in GLUE_RE.finditer(p) if g.start(1) >= head]
    if not cuts:
        return [p]
    parts, prev = [], 0
    for c in cuts:
        chunk = p[prev:c].strip()
        if chunk:
            parts.append(chunk)
        prev = c
    tail = p[prev:].strip()
    if tail:
        parts.append(tail)
    return parts


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
    # расклеить абзацы, в которых несколько реплик подряд оказались в одной строке
    paras = [q for p in paras for q in split_glued(p)]

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

        who, m_action, m_text = manual_line(p)
        if who:
            units.append({
                "type": "line",
                "id": len([u for u in units if u.get("type") == "line"]),
                "speaker": who, "speaker_raw": who, "chorus": False,
                "action": m_action,
                "inline_actions": re.findall(r"\(([^)]*)\)", m_text),
                "text": m_text, "act": act, "scene": scene,
            })
            continue

        m = SPEAKER_RE.match(p)
        nosep = None if m else NOSEP_SPEAKER.match(p)
        if m or nosep:
            if m:
                name = m.group("name").strip()
                paren = (m.group("paren") or "").strip()
                body = m.group("text")
            else:
                # подпись без точки и двоеточия: «Анфиса Я по водочке скучаю!»
                whole = nosep.group(1).strip()
                pm = re.match(r"^(.*?)\s*(\([^)]*\))\s*$", whole)
                name = (pm.group(1) if pm else whole).strip()
                paren = pm.group(2) if pm else ""
                body = p[nosep.end():]
            if is_stage_start(name):
                units.append({"type": "stage", "text": p, "act": act, "scene": scene})
                continue
            canon, chorus, raw = resolve_speaker(name)
            if canon is None:
                units.append({"type": "stage", "text": p, "act": act, "scene": scene})
                continue
            action = paren
            action = action[1:-1].strip() if action.startswith("(") else action
            orphan, body = strip_orphan_action(body)
            if orphan and not action:
                action = orphan
            # ремарки внутри текста реплики вытащим отдельно, но текст оставим целым
            inline_actions = re.findall(r"\(([^)]*)\)", body)
            units.append({
                "type": "line",
                "id": len([u for u in units if u.get("type") == "line"]),  # стабильный id реплики
                "speaker": canon,
                "speaker_raw": raw,
                "chorus": chorus,
                "action": action,                 # ремарка перед репликой
                "inline_actions": inline_actions,  # ремарки внутри
                "text": body.strip(),
                "act": act,
                "scene": scene,
            })
            continue

        # абзац без подписи, но с прямой речью — продолжение предыдущего говорящего
        last = next((u for u in reversed(units) if u.get("type") == "line"), None)
        if last and is_continuation(p):
            orphan, body = strip_orphan_action(p)
            units.append({
                "type": "line",
                "id": len([u for u in units if u.get("type") == "line"]),
                "speaker": last["speaker"], "speaker_raw": last["speaker"],
                "chorus": False, "action": orphan,
                "inline_actions": re.findall(r"\(([^)]*)\)", body),
                "text": body, "act": act, "scene": scene,
                "continued": True,
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

    # --- «про что явление»: короткое описание из scene_notes.json
    notes = {}
    if NOTES.exists():
        notes = json.loads(NOTES.read_text(encoding="utf-8"))
    missing_notes = []
    for u in units:
        if u["type"] != "scene":
            continue
        key = f"{u.get('act') or ''}|{u['title']}"
        if key in notes:
            u["summary"] = notes[key]
        else:
            missing_notes.append(key)
    if missing_notes:
        print(f"Без описания: {len(missing_notes)} явлений")
        for k in missing_notes[:10]:
            print("   ", k)

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
