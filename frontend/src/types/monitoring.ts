export type PlantStatus = "healthy" | "warning" | "expert_review";

export interface SensorReading {
  temperature: number;
  humidity: number;
  soilMoisture: number;
  illuminance: number;
  measuredAt: string;
}

export interface PlantObservation {
  plantId: string;
  leafArea: number;
  growthRate: number;
  status: PlantStatus;
  observation: string;
  capturedAt: string;
}

export interface GrowthPoint {
  label: string;
  leafArea: number;
}

export interface MonitoringSnapshot {
  plant: PlantObservation;
  sensors: SensorReading;
  growth: GrowthPoint[];
}
