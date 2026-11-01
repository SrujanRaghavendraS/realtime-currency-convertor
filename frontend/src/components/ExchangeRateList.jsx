import StatusBadge from './StatusBadge.jsx';
import { CURRENCY_NAMES, QUOTES, fmtAbsolute, fmtRate, fmtRelative, humanize, show } from '../utils/format.js';

function Timestamp({ label, ts, now }) {
  return (
    <span className="rate__ts">
      {label}{' '}
      <time dateTime={ts || undefined} title={fmtAbsolute(ts)}>
        {ts ? fmtRelative(ts, now) : '—'}
      </time>
    </span>
  );
}

function methodText(entry) {
  if (!entry?.method || entry.method === 'PROVIDER') return null;
  if (entry.method === 'EWMA') {
    const n = entry.observations_used;
    return `EWMA of ${typeof n === 'number' ? n : '—'} observation${n === 1 ? '' : 's'}`;
  }
  if (entry.method === 'LAST_KNOWN_GOOD') return 'Last-known-good value';
  if (entry.method === 'CACHE') return 'From earlier snapshot';
  return humanize(entry.method);
}

function RateRow({ code, entry, now }) {
  const status = entry?.status || 'UNAVAILABLE';
  const method = methodText(entry);
  return (
    <li className={`rate rate--${status.toLowerCase()}`}>
      <div className="rate__pair">
        <span className="rate__code">USD/{code}</span>
        <span className="rate__name">{CURRENCY_NAMES[code]}</span>
      </div>
      <div className="rate__value num" aria-label={`1 USD equals ${fmtRate(entry?.rate)} ${code}`}>
        {fmtRate(entry?.rate)}
      </div>
      <div className="rate__badge">
        <StatusBadge status={status} />
      </div>
      <div className="rate__meta">
        <span className="rate__source">{show(entry?.source)}</span>
        {method && (
          <span className={`rate__method${entry.method === 'CACHE' ? '' : ' rate__method--warn'}`}>{method}</span>
        )}
        <Timestamp label="Observed" ts={entry?.provider_timestamp} now={now} />
        <Timestamp label="Retrieved" ts={entry?.retrieved_at} now={now} />
      </div>
    </li>
  );
}

function RowsSkeleton() {
  return (
    <ul className="rates" aria-busy="true" aria-label="Loading exchange rates">
      {QUOTES.map((q) => (
        <li key={q} className="rate rate--loading">
          <span className="skeleton skeleton--text" />
          <span className="skeleton skeleton--num" />
        </li>
      ))}
    </ul>
  );
}

export default function ExchangeRateList({ plan, rates, fallbackAttribution, now }) {
  const { data, error, loading } = rates;
  const attribution = data?.attribution || fallbackAttribution;
  const headingId = `${plan}-rates-title`;

  return (
    <section className="block" aria-labelledby={headingId}>
      <div className="block__head">
        <h3 id={headingId}>Current exchange rates</h3>
        <span className="block__aside">1 USD equals</span>
      </div>

      {error && (
        <p className="inline-error" role="status">
          {data ? 'Showing last received rates. ' : ''}
          {error.status === 503 ? 'Rate store unavailable' : error.message}.
        </p>
      )}

      {loading && !data ? (
        <RowsSkeleton />
      ) : data ? (
        <>
          {data.message && <p className="rates__message">{data.message}</p>}
          <ul className="rates">
            {QUOTES.map((q) => (
              <RateRow key={q} code={q} entry={data.rates?.[q]} now={now} />
            ))}
          </ul>
          <dl className="facts facts--inline">
            <div>
              <dt>Snapshot updated</dt>
              <dd title={fmtAbsolute(data.snapshot_updated_at)}>
                {data.snapshot_updated_at ? fmtRelative(data.snapshot_updated_at, now) : '—'}
              </dd>
            </div>
            <div>
              <dt>Fallback</dt>
              <dd>
                {data.fallback?.active
                  ? `${humanize(data.fallback.method)}${data.fallback.reason ? ` (${data.fallback.reason})` : ''}`
                  : 'Not in use'}
              </dd>
            </div>
          </dl>
          {data.refresh_policy?.description && (
            <p className="rates__policy">{data.refresh_policy.description}</p>
          )}
        </>
      ) : (
        <p className="empty">No rate data received yet.</p>
      )}

      <p className="rates__attribution">
        <a href={attribution.url} target="_blank" rel="noopener noreferrer">
          {attribution.text}
        </a>
        <span>Indicative rates, not for settlement.</span>
      </p>
    </section>
  );
}
