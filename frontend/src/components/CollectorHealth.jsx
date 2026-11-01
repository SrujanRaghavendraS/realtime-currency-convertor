import StatusBadge from './StatusBadge.jsx';
import PanelSkeleton from './PanelSkeleton.jsx';
import { fmtAbsolute, fmtDuration, fmtNumber, fmtRelative, humanize } from '../utils/format.js';

function When({ ts, now }) {
  return <span title={fmtAbsolute(ts)}>{ts ? fmtRelative(ts, now) : '—'}</span>;
}

export default function CollectorHealth({ metrics, loading, now }) {
  if (loading && !metrics) return <PanelSkeleton title="Collector" />;
  const c = metrics?.collector || {};

  return (
    <section className="panel" aria-labelledby="collector-title">
      <h3 id="collector-title">Collector</h3>
      <p className="panel__status">
        {c.health ? <StatusBadge status={c.health} /> : <span className="muted">—</span>}
        {c.running_now && <span className="tag tag--info">Running now</span>}
      </p>
      <dl className="facts facts--single">
        <div>
          <dt>Last run</dt>
          <dd><When ts={c.last_run_at} now={now} /></dd>
        </div>
        <div>
          <dt>Last outcome</dt>
          <dd>{humanize(c.last_outcome)}</dd>
        </div>
        <div>
          <dt>Next run</dt>
          <dd><When ts={c.next_run_at} now={now} /></dd>
        </div>
        <div>
          <dt>Last success</dt>
          <dd><When ts={c.last_success_at} now={now} /></dd>
        </div>
        <div>
          <dt>Interval</dt>
          <dd className="num">{fmtDuration(c.interval_seconds)}</dd>
        </div>
        <div>
          <dt>Successful collections</dt>
          <dd className="num">{fmtNumber(c.successful_collections_total)}</dd>
        </div>
      </dl>
    </section>
  );
}
