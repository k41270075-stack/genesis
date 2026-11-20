// Russian number formatting: decimal comma, thin-space thousands, true minus.
const THIN = " ";

export function num(x: number | string, decimals?: number): string {
  const v = typeof x === "string" ? Number(x) : x;
  if (!Number.isFinite(v)) return String(x);
  const s = decimals === undefined ? String(Math.abs(v)) : Math.abs(v).toFixed(decimals);
  const [int, frac] = s.split(".");
  const grouped = (int ?? "").replace(/\B(?=(\d{3})+(?!\d))/g, THIN);
  return (v < 0 ? "−" : "") + grouped + (frac ? "," + frac : "");
}

/** "+0,97" / "−1,00" */
export function signed(x: number | string, decimals = 2): string {
  const v = typeof x === "string" ? Number(x) : x;
  const rounded = Number(v.toFixed(decimals));
  return (rounded > 0 ? "+" : "") + num(rounded, decimals);
}

/** Raw report value as written ("0.9692", "-0.4806") in Russian notation, digits untouched. */
export function asWritten(s: string): string {
  return s.replace(/^-/, "−").replace(/(\d)\.(\d)/g, "$1,$2");
}

export function money(minor: number, currency: string, exponents: Record<string, number>): string {
  const e = exponents[currency] ?? 2;
  return `${num(minor / 10 ** e, e)} ${currency === "KZT" ? "₸" : currency}`;
}

/** Fraction string "-871/1050" with a true minus. */
export const frac = (s: string) => s.replace(/^-/, "−");

/** Local wall-clock parts of an instant at a fixed offset "+05:00". */
export function atOffset(iso: string, offset: string) {
  const m = /^([+-])(\d\d):(\d\d)$/.exec(offset);
  const mins = m ? (m[1] === "-" ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3])) : 0;
  const d = new Date(Date.parse(iso) + mins * 60000);
  const p = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)}.${d.getUTCFullYear()}`,
    iso: `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`,
    time: `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`,
    seconds: `${p(d.getUTCSeconds())}`,
    h: d.getUTCHours(), m: d.getUTCMinutes(),
  };
}

export const ruDate = (isoDate: string) => isoDate.slice(0, 10).split("-").reverse().join(".");

export const plural = (n: number, one: string, few: string, many: string) => {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
};
