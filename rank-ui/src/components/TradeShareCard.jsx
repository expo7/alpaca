import { useRef, useState } from "react";

const WIDTH = 1200;
const HEIGHT = 1200;

function dollars(value) {
  return value == null || value === "" ? "—" : `$${Number(value).toFixed(2)}`;
}

function date(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "America/New_York" });
}

function wrap(text, max = 53, rows = 3) {
  const words = String(text || "").replace(/\s+/g, " ").trim().split(" ");
  const lines = [];
  for (const word of words) {
    if (!word) continue;
    const last = lines.length - 1;
    if (last >= 0 && `${lines[last]} ${word}`.length <= max) lines[last] += ` ${word}`;
    else lines.push(word);
  }
  if (lines.length > rows) {
    lines.length = rows;
    lines[rows - 1] = `${lines[rows - 1].replace(/[.,;: ]+$/, "")}…`;
  }
  return lines;
}

function ShareArtwork({ signal, svgRef }) {
  const closed = signal.status === "closed" && signal.actual_entry != null && signal.final_exit != null && signal.realized_return_pct != null;
  const cancelled = ["cancelled", "expired"].includes(signal.status);
  const paper = Boolean(signal.paper_execution_enabled);
  const returnValue = closed ? Number(signal.realized_return_pct) : null;
  const accent = returnValue == null ? "#60a5fa" : returnValue >= 0 ? "#34d399" : "#fb7185";
  const badge = closed ? (returnValue >= 0 ? "CLOSED · GAIN" : "CLOSED · LOSS")
    : cancelled ? "NO FILL" : signal.status === "open" ? "POSITION OPEN" : "ENTRY PENDING";
  const headline = closed ? `${returnValue >= 0 ? "+" : ""}${returnValue.toFixed(2)}%`
    : cancelled ? "NO ENTRY" : signal.status === "open" ? "POSITION OPEN" : "WAITING FOR ENTRY";
  const subhead = closed ? `${paper ? "Realized paper" : "Recorded"} return · ${date(signal.closed_at)}`
    : cancelled ? "Setup ended without a filled position" : signal.status === "open" ? "Result is not final" : "Published plan · no position yet";
  const entry = closed || signal.status === "open" ? dollars(signal.actual_entry)
    : signal.entry_high && signal.entry_high !== signal.entry_low ? `${dollars(signal.entry_low)}–${dollars(signal.entry_high)}` : dollars(signal.entry_low);
  const stop = dollars(signal.initial_stop);
  const third = closed ? dollars(signal.final_exit) : dollars(signal.target_1);
  const thesis = wrap(signal.thesis || signal.invalidation || "See the full published plan and trade history on Quantelle.");
  return <svg ref={svgRef} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width={WIDTH} height={HEIGHT} xmlns="http://www.w3.org/2000/svg" role="img" aria-label={`${signal.instrument} ${headline} share image`} style={{ width: "100%", height: "auto", display: "block" }}>
    <defs>
      <linearGradient id="share-bg" x2="1" y2="1"><stop stopColor="#071226" /><stop offset="1" stopColor="#101c39" /></linearGradient>
      <linearGradient id="share-line"><stop stopColor="#22d3ee" /><stop offset="1" stopColor="#818cf8" /></linearGradient>
    </defs>
    <rect width={WIDTH} height={HEIGHT} fill="url(#share-bg)" />
    <circle cx="1110" cy="90" r="340" fill="#0d3150" opacity=".32" />
    <rect x="52" y="52" width="1096" height="1096" rx="42" fill="none" stroke="#314265" strokeWidth="2" />
    <path d="M86 175H1114" stroke="url(#share-line)" strokeWidth="3" />
    <text x="86" y="128" fill="#f8fafc" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="42" letterSpacing="7">QUANTELLE</text>
    <text x="1114" y="126" textAnchor="end" fill="#67e8f9" fontFamily="Arial, sans-serif" fontSize="22" fontWeight="700" letterSpacing="2">{paper ? "PAPER TRADE" : "TRADE RECORD"}</text>
    <text x="86" y="252" fill="#94a3b8" fontFamily="Arial, sans-serif" fontSize="24" fontWeight="700" letterSpacing="3">{signal.status_label?.toUpperCase() || signal.status.toUpperCase()} · PUBLISHED {date(signal.published_at).toUpperCase()}</text>
    <text x="86" y="333" fill="#ffffff" fontFamily="Arial, sans-serif" fontSize="50" fontWeight="800">{signal.instrument}</text>
    <text x="86" y="380" fill="#a7b5cb" fontFamily="Arial, sans-serif" fontSize="28">{signal.company_name || signal.symbol}</text>
    <rect x="86" y="432" width="1028" height="220" rx="26" fill="#111e37" stroke="#35476a" />
    <path d="M87 460 Q87 432 115 432 H124 V652 H115 Q87 652 87 624 Z" fill={accent} />
    <path d="M836 456 H1090 V506 L1072 524 H836 L818 506 V474 Z" fill={accent} opacity=".14" stroke={accent} strokeWidth="3" />
    <path d="M836 510 H1072 L1090 492" fill="none" stroke={accent} strokeWidth="3" />
    <circle cx="851" cy="490" r="6" fill={accent} />
    <text x="870" y="499" fill={accent} fontFamily="Arial, sans-serif" fontSize="21" fontWeight="800" letterSpacing="1.5">{badge}</text>
    <text x="118" y="550" fill={accent} fontFamily="Arial, sans-serif" fontWeight="800" fontSize={headline.length > 15 ? "60" : "82"}>{headline}</text>
    <text x="120" y="607" fill="#cbd5e1" fontFamily="Arial, sans-serif" fontSize="26">{subhead}</text>
    {[0, 1, 2].map((i) => <g key={i} transform={`translate(${86 + i * 350}, 710)`}>
      <text fill="#94a3b8" fontFamily="Arial, sans-serif" fontSize="22" fontWeight="700" letterSpacing="2">{[closed || signal.status === "open" ? "ACTUAL FILL" : "ENTRY PLAN", "PUBLISHED STOP", closed ? "ACTUAL EXIT" : "TARGET 1"][i]}</text>
      <text y="65" fill="#f8fafc" fontFamily="Arial, sans-serif" fontSize="39" fontWeight="700">{[entry, stop, third][i]}</text>
    </g>)}
    <path d="M86 823H1114" stroke="#314265" strokeWidth="2" />
    <text x="86" y="875" fill="#67e8f9" fontFamily="Arial, sans-serif" fontSize="21" fontWeight="700" letterSpacing="2">THE PUBLISHED IDEA</text>
    {thesis.map((line, i) => <text key={i} x="86" y={920 + i * 37} fill="#d6deec" fontFamily="Arial, sans-serif" fontSize="27">{line}</text>)}
    <path d="M86 1054H1114" stroke="#314265" strokeWidth="2" />
    <text x="86" y="1112" fill="#ffffff" fontFamily="Arial, sans-serif" fontSize="38" fontWeight="800">quantelle.io</text>
    <text x="1114" y="1093" textAnchor="end" fill="#94a3b8" fontFamily="Arial, sans-serif" fontSize="17">Research and education only</text>
    <text x="1114" y="1119" textAnchor="end" fill="#94a3b8" fontFamily="Arial, sans-serif" fontSize="17">Options involve substantial risk · #{signal.id}</text>
  </svg>;
}

