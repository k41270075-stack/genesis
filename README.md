# VouchAI

**Every claim needs a receipt.**

RL-среда для дообучения ИИ-аудиторов: вымышленные компании, инструменты
расследования, скрытые финансовые ошибки и награда, которую нельзя заговорить.
Вывод агента засчитывается, только если он подтверждён записями книг.
Genesis Hackathon 2026, трек FinTech.

*Vouching* — аудиторский термин: проверка записи в книгах по первичному документу.
Ровно это делает агент в VouchAI.

## Одна команда проверки

```
docker build -t vouchai .
docker run --rm --network none --read-only --tmpfs /tmp --cpus 2 --memory 4g vouchai check
```

Без Docker — на любом Python 3.10+ (только стандартная библиотека, зависимостей нет):

```
python -m vouchai check
```

Платформа сборки образа: `python:3.11-slim` (закреплён по digest), linux/amd64 и
linux/arm64. Сеть при сборке нужна только для загрузки базового образа (шагов
`RUN` нет), при проверке отключена. Проверка занимает около 2 минут в CI на
Linux и 4–6 минут на ноутбуке с Windows; печатает время по разделам.

Официальный изолированный запуск — зона среды и оценщика (uid 10001) и политика
(uid 10002, пустое окружение) под разными пользователями ОС; политика-шпион
пытается прочитать `/proc` и журналы зоны оценщика:

```
docker run --rm --network none --read-only --tmpfs /tmp --user 0 vouchai \
    eval --isolated --policy simple_reconciler --config jury_like --seeds 0:20 --spy
```

Обычный `check` в образе идёт от uid 10001, поэтому разделение по uid в нём не
проверяется — его проверяет эта команда (так же делает CI).

## Подключение среды (Python-импорт)

Скрипт в корне репозитория или `PYTHONPATH=<путь к репозиторию>` (в PowerShell:
`$env:PYTHONPATH="<путь>"`; то же нужно для `--policy pkg.module:Class`):

```python
from vouchai import VouchAIEnv

env = VouchAIEnv(mode="eval")        # аргументы необязательны; "train" — открытый режим обучения
obs, info = env.reset(seed, config)  # config: None | имя пресета | {"preset": ..., "overrides": {...}}
obs, reward, terminated, truncated, info = env.step(
    {"action": "list_records", "table": "ledger", "cursor": None, "limit": 50})
...
results = env.finalize()             # P, R, F1, return, steps, termination по эпизодам
env.close()
```

- Первое наблюдение содержит `action_formats` — пример каждого действия и полного
  ответа, так что LLM-агенту ничего не нужно угадывать.
- Действия: `list_records(table, cursor, limit)`, `get_record(table, id)`,
  `get_document(doc_id)`, `calculator(expression)`, `submit(findings)` — схема
  `schemas/action.json`; наблюдение — `schemas/observation.json`.
- Ответ: `{"action": "submit", "findings": {"episode_id": ..., "findings": [...]}}`;
  принимается и плоская форма `{"action": "submit", "episode_id": ..., "findings": [...]}`.
  Формат вывода — `schemas/findings.json`, правила сумм и доказательств — `policy.findings`
  в первом наблюдении.
- Генератор, эталон и оценщик живут в дочернем процессе. Это граница по процессам;
  граница по правам ОС — `eval --isolated` выше (см. `docs/LIMITATIONS.md`).
- В `eval` награда на каждом шаге 0, итоги — через `finalize()`. В `train`
  терминальная награда возвращается агенту, а при неверной структуре ответа
  `info["grade"]["errors"]` объясняет, какого поля не хватило.
- Готовую или преобразованную папку эпизода можно загрузить:
  `env.reset(options={"episode_dir": "episodes/dev/ep_…"})` (относительный путь — от
  текущей папки).

### Конфиг

`reset(seed, config)`: `config` — имя пресета или `{"preset": ..., "overrides": {...}}`
(ключи переопределений можно писать и рядом с `preset`). Значения пресетов вида
«выбор» и «диапазон» разрешаются от seed.

| Поле | Значения |
|---|---|
| `company.base_currency` | KZT, USD, EUR (а также GBP, CNY, JPY, KWD) |
| `company.timezone`, `company.bank_timezone` | смещение `±HH:MM`, до ±14:00 |
| `company.period`, `company.period_start` | `month` или `quarter`; первое число месяца (квартала) |
| `size.customers`, `size.invoices`, `size.target_ledger_rows` | 3–60, 15–200, 200–2000 |
| `size.foreign_share`, `size.currencies` | 0–1; список валют |
| `policy.fx_rate_date`, `policy.rounding` | `same_day_or_previous` / `previous_day_or_earlier`; `half_even` / `half_up` |
| `errors.<тип>.count`, `errors.<тип>.variants` | 0–12 на тип (всего ≤ 12); подмножество вариантов |
| `interactions.partial_fx_boundary`, `interactions.duplicate_with_partial` | X1, X2 (каждое считается за 2 ошибки) |
| `mix` | `regular`, `clean`, `interaction` |
| `render.id_seed`, `render.order_seed` | перерисовать ID и порядок строк того же мира |

