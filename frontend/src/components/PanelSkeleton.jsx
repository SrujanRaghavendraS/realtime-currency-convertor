export default function PanelSkeleton({ title }) {
  return (
    <section className="panel" aria-busy="true" aria-label={`Loading ${title}`}>
      <h3>{title}</h3>
      <span className="skeleton skeleton--text" />
      <span className="skeleton skeleton--text" />
      <span className="skeleton skeleton--text skeleton--short" />
    </section>
  );
}
