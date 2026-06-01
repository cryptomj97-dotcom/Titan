export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">TITAN</p>
          <h1>Trading intelligence for quant-led decision making.</h1>
          <p className="description">
            Analyze symbols, stream market signals, and inspect AI-backed trade plans in a single investor-ready war room.
          </p>
          <button className="primary-button">Analyze BTC/USD</button>
        </div>
        <div className="hero-panel">
          <div className="panel-header">Live analysis ready</div>
          <div className="panel-body">Select an asset, request analysis, and watch the pipeline stream results.</div>
        </div>
      </section>
    </main>
  );
}
