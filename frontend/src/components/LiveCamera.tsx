import { Camera } from "lucide-react";

export default function LiveCamera() {
  return (
    <section className="panel camera-panel">
      <div className="panel-title">
        <Camera size={20} />
        <span>Live Crop Monitoring</span>
      </div>

      <div className="camera-view">
        <div className="plant-box plant-box-a">
          <span>Plant A-01</span>
        </div>

        <div className="plant-box plant-box-b">
          <span>Plant A-02</span>
        </div>

        <div className="camera-placeholder">
          <Camera size={48} />
          <strong>Camera Stream</strong>
          <small>Edge camera will be connected here.</small>
        </div>
      </div>
    </section>
  );
}
