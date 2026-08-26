import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const data = [
  { day: "Day 1", area: 21 },
  { day: "Day 2", area: 23 },
  { day: "Day 3", area: 26 },
  { day: "Day 4", area: 29 },
  { day: "Day 5", area: 31 },
  { day: "Day 6", area: 34.2 },
];

export default function GrowthChart() {
  return (
    <section className="panel">
      <div className="panel-title">
        <span>Growth History</span>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="day" />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="area"
              stroke="currentColor"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
