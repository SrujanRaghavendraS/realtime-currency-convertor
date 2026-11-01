// Client-side cross-rate conversion using ONLY the backend-supplied USD rates of one plan.
// All rates are "1 USD = X quote". No values are hardcoded here.

const ESTIMATED_STATUSES = new Set(['FALLBACK_ESTIMATED', 'STALE']);

function usdLeg(code, rates) {
  if (code === 'USD') return { ok: true, rate: 1, estimated: false };
  const entry = rates?.[code];
  if (!entry || entry.status === 'UNAVAILABLE' || typeof entry.rate !== 'number' || !(entry.rate > 0)) {
    return { ok: false, code };
  }
  const estimated = Boolean(entry.is_estimated || entry.is_stale || ESTIMATED_STATUSES.has(entry.status));
  return { ok: true, rate: entry.rate, estimated, status: entry.status };
}

export function convert(amount, from, to, rates) {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) {
    return { ok: false, reason: 'Enter a valid amount.' };
  }
  if (amount < 0) return { ok: false, reason: 'Amount cannot be negative.' };

  const a = usdLeg(from, rates);
  const b = usdLeg(to, rates);
  const missing = [a, b].filter((l) => !l.ok).map((l) => l.code);
  if (missing.length) {
    const unique = [...new Set(missing)];
    return {
      ok: false,
      reason: `USD→${unique.join(' and USD→')} rate is unavailable for this plan, so this conversion cannot be calculated.`,
    };
  }

  const crossRate = b.rate / a.rate; // 1 FROM = crossRate TO
  return {
    ok: true,
    value: amount * crossRate,
    crossRate,
    estimated: a.estimated || b.estimated,
  };
}
