// One badge for every status vocabulary on the page. Text always carries the meaning;
// colour only reinforces it.
const MAP = {
  // per-currency rate status
  LIVE_FROM_PROVIDER: { label: 'Fresh from provider', tone: 'good' },
  CACHED: { label: 'Cached', tone: 'info' },
  FALLBACK_ESTIMATED: { label: 'Estimated (EWMA)', tone: 'warn' },
  STALE: { label: 'Stale', tone: 'stale' },
  UNAVAILABLE: { label: 'Unavailable', tone: 'bad' },
  // premium hierarchy stage state
  NOT_CONFIGURED: { label: 'Not configured (demo)', tone: 'muted' },
  SIMULATED_UNAVAILABLE: { label: 'Simulated unavailable', tone: 'bad' },
  ACTIVE: { label: 'Active', tone: 'good' },
  STANDBY: { label: 'Standby', tone: 'muted' },
  FAILED: { label: 'Failed', tone: 'bad' },
  CHECKING: { label: 'Checking', tone: 'info' },
  // health
  ok: { label: 'Backend healthy', tone: 'good' },
  degraded: { label: 'Backend degraded', tone: 'warn' },
  HEALTHY: { label: 'Healthy', tone: 'good' },
  STARTING: { label: 'Starting', tone: 'info' },
  DEGRADED: { label: 'Degraded', tone: 'warn' },
  DOWN: { label: 'Down', tone: 'bad' },
  READY: { label: 'Ready', tone: 'good' },
  INSUFFICIENT_DATA: { label: 'Insufficient data', tone: 'warn' },
};

export default function StatusBadge({ status, label, tone, title }) {
  const entry = MAP[status] || {};
  const text = label || entry.label || (status ? String(status).replace(/_/g, ' ').toLowerCase() : '—');
  const t = tone || entry.tone || 'muted';
  return (
    <span className={`badge badge--${t}`} title={title}>
      <span className="badge__dot" aria-hidden="true" />
      {text}
    </span>
  );
}
