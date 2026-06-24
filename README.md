# Military Neural Network Troop Prediction

This repository provides a starting point for a machine vision application that predicts troop movements using satellite imagery and OSINT data.

## Structure
- `app/` – Python package containing the main modules
  - `config.py` – configuration settings
  - `database.py` – MongoDB helpers
  - `data_ingestion.py` – OSINT and satellite retrieval
  - `detection/` – YOLO wrappers
  - `models/` – trajectory prediction models
  - `pipeline/` – scripts combining ingestion, detection and prediction
  - `api/` – FastAPI endpoints
- `scripts/` – setup, diagnostics, quickstart, and startup scripts
- `tests/` – lightweight smoke tests for setup and CLI behavior
- `.env.example` – copyable first-run configuration template
- `.github/workflows/ci.yml` – GitHub Actions smoke checks for pushes and pull requests
- `requirements-core.txt` – minimal packages for API, doctor, and CI smoke checks
- `requirements-optional.txt` – heavier ML, dashboard, mapping, and training packages
- `notes.md` – project notes
- `dev_notes.md` – developer notes
- `goals.md` – high-level roadmap

## Usage

### Fast first run

For a guided local setup path that installs the small core dependency set, creates
`.env` when needed, runs diagnostics, and prints the next command to run:

```bash
python -m app.cli.quickstart
# or
bash scripts/quickstart.sh
```

Useful options:

```bash
python -m app.cli.quickstart --skip-install
python -m app.cli.quickstart --install-profile optional --check-optional --check-mongo
python -m app.cli.quickstart --launch-api --host 127.0.0.1 --port 8000
```

The default quickstart path is intentionally conservative: it installs only
`requirements-core.txt`, creates a safe local config if one does not already
exist, skips optional ML/GIS/dashboard dependency checks, skips MongoDB socket
checks, and does not run detection or prediction.

### 1. Install dependencies

For a fast smoke-test/API environment:

```bash
python -m pip install -r requirements-core.txt
```

For the full local toolkit, including ML, dashboard, mapping, and training helpers:

```bash
python -m pip install -r requirements-optional.txt
```

You can also use the setup wrapper, which installs the full optional stack by default:

```bash
bash scripts/setup.sh
```

Set `INSTALL_PROFILE=core` when you only want the smaller runtime used by CI:

```bash
INSTALL_PROFILE=core bash scripts/setup.sh
```

Run `scripts/start.sh` to install dependencies and launch the API:

```bash
bash scripts/start.sh
```

This will start a local server at `http://localhost:8000` with several endpoints:

- `POST /predict/{area}` - run detection and prediction for an area
- `GET /detections/{area}?limit=10` - fetch recent detections
- `GET /predictions/{area}?limit=10` - fetch recent trajectory predictions

### 2. Create local configuration

The app reads a simple `.env` file when present. To create one with safe local
defaults from `.env.example`, run:

```bash
python -m app.cli.configure --non-interactive
```

For guided setup, run the interactive mode instead:

```bash
python -m app.cli.configure
```

Use `--path custom.env` to write a different file and `--overwrite` to replace an
existing file. The default configuration uses `data/`, `mongodb://localhost:27017`,
and `troop_db`; Sentinel Hub values can be left blank when you want placeholder
imagery instead of live Sentinel imagery.

### 3. Check your setup first

Before launching heavier workflows, run the setup doctor to verify that Python,
configuration templates, local environment files, core dependencies, optional
analysis dependencies, the data directory, Sentinel Hub environment variables,
and MongoDB socket connectivity are configured:

```bash
python -m app.cli.doctor
# or
bash scripts/doctor.sh
```

Useful options:

```bash
python -m app.cli.doctor --skip-optional --skip-mongo
python -m app.cli.doctor --skip-env-files
python -m app.cli.doctor --json
```

The command is read-only except for creating the configured `DATA_DIR` and a
short-lived write probe inside it. Warnings identify optional capabilities that
are missing; failures identify core setup problems that should be fixed before
running the API or automation pipeline.

### Automated checks

A lightweight GitHub Actions workflow runs on pushes and pull requests to catch
basic breakage before heavier ML workflows are attempted. It installs the shared
core requirements file, compiles the Python package and tests, runs the setup
doctor in minimal mode, and executes the standard-library unit tests:

