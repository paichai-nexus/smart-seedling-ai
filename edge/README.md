# Raspberry Pi edge agent

The edge agent captures a fixed-camera JPEG with `rpicam-still`, records the
timezone-aware capture timestamp in a durable SQLite queue, uploads due captures
to the tray analysis API, and retries failures with exponential backoff. Sent
queue rows remain available as an audit trail.

## Raspberry Pi setup

```bash
sudo apt install python3-venv rpicam-apps
git clone https://github.com/paichai-nexus/smart-seedling-ai.git /opt/smart-seedling-ai
cd /opt/smart-seedling-ai
python3 -m venv .venv
.venv/bin/pip install -r edge/requirements.txt
```

Create `/etc/smart-seedling-edge.env`:

```dotenv
SERVER_URL=http://192.168.0.10:8000
TRAY_CODE=TRAY-A
TIMEZONE=Asia/Seoul
CAPTURE_INTERVAL_SECONDS=3600
```

The tray and its capture profile must already exist on the server. Verify one
capture manually before enabling automatic startup:

```bash
.venv/bin/python -m edge.agent.main \
  --server-url http://192.168.0.10:8000 \
  --tray-code TRAY-A \
  --timezone Asia/Seoul \
  --once
```

Install the service after updating its `User` if the device account is not
`pi`:

```bash
sudo cp edge/systemd/smart-seedling-edge.service /etc/systemd/system/
sudo mkdir -p /var/lib/smart-seedling-edge
sudo chown pi:pi /var/lib/smart-seedling-edge
sudo systemctl daemon-reload
sudo systemctl enable --now smart-seedling-edge
journalctl -u smart-seedling-edge -f
```
