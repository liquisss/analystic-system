/* ─────────────────────── STEP INDICATOR ────────────────────────────── */
import Icon from './Icon'

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

export { steps }
export default StepIndicator