```bash
python -m pip install -r requirements-core.txt
python -m compileall app tests
python -m app.cli.doctor --skip-optional --skip-mongo --json
python -m unittest discover -s tests -p 'test_*.py'
```

You can run the same checks locally with:

```bash
bash scripts/test.sh
```

CI also creates a `ci-diagnostics` artifact bundle on every run, even failed
runs. The bundle includes the Python and pip versions, `pip freeze`, doctor JSON,
and the current help output for the doctor and quickstart CLIs. To build the same
bundle locally:

```bash
bash scripts/ci_report.sh
```

These checks are intentionally small and fast. Optional ML, dashboard, mapping,
and training dependencies should be validated by targeted workflows as those
areas mature.

Additional modules handle Sentinel Hub imagery and CLI workflows:
- `satellite/` – Sentinel image download and inference pipeline
  - `movement_history.py` – query MongoDB for recent unit positions
  - `pipeline/run_real_time_pipeline.py` – CLI to fetch imagery and run detection
  - `pipeline/realtime.py` – store detections and predictions in MongoDB
  - `detection/ground_troop.py` – enhanced detection for irregular troop images
  - `drones/live_feed.py` – capture drone video streams for live inference
  Detection results are stored in the `detections` collection and trajectory predictions in `predictions`.

## Environment
The pipeline can optionally fetch imagery from Sentinel Hub. Set the following
environment variables before running the scripts, or put them in `.env`:

```
export SENTINEL_CLIENT_ID="your-client-id"
export SENTINEL_CLIENT_SECRET="your-secret"
export SENTINEL_INSTANCE_ID="your-instance-id"
```

If these variables are unset, placeholder images will be used instead.

To run the standalone pipeline from the command line:

```bash
python -m app.pipeline.run_real_time_pipeline AREA path/to/model
```

## Utilities

Several helper scripts aid with data preparation and automation:

- `cli/quickstart.py` – guided first-run setup. Run as `python -m app.cli.quickstart`.
- `cli/doctor.py` – run read-only setup diagnostics. Run as `python -m app.cli.doctor`.
- `utils/dataset_augmentation.py` – create augmented training images using
  Albumentations. Run as `python -m app.utils.dataset_augmentation SRC DST -n 5`.
- `utils/troop_training_cli.py` – label troop images and train a classifier. Run
  as `python -m app.utils.troop_training_cli DIR model.h5 --csv labels.csv`.
- `utils/human_feedback_viewer.py` – review predictions in a simple Tkinter
  GUI and record whether they are correct.
- `watch_directory.py` – poll a folder for new satellite images and process them
  automatically via the real-time pipeline.
- `pipeline/monitor.py` – periodically fetch imagery from Sentinel Hub and run
  detection without manual intervention.
- `cli/configure.py` – interactive or non-interative setup to write environment variables to a `.env` file.
- `drones/live_feed.py` – capture a drone camera stream and perform live inference.
- `detection/ground_troop.py` – detect troops from low-quality or angled images.
- `detection/troop_identifier.py` – classify detected troops by type and uniform.
- `detection/drone_identifier.py` – classify drone models from images.
- `detection/vehicle_identifier.py` – classify vehicles from images.
- `training/dataset_loader.py` – generate YOLO data.yaml files.
- `training/train_yolo.py` – train a YOLO model from prepared datasets.
- `training/train_sequential_yolo.py` – train on multiple datasets sequentially.
- `analysis/dbscan_cluster.py` – cluster movement logs with DBSCAN to find
  common locations. Run as `python -m app.analysis.dbscan_cluster UNIT_ID`.
- `analysis/heatmap.py` – generate detection heatmaps as PNG images.
- `analysis/geo_mapper.py` – create interactive HTML maps from stored detections.
- `movement_logger.py` – log detection records for clustering.
- `analysis/cluster_strategy_tracker.py` – cluster unit movements and generate heatmaps.
- `analysis/threat_assessment.py` – compute simple threat scores from clusters.
- `analysis/state_encoder.py` – encode detections into a grid tensor for ML models.
- `analysis/image_stats.py` – compute brightness and blur metrics for training datasets.
- `analysis/movement_stats.py` – summarize average speed and heading from logged movements.
- `analysis/hog_features.py` – extract HOG descriptors from images for feature analysis.
