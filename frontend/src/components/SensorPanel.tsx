import {
  Droplets,
  Sun,
  Thermometer,
  Waves,
} from "lucide-react";

const sensors = [
  {
    label: "Temperature",
    value: "27.2 °C",
    icon: Thermometer,
  },
  {
    label: "Humidity",
    value: "64 %",
    icon: Waves,
  },
  {
    label: "Soil Moisture",
    value: "37 %",
    icon: Droplets,
  },
  {
    label: "Illuminance",
    value: "12,300 lux",
    icon: Sun,
  },
];

export default function SensorPanel() {
  return (
    <section className="panel">
      <div className="panel-title">
        <span>Environment Sensors</span>
      </div>

      <div className="sensor-grid">
        {sensors.map(({ label, value, icon: Icon }) => (
          <article className="sensor-card" key={label}>
            <Icon size={20} />
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}
