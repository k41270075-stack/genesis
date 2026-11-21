// «Паспорт ревизора»: stamps for what a visitor has really done on the site.
// Kept in this browser only (localStorage); nothing leaves the page.
import { useSyncExternalStore } from "react";
import { MODULES } from "../modules/registry";

export interface StampDef { id: string; title: string; hint: string }

// built on first use: the modules import this file, so the registry must not be read at load time
let cache: StampDef[] | null = null;
export const stamps = (): StampDef[] => (cache ??= [
  ...MODULES.map((m) => ({
    id: `m:${m.id}`, title: m.title,
    hint: m.id === "sandbox" ? "сдать ответ в песочнице" : m.id === "grade" ? "досмотреть разбор любого ответа" : "досмотреть запись до конца",
  })),
  { id: "tour", title: "Автотур", hint: "пройти 60-секундный тур целиком" },
  { id: "game", title: "Ошибка или двойник", hint: "закончить игру" },
  { id: "game_ace", title: "Без ложных обвинений", hint: "закончить игру с наградой не ниже +0,90" },
  { id: "custom", title: "Попытка обмана", hint: "отдать оценщику свой JSON" },
]);

const RANKS = [
  { from: 0, title: "Стажёр" },
  { from: 4, title: "Помощник ревизора" },
  { from: 9, title: "Ревизор" },
  { from: 14, title: "Старший ревизор" },
];
export const rankOf = (n: number) => (n >= stamps().length ? "Главный ревизор" : [...RANKS].reverse().find((r) => n >= r.from)!.title);

const KEY = "vouchai.passport.v1";
let earned: Record<string, number> = load();
const listeners = new Set<() => void>();
const toastListeners = new Set<(s: StampDef) => void>();

function load(): Record<string, number> {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, number>; } catch { return {}; }
}

export function earn(id: string): void {
  if (earned[id] || !stamps().some((s) => s.id === id)) return;
  earned = { ...earned, [id]: Date.now() };
  try { localStorage.setItem(KEY, JSON.stringify(earned)); } catch { /* private mode: keep in memory */ }
  listeners.forEach((f) => f());
  const def = stamps().find((s) => s.id === id)!;
  toastListeners.forEach((f) => f(def));
}

export function resetPassport(): void {
  earned = {};
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  listeners.forEach((f) => f());
}

export function usePassport(): Record<string, number> {
  return useSyncExternalStore((f) => { listeners.add(f); return () => listeners.delete(f); }, () => earned, () => earned);
}

export function onStamp(f: (s: StampDef) => void): () => void {
  toastListeners.add(f);
  return () => toastListeners.delete(f);
}
