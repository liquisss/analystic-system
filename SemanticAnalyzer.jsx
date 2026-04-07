import { useState, useEffect, useRef, useCallback } from "react";

/* ─────────────────────────── GLOBAL STYLES ─────────────────────────── */
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Manrope:wght@300;400;500;600;700;800&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg-deep:    #070b14;
    --bg-base:    #0c1220;
    --bg-card:    #111827;
    --bg-card2:   #1a2235;
    --border:     rgba(0,212,255,0.12);
    --border-hi:  rgba(0,212,255,0.35);
    --cyan:       #00d4ff;
    --cyan-dim:   rgba(0,212,255,0.15);
    --amber:      #f59e0b;
    --amber-dim:  rgba(245,158,11,0.15);
    --green:      #10b981;
    --red:        #ef4444;
    --text-hi:    #f0f6ff;
    --text-mid:   #8899b4;
    --text-lo:    #4a5878;
    --mono:       'Space Mono', monospace;
    --sans:       'Manrope', sans-serif;
    --radius:     10px;
    --shadow:     0 4px 32px rgba(0,0,0,0.5);
  }

  body {
    background: var(--bg-deep);
    color: var(--text-hi);
    font-family: var(--sans);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Grid background */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 48px 48px;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-base); }
  ::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 3px; }

  /* ── Animations ── */
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }
  @keyframes pulse-ring {
    0%   { transform: scale(1);   opacity: .6; }
    100% { transform: scale(1.5); opacity: 0; }
  }
  @keyframes spin-slow {
    to { transform: rotate(360deg); }
  }
  @keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  @keyframes scan-line {
    0%   { top: 0%; }
    100% { top: 100%; }
  }
  @keyframes dash-flow {
    to { stroke-dashoffset: -20; }
  }
  @keyframes progress-bar {
    from { width: 0%; }
  }
  @keyframes float {
    0%, 100% { transform: translateY(0px); }
    50%       { transform: translateY(-6px); }
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
  }

  .animate-fadeUp   { animation: fadeUp .5s cubic-bezier(.22,1,.36,1) both; }
  .animate-fadeIn   { animation: fadeIn .4s ease both; }

  /* ── Cards ── */
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    transition: border-color .2s;
  }
  .card:hover { border-color: var(--border-hi); }

  /* ── Buttons ── */
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer;
    font-family: var(--sans); font-size: 14px; font-weight: 600;
    transition: all .18s ease; white-space: nowrap;
  }
  .btn-primary {
    background: var(--cyan); color: #070b14;
  }
  .btn-primary:hover { filter: brightness(1.15); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0,212,255,0.35); }
  .btn-secondary {
    background: transparent; color: var(--cyan); border: 1px solid var(--border-hi);
  }
  .btn-secondary:hover { background: var(--cyan-dim); }
  .btn-amber {
    background: var(--amber); color: #070b14;
  }
  .btn-amber:hover { filter: brightness(1.1); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(245,158,11,0.3); }
  .btn-ghost {
    background: transparent; color: var(--text-mid); border: 1px solid var(--border);
  }
  .btn-ghost:hover { color: var(--text-hi); border-color: var(--border-hi); }
  .btn:disabled { opacity: .45; cursor: not-allowed; transform: none !important; filter: none !important; }

  /* ── Badge ── */
  .badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; font-family: var(--mono);
  }
  .badge-cyan  { background: var(--cyan-dim);  color: var(--cyan);  border: 1px solid rgba(0,212,255,0.25); }
  .badge-amber { background: var(--amber-dim); color: var(--amber); border: 1px solid rgba(245,158,11,0.25); }
  .badge-green { background: rgba(16,185,129,0.1); color: var(--green); border: 1px solid rgba(16,185,129,0.25); }
  .badge-red   { background: rgba(239,68,68,0.1);  color: var(--red);   border: 1px solid rgba(239,68,68,0.25); }

  /* ── Input / Select / Slider ── */
  .field-label { font-size: 11px; font-weight: 700; color: var(--text-mid); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; display: block; }
  .field-input {
    width: 100%; background: var(--bg-deep); border: 1px solid var(--border);
    border-radius: 6px; padding: 9px 12px; color: var(--text-hi); font-family: var(--sans); font-size: 13px;
    outline: none; transition: border-color .18s;
  }
  .field-input:focus { border-color: var(--cyan); box-shadow: 0 0 0 2px var(--cyan-dim); }
  .field-select {
    appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%238899b4' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 12px center; background-size: 12px;
    padding-right: 32px; cursor: pointer;
  }
  input[type=range] { appearance: none; width: 100%; height: 4px; background: var(--border); border-radius: 2px; outline: none; cursor: pointer; }
  input[type=range]::-webkit-slider-thumb { appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 8px rgba(0,212,255,.5); }
  input[type=checkbox] { appearance: none; width: 16px; height: 16px; border: 1px solid var(--border-hi); border-radius: 4px; cursor: pointer; background: var(--bg-deep); transition: all .15s; flex-shrink: 0; }
  input[type=checkbox]:checked { background: var(--cyan); border-color: var(--cyan); background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 10'%3E%3Cpath d='M1 5l4 4 6-8' stroke='%23070b14' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: center; }

  /* ── Toggle ── */
  .toggle { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle-slider { position: absolute; inset: 0; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 999px; cursor: pointer; transition: .2s; }
  .toggle-slider::before { content: ''; position: absolute; left: 2px; top: 50%; transform: translateY(-50%); width: 14px; height: 14px; border-radius: 50%; background: var(--text-lo); transition: .2s; }
  .toggle input:checked + .toggle-slider { background: var(--cyan-dim); border-color: var(--cyan); }
  .toggle input:checked + .toggle-slider::before { left: calc(100% - 16px); background: var(--cyan); }

  /* ── Progress bar ── */
  .progress-track { width: 100%; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--cyan), #00aaff); transition: width .4s ease; }
  .progress-fill.shimmer {
    background: linear-gradient(90deg, var(--cyan) 0%, #00aaff 40%, rgba(0,212,255,.3) 60%, #00aaff 80%, var(--cyan) 100%);
    background-size: 200% 100%; animation: shimmer 1.4s linear infinite;
  }

  /* ── Log terminal ── */
  .terminal {
    background: var(--bg-deep); border: 1px solid var(--border); border-radius: 8px;
    font-family: var(--mono); font-size: 12px; line-height: 1.7; padding: 16px;
    max-height: 220px; overflow-y: auto;
  }
  .log-info  { color: var(--cyan); }
  .log-ok    { color: var(--green); }
  .log-warn  { color: var(--amber); }
  .log-error { color: var(--red); }
  .log-dim   { color: var(--text-lo); }
  .cursor { display: inline-block; width: 7px; height: 13px; background: var(--cyan); animation: blink 1s step-end infinite; vertical-align: text-bottom; margin-left: 2px; }

  /* ── Tabs ── */
  .tabs { display: flex; gap: 2px; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 8px; padding: 3px; width: fit-content; }
  .tab { padding: 7px 18px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all .18s; color: var(--text-mid); border: none; background: transparent; }
  .tab.active { background: var(--bg-card2); color: var(--cyan); box-shadow: 0 1px 8px rgba(0,0,0,.3); }
  .tab:hover:not(.active) { color: var(--text-hi); }

  /* ── File drop zone ── */
  .dropzone {
    border: 2px dashed var(--border-hi); border-radius: 12px; padding: 48px 32px;
    text-align: center; cursor: pointer; transition: all .2s;
    background: linear-gradient(135deg, rgba(0,212,255,.03), transparent);
    position: relative; overflow: hidden;
  }
  .dropzone:hover, .dropzone.drag-over { border-color: var(--cyan); background: var(--cyan-dim); }
  .dropzone .scan {
    position: absolute; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
    opacity: 0; top: 0;
  }
  .dropzone:hover .scan { opacity: 1; animation: scan-line 2s linear infinite; }

  /* ── Step indicator ── */
  .step-dot { width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--border); background: transparent; transition: all .3s; }
  .step-dot.active { border-color: var(--cyan); background: var(--cyan); box-shadow: 0 0 10px rgba(0,212,255,.6); }
  .step-dot.done { border-color: var(--green); background: var(--green); }
  .step-line { flex: 1; height: 1px; background: var(--border); transition: background .3s; }
  .step-line.done { background: var(--green); }

  /* ── Stat card ── */
  .stat-num { font-family: var(--mono); font-size: 28px; font-weight: 700; color: var(--cyan); line-height: 1; }
  .stat-label { font-size: 11px; color: var(--text-mid); margin-top: 4px; text-transform: uppercase; letter-spacing: .06em; }

  /* ── Topic chip ── */
  .topic-chip {
    display: flex; align-items: center; gap: 8px; padding: 10px 14px;
    background: var(--bg-deep); border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: all .18s;
  }
  .topic-chip:hover { border-color: var(--border-hi); background: var(--bg-card2); }
  .topic-chip.selected { border-color: var(--cyan); background: var(--cyan-dim); }
  .topic-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

  /* ── VOSviewer placeholder ── */
  .vos-frame { width: 100%; background: var(--bg-deep); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; position: relative; }
  .vos-node { position: absolute; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-weight: 700; cursor: pointer; transition: transform .2s; }
  .vos-node:hover { transform: scale(1.15); z-index: 10; }

  /* ── Report modal ── */
  .modal-overlay { position: fixed; inset: 0; background: rgba(7,11,20,.85); backdrop-filter: blur(6px); z-index: 100; display: flex; align-items: center; justify-content: center; animation: fadeIn .2s ease; }
  .modal { background: var(--bg-card); border: 1px solid var(--border-hi); border-radius: 14px; padding: 32px; max-width: 880px; width: 95vw; max-height: 92vh; overflow-y: auto; box-shadow: 0 24px 80px rgba(0,0,0,.6); animation: fadeUp .3s cubic-bezier(.22,1,.36,1); }

  /* ── Scrollable rows ── */
  .files-list { display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow-y: auto; }

  /* Nav arrow button */
  .nav-arrow { width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--border-hi); background: var(--bg-card); color: var(--cyan); display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .18s; flex-shrink: 0; }
  .nav-arrow:hover:not(:disabled) { background: var(--cyan-dim); box-shadow: 0 0 16px rgba(0,212,255,.25); }
  .nav-arrow:disabled { opacity: .3; cursor: not-allowed; }
`;

/* ─────────────────────── ICONS (inline SVG) ─────────────────────────── */
const Icon = ({ name, size = 16, color = "currentColor" }) => {
  const paths = {
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></>,
    file:   <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>,
    trash:  <><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></>,
    arrow_r: <><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>,
    arrow_l: <><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></>,
    check:  <polyline points="20 6 9 12 4 9"/>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 0-14.14 0M4.93 19.07a10 10 0 0 0 14.14 0M22 12h-4M6 12H2M12 6V2M12 22v-4"/></>,
    layers: <><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></>,
    bar_chart: <><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>,
    eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>,
    pdf: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13h6M9 17h3"/></>,
    close: <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    cpu: <><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></>,
    network: <><circle cx="12" cy="5" r="3"/><circle cx="19" cy="19" r="3"/><circle cx="5" cy="19" r="3"/><line x1="12" y1="8" x2="12" y2="14"/><line x1="12" y1="14" x2="19" y2="17"/><line x1="12" y1="14" x2="5" y2="17"/></>,
    info: <><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
};

/* ─────────────────────── STEP INDICATOR ────────────────────────────── */
const steps = [
  { label: "Загрузка", icon: "upload" },
  { label: "Natasha",  icon: "layers" },
  { label: "BERTopic", icon: "cpu" },
  { label: "Анализ",   icon: "network" },
];

const StepIndicator = ({ current }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 40 }}>
    {steps.map((s, i) => (
      <div key={i} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : 0 }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            border: `2px solid ${i < current ? "var(--green)" : i === current ? "var(--cyan)" : "var(--border)"}`,
            background: i < current ? "rgba(16,185,129,.15)" : i === current ? "var(--cyan-dim)" : "var(--bg-card)",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "all .3s",
            boxShadow: i === current ? "0 0 16px rgba(0,212,255,.3)" : "none",
          }}>
            <Icon name={s.icon} size={15} color={i < current ? "var(--green)" : i === current ? "var(--cyan)" : "var(--text-lo)"} />
          </div>
          <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".06em", color: i === current ? "var(--cyan)" : i < current ? "var(--green)" : "var(--text-lo)", whiteSpace: "nowrap" }}>{s.label}</span>
        </div>
        {i < steps.length - 1 && (
          <div style={{ flex: 1, height: 1, background: i < current ? "var(--green)" : "var(--border)", margin: "0 8px", marginBottom: 20, transition: "background .4s" }} />
        )}
      </div>
    ))}
  </div>
);

/* ─────────────────────── TERMINAL LOG ──────────────────────────────── */
const LogEntry = ({ level, text }) => {
  const colors = { info: "var(--cyan)", ok: "var(--green)", warn: "var(--amber)", error: "var(--red)", dim: "var(--text-lo)" };
  const prefixes = { info: "►", ok: "✓", warn: "⚠", error: "✗", dim: "#" };
  return (
    <div style={{ color: colors[level] || "var(--text-mid)", fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.7 }}>
      <span style={{ color: "var(--text-lo)" }}>[{new Date().toLocaleTimeString("ru")}] </span>
      <span>{prefixes[level]} {text}</span>
    </div>
  );
};

/* ─────────────────────── MOCK DATA ─────────────────────────────────── */
const MOCK_TOPICS = [
  { id: 0, label: "Машинное обучение", words: ["модель","обучение","данные","нейронная","сеть","алгоритм"], color: "#00d4ff", size: 42, docs: 18 },
  { id: 1, label: "Обработка текста", words: ["токенизация","лемматизация","стоп-слова","морфология","синтаксис"], color: "#f59e0b", size: 35, docs: 14 },
  { id: 2, label: "Визуализация данных", words: ["граф","кластер","узел","связь","карта","визуализация"], color: "#10b981", size: 28, docs: 11 },
  { id: 3, label: "Семантический анализ", words: ["смысл","контекст","вектор","близость","embedding"], color: "#a78bfa", size: 22, docs: 9 },
  { id: 4, label: "Отчётность", words: ["отчёт","PDF","шаблон","экспорт","документ"], color: "#f87171", size: 16, docs: 6 },
];

const VOSNodes = () => {
  const nodes = [
    { x: 50, y: 48, r: 38, color: "#00d4ff", label: "ML", opacity: .9 },
    { x: 28, y: 30, r: 28, color: "#f59e0b", label: "NLP", opacity: .85 },
    { x: 72, y: 28, r: 24, color: "#10b981", label: "VIZ", opacity: .8 },
    { x: 22, y: 65, r: 20, color: "#a78bfa", label: "SEM", opacity: .75 },
    { x: 74, y: 66, r: 16, color: "#f87171", label: "RPT", opacity: .75 },
    { x: 48, y: 20, r: 12, color: "#00d4ff", label: "", opacity: .5 },
    { x: 60, y: 75, r: 10, color: "#f59e0b", label: "", opacity: .5 },
    { x: 35, y: 80, r: 9,  color: "#10b981", label: "", opacity: .45 },
  ];
  const edges = [[0,1],[0,2],[0,3],[1,2],[1,4],[2,4],[0,5],[3,7]];
  return (
    <svg viewBox="0 0 100 100" width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
      <defs>
        {nodes.map((n,i) => (
          <radialGradient key={i} id={`ng${i}`} cx="50%" cy="50%">
            <stop offset="0%" stopColor={n.color} stopOpacity=".8"/>
            <stop offset="100%" stopColor={n.color} stopOpacity=".15"/>
          </radialGradient>
        ))}
      </defs>
      {edges.map(([a,b],i) => (
        <line key={i}
          x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y}
          stroke="rgba(255,255,255,.08)" strokeWidth=".4"
          strokeDasharray="1 1" style={{ animation: "dash-flow 2s linear infinite" }}
        />
      ))}
      {nodes.map((n,i) => (
        <g key={i} style={{ cursor: "pointer" }}>
          <circle cx={n.x} cy={n.y} r={n.r * .95} fill={`url(#ng${i})`} opacity={n.opacity} />
          <circle cx={n.x} cy={n.y} r={n.r * .95} fill="none" stroke={n.color} strokeWidth=".4" opacity=".5" />
          {n.label && <text x={n.x} y={n.y} textAnchor="middle" dominantBaseline="middle" fill={n.color} fontSize={n.r * .35} fontWeight="700" fontFamily="'Space Mono',monospace" opacity=".95">{n.label}</text>}
        </g>
      ))}
    </svg>
  );
};

