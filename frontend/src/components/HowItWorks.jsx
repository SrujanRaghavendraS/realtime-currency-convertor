import StatusBadge from './StatusBadge.jsx';
import EwmaExplainer from './EwmaExplainer.jsx';
import { fmtDuration, fmtNumber, humanize } from '../utils/format.js';

/* ---------- Flow primitives (HTML/CSS boxes and arrows) ---------- */

function Node({ live, children, tone }) {
  return (
    <div className={`flow__node${tone ? ` flow__node--${tone}` : ''}${live ? ' flow__node--live' : ''}`}>
      {live && <span className="flow__now">Now</span>}
      {children}
    </div>
  );
}

function Arrow({ label }) {
  return (
    <div className="flow__arrow" aria-hidden={label ? undefined : 'true'}>
      {label && <span>{label}</span>}
    </div>
  );
}

function Branch({ children }) {
  return <div className="flow__branch">{children}</div>;
}

function Path({ label, children }) {
  return (
    <div className="flow__path">
      <span className="flow__path-label">{label}</span>
      {children}
    </div>
  );
}

/* ---------- Live state ---------- */

function freeActiveKey(rates) {
  if (!rates) return null;
  const fb = rates.fallback;
  if (fb?.active) {
    if (fb.method === 'EWMA') return 'ewma';
    if (fb.method === 'LAST_KNOWN_GOOD') return 'lkg';
    if (fb.method === 'UNAVAILABLE') return 'unavailable';
  }
  switch (rates.overall_status) {
    case 'LIVE_FROM_PROVIDER':
      return 'update';
    case 'CACHED':
      return 'cached';
    case 'FALLBACK_ESTIMATED':
      return 'ewma';
    case 'STALE':
      return 'lkg';
    case 'UNAVAILABLE':
      return 'unavailable';
    default:
      return null;
  }
}

function premiumActiveKey(rates) {
  if (!rates) return null;
  if (rates.overall_status === 'UNAVAILABLE') return 'UNAVAILABLE';
  return rates.premium_hierarchy?.active_stage ?? null;
}

/* ---------- a. Free tier ---------- */

function FreeFlow({ rates }) {
  const k = freeActiveKey(rates);
  const policy = rates?.refresh_policy;
  return (
    <figure className="flow-card flow-card--wide" aria-labelledby="flow-free-title">
      <h3 id="flow-free-title">Free tier: refresh strategy and fallback</h3>
      <div className="flow">
        <Node tone="start">Scheduled collection</Node>
        <Arrow />
        <Branch>
          <Path label="Provider responds">
            <Node>
              Count successful collections
              {policy && (
                <small className="num">
                  {fmtNumber(policy.successful_collections_since_update)} of{' '}
                  {fmtNumber(policy.update_every_n_successful_collections)} since last update
                </small>
              )}
            </Node>
            <Arrow />
            <Node tone="decision">Every 5th success?</Node>
            <Arrow />
            <Branch>
              <Path label="Yes">
                <Node live={k === 'update'}>
                  Update Free snapshot
                  <StatusBadge status="LIVE_FROM_PROVIDER" />
                </Node>
              </Path>
              <Path label="No">
                <Node live={k === 'cached'}>
                  Keep previous snapshot
                  <StatusBadge status="CACHED" />
                </Node>
              </Path>
            </Branch>
          </Path>
          <Path label="Provider fails">
            <Node tone="fail">Failure: HTTP 429, timeout or outage</Node>
            <Arrow />
            <Node tone="decision">3 or more observations in window?</Node>
            <Arrow />
            <Branch>
              <Path label="Yes">
                <Node live={k === 'ewma'}>
                  EWMA estimate
                  <StatusBadge status="FALLBACK_ESTIMATED" />
                </Node>
              </Path>
              <Path label="No">
                <Node live={k === 'lkg'}>
                  Last-known-good
                  <StatusBadge status="STALE" />
                </Node>
                <Arrow label="retrieved over 6 h ago" />
                <Node live={k === 'unavailable'}>
                  No usable rate
                  <StatusBadge status="UNAVAILABLE" />
                </Node>
              </Path>
            </Branch>
          </Path>
        </Branch>
        <Arrow />
        <Node tone="start">Next successful collection: back to provider data</Node>
      </div>
    </figure>
  );
}

/* ---------- b. Premium ---------- */

const PREMIUM_STEPS = [
  { key: 'PRIMARY_PREMIUM', label: 'Primary premium provider', demo: true },
  { key: 'SECONDARY_PREMIUM', label: 'Secondary premium provider', demo: true },
  { key: 'PUBLIC_API', label: 'Public API (exchangerate.dev)' },
  { key: 'LAST_KNOWN_GOOD', label: 'Last-known-good rate' },
];

