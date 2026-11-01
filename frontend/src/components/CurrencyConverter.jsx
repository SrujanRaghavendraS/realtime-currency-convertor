import { useId, useMemo, useState } from 'react';
import { CURRENCIES, fmtAmount, fmtRate } from '../utils/format.js';
import { convert } from '../utils/convert.js';

export default function CurrencyConverter({ plan, rates, loading }) {
  const id = useId();
  const [amount, setAmount] = useState('100');
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState('INR');

  const parsed = amount.trim() === '' ? NaN : Number(amount);
  const result = useMemo(() => convert(parsed, from, to, rates), [parsed, from, to, rates]);

  const swap = () => {
    setFrom(to);
    setTo(from);
  };

  return (
    <section className="block" aria-labelledby={`${id}-title`}>
      <div className="block__head">
        <h3 id={`${id}-title`}>Currency converter</h3>
        <span className="block__aside">Uses {plan === 'free' ? 'Free' : 'Premium'} rates above</span>
      </div>

      <div className="converter">
        <div className="field field--amount">
          <label htmlFor={`${id}-amount`}>Amount</label>
          <input
            id={`${id}-amount`}
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-from`}>From</label>
          <select id={`${id}-from`} value={from} onChange={(e) => setFrom(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <button type="button" className="converter__swap" onClick={swap} aria-label="Swap currencies">
          ⇄
        </button>
        <div className="field">
          <label htmlFor={`${id}-to`}>To</label>
          <select id={`${id}-to`} value={to} onChange={(e) => setTo(e.target.value)}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="converter__result" aria-live="polite">
        {loading && !rates ? (
          <span className="skeleton skeleton--num" aria-label="Loading rates" />
        ) : !rates ? (
          <p className="converter__unavailable">Rates not loaded, so conversion is unavailable.</p>
        ) : result.ok ? (
          <>
            <p className="converter__value num">
              {fmtAmount(result.value, to)} <span className="converter__code">{to}</span>
              {result.estimated && <span className="tag tag--warn">Estimated</span>}
            </p>
            <p className="converter__rate num">
              1 {from} = {fmtRate(result.crossRate)} {to}
              {result.estimated && ' · uses an estimated or stale rate'}
            </p>
          </>
        ) : (
          <p className="converter__unavailable">{result.reason}</p>
        )}
      </div>
    </section>
  );
}
