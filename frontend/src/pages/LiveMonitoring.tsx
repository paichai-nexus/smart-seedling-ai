import GrowthChart from "../components/GrowthChart";
import LiveCamera from "../components/LiveCamera";
import PlantStatusCard from "../components/PlantStatusCard";
import SensorPanel from "../components/SensorPanel";

export default function LiveMonitoring() {
  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">SMART SEEDLING AI</p>
          <h1>Vision AI Crop Monitoring</h1>
          <p className="subtitle">
            Vision AI · IoT · Expert Review · Smart Agriculture
          </p>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          System Online
        </div>
      </header>

      <div className="dashboard-grid">
        <div className="main-column">
          <LiveCamera />
          <SensorPanel />
        </div>

        <div className="side-column">
          <PlantStatusCard />
          <GrowthChart />
        </div>
      </div>
    </main>
  );
}
