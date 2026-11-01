import { useCallback, useEffect, useState } from 'react';
import DashboardHeader from '../components/DashboardHeader.jsx';
import PlanSection from '../components/PlanSection.jsx';
import ApiUsagePanel from '../components/ApiUsagePanel.jsx';
import SlidingWindowPanel from '../components/SlidingWindowPanel.jsx';
import CollectorHealth from '../components/CollectorHealth.jsx';
import HowItWorks from '../components/HowItWorks.jsx';
import { getDemoStatus, getHealth, getMetrics, getRates, startDemo, stopDemo } from '../services/api.js';
import { usePolling } from '../utils/usePolling.js';
import { useNow } from '../utils/useNow.js';

const DATA_POLL_MS = 15000;
const DEMO_FAST_MS = 2000;
const DEMO_SLOW_MS = 10000;

const DEFAULT_ATTRIBUTION = { text: 'Rates by exchangerate.dev', url: 'https://exchangerate.dev' };

const PLANS = {
  free: {
    plan: 'free',
    tierLabel: 'Free tier',
    badge: { text: 'Active', tone: 'active' },
    name: 'Free',
    price: null,
    tagline: 'Public API-powered exchange rates.',
    note: 'If the public provider fails, rates are served from cached observations and an EWMA estimate of recent values, and are marked as such.',
    simTitle: 'Free API Failure Simulation',
    simDescription: 'Demonstrate public API failure and EWMA-based fallback.',
    simButton: 'Simulate Free API Failure',
    showHierarchy: false,
    showUpgrade: true,
  },
  premium: {
    plan: 'premium',
    tierLabel: 'Premium tier',
    badge: { text: 'Premium Preview', tone: 'preview' },
    name: 'Premium',
    price: '$9/month',
    tagline:
      'Intended experience: a snapshot that refreshes after every successful collection, with failover across two premium providers before the public API.',
    note: 'Preview only. No premium provider is integrated: the premium stages below are demo states, and rates shown here still come from the public API.',
    simTitle: 'Premium API Failure Simulation',
    simDescription: 'Demonstrate primary, secondary, public API and last-known-good fallback.',
    simButton: 'Simulate Premium API Failure',
    showHierarchy: true,
    showTrend: true,
    showUpgrade: false,
  },
};

function demoNeedsFastPoll(demo) {
  if (!demo) return false;
  return ['free', 'premium'].some(
    (p) => demo[p]?.active || demo[p]?.recovery?.state === 'RECOVERED'
  );
}

export default function Dashboard() {
  const now = useNow(1000);

  const fetchFree = useCallback(() => getRates('free'), []);
  const fetchPremium = useCallback(() => getRates('premium'), []);
  const free = usePolling(fetchFree, DATA_POLL_MS);
  const premium = usePolling(fetchPremium, DATA_POLL_MS);
  const metrics = usePolling(getMetrics, DATA_POLL_MS);
  const health = usePolling(getHealth, DATA_POLL_MS);

  const [demoFast, setDemoFast] = useState(false);
  const demo = usePolling(getDemoStatus, demoFast ? DEMO_FAST_MS : DEMO_SLOW_MS);
  const needsFast = demoNeedsFastPoll(demo.data);
  useEffect(() => {
    setDemoFast(needsFast);
  }, [needsFast]);

  // While a simulation runs, rates change with each stage; keep them in step with demo polls.
  const { refresh: refreshFree } = free;
  const { refresh: refreshPremium } = premium;
  const freeActive = Boolean(demo.data?.free?.active);
  const premiumActive = Boolean(demo.data?.premium?.active);
  useEffect(() => {
    if (freeActive) refreshFree();
    if (premiumActive) refreshPremium();
  }, [demo.updatedAt, freeActive, premiumActive, refreshFree, refreshPremium]);

  const [actionState, setActionState] = useState({
    free: { pending: false, error: null },
    premium: { pending: false, error: null },
  });

  const runDemoAction = async (plan, action, failureType) => {
    setActionState((s) => ({ ...s, [plan]: { pending: true, error: null } }));
    try {
      const result = action === 'start' ? await startDemo(plan, failureType) : await stopDemo(plan);
      if (result) demo.setData(result);
      setActionState((s) => ({ ...s, [plan]: { pending: false, error: null } }));
    } catch (err) {
      const message =
        err.status === 403
          ? 'Demo mode is disabled on the backend.'
          : `Could not ${action === 'start' ? 'start' : 'stop'} the simulation: ${err.message}.`;
      setActionState((s) => ({ ...s, [plan]: { pending: false, error: message } }));
    }
    (plan === 'free' ? free : premium).refresh();
    demo.refresh();
  };

  const sources = [free, premium, metrics, health];
  const backendUnreachable =
    sources.every((s) => !s.loading) && sources.every((s) => s.error && s.error.status === undefined);

  const attribution = free.data?.attribution || premium.data?.attribution || DEFAULT_ATTRIBUTION;
  const demoEnabled = demo.data ? demo.data.demo_mode_enabled !== false : null;

  return (
    <div className="page">
      <DashboardHeader
        health={health}
        lastSuccessAt={metrics.data?.collector?.last_success_at ?? null}
        now={now}
      />

      {backendUnreachable && (
        <div className="banner banner--error" role="alert">
          <strong>Backend unreachable.</strong> Retrying every 15 seconds. Any values shown are from the
          last successful response.
        </div>
      )}

      <main className="plans">
        {['free', 'premium'].map((p) => (
          <PlanSection
            key={p}
            config={PLANS[p]}
            rates={p === 'free' ? free : premium}
            fallbackAttribution={attribution}
            sim={demo.data?.[p] ?? null}
            simUpdatedAt={demo.updatedAt}
            demoLoading={demo.loading}
            demoError={demo.error}
            demoEnabled={demoEnabled}
            action={actionState[p]}
            onStart={(failureType) => runDemoAction(p, 'start', failureType)}
            onStop={() => runDemoAction(p, 'stop')}
            now={now}
          />
        ))}
      </main>

      <section className="monitor" aria-labelledby="monitor-title">
        <div className="monitor__head">
          <h2 id="monitor-title">API usage &amp; system monitoring</h2>
          {metrics.error && (
            <span className="inline-error" role="status">
              Metrics unavailable: {metrics.error.message}
            </span>
          )}
        </div>
        <div className="monitor__grid">
          <ApiUsagePanel metrics={metrics.data} loading={metrics.loading} now={now} />
          <SlidingWindowPanel metrics={metrics.data} loading={metrics.loading} now={now} />
          <CollectorHealth metrics={metrics.data} loading={metrics.loading} now={now} />
        </div>
      </section>

      <HowItWorks freeRates={free.data} premiumRates={premium.data} metrics={metrics.data} />

      <footer className="footer">
        <a href={attribution.url} target="_blank" rel="noopener noreferrer">
          {attribution.text}
        </a>
        <p>Rates are delayed public reference data, not live market quotes. Indicative rates, not for settlement.</p>
      </footer>
    </div>
  );
}
