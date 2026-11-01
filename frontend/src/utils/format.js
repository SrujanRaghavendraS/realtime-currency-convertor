export const DASH = '—';

export const QUOTES = ['INR', 'EUR', 'GBP', 'JPY'];
export const CURRENCIES = ['USD', 'INR', 'EUR', 'GBP', 'JPY'];

export const CURRENCY_NAMES = {
  USD: 'US dollar',
  INR: 'Indian rupee',
  EUR: 'Euro',
  GBP: 'British pound',
  JPY: 'Japanese yen',
};

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

export function show(v) {
  return v === null || v === undefined || v === '' ? DASH : String(v);
}

export function fmtNumber(v, digits = 0) {
  if (!isNum(v)) return DASH;
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtRate(v) {
  if (!isNum(v)) return DASH;
  const digits = v >= 100 ? 2 : 4;
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtAmount(v, code) {
  if (!isNum(v)) return DASH;
  const digits = code === 'JPY' ? 0 : 2;
  return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function parse(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtAbsolute(ts) {
  const d = parse(ts);
  if (!d) return DASH;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  });
}

export function fmtTime(ts) {
  const d = parse(ts);
  if (!d) return DASH;
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function fmtRelative(ts, now = Date.now()) {
  const d = parse(ts);
  if (!d) return DASH;
  const diff = Math.round((now - d.getTime()) / 1000);
  const future = diff < 0;
  const s = Math.abs(diff);
  let text;
  if (s < 10) return future ? 'in a few sec' : 'just now';
  if (s < 60) text = `${s} sec`;
  else if (s < 3600) text = `${Math.floor(s / 60)} min`;
  else if (s < 86400) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    text = m ? `${h} h ${m} min` : `${h} h`;
  } else {
    const days = Math.floor(s / 86400);
    text = `${days} day${days === 1 ? '' : 's'}`;
  }
  return future ? `in ${text}` : `${text} ago`;
}

export function fmtDuration(seconds) {
  if (!isNum(seconds)) return DASH;
  if (seconds < 60) return `${seconds} s`;
  if (seconds % 3600 === 0) return `${seconds / 3600} h`;
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

export function fmtCountdown(seconds) {
  if (!isNum(seconds)) return DASH;
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function humanize(enumValue) {
  if (!enumValue) return DASH;
  const s = String(enumValue).replace(/_/g, ' ').toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
