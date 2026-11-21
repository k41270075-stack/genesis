import type { ComponentType } from "react";
import type { Run } from "../terminal";

export interface VizProps {
  /** progress of the playback, 0..1 */
  p: number;
  /** the recording on the right (null for interactive modules) */
  run: Run | null;
  /** output lines of the recording visible right now */
  lines: number;
  /** autoplay (tour / video): interactive modules play themselves */
  auto: boolean;
  /** interactive modules write their own terminal lines */
  setLive?: (lines: string[]) => void;
}

export interface ModuleDef {
  id: string;
  title: string;
  tag: string;
  about: string;
  cmd: string;
  runs: string[];
  duration: number;
  interactive?: boolean;
  accent: "stamp" | "blue" | "ok" | "gold";
  Viz: ComponentType<VizProps>;
  /** a note under the terminal (where the full numbers live) */
  note?: string;
}

export const ACCENT: Record<ModuleDef["accent"], string> = {
  stamp: "#FF4D3D", blue: "#5B8CFF", ok: "#3DDC97", gold: "#FFC34D",
};
