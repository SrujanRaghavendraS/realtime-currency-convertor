import StatusBadge from './StatusBadge.jsx';
import PanelSkeleton from './PanelSkeleton.jsx';
import { QUOTES, fmtAbsolute, fmtNumber, fmtRelative, humanize, show } from '../utils/format.js';

export default function SlidingWindowPanel({ metrics, loading, now }) {
  if (loading && !metrics) return <PanelSkeleton title="Sliding window" />;
  const sw = metrics?.sliding_window || {};
  const max = sw.max_observations;
  const perPair = sw.per_pair || {};

  return (
    <section className="panel" aria-labelledby="window-title">
      <h3 id="window-title">Sliding window</h3>
      <p className="panel__big num">
        {fmtNumber(sw.observation_count)}
        <span> / {fmtNumber(max)} observations</span>
      </p>

      <ul className="pairs">
        {QUOTES.map((q) => {
          const p = perPair[q] || {};
          const pct = typeof p.count === 'number' && typeof max === 'number' && max > 0
            ? Math.min(100, (p.count / max) * 100)
            : 0;
          return (
            <li key={q}>
              <span className="pairs__code">{q}</span>
              <span className="pairs__bar" aria-hidden="true"><span style={{ width: `${pct}%` }} /></span>
              <span className="pairs__count num">{fmtNumber(p.count)}</span>
            </li>
          );
        })}
      </ul>

      <dl className="facts facts--single">
        <div>
          <dt>Latest observation</dt>
          <dd title={fmtAbsolute(sw.latest_observation_at)}>
            {sw.latest_observation_at ? fmtRelative(sw.latest_observation_at, now) : '—'}
          </dd>
        </div>
        <div>
          <dt>EWMA alpha</dt>
          <dd className="num">{show(sw.ewma_alpha)}</dd>
        </div>
        <div>
          <dt>EWMA status</dt>
          <dd>{sw.ewma_status ? <StatusBadge status={sw.ewma_status} /> : '—'}</dd>
        </div>
        <div>
          <dt>Min. observations for EWMA</dt>
          <dd className="num">{show(sw.ewma_min_observations)}</dd>
        </div>
        <div>
          <dt>Fallback (free tier)</dt>
          <dd>{sw.fallback_status === 'NONE' ? 'Not in use' : humanize(sw.fallback_status)}</dd>
        </div>
      </dl>
    </section>
  );
}
