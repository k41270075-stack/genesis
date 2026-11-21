import { useCallback, useEffect, useState } from "react";
import { PassportButton, PassportDrawer, StampToasts } from "./game/PassportUI";
import { Hero } from "./hero/Hero";
import { Game } from "./sections/Game";
import { Footer } from "./sections/Footer";
import { Lab } from "./sections/Lab";
import { REPO } from "./sections/links";
import { Story } from "./sections/Story";
import { Tour } from "./sections/Tour";

function Nav({ onTour, onPassport }: { onTour: () => void; onPassport: () => void }) {
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const on = () => setSolid(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <nav className={`fixed inset-x-0 top-0 z-40 transition-colors duration-300 ${solid ? "border-b border-line bg-void/80 backdrop-blur-md" : ""}`}>
      <div className="mx-auto flex max-w-[1320px] items-center gap-6 px-5 py-4 sm:px-8">
        <a href="#top" className="flex items-center gap-2.5">
          <img src="./favicon.svg" alt="" className="h-7 w-7" />
          <span className="font-display text-[17px] font-semibold">Vouch<span className="text-stamp">AI</span></span>
        </a>
        <div className="ml-auto hidden items-center gap-6 text-[14px] text-soft md:flex">
          <a href="#how" className="hover:text-text">Как устроено</a>
          <a href="#game" className="hover:text-text">Игра</a>
          <a href="#lab" className="hover:text-text">Тренажёры</a>
          <a href="#check" className="hover:text-text">Проверить</a>
          <button onClick={onTour} className="hover:text-text">Автотур</button>
        </div>
        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <PassportButton onOpen={onPassport} />
          <a href={REPO} target="_blank" rel="noreferrer" className="btn-ghost !px-4 !py-2 text-[13px]">GitHub</a>
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  const [tour, setTour] = useState(() => /^#(tour|video)$/.test(window.location.hash));
  const video = window.location.hash === "#video";
  const open = useCallback(() => { setTour(true); history.replaceState(null, "", "#tour"); }, []);
  const close = useCallback(() => { setTour(false); history.replaceState(null, "", " "); }, []);
  const [passport, setPassport] = useState(false);
  const closePassport = useCallback(() => setPassport(false), []);
  if (video) return <Tour onClose={close} video />;
  return (
    <>
      <Nav onTour={open} onPassport={() => setPassport(true)} />
      <main>
        <Hero onTour={open} />
        <Story />
        <Game />
        <Lab />
      </main>
      <Footer />
      {tour && <Tour onClose={close} />}
      <PassportDrawer open={passport} onClose={closePassport} />
      <StampToasts />
    </>
  );
}
