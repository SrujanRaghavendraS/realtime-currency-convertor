import { useEffect, useId, useRef, useState } from 'react';
import { useHistory } from '../utils/useHistory.js';
import { QUOTES, fmtAbsolute, fmtRate, fmtRelative } from '../utils/format.js';

const HEIGHT = 220;
const M = { top: 12, right: 14, bottom: 28, left: 58 };

function useWidth(ref, fallback = 560) {
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([entry]) => setW(Math.max(240, Math.round(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

function niceTicks(min, max, count = 4) {
  const span = max - min;
  if (!(span > 0)) return [min];
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toPrecision(12));
  return ticks;
}

function fmtTick(ms, spanMs) {
  const d = new Date(ms);
  if (spanMs > 36 * 3600e3) return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function Chart({ points, pair, now }) {
  const wrapRef = useRef(null);
  const width = useWidth(wrapRef);
  const [hover, setHover] = useState(null);
  const iw = width - M.left - M.right;
  const ih = HEIGHT - M.top - M.bottom;

  const xs = points.map((p) => p.t);
  let x0 = Math.min(...xs);
  let x1 = Math.max(...xs);
  if (x1 === x0) {
    x0 -= 1800e3;
    x1 += 1800e3;
  }
  const vals = points.flatMap((p) => [p.rate, p.ewma]).filter((v) => typeof v === 'number');
  let y0 = Math.min(...vals);
  let y1 = Math.max(...vals);
  const pad = y1 > y0 ? (y1 - y0) * 0.15 : Math.abs(y0) * 0.001 || 0.01;
  y0 -= pad;
  y1 += pad;

  const sx = (t) => M.left + ((t - x0) / (x1 - x0)) * iw;
  const sy = (v) => M.top + (1 - (v - y0) / (y1 - y0)) * ih;
  const line = (key) =>
    points
      .filter((p) => typeof p[key] === 'number')
      .map((p, i) => `${i ? 'L' : 'M'}${sx(p.t).toFixed(1)},${sy(p[key]).toFixed(1)}`)
      .join(' ');

  const yTicks = niceTicks(y0, y1, 4);
  const xTickCount = width < 420 ? 3 : 5;
  const xTicks = Array.from({ length: xTickCount }, (_, i) => x0 + ((x1 - x0) * i) / (xTickCount - 1));

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * width;
    let best = 0;
    points.forEach((p, i) => {
      if (Math.abs(sx(p.t) - px) < Math.abs(sx(points[best].t) - px)) best = i;
    });
    setHover(best);
  };

  const hp = hover !== null ? points[hover] : null;
  const tipLeft = hp ? Math.min(Math.max(sx(hp.t), 90), width - 90) : 0;
  const last = points[points.length - 1];

  return (
    <div className="trend__plot" ref={wrapRef}>
      <svg
        width={width}
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="img"
        aria-label={`USD/${pair} collected rates, ${points.length} observations. Latest ${fmtRate(last.rate)}, EWMA ${fmtRate(last.ewma)}.`}
      >
        {yTicks.map((v) => (
          <g key={v}>
            <line className="trend__grid" x1={M.left} x2={width - M.right} y1={sy(v)} y2={sy(v)} />
            <text className="trend__axis" x={M.left - 8} y={sy(v)} dy="0.32em" textAnchor="end">
              {fmtRate(v)}
            </text>
          </g>
        ))}
        {xTicks.map((t, i) => (
          <text
            key={t}
            className="trend__axis"
            x={sx(t)}
            y={HEIGHT - 8}
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
          >
            {fmtTick(t, x1 - x0)}
          </text>
        ))}

        <path className="trend__line trend__line--ewma" d={line('ewma')} />
        <path className="trend__line trend__line--raw" d={line('rate')} />
        {points.map((p, i) => (
          <circle
            key={p.t + '-' + i}
            className="trend__dot"
            cx={sx(p.t)}
            cy={sy(p.rate)}
            r={hover === i ? 5.5 : 4}
          />
        ))}

        {hp && (
          <g pointerEvents="none">
            <line className="trend__cross" x1={sx(hp.t)} x2={sx(hp.t)} y1={M.top} y2={M.top + ih} />
            {typeof hp.ewma === 'number' && (
              <circle className="trend__dot trend__dot--ewma" cx={sx(hp.t)} cy={sy(hp.ewma)} r={4.5} />
            )}
          </g>
        )}

        <rect
          x={M.left - 10}
          y={M.top}
          width={iw + 20}
          height={ih}
          fill="transparent"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        />
      </svg>

      {hp && (
        <div className="trend__tip" style={{ left: tipLeft }} role="status">
          <div className="trend__tip-row">
            <span className="key key--raw" aria-hidden="true" /> Rate <strong className="num">{fmtRate(hp.rate)}</strong>
          </div>
          <div className="trend__tip-row">
            <span className="key key--ewma" aria-hidden="true" /> EWMA <strong className="num">{fmtRate(hp.ewma)}</strong>
          </div>
          <div className="trend__tip-meta">Observed {fmtAbsolute(hp.provider_timestamp)}</div>
          <div className="trend__tip-meta">
            Retrieved {fmtAbsolute(hp.retrieved_at)} ({fmtRelative(hp.retrieved_at, now)})
          </div>
        </div>
      )}
    </div>
  );
}

export default function RateTrendChart({ now }) {
  const id = useId();
  const [pair, setPair] = useState('INR');
  const history = useHistory(pair);
  const data = history.data;

  const points = (Array.isArray(data?.observations) ? data.observations : [])
    .map((o) => ({ ...o, t: new Date(o.retrieved_at).getTime() }))
    .filter((o) => Number.isFinite(o.t) && typeof o.rate === 'number');
  const windowSize = data?.window_size ?? 15;

  let body;
  if (history.error && !data) {
    body =
      history.error.status === 404 ? (
        <p className="empty">Trend history is not available from the backend yet. It will appear once the history endpoint is live.</p>
      ) : (
        <p className="inline-error" role="status">Could not load history: {history.error.message}.</p>
      );
  } else if (history.loading && !data) {
    body = <span className="skeleton trend__skeleton" aria-label="Loading trend" />;
  } else if (points.length < 2) {
    body = (
      <p className="empty">
        {points.length === 1 ? 'Only 1 observation collected so far.' : 'No observations collected yet.'} The chart
        fills in as the collector runs (each run adds one point, up to {windowSize}).
      </p>
    );
  } else {
    body = <Chart points={points} pair={pair} now={now} />;
  }

  return (
    <section className="block trend" aria-labelledby={`${id}-title`}>
      <div className="block__head">
        <h3 id={`${id}-title`}>Collected rate trend</h3>
        <div className="field field--compact field--inline">
          <label htmlFor={`${id}-pair`}>USD /</label>
          <select id={`${id}-pair`} value={pair} onChange={(e) => setPair(e.target.value)}>
            {QUOTES.map((q) => (
              <option key={q} value={q}>{q}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="trend__legend">
        <span><span className="key key--raw" aria-hidden="true" /> Collected rate</span>
        <span>
          <span className="key key--ewma" aria-hidden="true" /> EWMA (α {data?.alpha ?? '—'})
        </span>
        <span className="trend__count num">
          {data ? points.length : '—'} / {windowSize} observations
        </span>
      </div>

      {body}

      <p className="trend__note">
        x = retrieval time, y = USD/{pair}. Points come from this service's sliding window; refreshed every 60 s.
      </p>
    </section>
  );
}
