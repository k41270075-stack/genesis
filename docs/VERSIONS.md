# Версии и параметры повтора

Всё, что нужно, чтобы повторить любой прогон бит в бит.

| Что | Где зафиксировано | Значение |
|---|---|---|
| Код | git-тег сдачи | `v1.3.0` (`python -m vouchai version`) |
| Версии среды | `vouchai/version.py`, в каждом `manifest.json` и `provenance.json` | `env_version`, `generator_version`, `schema_version`, `config_version`, `reward_version` |
| Python | `Dockerfile`, CI | образ — 3.11; CI — 3.10, 3.11, 3.12 (Linux) и 3.11 (Windows, путь с кириллицей и пробелами) |
| Базовый образ | `Dockerfile` | `python:3.11-slim` по multi-arch digest `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535` |
| Зависимости | `pyproject.toml` | нет: ядро, проверка и адаптер жюри — только стандартная библиотека; линтер `ruff==0.6.9` — только в CI |
| Случайность | `vouchai/rng.py` | счётчиковые потоки SHA-256 от `(seed, имя потока)`; ключ корня по умолчанию публичный, для закрытого прогона — `VOUCHAI_KEY` (видит только зона оценщика) |
| Конфиг эпизода | `provenance.json` → `config` (полностью разрешённый), `episodes.jsonl` → sha256 конфига | пресет или объект; все выборы `choice`/`range` разрешаются от seed |
| Рецепты жюри | `recipes/jury_d01_d20.json` | `team_config` для D01–D20, строгая постановка |
| Эталонные хеши | `tests/golden.json` | sha256 открытых таблиц для набора seed и конфигов; `tests/test_repro.py` |
| Окружение процесса | `ProcessEnv`, `Dockerfile` | `PYTHONHASHSEED=0`, `PYTHONUTF8=1`; порядок ключей JSON фиксирован, деньги — целые, курсы — десятичные строки |

**Повтор эпизода:** `python -m vouchai generate --seed S --config C --out ep` даёт те же
файлы при той же версии; `python -m vouchai replay` проигрывает `trajectories.jsonl` и
сравнивает каждый переход. Эпизод жюри: `judge_adapter.generate_episode(S, team_config,
dir)` — те же байты при тех же `S`, `team_config` и версии (проверяется в
`reports/JURY_SELFTEST.md`, парные проверки, условие 1).
