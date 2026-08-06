# Разведка рынка: приложения для заучивания роли (2026)

Исследование перед разработкой: что уже есть, где пробел. Кратко — **пословной
проверки текста на русском для театральной пьесы нет ни у кого**, это и есть ниша.

## Три поколения приложений

1. **Суфлёры-читалки** (2010-е): сам записываешь реплики или робо-TTS, приложение
   прячет твои строки. Проверки правильности нет.
   → LineLearner ($5), Rehearsal Pro ($20), Script Rehearser (~$10/год), Run Lines With Me.
2. **Cue-recognition** (2017+): слушает микрофон, ловит что ты *договорил* реплику
   (по последним словам), подаёт следующую. ASR только для тайминга, не для правильности.
   → **coldRead** (лидер Backstage, поддерживает русский — но только cue).
3. **AI-партнёр + проверка** (2024–2026): LLM + студийный TTS (обычно ElevenLabs).
   → ScenePartner, ActingPal (53 голоса, умеет импровизировать), RehearseNow, SceneStudy.

## Кто реально сверяет слова (ключевой вопрос)

Узкое место рынка. Пословно сверяют произнесённое с текстом только:
- **ActOnCue** (web+iOS) — «line validation», облачный ASR ловит пропуски. PAYG ~$20.
- **LineLearn.app** (web) — фонемные алгоритмы, оценка A–F за строку. Free / $4.99 / $8.99.

Оба — **на английском**, без детального диффа «сказал/в тексте». Остальные (coldRead,
ScenePartner, ActingPal, RehearseNow) слушают микрофон **только для тайминга подачи**.

## Технологии ASR под задачу

- **Whisper** (Large-v3 **Turbo** — ~5× быстрее, качество на русском держит), **faster-whisper**
  (CTranslate2), **WhisperX** (+ forced alignment на wav2vec2 → пословные таймстемпы ±50мс,
  именно это нужно для подсветки конкретных слов).
- **superwhisper** (macOS, on-device, офлайн, русский), **Apple Speech / SpeechAnalyzer**,
  **WhisperKit** (Apple Silicon/CoreML), **NVIDIA Parakeet V3** (25 языков вкл. русский, ~10× Whisper).
- **Forced alignment + WER** — пословный дифф «распознанное vs эталон» с подсветкой
  пропусков/замен/вставок. Именно этого нет в актёрских приложениях.

## Пробелы = возможности

1. Пословная сверка с подсветкой почти отсутствует (2–3 решения, только английский).
2. **Русского в проверке точности нет вообще** — чистое белое пятно (технически всё готово:
   Whisper Turbo/Parakeet + alignment на русском работают).
3. Все заточены под киносайды/кастинг, не под **длинную пьесу** (акты, монологи, роль целиком).
4. «Смысловая» проверка (LLM-судья перифраза) вместо буквальной — незанятая ниша.
5. Полноценного SRS (интервальные повторения по репликам) почти нет.
6. Локальный офлайн-вариант на русском (superwhisper/WhisperKit + alignment) не существует.

**Итог:** русскоязычное приложение, которое слушает актёра локальным Whisper, пословно
подсвечивает расхождения с текстом пьесы, отличает перифраз от ошибки (LLM), играет партнёра
голосом и держит длинные театральные тексты с SRS — конкурентов на русском не имеет.

## Таблица сравнения

| Приложение | Платформа | Цена | ASR-проверка | TTS-партнёр | Скрытие реплик | Русский |
|---|---|---|---|---|---|---|
| LineLearner | iOS, Android | $5 разово | Нет | Нет | Нет | — |
| Rehearsal Pro | iOS, Mac | $19.99 | Нет | Нет | Да | — |
| Script Rehearser | iOS, Android | ~$10/год | Нет | Да (20+) | Да | вероятно |
| coldRead | iOS, Mac | free / $6.99–10.99 мес | Нет (cue) | Нет | Нет | **Да** (cue) |
| ScenePartner | web, iOS | free / $12.99 / $29.99 | Нет (cue) | Да (ElevenLabs) | Да | Нет |
| ActingPal | iOS, Android | $9.99/мес | Нет (cue) | Да (53) | Да | Нет |
| ActOnCue | web, iOS | PAYG ~$20 | **Да** | Да | Да | не указано |
| LineLearn.app | web | free / $4.99 / $8.99 | **Да** (A–F) | Да (Gemini) | Да | не указано |
| **Этот проект** | web (Mac+телефон) | бесплатно | **Да, пословно** | Да (система) | Да | **Да** |

## Источники
- Backstage — Line Memorization Apps: https://www.backstage.com/magazine/article/line-memorization-apps-actors-70280/
- ActOnCue blog — Best Line Learning Apps: https://actoncue.com/blog/best-line-learning-apps
- coldRead: https://coldreadapp.com/ · ScenePartner: https://scenepartner.ai/ · ActingPal: https://www.actingpal.com/
- LineLearn.app: https://linelearn.app/ · Rehearsal Pro: https://rehearsal.pro/
- WhisperX: https://github.com/m-bain/whisperx · Whisper variants: https://modal.com/blog/choosing-whisper-variants
- superwhisper models (русский, on-device): https://superwhisper.com/models
- Русские суфлёры: SUFLER.PRO, Телесуфлер (App Store)
