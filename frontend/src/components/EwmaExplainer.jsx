import { useEffect, useId, useState } from 'react';
import { useHistory } from '../utils/useHistory.js';
import { fmtRate } from '../utils/format.js';

// Made-up teaching values. This widget recomputes them client-side; the real EWMA comes from the backend.
const SAMPLE = [94.0, 94.5, 94.2, 95.0, 94.8];

const f2 = (v) => v.toFixed(2);

export default function EwmaExplainer({ alpha: liveAlpha }) {
  const id = useId();
  const defaultAlpha = typeof liveAlpha === 'number' ? liveAlpha : 0.4;
  const [alpha, setAlpha] = useState(defaultAlpha);
  const [touched, setTouched] = useState(false);
  useEffect(() => {
    if (!touched) setAlpha(defaultAlpha);
  }, [defaultAlpha, touched]);

  const rows = [];
  let prev = null;
  SAMPLE.forEach((x, i) => {
    const s = prev === null ? x : alpha * x + (1 - alpha) * prev;
    rows.push({ i: i + 1, x, prev, s });
    prev = s;
  });

  const history = useHistory('INR');
  const hist = history.data;
  const n = Array.isArray(hist?.observations) ? hist.observations.length : 0;

  return (
    <figure className="flow-card ewma" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>EWMA fallback estimate</h3>
      <p className="ewma__formula">
        S(t) = α·X(t) + (1 − α)·S(t−1)
        <span className="num">α = {alpha.toFixed(2)}</span>
      </p>
      <p className="ewma__plain">
        Recent values weigh more, so spikes are smoothed. It is an estimate from past observations, not a prediction,
        and is used only when the provider fails.
      </p>

      <div className="field ewma__slider">
        <label htmlFor={`${id}-alpha`}>Try a different α (teaching only)</label>
        <input
          id={`${id}-alpha`}
          type="range"
          min="0.05"
          max="0.95"
          step="0.05"
          value={alpha}
          onChange={(e) => {
            setTouched(true);
            setAlpha(Number(e.target.value));
          }}
        />
      </div>

      <div className="ewma__table-wrap">
        <table className="ewma__table num">
          <caption>Worked example with illustrative USD/INR values</caption>
          <thead>
            <tr>
              <th scope="col">t</th>
              <th scope="col">X(t)</th>
              <th scope="col">Calculation</th>
              <th scope="col">S(t)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.i}>
                <td>{r.i}</td>
                <td>{f2(r.x)}</td>
                <td className="ewma__calc">
                  {r.prev === null
                    ? 'Seed: S(1) = X(1)'
                    : `${alpha.toFixed(2)}×${f2(r.x)} + ${(1 - alpha).toFixed(2)}×${f2(r.prev)}`}
                </td>
                <td>
                  <strong>{f2(r.s)}</strong>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="ewma__live">
        {hist && typeof hist.latest_ewma === 'number' ? (
          <>
            Live: current INR EWMA = <strong className="num">{fmtRate(hist.latest_ewma)}</strong> from{' '}
            <span className="num">{n}</span> observation{n === 1 ? '' : 's'}
            {typeof hist.ewma_min_observations === 'number' && n < hist.ewma_min_observations
              ? ` (fallback needs at least ${hist.ewma_min_observations})`
              : ''}
            .
          </>
        ) : (
          'Live INR EWMA appears here once the backend reports history.'
        )}
      </p>
    </figure>
  );
}
