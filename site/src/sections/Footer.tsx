import { useState } from "react";
import { readme } from "../data";
import { terminal } from "../terminal";
import { REPO } from "./links";

function Copy({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button className="kbd shrink-0 hover:text-text" onClick={() => { void navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1200); }); }}>
      {ok ? "✓" : "копировать"}
    </button>
  );
}

export function Footer() {
  const cmds = readme.check_command ?? [];
  return (
    <footer id="check" className="relative border-t border-line">
      <div className="mx-auto grid max-w-[1320px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-[1fr_1fr]">
        <div>
          <p className="eyebrow">проверьте сами</p>
          <h2 className="h-display mt-4 text-[clamp(32px,4vw,56px)]">Три минуты,<br />одна машина</h2>
          <p className="mt-5 max-w-[480px] text-soft">Контейнер без сети, только для чтения. Те же команды, чей вывод показан на этом сайте.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a className="btn-red" href={REPO} target="_blank" rel="noreferrer">GitHub · vouchai</a>
            <a className="btn-ghost" href={`${REPO}#readme`} target="_blank" rel="noreferrer">README: тур для жюри</a>
          </div>
        </div>
        <div className="term overflow-hidden rounded-2xl border border-line">
          <div className="border-b border-line px-4 py-2.5 text-[11px] text-mute">terminal</div>
          <div className="space-y-3 p-4">
            {cmds.map((c, i) => (
              <div key={i} className="flex items-start gap-3">
                <code className="min-w-0 flex-1 whitespace-pre-wrap break-all text-[12.5px] text-text"><span className="text-ok">$</span> {c}</code>
                <Copy text={c} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="mx-auto flex max-w-[1320px] flex-wrap justify-between gap-4 border-t border-line px-5 py-8 text-[12px] text-mute sm:px-8">
        <span>VouchAI · Genesis Hackathon 2026 · {readme.license ?? "Apache-2.0"} · все компании и данные вымышлены</span>
        <span>Терминалы сайта — записи настоящего вывода ({terminal.recorded_on}), ускоренные. Оценщик и песочница работают в браузере и сверены с Python тестами site/tests.</span>
      </div>
    </footer>
  );
}