Пресеты: `default`, `jury_like` (25 % чистых, 25 % со взаимодействием), `clean`,
`train`, `dev`, `smoke`, `L1`–`L5`, `corners_small`, `corners_large`.

### Адаптеры политик (четыре базовые политики жюри)

`vouchai/adapters` — единственное место трансляции между политикой и средой:

```python
from vouchai.adapters import python_policy, subprocess_policy, baseline
from vouchai.harness.runner import run

run(python_policy(my_agent), [(seed, "jury_like")])          # объект с act/predict/__call__
run(subprocess_policy(["my-agent"]), [(seed, "jury_like")])  # отдельная программа, JSON lines
run(baseline("oracle", episode_dirs=["ep"]), [(0, None)],     # oracle — только у оценщика
    options_for=lambda s, c: {"episode_dir": "ep"})
```

Наши версии четырёх базовых политик: `baseline("random_explorer")`,
`baseline("simple_reconciler")`, `baseline("flag_all")`, `baseline("oracle", ...)`.
Из командной строки: `python -m vouchai run --policy pkg.module:Class --config
jury_like --seeds 0:20` (среда — в дочернем процессе). `vouchai_auditor` в отчётах —
это класс `vouchai_verify.auditor:Auditor`.

## Утверждение → доказательство → команда

| Утверждение | Доказательство | Команда |
|---|---|---|
| Контракт reset/step соблюдён: лимиты, завершение, неверный ввод, режимы; враждебный ввод не роняет прогон | `tests/test_env.py`, `tests/test_process_env.py` | `python -m unittest tests.test_env tests.test_process_env` |
| Эталон не утекает в наблюдения, ошибки и траектории; шпион не находит эталон в окружении, на диске и в памяти своего процесса, а при разных uid (`eval --isolated`) — и в `/proc` зоны оценщика | `tests/test_attacks.py`, `tests/test_isolated.py`, CI | `python -m unittest tests.test_attacks` |
| Чистые книги сходятся; в открытых — ровно объявленные расхождения; каждый набор доказательств достаточен сам по себе | независимый `vouchai_verify`, отчёт A/B/C | `python -m vouchai_verify episodes/dev/* --report` |
| Ни один из 10 проверенных «пустых» признаков (секунды, символы ID, день недели, круглость суммы, позиция строки, похожие документы рядом) не отличает цели ошибок от подобранных контрольных документов: \|AUC − 0,5\| ≤ 0,1 | `reports/LEAK_AUDIT.md`, `tests/test_attacks.py` | `python -m vouchai report` |
| Награду нельзя обмануть: дубли, «пометить всё», угаданные ID, текст объяснения, валюта документа, однострочные признаки | `tests/test_grader.py`, `reports/FAILURE_ANALYSIS.md` | `python -m vouchai report` |
| Oracle получает 1.0, базовые политики — заметно меньше; P, R, F1, награда, шаги и время отдельно | `reports/BASELINES.md` | `python -m vouchai demo` |
| Задача решаема по открытым данным: скриптовый аудитор, видящий только наблюдения, находит все ошибки с полными доказательствами примерно за 15 шагов (F1 = 1.0), наивная сверка — около 0,25 на dev (0,34 на `jury_like` 0:20) | `tests/test_auditor.py`, `reports/BASELINES.md` | `python -m vouchai run --policy vouchai_verify.auditor:Auditor --config jury_like` |
| Повтор seed и действий точен до байта, на Windows и Linux | `tests/golden.json`, `tests/test_repro.py`, CI на двух ОС | `python -m vouchai replay` |
| Перестановка строк и смена ID (в том числе враждебная) сохраняют ответ oracle и награду | `tests/test_repro.py`, `tests/test_adapters.py` | `python -m vouchai transform ep7 --out ep7b --hostile` (после `generate ... --out ep7`) |

Самопроверка — по нашей интерпретации раздела 10 ТЗ (`reports/SCORECARD.md`);
официальные определения проверок организаторы пришлют отдельно, баллы ставит жюри.

## Состав сдачи (раздел 09 ТЗ)

