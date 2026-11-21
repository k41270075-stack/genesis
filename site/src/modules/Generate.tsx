// `generate` + sha256 + `vouchai_verify`: one seed -> the same company on any
// machine, byte for byte. The hash is compared with the one sealed in README.
import { easeOut, hash01, seg } from "../engine/clock";
import { readme } from "../data";
import { runOf } from "../terminal";
import { lineAt } from "../ui/Terminal";
import { Appear, Label, StampMark } from "./parts";
import type { VizProps } from "./types";

const HEX = "0123456789abcdef";

export default function Generate({ run, p }: VizProps) {
  const all = (run?.lines ?? []).map((l) => l[1]);
  const gen = runOf("generate");
  const sha = gen?.sha256 ?? "";
  const sealed = readme.prediction?.sha256 ?? "";
  const seed = readme.prediction?.seed ?? "28112026";
  const idLine = all.findIndex((s) => /^ep_[A-Z0-9]+$/.test(s));
  const shaLine = all.findIndex((s) => /^[0-9a-f]{64}$/.test(s));
  const verLine = all.findIndex((s) => /A:ok B:ok C:ok/.test(s));
  const demo = (runOf("demo")?.lines ?? []).map((l) => /^Ledger rows (\d+), invoices (\d+), payments (\d+)/.exec(l[1])).find(Boolean);
  const pId = lineAt(run, idLine), pSha = lineAt(run, shaLine), pVer = lineAt(run, verLine);
  const tables = [
    { k: "ledger.csv", n: demo ? Number(demo[1]) : 0 },
    { k: "invoices.jsonl", n: demo ? Number(demo[2]) : 0 },
    { k: "payments.jsonl", n: demo ? Number(demo[3]) : 0 },
    { k: "fx.csv", n: 0 },
  ];
  const settle = seg(p, pSha, pSha + 0.14);
  const compare = seg(p, pSha + 0.12, pSha + 0.26);

  return (
    <div className="flex h-full flex-col gap-5 p-5">
      <div className="flex flex-wrap items-end gap-6">
        <div>
          <Label>seed</Label>
          <div className="mt-1 flex gap-1">
            {seed.split("").map((d, i) => {
              const x = seg(p, 0.02 + i * 0.012, 0.08 + i * 0.012);
              const shown = x >= 1 ? d : String(Math.floor(hash01(i * 31 + Math.floor(p * 400)) * 10));
              return <div key={i} className="grid h-14 w-10 place-items-center rounded-lg border border-line2 bg-void font-mono text-[28px] font-bold"
                style={{ color: x >= 1 ? "#ECEAE4" : "#5B8CFF" }}>{shown}</div>;
            })}
          </div>
        </div>
        <div className="text-mute">→</div>
        <Appear p={p} at={pId - 0.02}>
          <Label>episode_id</Label>
          <div className="mt-1 font-mono text-[22px] text-text">{idLine >= 0 ? all[idLine] : "…"}</div>
          <div className="text-[12px] text-mute">конфиг <span className="text-soft">{readme.prediction?.config ?? "jury_like"}</span> · вымышленная компания</div>
        </Appear>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {tables.map((t, i) => {
          const x = easeOut(seg(p, pId - 0.04 + i * 0.03, pId + 0.12 + i * 0.03));
          return (
            <div key={t.k} className="rounded-xl border border-line bg-void/50 p-3">
              <div className="font-mono text-[11px] text-soft">{t.k}</div>
              <div className="mt-2 flex h-16 items-end gap-[2px]">
                {Array.from({ length: 24 }, (_, j) => (
                  <div key={j} className="flex-1 rounded-sm bg-blue/70" style={{ height: `${(25 + hash01(i * 99 + j) * 75) * x}%`, opacity: 0.35 + 0.65 * x }} />
                ))}
              </div>
              <div className="mt-1 font-mono text-[11px] text-mute">{t.n ? `${Math.round(t.n * x)} записей` : "курсы Нацбанка"}</div>
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-line bg-void/60 p-4">
        <Label>sha256 четырёх таблиц</Label>
        <div className="mt-2 break-all font-mono text-[15px] leading-relaxed tracking-wider">
          {sha.split("").map((c, i) => {
            const fixed = settle * 64 > i;
            const ch = fixed ? c : p > pSha - 0.05 ? HEX[Math.floor(hash01(i * 17 + Math.floor(p * 300)) * 16)] : "·";
            const ok = compare * 64 > i && sealed[i] === c;
            return <span key={i} style={{ color: ok ? "#3DDC97" : fixed ? "#ECEAE4" : "#2A3145" }}>{ch}</span>;
          })}
        </div>
        <div className="mt-3 border-t border-dashed border-line pt-3">
          <Label>запечатано в README до сдачи</Label>
          <div className="mt-1 break-all font-mono text-[15px] leading-relaxed tracking-wider text-mute">
            {sealed.split("").map((c, i) => <span key={i} style={{ color: compare * 64 > i ? "#3DDC97" : undefined, opacity: compare * 64 > i ? 1 : 0.5 }}>{c}</span>)}
          </div>
        </div>
      </div>

      <div className="relative flex flex-wrap items-center gap-3">
        {["A · схема и поля", "B · инварианты I1–I18", "C · независимый детектор"].map((t, i) => (
          <Appear key={t} p={p} at={pVer + i * 0.02} className="chip border-ok/50 text-ok">✓ {t}</Appear>
        ))}
        <span className="text-[12px] text-mute">vouchai_verify не использует код среды</span>
        <StampMark p={p} at={pSha + 0.27} className="absolute -top-3 right-2" size={22} color="#3DDC97">совпало до байта</StampMark>
      </div>
    </div>
  );
}
