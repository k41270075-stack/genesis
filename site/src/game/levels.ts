// The levels of «Ревизор»: each one is a function of the project, 30–60 seconds.
import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export interface ScoreLine { label: string; value: string; tone?: "good" | "bad" | "info" }
export interface LevelResult { stars: number; lines: ScoreLine[]; note?: string }
export interface LevelProps { finish: (r: LevelResult) => void }

export interface LevelInfo {
  id: string;
  title: string;
  covers: string;   // what part of VouchAI the level shows
  goal: string;     // one-line instruction
  icon: string;     // sprite name for the map
  Comp: LazyExoticComponent<ComponentType<LevelProps>>;
}

export const LEVELS: LevelInfo[] = [
  { id: "kassa", title: "Касса", icon: "receipt", covers: "Квитанции и формула награды",
    goal: "Посмотри, как настоящий аудитор сдал эпизод и за что получил награду.", Comp: lazy(() => import("../levels/L01Kassa")) },
  { id: "twins", title: "Двойники", icon: "invoice", covers: "Законные двойники-ловушки",
    goal: "Два счёта: один клиент, одна сумма. Дубль или нет?", Comp: lazy(() => import("../levels/L02Twins")) },
  { id: "clocks", title: "Часы", icon: "coin", covers: "Курс, граница периода, сценарий X1",
    goal: "Банк и компания живут в разных поясах. Выбери правильный курс.", Comp: lazy(() => import("../levels/L03Clocks")) },
  { id: "audit", title: "Ревизия", icon: "hero", covers: "5 инструментов, 100 шагов, matcher",
    goal: "Проведи мини-аудит настоящего эпизода и сдай бланк.", Comp: lazy(() => import("../levels/L04Audit")) },
  { id: "boss", title: "Хлестаков", icon: "boss", covers: "Награду нельзя заговорить",
    goal: "Босс-болтун. Слова его не ранят — только квитанции.", Comp: lazy(() => import("../levels/L05Boss")) },
  { id: "invaders", title: "Нашествие", icon: "enemy", covers: "Атаки-однострочники, массовая пометка",
    goal: "Разоблачи каждую атаку: ни одна не набирает F1 выше порога.", Comp: lazy(() => import("../levels/L06Invaders")) },
  { id: "coin", title: "Монета", icon: "coin", covers: "Аудит утечек: AUC ≈ 0,5",
    goal: "Подбрось монету и проверь, не подсказывают ли «пустые» признаки.", Comp: lazy(() => import("../levels/L07Coin")) },
  { id: "wall", title: "Стена", icon: "shield", covers: "Две зоны, закрытый режим, адаптер жюри",
    goal: "Отправь запросы через трубу stdio. Попробуй пролезть к эталону.", Comp: lazy(() => import("../levels/L08Wall")) },
  { id: "mirror", title: "Копирка", icon: "invoice", covers: "Парные проверки: смена ID и порядка",
    goal: "Шагни в зеркальный мир с чужими именами. Награда изменится?", Comp: lazy(() => import("../levels/L09Mirror")) },
  { id: "chest", title: "Сундук", icon: "chest", covers: "Seed → тот же мир, предсказание, replay",
    goal: "Вскрой запечатанное предсказание и сверь хеш.", Comp: lazy(() => import("../levels/L10Chest")) },
  { id: "scores", title: "Табло", icon: "star", covers: "Базовые политики, отчёты, команды",
    goal: "Таблица рекордов и все команды, чтобы проверить каждую цифру.", Comp: lazy(() => import("../levels/L11Scores")) },
];

export const levelIndex = (id: string) => LEVELS.findIndex((l) => l.id === id);
