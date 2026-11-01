import { fmtAbsolute, fmtDuration, fmtNumber, fmtRelative, show } from '../utils/format.js';
import PanelSkeleton from './PanelSkeleton.jsx';

function When({ ts, now }) {
  return <span title={fmtAbsolute(ts)}>{ts ? fmtRelative(ts, now) : '—'}</span>;
}

export default function ApiUsagePanel({ metrics, loading, now }) {
  if (loading && !metrics) return <PanelSkeleton title="API usage" />;

  const provider = metrics?.provider || {};
  const usage = metrics?.usage || {};
  const rel = metrics?.reliability || {};
  const sim = metrics?.simulated || {};
  const quota = provider.provider_reported_quota;

  const limit = usage.monthly_limit;
  const used = usage.requests_this_month;
  const pct =
    typeof usage.usage_percent === 'number'
      ? usage.usage_percent
      : typeof used === 'number' && typeof limit === 'number' && limit > 0
        ? (used / limit) * 100
        : null;
  const barPct = pct === null ? 0 : Math.min(100, Math.max(0, pct));
  const barTone = barPct >= 90 ? 'bad' : barPct >= 70 ? 'warn' : 'good';

  const delay =
    typeof provider.price_delay_seconds === 'number' ? fmtDuration(provider.price_delay_seconds) : null;

  return (
    <section className="panel panel--wide" aria-labelledby="usage-title">
      <h3 id="usage-title">API usage</h3>

      <div className="usage">
        <div className="usage__head">
          <span>Monthly requests {usage.month ? `(${usage.month})` : ''}</span>
          <span className="num">
            <strong>{fmtNumber(used)}</strong> / {fmtNumber(limit)}
          </span>
        </div>
        <div
          className={`meter meter--${barTone}`}
          role="progressbar"
          aria-label="Monthly quota used"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct === null ? undefined : Math.round(barPct)}
        >
          <span style={{ width: `${barPct}%` }} />
        </div>
        <div className="usage__foot num">
          <span>{pct === null ? '—' : `${fmtNumber(pct, 1)}% used`}</span>
          <span>{fmtNumber(usage.remaining)} remaining</span>
        </div>
      </div>

      <dl className="facts">
        <div>
          <dt>Documented monthly limit</dt>
          <dd className="num">{fmtNumber(provider.documented_monthly_limit)}</dd>
        </div>
        <div>
          <dt>Documented per-minute limit</dt>
          <dd className="num">{fmtNumber(provider.documented_per_minute_limit)}</dd>
        </div>
        <div>
          <dt>Internal per-minute guard</dt>
          <dd className="num">
            {fmtNumber(usage.rolling_minute_count)} / {fmtNumber(usage.per_minute_limit)} in rolling minute
          </dd>
        </div>
        <div>
          <dt>Provider delay</dt>
          <dd>{delay ?? '—'}</dd>
        </div>
      </dl>
      <p className="panel__hint">
        Counts above are observed internally by this service. Documented limits come from the provider's
        published docs{provider.docs_url ? (
          <>
            {' '}(<a href={provider.docs_url} target="_blank" rel="noopener noreferrer">docs</a>)
          </>
        ) : null}.
      </p>

      {quota && (
        <div className="subpanel">
          <h4>Provider-reported (from response headers)</h4>
          <dl className="facts">
            <div>
              <dt>Remaining / limit</dt>
              <dd className="num">
                {fmtNumber(quota.remaining)} / {fmtNumber(quota.limit)}
              </dd>
            </div>
            <div>
              <dt>Scope</dt>
              <dd>{show(quota.scope)}</dd>
            </div>
            <div>
              <dt>Resets</dt>
              <dd><When ts={quota.reset_at} now={now} /></dd>
            </div>
            <div>
              <dt>Observed</dt>
              <dd><When ts={quota.observed_at} now={now} /></dd>
            </div>
          </dl>
        </div>
      )}

      <div className="subpanel">
        <h4>Reliability</h4>
        <dl className="facts">
          <div>
            <dt>Successful</dt>
            <dd className="num">{fmtNumber(rel.successful_requests)}</dd>
          </div>
          <div>
            <dt>Failed</dt>
            <dd className="num">{fmtNumber(rel.failed_requests)}</dd>
          </div>
          <div>
            <dt>HTTP 429</dt>
            <dd className="num">{fmtNumber(rel.http_429_count)}</dd>
          </div>
          <div>
            <dt>Last success</dt>
            <dd><When ts={rel.last_success_at} now={now} /></dd>
          </div>
          <div className="facts__full">
            <dt>Last failure</dt>
            <dd>
              <When ts={rel.last_failure_at} now={now} />
              {rel.last_failure_reason ? <span className="muted"> · {rel.last_failure_reason}</span> : null}
            </dd>
          </div>
        </dl>
      </div>

      <div className="subpanel subpanel--sim">
        <h4>Simulated (not real API usage)</h4>
        <dl className="facts">
          <div>
            <dt>Free simulated failures</dt>
            <dd className="num">{fmtNumber(sim.free?.simulated_failures)}</dd>
          </div>
          <div>
            <dt>Premium simulated failures</dt>
            <dd className="num">{fmtNumber(sim.premium?.simulated_failures)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
