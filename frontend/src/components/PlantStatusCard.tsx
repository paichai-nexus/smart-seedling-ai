import { Leaf, TriangleAlert } from "lucide-react";

export default function PlantStatusCard() {
  return (
    <section className="panel">
      <div className="panel-title">
        <Leaf size={20} />
        <span>Plant Status</span>
      </div>

      <div className="plant-status">
        <div>
          <span className="muted">Plant ID</span>
          <strong>A-R03C02</strong>
        </div>

        <div>
          <span className="muted">Current Status</span>
          <strong className="status-warning">
            <TriangleAlert size={18} />
            Warning
          </strong>
        </div>

        <div>
          <span className="muted">Leaf Area</span>
          <strong>34.2 cm²</strong>
        </div>

        <div>
          <span className="muted">Growth</span>
          <strong>+4.6 %</strong>
        </div>

        <div className="review-box">
          <span>AI Observation</span>
          <strong>Growth slowdown detected</strong>
          <small>Expert review recommended</small>
        </div>
      </div>
    </section>
  );
}
