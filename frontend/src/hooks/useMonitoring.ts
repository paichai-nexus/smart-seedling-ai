import { useEffect, useState } from "react";

import { getMonitoringSnapshot } from "../api/monitoring";
import type { MonitoringSnapshot } from "../types/monitoring";

export function useMonitoring() {
  const [data, setData] = useState<MonitoringSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadMonitoringData() {
      try {
        const snapshot = await getMonitoringSnapshot();

        if (active) {
          setData(snapshot);
          setError(null);
        }
      } catch {
        if (active) {
          setError("Monitoring API is not connected yet.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadMonitoringData();

    return () => {
      active = false;
    };
  }, []);

  return {
    data,
    loading,
    error,
  };
}
