# VouchAI

RL-среда для дообучения ИИ-аудиторов: вымышленные компании, инструменты
расследования, скрытые финансовые ошибки и награда, которую нельзя заговорить.
Genesis Hackathon 2026, трек FinTech.

**Every claim needs a receipt.**

Статус: фаза 1 — генератор (мир, события, движок проводок, ошибки
`duplicate_invoice` и `period_cutoff`), среда с пятью инструментами и общий
оценщик. Остальные два типа ошибок, сценарии взаимодействия, двойники и
независимый проверяльщик — следующие фазы. План: [PLAN.md](PLAN.md).

Подключение (Python 3.10+, только стандартная библиотека; из корня репозитория
или с `PYTHONPATH=<путь к репозиторию>`):

```python
from vouchai import VouchAIEnv

env = VouchAIEnv(mode="eval")          # аргументы необязательны; среда и оценщик — в дочернем процессе
obs, info = env.reset(seed, config)    # config: None, имя пресета или {"preset": ..., "overrides": {...}}
obs, reward, terminated, truncated, info = env.step(
    {"action": "list_records", "table": "ledger", "cursor": None, "limit": 50})
results = env.finalize()               # P, R, F1, return, steps по эпизодам
env.close()
```

Проверка:

```
python -m vouchai check
```

Один эпизод на диск: `python -m vouchai generate --seed 7 --config jury_like --out ep7`.

Все компании, счета и суммы в данных проекта вымышлены. Это программная задача,
а не профессиональное аудиторское заключение.
