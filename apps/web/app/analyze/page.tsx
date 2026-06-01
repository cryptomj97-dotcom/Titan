"use client";

import { useState } from "react";
import { useAnalysis, useAnalysisStream } from "@/lib/hooks";
import type { DataReadyPayload, AnalysisError } from "@/lib/types";

export default function AnalyzePage() {
  const [asset, setAsset] = useState("BTC/USD");
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const { requestAnalysis, loading, error } = useAnalysis();
  const { events, streamError, isConnected } = useAnalysisStream(analysisId);

  const handleAnalyze = async () => {
    const result = await requestAnalysis(asset);
    if (result) {
      setAnalysisId(result.analysis_id);
    }
  };

  const getLatestEvent = () => {
    if (events.length === 0) return null;
    return events[events.length - 1];
  };

  const latestEvent = getLatestEvent();
  const dataReady = latestEvent?.event === "analysis:update" && (latestEvent.payload as any)?.event === "DATA_READY";

  return (
    <main className="page-shell">
      <section className="analysis-container">
        <div className="left-panel">
          <h2>Asset Selector</h2>
          <input
            type="text"
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
            placeholder="BTC/USD"
            className="asset-input"
          />
          <button onClick={handleAnalyze} disabled={loading} className="primary-button">
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          {error && <div className="error-box">{error}</div>}

          <div className="status-panel">
            <h3>Pipeline Status</h3>
            {!analysisId ? (
              <p className="muted">No analysis running</p>
            ) : (
              <>
                <p>Analysis ID: {analysisId}</p>
                <p className={isConnected ? "status-connected" : "status-disconnected"}>
                  {isConnected ? "✓ Connected" : "✗ Disconnected"}
                </p>
                {streamError && <div className="error-box">{streamError}</div>}
              </>
            )}
          </div>
        </div>

        <div className="center-panel">
          <h2>Data Stream</h2>
          {events.length === 0 ? (
            <p className="muted">Waiting for events...</p>
          ) : (
            <div className="events-list">
              {events.map((evt, idx) => {
                const event = (evt as any).event;
                return (
                  <div key={idx} className="event-item">
                    <span className="event-type">{event}</span>
                    {event === "DATA_READY" && (
                      <pre className="event-payload">
                        {JSON.stringify((evt as any).payload?.quality_report, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="right-panel">
          <h2>Data Quality</h2>
          {dataReady ? (
            <div className="quality-result">
              <p>
                Quality:{" "}
                <span className="badge-success">
                  {((latestEvent?.payload as any)?.quality_report?.passed ? "✓ PASSED" : "✗ FAILED")}
                </span>
              </p>
            </div>
          ) : (
            <p className="muted">Waiting for data...</p>
          )}
        </div>
      </section>
    </main>
  );
}
