import StatusBadge from './StatusBadge.jsx';

const FALLBACK_LABELS = {
  PRIMARY_PREMIUM: 'Primary premium provider',
  SECONDARY_PREMIUM: 'Secondary premium provider',
  PUBLIC_API: 'Public API',
  LAST_KNOWN_GOOD: 'Last-known-good',
};
const ORDER = Object.keys(FALLBACK_LABELS);

// Prefer the live demo view of the stages while a premium simulation runs; otherwise use
// the hierarchy returned with /api/rates?plan=premium.
export default function PremiumHierarchy({ hierarchy, sim }) {
  const simStages = sim?.active && Array.isArray(sim.stages) && sim.stages.length ? sim.stages : null;
  const stages = simStages || hierarchy?.stages || [];
  const activeKey = simStages ? sim.current_stage : hierarchy?.active_stage;

  const byKey = Object.fromEntries(stages.map((s) => [s.key, s]));
  const rows = ORDER.map((key) => byKey[key] || { key, label: FALLBACK_LABELS[key], state: null, note: null });

  return (
    <section className="block" aria-labelledby="premium-hierarchy-title">
      <div className="block__head">
        <h3 id="premium-hierarchy-title">Provider failover order</h3>
        {simStages && <span className="block__aside">Simulation view</span>}
      </div>
      <ol className="hierarchy">
        {rows.map((s, i) => {
          const isActive = s.key === activeKey || s.state === 'ACTIVE';
          return (
            <li key={s.key} className={`hierarchy__step${isActive ? ' hierarchy__step--active' : ''}`}>
              <span className="hierarchy__index num" aria-hidden="true">{i + 1}</span>
              <div className="hierarchy__body">
                <span className="hierarchy__label">{s.label || FALLBACK_LABELS[s.key]}</span>
                {s.note && <span className="hierarchy__note">{s.note}</span>}
              </div>
              {s.state ? <StatusBadge status={s.state} /> : <span className="muted">—</span>}
            </li>
          );
        })}
      </ol>
      {!hierarchy && !simStages && <p className="empty">Hierarchy not reported by backend yet.</p>}
    </section>
  );
}
