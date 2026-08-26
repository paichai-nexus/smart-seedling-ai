import axios from "axios";

import type { MonitoringSnapshot } from "../types/monitoring";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 5000,
});

export async function getMonitoringSnapshot(): Promise<MonitoringSnapshot> {
  const response = await api.get<MonitoringSnapshot>("/api/monitoring/current");
  return response.data;
}
