# 🌱 Smart Seedling AI

<!-- NEXUS_PROJECT_META_START -->

## Project Management

| Field | Value |
| --- | --- |
| Status | 🟢 Active |
| Project Lead | 김현규 |
| Team / Support | 부팀장: 이금령 |
| Next Milestone | 2026-09-22 원예산림학과 미팅 및 1차 실험 요구사항 정리 |
| Registry | [NEXUS Project Registry](https://github.com/paichai-nexus/nexus-project-registry) |

<!-- NEXUS_PROJECT_META_END -->


**Vision AI × Longitudinal Data × IoT × ROS 2 × Robotics × Drone × Smart Agriculture**

Smart Seedling AI is an interdisciplinary smart-agriculture research platform developed by **PAICHAI NEXUS**.

The project continuously observes individual seedlings using RGB imaging and environmental sensors, analyzes visible abnormalities and growth changes over time, and connects the results with expert review.

The long-term objective is not to build a single AI classifier, sensor device, or robot independently.
Instead, Smart Seedling AI integrates these technologies into a reproducible research platform for plant monitoring.

> **Important**
>
> Smart Seedling AI does not autonomously diagnose biological disease or prescribe pesticide, fertilizer, or treatment decisions.
>
> AI results are treated as observable signals and decision-support information. Biological interpretation and treatment decisions remain with qualified horticultural experts.

---

# 🎯 Project Objective

The project studies the following research pipeline:

```text
Seedling
   │
   ├── RGB Camera
   │       ↓
   │     RGB AI
   │
   ├── Environmental Sensors
   │       ↓
   │     IoT Data
   │
   └── Track Robot / Drone
           ↓

      Data Acquisition
           ↓
   Individual Plant ID
           ↓
 Longitudinal Dataset
           ↓
     AI Analysis
           ↓
   Expert Review
           ↓
 Research / Decision Support
```

The system is organized into **three connected R&D tracks**.

---

# 1. 📷 RGB AI

## Goal

Analyze RGB plant images to detect visible abnormalities and support plant disease symptom classification.

RGB AI focuses on what can actually be observed from ordinary visible-light imagery:

* lesions
* discoloration
* yellowing
* visible damage
* abnormal texture
* leaf coverage
* growth-related visual features

It does **not** directly identify microscopic pathogens from RGB images.

## Development Flow

```text
Fixed Camera
     ↓
RGB Image Acquisition
     ↓
Capture Quality Validation
     ↓
Leaf / Plant Segmentation
     ↓
Visual Feature Extraction
     ↓
Disease / Abnormality Detection
     ↓
Multi-class Research
     ↓
Edge Deployment
     ↓
Drone Expansion
```

## Current Scope

* fixed-camera RGB capture
* image quality gate
* blur / brightness validation
* tray perspective rectification
* tray-grid segmentation
* HSV-based baseline leaf-area estimation
* image-linked observations
* reproducible image metadata
* expert-review routing for abnormal observations

## Future Scope

* deep-learning segmentation
* disease symptom classification
* disease severity estimation
* uncertainty estimation
* field-environment robustness
* RGB drone imagery
* edge inference

---

# 2. 📈 Longitudinal AI

## Goal

Analyze **how the same seedling changes over time**, instead of judging the plant from only one image.

Every monitored seedling receives a stable identifier based on its tray location.

Example:

```text
TRAY-A-R02C07
```

Repeated observations can then form an individual time series.

```text
Seedling ID
   │
   ├── Timestamp
   ├── RGB Image
   ├── Leaf Area
   ├── Discoloration Ratio
   ├── Damage Ratio
   ├── Growth Rate
   ├── Environmental Context
   ├── AI Confidence
   ├── Health Status
   └── Expert Assessment
```

## Research Questions

Longitudinal AI can be used to investigate:

* individual seedling growth curves
* relative leaf-area change
* visual symptom progression
* disease severity changes
* environmental effects on growth
* differences between control and treatment groups
* relationships between AI measurements and expert assessments

## Experimental Principle

Controlled experiments may contain:

```text
Experiment
   ├── Control Group
   └── Treatment Group
```

Each tray belongs to only one group in the same experiment.

The current statistics are descriptive and must not be interpreted automatically as evidence of causality or statistical significance.

Long-term research may accumulate multiple cultivation cycles and multi-year observations.

---

# 3. 🤖 Physical AI / Smart Farm

## Goal

Automate repeatable plant observation using sensors, edge devices, and robotic systems.

The Physical AI track connects software intelligence with real-world agricultural hardware.

```text
Environmental Sensors
        +
     RGB Camera
        +
   Edge Computer
        +
    Track Robot
        ↓
 Automated Observation
        ↓
    Smart Seedling AI
```

## Environmental Measurements

The platform is designed to support measurements such as:

* air temperature
* atmospheric pressure
* relative humidity
* soil moisture
* raw soil-moisture ADC
* soil-moisture voltage
* illuminance
* electrical conductivity (EC)
* pH

Not every deployment must contain every sensor.

Sensor readings can be ingested independently depending on the available hardware.

## Soil Moisture Principle

Raw soil-moisture measurements are preserved as the source measurement.

Derived percentages depend on calibration and must not be treated as absolute volumetric water content unless scientifically validated.

Calibration records preserve:

* sensor identity
* dry reference
* wet reference
* calibration operator
* calibration timestamp
* calibration method

---

# 🚃 Track Robot

The first robotic platform is planned as a **repeatable track-based observation system**, rather than a complex autonomous mobile robot.

Initial concept:

```text
Home
 ↓
Plant Position 01
 ↓
Capture Image
 ↓
Read Sensors
 ↓
Plant Position 02
 ↓
Capture Image
 ↓
Read Sensors
 ↓
...
 ↓
Return Home
```

Each observation can eventually produce:

```text
Plant ID
+ Timestamp
+ RGB Image
+ Sensor Context
+ Robot Position
```

Future ROS 2 integration may separate:

* camera nodes
* sensor nodes
* motor-control nodes
* observation scheduling
* safety state
* edge AI inference

---

# 🚁 Drone Extension

The drone is not a separate fourth product.

It extends the observation range of the RGB AI system.

Development order:

```text
Fixed Camera
      ↓
Track Robot Camera
      ↓
Drone RGB Camera
```

The fixed-camera environment is used first because it reduces variability from:

* distance
* angle
* illumination
* motion
* background
* image scale

After the RGB pipeline is validated under controlled conditions, the research can expand toward drone imagery and larger cultivation areas.

---

# 🧠 Expert-in-the-Loop

Smart Seedling AI follows an **expert-in-the-loop** principle.

```text
Measured Data
     ↓
AI / Rule Analysis
     ↓
Observable Signals
     ↓
Expert Review
     ↓
Validated Knowledge
```

Observations may be classified conservatively into states such as:

* `healthy`
* `warning`
* `expert_review`

These states are triage labels, not biological diagnoses.

Expert reviews keep observable evidence separate from possible causes.

Knowledge rules use a draft-and-approval workflow so unapproved recommendations are not treated as validated agricultural knowledge.

---

# 🏗️ System Architecture

```text
┌───────────────────────────────────────────────┐
│               Smart Seedling AI               │
├───────────────────────────────────────────────┤
│                                               │
│  RGB AI             Longitudinal AI           │
│    │                      │                    │
│    └──────────┬───────────┘                    │
│               │                               │
│         Observation Data                      │
│               │                               │
│        Expert Review Layer                    │
│               │                               │
│        Research / Dashboard                   │
│                                               │
├───────────────────────────────────────────────┤
│          Physical AI / Smart Farm             │
│                                               │
│ Sensors ─ Camera ─ Edge ─ Track Robot         │
│                       └──── Drone             │
└───────────────────────────────────────────────┘
```

---

# 🗂 Repository Structure

```text
smart-seedling-ai/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── domain.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── vision/
│   │   │   └── service.py
│   │   │
│   │   ├── longitudinal/
│   │   │   └── experiments.py
│   │   │
│   │   ├── smartfarm/
│   │   │   ├── telemetry.py
│   │   │   └── soil.py
│   │   │
│   │   ├── expert/
│   │   │   └── recommendations.py
│   │   │
│   │   └── infrastructure/
│   │       └── repository.py
│   │
│   └── tests/
│       ├── test_api.py
│       ├── vision/
│       ├── longitudinal/
│       ├── smartfarm/
│       ├── expert/
│       └── infrastructure/
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── api/
│       ├── assets/
│       ├── components/
│       ├── hooks/
│       ├── pages/
│       ├── types/
│       ├── features/
│       │   ├── rgb-ai/
│       │   ├── longitudinal-ai/
│       │   └── smart-farm/
│       └── shared/
│
├── edge/
│   ├── agent/
│   │   ├── camera.py
│   │   ├── main.py
│   │   ├── queue.py
│   │   └── uploader.py
│   │
│   ├── drivers/
│   │   ├── sensors/
│   │   ├── camera/
│   │   └── motor/
│   │
│   ├── robot/
│   ├── systemd/
│   └── tests/
│
├── hardware/
│   ├── bom/
│   ├── datasheets/
│   ├── wiring/
│   ├── mechanical/
│   └── README.md
│
├── docs/
│   ├── architecture/
│   │   └── system.md
│   ├── research/
│   ├── protocols/
│   │   ├── experiment.md
│   │   └── validation.md
│   └── adr/
│
├── scripts/
│   ├── dev/
│   ├── data/
│   └── deployment/
│
├── uploads/
├── legacy/
├── .env.example
├── .gitattributes
├── .gitignore
├── pyproject.toml
└── README.md
```

---

# 📦 Module Responsibilities

## `backend/app/core`

Shared domain rules and API schemas.

Examples:

* seedling identifiers
* common enums
* observation metrics
* health triage rules
* Pydantic schemas

---

## `backend/app/vision`

RGB image processing and Vision AI.

Current responsibilities include:

* image decoding
* capture quality assessment
* HSV leaf-area baseline
* tray detection
* perspective rectification
* tray-grid splitting

Future deep-learning models should remain behind this module boundary.

---

## `backend/app/longitudinal`

Time-series growth and long-term research logic.

Responsibilities include:

* repeated seedling observations
* growth analysis
* experimental groups
* longitudinal metrics
* future severity analysis

---

## `backend/app/smartfarm`

Smart-farm telemetry and environmental measurement logic.

Responsibilities include:

* sensor matching
* environmental context
* soil calibration
* future IoT integration
* future robot-related application services

---

## `backend/app/expert`

Expert-validation and knowledge-support logic.

Responsibilities include:

* expert review
* observable signal derivation
* knowledge rules
* recommendation ranking
* validation workflow

---

## `backend/app/infrastructure`

Persistence and external infrastructure.

Responsibilities include:

* SQLite
* repository layer
* future database abstraction
* future file/object storage

---

## `edge`

Software executed near the physical farm hardware.

Current scope:

* Raspberry Pi camera
* offline capture queue
* uploader
* edge agent

Future scope:

* sensor drivers
* motor drivers
* track-robot controller
* local inference
* ROS 2 interfaces

---

## `hardware`

Physical-system documentation.

Includes:

* BOM
* datasheets
* wiring
* mechanical design
* hardware baseline documentation

---

## `docs`

Research and engineering documentation.

```text
architecture/  → system design and interfaces
research/      → research-track documentation
protocols/     → experiment / capture / validation protocols
adr/           → Architecture Decision Records
```

---

# 💾 Core Data Model

The platform currently connects the following research entities:

```text
Tray
  ↓
Seedling
  ↓
Observation
  ├── Image Asset
  ├── Sensor Context
  ├── Growth Metrics
  └── Health Status
          ↓
     Expert Review
```

Experiments extend the model:

```text
Experiment
   ↓
Experiment Group
   ↓
Tray
   ↓
Seedling Observations
```

This shared data model is why RGB AI, Longitudinal AI, and Smart Farm remain inside one repository rather than being separated into independent products.

---

# ✅ Current Capabilities

The current platform already supports:

* stable seedling IDs
* tray registration
* repeated seedling observations
* leaf-area tracking
* discoloration and damage metrics
* relative growth calculations
* conservative health triage
* JPEG / PNG image ingestion
* capture-quality validation
* tray perspective rectification
* full-tray grid analysis
* environmental sensor ingestion
* sensor-to-capture temporal matching
* soil-moisture calibration
* expert-review queue
* expert assessments
* approved knowledge rules
* observation recommendations
* controlled experiment definitions
* experiment CSV export
* descriptive growth comparison
* Raspberry Pi edge capture
* offline capture queue
* monitoring frontend

---

# 🧪 Research Principles

## 1. Reproducibility

Store enough information to reproduce measurements.

Preserve:

* timestamps
* sensor identity
* calibration
* image source
* capture configuration
* operator
* experiment group
* raw measurement values

---

## 2. Raw Data First

Derived values must not replace source measurements.

For example:

```text
Raw ADC
   ↓
Calibration
   ↓
Relative Soil Moisture %
```

The raw ADC remains preserved.

---

## 3. No Silent Diagnosis

The platform may detect:

```text
discoloration
damage
growth decline
low confidence
```

It must not silently convert these observations into unsupported biological diagnoses.

---

## 4. Expert Validation

Agricultural interpretation should be reviewed by domain experts.

---

## 5. Controlled Expansion

Development proceeds from low-variance environments toward more difficult field conditions.

```text
Fixed Camera
      ↓
Controlled Seedling Dataset
      ↓
Sensor Integration
      ↓
Longitudinal Research
      ↓
Track Robot
      ↓
Greenhouse Validation
      ↓
Drone / Field Research
```

---

# 🚀 Development Roadmap

## Phase 1 — Baseline Platform

* stable seedling ID
* tray model
* image capture
* baseline segmentation
* observation database
* monitoring dashboard

**Status: Active**

---

## Phase 2 — Environmental Integration

* temperature
* humidity
* pressure
* soil moisture
* illuminance
* EC
* pH
* calibration tracking

**Status: Active**

---

## Phase 3 — Longitudinal Research

* individual growth curves
* repeated observations
* experiment groups
* severity metrics
* expert annotations
* long-term dataset

**Status: In Development**

---

## Phase 4 — Advanced RGB AI

* manually reviewed dataset
* segmentation model
* multi-class disease symptom research
* uncertainty estimation
* edge inference

**Status: Planned**

---

## Phase 5 — Physical AI

* track hardware
* motor driver
* fixed observation positions
* automated capture sequence
* safety states
* ROS 2 integration

**Status: Planned**

---

## Phase 6 — Drone / Field Extension

* aerial RGB capture
* larger-area monitoring
* field-domain adaptation
* edge deployment

**Status: Research Roadmap**

---

# 🖥️ Quick Start

## Windows PowerShell

```powershell
git clone https://github.com/paichai-nexus/smart-seedling-ai.git
cd smart-seedling-ai

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"

uvicorn app.main:app --app-dir backend --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Linux / macOS

```bash
git clone https://github.com/paichai-nexus/smart-seedling-ai.git
cd smart-seedling-ai

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e '.[dev]'

uvicorn app.main:app --app-dir backend --reload
```

---

# 🌐 Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite development server will display its local URL in the terminal.

---

# 🧪 Tests

From the repository root:

```bash
python -m pytest -q
```

Backend only:

```bash
python -m pytest backend/tests -q
```

Edge only:

```bash
python -m pytest edge/tests -q
```

---

# 🔧 Hardware References

* [`hardware/README.md`](hardware/README.md)
* [`hardware/datasheets/Datasheet_Manifest_v1.md`](hardware/datasheets/Datasheet_Manifest_v1.md)
* [`hardware/bom/Paichai_NEXUS_Smart_Seedling_AI_BOM_v1.1.xlsx`](hardware/bom/Paichai_NEXUS_Smart_Seedling_AI_BOM_v1.1.xlsx)
* [`edge/README.md`](edge/README.md)

---

# 📚 Research Documentation

Architecture:

* [`docs/architecture/system.md`](docs/architecture/system.md)

Protocols:

* [`docs/protocols/experiment.md`](docs/protocols/experiment.md)
* [`docs/protocols/validation.md`](docs/protocols/validation.md)

Additional documents will be added under:

```text
docs/research/
docs/adr/
```

---

# 🤝 Collaboration

Smart Seedling AI is designed as an interdisciplinary project.

Relevant areas include:

* Horticulture
* Computer Engineering
* Vision AI
* Embedded Systems
* Electronics
* IoT
* Robotics
* Drone Engineering
* Architecture
* Landscape / Planting Environment
* Research Operations

Contributors are not restricted to only one technical area.

The project encourages:

```text
Research
   +
Implementation
   +
Experiment
   +
Documentation
   +
Review
```

---

# ⚠️ Disclaimer

This repository is a research and educational platform.

Outputs generated by the system must not be interpreted as autonomous agricultural diagnosis, pesticide prescription, fertilizer prescription, or guaranteed crop-management advice.

Agricultural decisions require appropriate measurements, experimental validation, and qualified domain expertise.

---

# 🌱 PAICHAI NEXUS

**Smart Seedling AI**

Building a reproducible bridge between:

**Plants × Data × AI × IoT × Robotics × Agricultural Expertise**