function PremiumFlow({ rates }) {
  const active = premiumActiveKey(rates);
  const stages = Object.fromEntries((rates?.premium_hierarchy?.stages || []).map((s) => [s.key, s]));
  return (
    <figure className="flow-card" aria-labelledby="flow-premium-title">
      <h3 id="flow-premium-title">Premium preview: fallback hierarchy</h3>
      <div className="flow">
        {PREMIUM_STEPS.map((s, i) => (
          <div key={s.key} className="flow__seq">
            {i > 0 && <Arrow label="if unavailable" />}
            <Node live={active === s.key} tone={s.demo ? 'demo' : undefined}>
              <span>
                {i + 1}. {s.label}
              </span>
              {stages[s.key]?.state ? (
                <StatusBadge status={stages[s.key].state} />
              ) : s.demo ? (
                <StatusBadge status="NOT_CONFIGURED" />
              ) : null}
            </Node>
          </div>
        ))}
        <Arrow label="older than 6 h" />
        <Node live={active === 'UNAVAILABLE'}>
          No usable rate
          <StatusBadge status="UNAVAILABLE" />
        </Node>
      </div>
      <figcaption>
        The premium snapshot updates on every successful collection. Premium providers are not integrated; stages 1
        and 2 exist only for the demo.
      </figcaption>
    </figure>
  );
}

/* ---------- c. Rate limits ---------- */

function RateLimitFlow({ metrics }) {
  const c = metrics?.collector || {};
  const sch = c.schedule || {};
  const usage = metrics?.usage || {};
  const session = sch.market_session;
  const interval = sch.current_interval_seconds ?? c.interval_seconds;

  return (
    <figure className="flow-card" aria-labelledby="flow-limit-title">
      <h3 id="flow-limit-title">Rate-limit strategy</h3>

      <dl className="flow__live">
        <div>
          <dt>Current interval</dt>
          <dd className="num">{fmtDuration(interval)}</dd>
        </div>
        <div>
          <dt>Market session</dt>
          <dd>{session ? humanize(session) : '—'}</dd>
        </div>
        <div>
          <dt>Calls this month</dt>
          <dd className="num">
            {fmtNumber(usage.requests_this_month)} / {fmtNumber(usage.monthly_limit)}
          </dd>
        </div>
        <div>
          <dt>Projected monthly calls</dt>
          <dd className="num">{fmtNumber(sch.projected_monthly_calls)}</dd>
        </div>
      </dl>

      <div className="flow">
        <Node tone="start">Scheduler tick</Node>
        <Arrow />
        <Branch>
          <Path label="Market open">
            <Node live={session === 'OPEN'}>Every {fmtDuration(sch.trading_interval_seconds ?? 600)}</Node>
          </Path>
          <Path label="Market closed">
            <Node live={session === 'CLOSED'}>Every {fmtDuration(sch.non_trading_interval_seconds ?? 900)}</Node>
          </Path>
        </Branch>
        <Arrow />
        <Node live={sch.budget_adjusted === true}>
          Budget guard
          <small>Stretches the interval if the monthly budget is at risk</small>
        </Node>
        <Arrow />
        <Node>Redis lock: no overlapping runs</Node>
        <Arrow />
        <Node>
          Monthly quota check
          <small className="num">{fmtNumber(usage.remaining)} calls remaining</small>
        </Node>
        <Arrow />
        <Node>
          Per-minute guard ({fmtNumber(usage.per_minute_limit ?? 10)}/min)
          <small className="num">{fmtNumber(usage.rolling_minute_count)} in the last minute</small>
        </Node>
        <Arrow />
        <Node tone="decision">Retry-After from a previous 429 still in effect? Skip this run.</Node>
        <Arrow />
        <Node tone="start">One request for all 4 currencies</Node>
        <Arrow />
        <Branch>
          <Path label="Success">
            <Node>Store in Redis</Node>
          </Path>
          <Path label="HTTP 429">
            <Node tone="fail">Record Retry-After, no retry</Node>
          </Path>
          <Path label="Timeout / 5xx">
            <Node tone="fail">Up to 2 retries with backoff</Node>
          </Path>
        </Branch>
      </div>
      <figcaption>Users only read from Redis. Page views never call the provider.</figcaption>
    </figure>
  );
}

export default function HowItWorks({ freeRates, premiumRates, metrics }) {
  return (
    <section className="how" aria-labelledby="how-title">
      <div className="how__head">
        <h2 id="how-title">How it works</h2>
        <p>The highlighted step shows where each tier is right now.</p>
      </div>
      <div className="how__grid">
        <FreeFlow rates={freeRates} />
        <PremiumFlow rates={premiumRates} />
        <RateLimitFlow metrics={metrics} />
        <EwmaExplainer alpha={metrics?.sliding_window?.ewma_alpha} />
      </div>
    </section>
  );
}
