import StatusBadge from './StatusBadge.jsx';
import { fmtAbsolute, fmtRelative } from '../utils/format.js';

export default function DashboardHeader({ health, lastSuccessAt, now }) {
  let pill;
  if (health.loading && !health.data) {
    pill = <span className="skeleton skeleton--pill" aria-label="Checking backend health" />;
  } else if (health.error && health.error.status === undefined) {
    pill = <StatusBadge label="Backend unreachable" tone="bad" />;
  } else if (health.error) {
    pill = <StatusBadge label={`Health check failed (${health.error.message})`} tone="bad" />;
  } else {
    const d = health.data || {};
    const title = `Redis: ${d.redis ?? '—'} · Collector: ${d.collector ?? '—'}`;
    pill = <StatusBadge status={d.status} label={d.status ? undefined : 'Health unknown'} title={title} />;
  }

  return (
    <header className="header">
      <div className="header__titles">
        <h1>FX Rate Monitor</h1>
        <p className="header__subtitle">Real-Time Data Aggregation Service</p>
      </div>
      <div className="header__status">
        {pill}
        <p className="header__last" title={fmtAbsolute(lastSuccessAt)}>
          Last successful collection{' '}
          <strong className="num">{lastSuccessAt ? fmtRelative(lastSuccessAt, now) : '—'}</strong>
        </p>
      </div>
    </header>
  );
}
