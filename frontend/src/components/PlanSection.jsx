import ExchangeRateList from './ExchangeRateList.jsx';
import CurrencyConverter from './CurrencyConverter.jsx';
import PremiumHierarchy from './PremiumHierarchy.jsx';
import FailureSimulation from './FailureSimulation.jsx';
import RateTrendChart from './RateTrendChart.jsx';

export default function PlanSection({
  config,
  rates,
  fallbackAttribution,
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
  const { plan } = config;
  const titleId = `${plan}-plan-title`;

  return (
    <article className={`plan plan--${plan}`} aria-labelledby={titleId}>
      <header className="plan__head">
        <div className="plan__tier">
          <span>{config.tierLabel}</span>
          <span className={`plan__badge plan__badge--${config.badge.tone}`}>{config.badge.text}</span>
        </div>
        <h2 id={titleId} className="plan__name">
          {config.name}
          {config.price && <span className="plan__price num">{config.price}</span>}
        </h2>
        <p className="plan__tagline">{config.tagline}</p>
        <p className="plan__note">{config.note}</p>
      </header>

      <div className="plan__body">
        <ExchangeRateList plan={plan} rates={rates} fallbackAttribution={fallbackAttribution} now={now} />

        {config.showTrend && <RateTrendChart now={now} />}

        <CurrencyConverter plan={plan} rates={rates.data?.rates ?? null} loading={rates.loading} />

        {config.showHierarchy && (
          <PremiumHierarchy hierarchy={rates.data?.premium_hierarchy ?? null} sim={sim} />
        )}

        <FailureSimulation
          plan={plan}
          title={config.simTitle}
          description={config.simDescription}
          buttonLabel={config.simButton}
          sim={sim}
          simUpdatedAt={simUpdatedAt}
          demoLoading={demoLoading}
          demoError={demoError}
          demoEnabled={demoEnabled}
          action={action}
          onStart={onStart}
          onStop={onStop}
          now={now}
        />
      </div>

      {config.showUpgrade && (
        <p className="plan__upgrade">
          Upgrade to Premium for a more frequent refresh experience and enhanced data reliability. $9/month.
        </p>
      )}
    </article>
  );
}