export default function TradeShareCard({ signal, onClose }) {
  const svgRef = useRef(null);
  const [error, setError] = useState("");

  async function download() {
    try {
      const svg = new XMLSerializer().serializeToString(svgRef.current);
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
      const image = new Image();
      image.src = url;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = WIDTH;
      canvas.height = HEIGHT;
      canvas.getContext("2d").drawImage(image, 0, 0, WIDTH, HEIGHT);
      URL.revokeObjectURL(url);
      const png = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!png) throw new Error("Could not create the PNG image.");
      const downloadUrl = URL.createObjectURL(png);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = `quantelle-${signal.symbol.toLowerCase()}-trade-${signal.id}.png`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 60_000);
      setError("");
    } catch {
      setError("Image download failed. You can still capture the preview as a screenshot.");
    }
  }

  return <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/90 p-4 sm:p-8" role="dialog" aria-modal="true" aria-label={`Share ${signal.instrument}`}>
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-white">
        <div><h2 className="text-xl font-bold">Share trade image</h2><p className="text-sm text-slate-300">Square PNG with the source visible in the image.</p></div>
        <div className="flex gap-2"><button type="button" onClick={download} className="rounded-lg bg-cyan-400 px-4 py-2 font-bold text-slate-950 hover:bg-cyan-300">Download PNG</button><button type="button" onClick={onClose} className="rounded-lg border border-slate-500 px-4 py-2 font-semibold hover:bg-slate-800">Close</button></div>
      </div>
      {error && <p role="alert" className="mb-3 text-rose-300">{error}</p>}
      <ShareArtwork signal={signal} svgRef={svgRef} />
      <p className="mt-3 text-sm text-slate-400">The image reflects the current public record. Review it before posting; live setups can change, and completed paper returns exclude fees and execution differences.</p>
    </div>
  </div>;
}