/* ═══════════════════════════════════════════════════════════════════════
   PAGES
═══════════════════════════════════════════════════════════════════════ */

/* ── PAGE 1: Upload ── */
const PageUpload = ({ files, setFiles }) => {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef();

  const handleDrop = (e) => {
    e.preventDefault(); setDrag(false);
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped.filter(f => !prev.find(p => p.name === f.name))]);
  };
  const handlePick = (e) => {
    const picked = Array.from(e.target.files);
    setFiles(prev => [...prev, ...picked.filter(f => !prev.find(p => p.name === f.name))]);
  };
  const remove = (name) => setFiles(prev => prev.filter(f => f.name !== name));

  const extColor = (name) => {
    const ext = name.split(".").pop().toLowerCase();
    return { pdf: "var(--red)", docx: "var(--cyan)", txt: "var(--green)", csv: "var(--amber)" }[ext] || "var(--text-mid)";
  };

  return (
    <div className="animate-fadeUp">
      {/* Hero */}
      <div style={{ marginBottom: 36, display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <div style={{ width: 48, height: 48, borderRadius: 12, background: "var(--cyan-dim)", border: "1px solid var(--border-hi)", display: "flex", alignItems: "center", justifyContent: "center", animation: "float 3s ease-in-out infinite" }}>
              <Icon name="network" size={22} color="var(--cyan)" />
            </div>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em", lineHeight: 1.2 }}>
                Semantic<span style={{ color: "var(--cyan)" }}>Analyzer</span>
              </h1>
              <p style={{ fontSize: 11, color: "var(--text-mid)", fontFamily: "var(--mono)" }}>v1.0.0 · Аналитическая система</p>
            </div>
          </div>
          <p style={{ fontSize: 14, color: "var(--text-mid)", lineHeight: 1.7, maxWidth: 440 }}>
            Загрузите документы для автоматического извлечения смысловых связей,
            тематического моделирования и построения семантических карт.
          </p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, minWidth: 240 }}>
          {[["PDF","Полный текст"],["DOCX","Word документы"],["TXT","Текстовые файлы"],["CSV","Табличные данные"]].map(([fmt,desc]) => (
            <div key={fmt} className="card" style={{ padding: "12px 14px" }}>
              <div className={`badge badge-${fmt==="PDF"?"red":fmt==="DOCX"?"cyan":fmt==="TXT"?"green":"amber"}`} style={{ marginBottom: 6, fontSize: 10 }}>{fmt}</div>
              <div style={{ fontSize: 11, color: "var(--text-mid)" }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      <div className={`dropzone${drag ? " drag-over" : ""}`}
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
        style={{ marginBottom: 20 }}
      >
        <div className="scan" />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, pointerEvents: "none" }}>
          <div style={{ width: 56, height: 56, borderRadius: "50%", border: "2px solid var(--border-hi)", background: "var(--cyan-dim)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="upload" size={24} color="var(--cyan)" />
          </div>
          <div>
            <p style={{ fontSize: 16, fontWeight: 700, color: "var(--text-hi)", marginBottom: 4 }}>Перетащите файлы или нажмите для выбора</p>
            <p style={{ fontSize: 12, color: "var(--text-mid)" }}>Поддерживаемые форматы: PDF, DOCX, TXT, CSV · Максимум 50 МБ</p>
          </div>
        </div>
        <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.txt,.csv" onChange={handlePick} style={{ display: "none" }} />
      </div>

      {/* Files list */}
      {files.length > 0 && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-mid)", textTransform: "uppercase", letterSpacing: ".06em" }}>
              Очередь · {files.length} файл{files.length > 1 ? "а" : ""}
            </span>
            <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => setFiles([])}>Очистить всё</button>
          </div>
          <div className="files-list">
            {files.map(f => (
              <div key={f.name} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "var(--bg-deep)", borderRadius: 6, border: "1px solid var(--border)" }}>
                <Icon name="file" size={15} color={extColor(f.name)} />
                <span style={{ flex: 1, fontSize: 13, fontFamily: "var(--mono)", color: "var(--text-hi)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                <span style={{ fontSize: 11, color: "var(--text-mid)", whiteSpace: "nowrap" }}>{f.size ? (f.size/1024).toFixed(1) + " KB" : "—"}</span>
                <button onClick={() => remove(f.name)} style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: "var(--text-lo)", transition: "color .15s" }} onMouseEnter={e => e.currentTarget.style.color="var(--red)"} onMouseLeave={e => e.currentTarget.style.color="var(--text-lo)"}>
                  <Icon name="trash" size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {files.length === 0 && (
        <div style={{ textAlign: "center", padding: "12px 0", color: "var(--text-lo)", fontSize: 12, fontFamily: "var(--mono)" }}>
          // файлы не выбраны
        </div>
      )}
    </div>
  );
};

/* ── PAGE 2: Natasha ── */
const Toggle = ({ checked, onChange }) => (
  <label className="toggle">
    <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
    <span className="toggle-slider" />
  </label>
);

const PageNatasha = ({ settings, setSettings }) => {
  const [logs] = useState([
    { level: "info", text: "Инициализация Natasha NLP pipeline..." },
    { level: "ok",   text: "Загружена модель NewsEmbedding (rubert-tiny2)" },
    { level: "info", text: "Подключён MorphVocab — 4.2M форм" },
    { level: "ok",   text: "Segmenter ready · SentTokenizer ready" },
    { level: "info", text: "NER: PER/ORG/LOC pipeline загружен" },
    { level: "ok",   text: "DatesExtractor ready" },
    { level: "warn", text: "Не найдены модели для слэнга — используется стандарт" },
    { level: "dim",  text: "Ожидание документов..." },
  ]);

  const update = (key, val) => setSettings(s => ({ ...s, [key]: val }));

  return (
    <div className="animate-fadeUp">
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <div className="badge badge-cyan">NLP</div>
          <h2 style={{ fontSize: 20, fontWeight: 800 }}>Предобработка · <span style={{ color: "var(--cyan)" }}>Natasha</span></h2>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-mid)" }}>Настройте параметры русскоязычного NLP‑конвейера перед запуском анализа.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Pipeline toggles */}
        <div className="card">
          <p className="field-label" style={{ marginBottom: 14 }}>Компоненты пайплайна</p>
          {[
            ["segmenter",    "Segmenter",       "Разбивка на предложения"],
            ["morph",        "MorphVocab",       "Морфологический анализ"],
            ["ner",          "NER",              "Распознавание сущностей"],
            ["dates",        "DatesExtractor",   "Извлечение дат"],
            ["lemmatize",    "Лемматизация",     "Приведение к начальной форме"],
            ["stopwords",    "Стоп-слова",       "Фильтрация шума"],
          ].map(([key, title, desc]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 0", borderBottom: "1px solid var(--border)" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 11, color: "var(--text-mid)" }}>{desc}</div>
              </div>
              <Toggle checked={settings[key] !== false} onChange={v => update(key, v)} />
            </div>
          ))}
        </div>

        {/* Params */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <p className="field-label">Минимальная длина токена</p>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <input type="range" min={1} max={5} value={settings.minTokenLen ?? 2} onChange={e => update("minTokenLen", +e.target.value)} style={{ flex: 1 }} />
              <span style={{ fontFamily: "var(--mono)", fontSize: 14, color: "var(--cyan)", minWidth: 20, textAlign: "right" }}>{settings.minTokenLen ?? 2}</span>
            </div>
          </div>

          <div className="card">
            <p className="field-label">Язык документов</p>
            <select className="field-input field-select" value={settings.lang ?? "ru"} onChange={e => update("lang", e.target.value)}>
              <option value="ru">Русский (основной)</option>
              <option value="ru_en">Русский + Английский</option>
              <option value="en">Английский</option>
            </select>
          </div>

          <div className="card">
            <p className="field-label">Пользовательский словарь стоп-слов</p>
            <textarea className="field-input" rows={4} style={{ resize: "none", fontFamily: "var(--mono)", fontSize: 11 }}
              placeholder={"также\nкроме\nпомимо\n..."} value={settings.customStop ?? ""} onChange={e => update("customStop", e.target.value)} />
          </div>

          <div className="card" style={{ padding: "12px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <Icon name="info" size={13} color="var(--amber)" />
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--amber)", textTransform: "uppercase", letterSpacing: ".06em" }}>Длинные документы</span>
            </div>
            <p style={{ fontSize: 12, color: "var(--text-mid)", lineHeight: 1.6 }}>
              При превышении 512 токенов текст автоматически разбивается на чанки с перекрытием 64 токена.
            </p>
          </div>
        </div>
      </div>

      {/* Terminal */}
      <div className="card">
        <p className="field-label" style={{ marginBottom: 10 }}>Системный журнал</p>
        <div className="terminal">
          {logs.map((l, i) => <LogEntry key={i} {...l} />)}
          <div style={{ color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 12, marginTop: 2 }}>
            $ natasha pipeline готов<span className="cursor" />
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── PAGE 3: BERTopic ── */
const ProgressRing = ({ pct, color = "var(--cyan)", size = 72 }) => {
  const r = 28, circ = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="5" />
      <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={circ * (1 - pct / 100)}
        transform="rotate(-90 36 36)" style={{ transition: "stroke-dashoffset .6s ease" }}
      />
      <text x="36" y="36" textAnchor="middle" dominantBaseline="middle" fill={color}
        fontSize="13" fontWeight="700" fontFamily="'Space Mono',monospace">{pct}%</text>
    </svg>
  );
};

const PageBERTopic = ({ btSettings, setBtSettings }) => {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("idle");
  const [done, setDone] = useState(false);

  const update = (k, v) => setBtSettings(s => ({ ...s, [k]: v }));

  const runAnalysis = () => {
    setRunning(true); setDone(false); setProgress(0);
    const stages = ["Построение TF-IDF матрицы...", "UMAP снижение размерности...", "HDBSCAN кластеризация...", "Формирование тем...", "Расчёт когерентности..."];
    let i = 0;
    const tick = setInterval(() => {
      setProgress(p => {
        const next = p + (Math.random() * 7 + 3);
        if (next >= 100) { clearInterval(tick); setRunning(false); setDone(true); setStage("Анализ завершён"); return 100; }
        setStage(stages[Math.floor(next / 20)]);
        return next;
      });
    }, 300);
    setStage(stages[0]);
  };

  const stageColors = { tfidf: "#00d4ff", umap: "#f59e0b", hdbscan: "#10b981", topics: "#a78bfa", coherence: "#f87171" };

  return (
    <div className="animate-fadeUp">
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div className="badge badge-amber">TOPIC</div>
        <h2 style={{ fontSize: 20, fontWeight: 800 }}>Тематическое моделирование · <span style={{ color: "var(--amber)" }}>BERTopic</span></h2>
      </div>
      <p style={{ fontSize: 13, color: "var(--text-mid)", marginBottom: 24 }}>Автоматическое выявление скрытых тем в корпусе документов.</p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        {/* Settings */}
        <div className="card">
          <p className="field-label" style={{ marginBottom: 14 }}>Параметры модели</p>

          <div style={{ marginBottom: 14 }}>
            <label className="field-label">Embedding модель</label>
            <select className="field-input field-select" value={btSettings.model ?? "rubert-tiny2"} onChange={e => update("model", e.target.value)}>
              <option value="rubert-tiny2">rubert-tiny2 (рекомендуется)</option>
              <option value="multilingual-e5">multilingual-e5-small</option>
              <option value="labse">LaBSE (тяжёлая)</option>
            </select>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label className="field-label">Мин. размер топика: <span style={{ color: "var(--cyan)" }}>{btSettings.minTopic ?? 5}</span></label>
            <input type="range" min={2} max={20} value={btSettings.minTopic ?? 5} onChange={e => update("minTopic", +e.target.value)} />
          </div>

          <div style={{ marginBottom: 14 }}>
            <label className="field-label">Количество топиков</label>
            <select className="field-input field-select" value={btSettings.numTopics ?? "auto"} onChange={e => update("numTopics", e.target.value)}>
              <option value="auto">Авто (HDBSCAN)</option>
              <option value="5">5</option>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label className="field-label">UMAP компоненты: <span style={{ color: "var(--cyan)" }}>{btSettings.umapComp ?? 5}</span></label>
            <input type="range" min={2} max={15} value={btSettings.umapComp ?? 5} onChange={e => update("umapComp", +e.target.value)} />
          </div>

          {[
            ["outlierReduce",  "Снижение шума (outlier reduction)"],
            ["dynamicTopics",  "Динамика тем (если есть даты)"],
            ["diversity",      "Максимизация разнообразия слов"],
          ].map(([k, label]) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <input type="checkbox" id={k} checked={btSettings[k] !== false} onChange={e => update(k, e.target.checked)} />
              <label htmlFor={k} style={{ fontSize: 13, cursor: "pointer" }}>{label}</label>
            </div>
          ))}
        </div>

        {/* Progress */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ flex: 1 }}>
            <p className="field-label" style={{ marginBottom: 16 }}>Прогресс анализа</p>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
              <ProgressRing pct={Math.round(progress)} color={done ? "var(--green)" : running ? "var(--cyan)" : "var(--text-lo)"} />
            </div>
            <div className="progress-track" style={{ marginBottom: 10 }}>
              <div className={`progress-fill${running ? " shimmer" : ""}`} style={{ width: `${progress}%` }} />
            </div>
            <p style={{ fontSize: 12, textAlign: "center", color: "var(--text-mid)", fontFamily: "var(--mono)", minHeight: 18 }}>
              {stage || "Ожидание запуска..."}
            </p>
          </div>

          {/* Pipeline stages */}
          <div className="card">
            <p className="field-label" style={{ marginBottom: 10 }}>Этапы конвейера</p>
            {["TF-IDF / CountVectorizer", "UMAP (снижение размерности)", "HDBSCAN кластеризация", "Генерация меток тем", "Расчёт когерентности"].map((s, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderBottom: i < 4 ? "1px solid var(--border)" : "none" }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: done || progress > i * 20 ? "var(--green)" : progress > 0 && Math.floor(progress / 20) === i ? "var(--cyan)" : "var(--text-lo)" }} />
                <span style={{ fontSize: 12, color: done || progress > i * 20 ? "var(--text-hi)" : "var(--text-mid)" }}>{s}</span>
                {(done || progress > i * 20) && <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--green)", fontFamily: "var(--mono)" }}>✓</span>}
              </div>
            ))}
          </div>
        </div>
      </div>

      <button className="btn btn-amber" onClick={runAnalysis} disabled={running} style={{ width: "100%", justifyContent: "center", padding: "13px" }}>
        {running ? <><span style={{ animation: "spin-slow 1s linear infinite", display: "inline-block" }}>⟳</span> Анализ запущен...</> : done ? "✓ Запустить повторно" : "▶ Запустить BERTopic анализ"}
      </button>

      {done && (
        <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
          {[["5", "Тем найдено"],["58","Документов"],["87%","Когерентность"],["6%","Шум"]].map(([n,l]) => (
            <div key={l} className="card" style={{ textAlign: "center", padding: "16px 12px" }}>
              <div className="stat-num">{n}</div>
              <div className="stat-label">{l}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── PAGE 4: Analytics + Visualization ── */
const MiniBarChart = ({ data, color }) => {
  const max = Math.max(...data.map(d => d.v));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 60 }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
          <div style={{ width: "100%", borderRadius: "3px 3px 0 0", background: color ?? "var(--cyan)", opacity: .7 + (d.v/max) * .3, transition: "height .4s", height: `${(d.v / max) * 52}px` }} />
          <span style={{ fontSize: 9, color: "var(--text-lo)", fontFamily: "var(--mono)" }}>{d.l}</span>
        </div>
      ))}
    </div>
  );
};

const ReportModal = ({ onClose }) => {
  const [preview, setPreview] = useState(false);
  const [sections, setSections] = useState({
    summary: true, topics: true, vos: true, stats: true, dynamics: false, anomalies: false, clusters: true,
  });
  const toggle = k => setSections(s => ({ ...s, [k]: !s[k] }));

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Icon name="pdf" size={20} color="var(--red)" />
            <h3 style={{ fontSize: 18, fontWeight: 800 }}>Формирование PDF отчёта</h3>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-mid)", padding: 4 }}>
            <Icon name="close" size={18} />
          </button>
        </div>

        {!preview ? (
          <>
            <p style={{ fontSize: 13, color: "var(--text-mid)", marginBottom: 20 }}>Выберите разделы, которые войдут в итоговый отчёт:</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 24 }}>
              {[
                ["summary",   "Краткое резюме",         true,  "Обязательный раздел"],
                ["topics",    "Тематический анализ",    true,  "Обязательный раздел"],
                ["vos",       "Карта VOSviewer",         true,  "Семантическая сеть"],
                ["stats",     "Общая статистика",       true,  "Метрики корпуса"],
                ["dynamics",  "Динамика тем",           false, "Требуются даты"],
                ["anomalies", "Аномалии и шум",         false, "Дополнительный анализ"],
                ["clusters",  "Межкластерные связи",    true,  "Граф кластеров"],
              ].map(([k, label, req, hint]) => (
                <div key={k} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: sections[k] ? "var(--cyan-dim)" : "var(--bg-deep)", border: `1px solid ${sections[k] ? "var(--border-hi)" : "var(--border)"}`, borderRadius: 8, cursor: "pointer", transition: "all .18s" }}
                  onClick={() => !req && toggle(k)}>
                  <input type="checkbox" checked={sections[k]} onChange={() => !req && toggle(k)} disabled={req} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
                    <div style={{ fontSize: 10, color: "var(--text-lo)" }}>{hint}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="btn btn-secondary" onClick={() => setPreview(true)} style={{ flex: 1, justifyContent: "center" }}>
                <Icon name="eye" size={14} /> Предпросмотр
              </button>
              <button className="btn btn-amber" style={{ flex: 1, justifyContent: "center" }}>
                <Icon name="download" size={14} /> Скачать PDF
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ background: "var(--bg-deep)", border: "1px solid var(--border)", borderRadius: 8, padding: 24, marginBottom: 20, minHeight: 360 }}>
              {/* Mock PDF preview */}
              <div style={{ maxWidth: 520, margin: "0 auto" }}>
                <div style={{ textAlign: "center", marginBottom: 20, paddingBottom: 20, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-.01em", marginBottom: 4 }}>Аналитический отчёт</div>
                  <div style={{ fontSize: 11, color: "var(--text-mid)", fontFamily: "var(--mono)" }}>SemanticAnalyzer v1.0 · {new Date().toLocaleDateString("ru-RU")}</div>
                </div>
                {sections.summary && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--cyan)", marginBottom: 6 }}>1. Краткое резюме</div>
                    <div style={{ fontSize: 11, color: "var(--text-mid)", lineHeight: 1.8 }}>Проанализировано <b style={{ color: "var(--text-hi)" }}>5 документов</b>, выявлено <b style={{ color: "var(--text-hi)" }}>5 тематических кластеров</b>. Доминирующие темы: машинное обучение (31%), обработка текста (24%), визуализация данных (19%).</div>
                  </div>
                )}
                {sections.stats && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--amber)", marginBottom: 6 }}>2. Статистика</div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
                      {[["58","Документов"],["2 341","Токенов"],["5","Тем"]].map(([n,l]) => (
                        <div key={l} style={{ background: "var(--bg-card)", borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
                          <div style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 700, color: "var(--cyan)" }}>{n}</div>
                          <div style={{ fontSize: 10, color: "var(--text-mid)" }}>{l}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {sections.topics && (
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--green)", marginBottom: 6 }}>3. Топики</div>
                    {MOCK_TOPICS.slice(0, 3).map(t => (
                      <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: t.color, flexShrink: 0 }} />
                        <span style={{ fontSize: 11, flex: 1 }}>{t.label}</span>
                        <span style={{ fontSize: 10, color: "var(--text-mid)", fontFamily: "var(--mono)" }}>{t.docs} doc</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="btn btn-ghost" onClick={() => setPreview(false)} style={{ flex: 1, justifyContent: "center" }}>← Назад к настройкам</button>
              <button className="btn btn-amber" style={{ flex: 1, justifyContent: "center" }}>
                <Icon name="download" size={14} /> Скачать PDF
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const PageAnalytics = () => {
  const [tab, setTab] = useState("analytics");
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [showReport, setShowReport] = useState(false);

  const trendData = [
    [{ l:"Q1", v:8 },{ l:"Q2", v:14 },{ l:"Q3", v:12 },{ l:"Q4", v:18 }],
    [{ l:"Q1", v:12 },{ l:"Q2", v:10 },{ l:"Q3", v:16 },{ l:"Q4", v:14 }],
  ];

  return (
    <div className="animate-fadeUp">
      {showReport && <ReportModal onClose={() => setShowReport(false)} />}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <div className="badge badge-green">RESULTS</div>
            <h2 style={{ fontSize: 20, fontWeight: 800 }}>Результаты анализа</h2>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-mid)" }}>Итоговая аналитика и семантическая визуализация корпуса документов</p>
        </div>
        <button className="btn btn-amber" onClick={() => setShowReport(true)}>
          <Icon name="pdf" size={14} /> Сформировать PDF отчёт
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 20 }}>
        {[["5","Тем","var(--cyan)"],["58","Документов","var(--amber)"],["2 341","Токенов","var(--green)"],["87%","Когерентность","var(--cyan)"]].map(([n,l,c]) => (
          <div key={l} className="card" style={{ textAlign: "center", padding: "16px 12px" }}>
            <div className="stat-num" style={{ color: c }}>{n}</div>
            <div className="stat-label">{l}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 20 }}>
        <button className={`tab${tab==="analytics"?" active":""}`} onClick={() => setTab("analytics")}>
          <Icon name="bar_chart" size={13} /> Аналитика
        </button>
        <button className={`tab${tab==="vos"?" active":""}`} onClick={() => setTab("vos")}>
          <Icon name="network" size={13} /> VOSviewer
        </button>
      </div>

      {tab === "analytics" && (
        <div className="animate-fadeIn">
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20, marginBottom: 20 }}>
            {/* Topics list */}
            <div className="card">
              <p className="field-label" style={{ marginBottom: 12 }}>Выявленные темы</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {MOCK_TOPICS.map(t => (
                  <div key={t.id} className={`topic-chip${selectedTopic===t.id?" selected":""}`} onClick={() => setSelectedTopic(t.id === selectedTopic ? null : t.id)}>
                    <div className="topic-dot" style={{ background: t.color }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{t.label}</div>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {t.words.slice(0, 4).map(w => (
                          <span key={w} style={{ fontSize: 10, color: "var(--text-lo)", fontFamily: "var(--mono)" }}>{w}</span>
                        ))}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--mono)", color: t.color }}>{t.docs}</div>
                      <div style={{ fontSize: 10, color: "var(--text-lo)" }}>docs</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Trend */}
              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Динамика тем</p>
                <MiniBarChart data={trendData[0]} color="var(--cyan)" />
                <p style={{ fontSize: 10, color: "var(--text-lo)", textAlign: "center", marginTop: 6, fontFamily: "var(--mono)" }}>Машинное обучение · квартальное распределение</p>
              </div>

              {/* Anomalies */}
              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Аномалии и шум</p>
                {[["Топик -1","Нераспознанные документы","6%","red"],["Дубликаты","Схожесть > 0.95","3 пары","amber"]].map(([t,d,v,c]) => (
                  <div key={t} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "7px 0", borderBottom: "1px solid var(--border)" }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>{t}</div>
                      <div style={{ fontSize: 10, color: "var(--text-mid)" }}>{d}</div>
                    </div>
                    <span className={`badge badge-${c}`}>{v}</span>
                  </div>
                ))}
              </div>

              {/* Clusters */}
              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Межкластерные связи</p>
                {[["ML","NLP",0.74],["NLP","SEM",0.61],["VIZ","ML",0.48]].map(([a,b,w]) => (
                  <div key={`${a}-${b}`} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ fontSize: 11, color: "var(--text-mid)" }}>{a} ↔ {b}</span>
                      <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--cyan)" }}>{w}</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${w*100}%`, background: `linear-gradient(90deg, var(--cyan), rgba(0,212,255,.4))` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Summary */}
          <div className="card" style={{ borderLeft: "3px solid var(--cyan)" }}>
            <p className="field-label" style={{ marginBottom: 8 }}>Краткая выжимка · Auto-summary</p>
            <p style={{ fontSize: 13, color: "var(--text-mid)", lineHeight: 1.8 }}>
              Корпус из <span style={{ color: "var(--cyan)", fontWeight: 700 }}>58 документов</span> разбит на <span style={{ color: "var(--cyan)", fontWeight: 700 }}>5 тематических кластеров</span>. Доминирующая тема — <b style={{ color: "var(--text-hi)" }}>«Машинное обучение»</b> (31% документов, 18 ед.). Высокая когерентность (87%) свидетельствует о чётком тематическом разграничении. Обнаружено <span style={{ color: "var(--amber)", fontWeight: 700 }}>3 пары дубликатов</span> и 6% необработанного шума — рекомендуется дополнительная фильтрация стоп-слов.
            </p>
          </div>
        </div>
      )}

      {tab === "vos" && (
        <div className="animate-fadeIn">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20 }}>
            <div className="vos-frame" style={{ height: 440 }}>
              <VOSNodes />
              <div style={{ position: "absolute", top: 12, left: 12, display: "flex", gap: 6, zIndex: 5 }}>
                <span className="badge badge-cyan">VOSviewer</span>
                <span className="badge badge-amber">Semantic Map</span>
              </div>
              <div style={{ position: "absolute", bottom: 12, right: 12, display: "flex", gap: 8, zIndex: 5 }}>
                {["zoom+","zoom−","reset"].map(a => (
                  <button key={a} style={{ background: "rgba(12,18,32,.8)", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 10px", color: "var(--text-mid)", cursor: "pointer", fontSize: 11, fontFamily: "var(--mono)" }}>{a}</button>
                ))}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Легенда</p>
                {MOCK_TOPICS.map(t => (
                  <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <div style={{ width: 10, height: 10, borderRadius: "50%", background: t.color, flexShrink: 0, opacity: .85 }} />
                    <span style={{ fontSize: 11, flex: 1 }}>{t.label}</span>
                    <span style={{ fontSize: 10, color: "var(--text-lo)", fontFamily: "var(--mono)" }}>×{t.docs}</span>
                  </div>
                ))}
              </div>

              <div className="card">
                <p className="field-label" style={{ marginBottom: 10 }}>Параметры отображения</p>
                {[["Размер узла","по частоте"],["Толщина связи","по схожести"],["Цвет","по кластеру"]].map(([k,v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 11, color: "var(--text-mid)" }}>{k}</span>
                    <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--text-hi)" }}>{v}</span>
                  </div>
                ))}
                <button className="btn btn-secondary" style={{ width: "100%", justifyContent: "center", padding: "8px", marginTop: 4, fontSize: 12 }}>
                  Открыть в VOSviewer
                </button>
              </div>

              <div className="card">
                <p className="field-label" style={{ marginBottom: 8 }}>Экспорт данных</p>
                {["network.json","map.txt","corpus.csv"].map(f => (
                  <div key={f} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <Icon name="download" size={12} color="var(--text-lo)" />
                    <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--text-mid)", flex: 1 }}>{f}</span>
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: "var(--cyan)", fontSize: 11 }}>↓</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════════════
   ROOT APP
═══════════════════════════════════════════════════════════════════════ */
export default function App() {
  const [step, setStep] = useState(0);
  const [files, setFiles] = useState([]);
  const [natSettings, setNatSettings] = useState({});
  const [btSettings, setBtSettings] = useState({ model: "rubert-tiny2", minTopic: 5, numTopics: "auto", umapComp: 5, outlierReduce: true, dynamicTopics: true, diversity: true });

  const canNext = () => {
    if (step === 0) return files.length > 0;
    return true;
  };

  const pages = [
    <PageUpload files={files} setFiles={setFiles} />,
    <PageNatasha settings={natSettings} setSettings={setNatSettings} />,
    <PageBERTopic btSettings={btSettings} setBtSettings={setBtSettings} />,
    <PageAnalytics />,
  ];

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div style={{ minHeight: "100vh", position: "relative", zIndex: 1 }}>
        {/* Top bar */}
        <div style={{ borderBottom: "1px solid var(--border)", background: "rgba(7,11,20,.8)", backdropFilter: "blur(10px)", padding: "0 32px", display: "flex", alignItems: "center", gap: 16, height: 52, position: "sticky", top: 0, zIndex: 50 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "var(--cyan-dim)", border: "1px solid var(--border-hi)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Icon name="network" size={14} color="var(--cyan)" />
            </div>
            <span style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700, color: "var(--cyan)" }}>SemanticAnalyzer</span>
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ display: "flex", gap: 8 }}>
            {files.length > 0 && <span className="badge badge-cyan">{files.length} файл{files.length > 1 ? "а" : ""}</span>}
            <span className="badge badge-amber">Python 3.11</span>
            <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--text-lo)" }}>v1.0.0</span>
          </div>
        </div>

        {/* Main content */}
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "36px 24px 60px" }}>
          <StepIndicator current={step} />

          <div style={{ minHeight: 480 }}>
            {pages[step]}
          </div>

          {/* Navigation */}
          <div style={{ marginTop: 32, display: "flex", alignItems: "center", gap: 16, justifyContent: "space-between" }}>
            <button className="nav-arrow" onClick={() => setStep(s => s - 1)} disabled={step === 0}>
              <Icon name="arrow_l" size={18} />
            </button>

            <div style={{ display: "flex", gap: 8, flex: 1, justifyContent: "center" }}>
              {steps.map((_,i) => (
                <div key={i} style={{
                  width: i === step ? 24 : 8, height: 8, borderRadius: 4,
                  background: i < step ? "var(--green)" : i === step ? "var(--cyan)" : "var(--border)",
                  transition: "all .3s",
                  boxShadow: i === step ? "0 0 10px rgba(0,212,255,.5)" : "none",
                  cursor: i <= step ? "pointer" : "default",
                }} onClick={() => i <= step && setStep(i)} />
              ))}
            </div>

            <button className="nav-arrow" onClick={() => setStep(s => s + 1)} disabled={step === steps.length - 1 || !canNext()} style={{ background: canNext() && step < steps.length - 1 ? "var(--cyan-dim)" : undefined }}>
              <Icon name="arrow_r" size={18} />
            </button>
          </div>

          {step === 0 && files.length === 0 && (
            <p style={{ textAlign: "center", fontSize: 11, color: "var(--text-lo)", marginTop: 10, fontFamily: "var(--mono)" }}>
              // загрузите минимум 1 файл для продолжения
            </p>
          )}
        </div>
      </div>
    </>
  );
}