| Материал | Где |
|---|---|
| Исходный код, лицензия, зависимости | `vouchai/`, `vouchai_verify/`, `LICENSE` (Apache-2.0); зависимостей нет, образ закреплён по digest |
| README: контейнер и одна команда | этот файл, `Dockerfile` |
| Matcher и награда, схемы, политики | `vouchai/grader/`, `docs/REWARD.md`, `schemas/`, `vouchai/policies/` |
| 10 train + 10 dev эпизодов | `episodes/train`, `episodes/dev` (с `PASSPORT.md`), индекс `episodes.jsonl` |
| Тесты среды, сопоставления и награды | `tests/` (`python -m vouchai check`) |
| Четыре адаптера базовых политик | `vouchai/adapters/` |
| Траектории | `trajectories.jsonl` (episode_id, step, action, observation, reward, terminated, truncated + policy, split; без эталона) |
| Записка о дизайне | `docs/DESIGN.md` |
| Демо | `python -m vouchai demo` |
| Диагностика P, R, F1, возврата, шагов и времени | `reports/BASELINES.md`, `reports/FAILURE_ANALYSIS.md` |

Отчёты в `reports/` написаны по-английски, документы в `docs/` — по-русски.

## Что внутри

| Каталог | Что |
|---|---|
| `vouchai/` | генератор, среда, оценщик, политики, харнесс (только стандартная библиотека) |
| `vouchai/grader/` | общий matcher и награда: нормализация, допуски, выбор при неоднозначности |
| `VOUCHAI_KEY` | секретный ключ корня случайности для закрытого прогона (видит только зона оценщика) |
| `vouchai/adapters/` | адаптеры политик: Python-объект, отдельный процесс (JSON lines), базовые политики |
| `vouchai_verify/` | независимый верификатор: не импортирует `vouchai`; скриптовый аудитор |
| `episodes/train`, `episodes/dev` | 10 + 10 открытых эпизодов с паспортами `PASSPORT.md` |
| `trajectories.jsonl` | траектории базовых политик и аудитора (train-режим, без oracle) |
| `episodes.jsonl` | индекс эпизодов для replay: seed и конфиг |
| `schemas/` | схемы действия, наблюдения и ответа |
| `docs/` | `DESIGN`, `REWARD`, `ACCOUNTING`, `SCHEMA`, `THREAT_MODEL`, `LIMITATIONS`, `claims.json` |
| `reports/` | `BASELINES`, `FAILURE_ANALYSIS`, `LEAK_AUDIT`, `SCORECARD` |
| `tests/` | тесты среды, сопоставления, награды, генератора, атак, воспроизводимости |

## Команды

```
python -m vouchai check [--full]                 # вся самопроверка
python -m vouchai demo [--seed 28112026]         # аудитор проходит эпизод + таблица политик
python -m vouchai generate --seed 7 --config jury_like --out ep7
python -m vouchai_verify ep7 --report --passport
python -m vouchai run --policy simple_reconciler --config jury_like --seeds 0:20
python -m vouchai eval --isolated --policy simple_reconciler --seeds 0:5 --spy
python -m vouchai transform ep7 --out ep7b --hostile
python -m vouchai replay trajectories.jsonl --index episodes.jsonl
python -m vouchai build-dataset                  # пересобрать episodes/, траектории, отчёт
python -m vouchai report                         # разбор сбоев и аудит утечек
python -m vouchai scorecard                      # самопроверка; пишет reports/SCORECARD.md на новых seed
```

## Четыре типа ошибок и два сценария

`duplicate_invoice`, `payment_allocation`, `fx_conversion`, `period_cutoff` —
каждый настраивается отдельно. **X1**: частичный валютный платёж у полуночи на
границе периода, курс взят по UTC-дате и разнесена только часть. **X2**: дубль
счёта и частичное распределение его оплаты. Подробно — `docs/DESIGN.md`.

## Предсказание

Эпизод `seed = 28112026`, конфиг `jury_like`, версия 1.2.0 — на любой машине:

- `episode_id = ep_QMQXXNPCGL35J5L4`;
- sha256 открытых таблиц `e421ba1a2f923cc43e1303a54e332b3a77a5b4e90574451464b0e1c3a65ae03b` —
  sha256 подряд записанных `ledger.csv`, `invoices.jsonl`, `payments.jsonl`, `fx.csv` из
  `public/` (на любой ОС: `python -c "import hashlib,pathlib as p;print(hashlib.sha256(b''.join(p.Path('ep/public',f).read_bytes() for f in ('ledger.csv','invoices.jsonl','payments.jsonl','fx.csv'))).hexdigest())"`);
- награда: oracle 1.0, `vouchai_auditor` 0.978, простая сверка −1.0,
  случайный исследователь −1.0, «пометить всё» −1.0.

```
python -m vouchai generate --seed 28112026 --config jury_like --out ep
python -m vouchai run --policy simple_reconciler --config jury_like --seeds 28112026:28112027
```

## Важно

Все компании, люди, счета, курсы и суммы вымышлены. Никаких реальных платежей,
карт и персональных данных. Это программная задача, а не профессиональное
аудиторское заключение. Лицензия — Apache-2.0.
