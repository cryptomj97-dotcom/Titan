import { useState, useEffect, useCallback } from "react";
import type { AnalysisResponse, AnalysisEvent } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useAnalysis() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestAnalysis = useCallback(async (asset: string, mode: string = "standard"): Promise<AnalysisResponse | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset, mode }),
      });

      if (!response.ok) {
        throw new Error(`Analysis request failed: ${response.statusText}`);
      }

      const data: AnalysisResponse = await response.json();
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { requestAnalysis, loading, error };
}

export function useAnalysisStream(analysisId: number | null) {
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!analysisId) return;

    const eventSource = new EventSource(`${API_URL}/analysis/${analysisId}/stream`);

    eventSource.onopen = () => {
      setIsConnected(true);
      setStreamError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.payload) {
          setEvents((prev) => [...prev, parsed.payload]);
        }
      } catch (err) {
        console.error("Failed to parse SSE message", err);
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      setStreamError("Connection lost");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [analysisId]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return { events, streamError, isConnected, clearEvents };
}
