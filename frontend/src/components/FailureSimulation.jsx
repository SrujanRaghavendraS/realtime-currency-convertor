import { useId, useState } from 'react';
import StatusBadge from './StatusBadge.jsx';
import { fmtAbsolute, fmtCountdown, fmtTime, humanize } from '../utils/format.js';

const FAILURE_TYPES = [
  { value: 'HTTP_429', label: 'HTTP 429' },
  { value: 'OUTAGE', label: 'Outage' },
  { value: 'TIMEOUT', label: 'Timeout' },
];

const STAGE_LABELS = {
  PRIMARY_PREMIUM: 'Primary premium provider',
  SECONDARY_PREMIUM: 'Secondary premium provider',
  PUBLIC_API: 'Public API',
  LAST_KNOWN_GOOD: 'Last-known-good',
};

export default function FailureSimulation({
  plan,
  title,
  description,
  buttonLabel,
  sim,
  simUpdatedAt,
  demoLoading,
  demoError,
  demoEnabled,
  action,
  onStart,
  onStop,
  now,
}) {
  const id = useId();
  const [failureType, setFailureType] = useState('HTTP_429');

  const active = Boolean(sim?.active);
  const recovered = !active && sim?.recovery?.state === 'RECOVERED';
  const disabled = demoEnabled === false;
  const unknown = demoEnabled === null; // status not yet loaded / unreachable

  // Tick the backend countdown locally between polls.
  let remaining = null;
  if (active && typeof sim.seconds_remaining === 'number') {
    const elapsed = simUpdatedAt ? Math.max(0, (now - simUpdatedAt) / 1000) : 0;
    remaining = Math.max(0, sim.seconds_remaining - elapsed);
  }

  const events = Array.isArray(sim?.events) ? sim.events.slice(-6).reverse() : [];
  const fallbackMethod = plan === 'free' ? sim?.fallback_method : null;

  return (
    <section className={`block sim${active ? ' sim--active' : ''}`} aria-labelledby={`${id}-title`}>
      <div className="block__head">
        <h3 id={`${id}-title`}>{title}</h3>
        <span className="block__aside">Demo</span>
      </div>
      <p className="sim__desc">{description}</p>

      {recovered && (
        <div className="banner banner--good" role="status">
          <strong>Recovered.</strong> Simulation ended
          {sim.recovery.recovered_at ? ` at ${fmtTime(sim.recovery.recovered_at)}` : ''}; normal collection
          has resumed.
        </div>
      )}

      <div className="sim__controls">
        {!active && plan === 'free' && (
          <div className="field field--compact">
            <label htmlFor={`${id}-type`}>Failure type</label>
            <select
              id={`${id}-type`}
              value={failureType}
              onChange={(e) => setFailureType(e.target.value)}
              disabled={disabled || action.pending}
            >
              {FAILURE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        )}
        {active ? (
          <button
            type="button"
            className="btn btn--stop"
            onClick={onStop}
            disabled={action.pending}
          >
            <span aria-hidden="true">■</span> {action.pending ? 'Stopping…' : 'Stop / Reset'}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => onStart(plan === 'free' ? failureType : undefined)}
            disabled={disabled || unknown || action.pending || demoLoading}
          >
            <span aria-hidden="true">▶</span> {action.pending ? 'Starting…' : buttonLabel}
          </button>
        )}
      </div>

      {disabled && (
        <p className="sim__note">Simulation is disabled because demo mode is off on the backend (DEMO_MODE).</p>
      )}
      {unknown && demoError && (
        <p className="inline-error" role="status">Simulation status unavailable: {demoError.message}.</p>
      )}
      {action.error && (
        <p className="inline-error" role="alert">{action.error}</p>
      )}

      {active ? (
        <dl className="facts sim__facts">
          {plan === 'free' && (
            <div>
              <dt>Failure</dt>
              <dd>{humanize(sim.failure_type)}</dd>
            </div>
          )}
          {plan === 'free' && (
            <div>
              <dt>Fallback method</dt>
              <dd>{humanize(fallbackMethod)}</dd>
            </div>
          )}
          {plan === 'premium' && (
            <div>
              <dt>Current stage</dt>
              <dd>{STAGE_LABELS[sim.current_stage] || humanize(sim.current_stage)}</dd>
            </div>
          )}
          <div>
            <dt>Resulting status</dt>
            <dd>{sim.resulting_status ? <StatusBadge status={sim.resulting_status} /> : '—'}</dd>
          </div>
          <div>
            <dt>Ends in</dt>
            <dd className="num" title={fmtAbsolute(sim.expires_at)}>{fmtCountdown(remaining)}</dd>
          </div>
        </dl>
      ) : (
        !recovered && <p className="sim__idle">Ready · not running</p>
      )}

      {events.length > 0 && (active || recovered) && (
        <div className="sim__events">
          <h4>Recent events</h4>
          <ol>
            {events.map((e, i) => (
              <li key={`${e.at}-${i}`}>
                <time className="num" dateTime={e.at || undefined} title={fmtAbsolute(e.at)}>
                  {fmtTime(e.at)}
                </time>
                <span>{e.message || '—'}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
