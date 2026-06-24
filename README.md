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
- `scripts/` – setup and startup scripts
- `tests/` – lightweight smoke tests for setup and CLI behavior
- `.env.example` – copyable first-run configuration template
- `.github/workflows/ci.yml` – GitHub Actions smoke checks for pushes and pull requests
- `requirements-core.txt` – minimal packages for API, doctor, and CI smoke checks
- `requirements-optional.txt` – heavier ML, dashboard, mapping, and training packages
- `notes.md` – project notes
- `dev_notes.md` – developer notes
- `goals.md` – high-level roadmap

## Usage

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
- `cli/configure.py` – interactive or non-interactive setup to write environment variables to a `.env` file.
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
- `cli/dashboard.py` – interactive Rich-based CLI to run common tasks.
- `utils/pseudo_labeler.py` – create YOLO label files from new images.
- `cli/self_reinforce.py` – label fresh images, merge them into the dataset and retrain the detector.

Example usage:

```bash
python -m app.cli.configure --non-interactive
python -m app.cli.doctor
python -m app.cli.dashboard
python -m app.cli.configure  # create or update a .env file interactively
python -m app.utils.dataset_augmentation images/raw images/augmented -n 5
python -m app.watch_directory data/sentinel path/to/model kyiv
python -m app.pipeline.monitor kyiv models/trajectory.h5 --interval 600
python -m app.drones.live_feed 0 --model models/trajectory.h5 \
    --troop-model troop_model.h5 --classify-drones --classify-vehicles
python -m app.utils.troop_training_cli images/train troop_model.h5 --csv troop_labels.csv
python -m app.utils.human_feedback_viewer images/train predictions.csv feedback.csv
python -m app.analysis.dbscan_cluster UNIT123 --hours 48
python -m app.analysis.heatmap kyiv --hours 24 -o kyiv_heatmap.png
python -m app.analysis.geo_mapper kyiv --hours 24 -o kyiv_map.html
python -m app.movement_logger UNIT123 movements.csv
python -m app.analysis.cluster_strategy_tracker UNIT123 --hours 24
python -m app.analysis.state_encoder kyiv --hours 24 --res 32 -o state.npy
python -m app.analysis.image_stats images/train -o image_stats.csv
python -m app.analysis.movement_stats UNIT123 --hours 24
python -m app.analysis.hog_features images/train -o hog_feats.npz

python -m app.analysis.threat_assessment '[{"center": [30.5, 50.4], "count": 5}]'
# Train a YOLO model after preparing a data.yaml file:
python -m app.training.dataset_loader /data/train/images /data/val/images \
    --classes troop vehicle -o data.yaml
python -m app.training.train_yolo /data/train/images /data/val/images yolo_model.pt \
    --classes troop vehicle --epochs 50
# Train sequentially on multiple YAML datasets
python -m app.training.train_sequential_yolo dataset1.yaml dataset2.yaml yolo_model.pt \
    --epochs 25
python -m app.utils.pseudo_labeler images/new -o pseudo_labels --conf 0.7
python -m app.cli.self_reinforce images/new /data/train/images /data/val/images \
    --classes troop vehicle --out-model updated_model.pt --epochs 5
```

## Training Methodology

1. **Prepare images**: Organize raw imagery by class and optionally run
   `utils/dataset_augmentation.py` to expand the dataset with flips, brightness
   changes and random rotations.
2. **Create data configuration**: Use `training/dataset_loader.py` to generate
   the `data.yaml` file required by the Ultralytics trainer.
3. **Train the detector**: Execute `training/train_yolo.py` pointing to the
   training and validation directories. Optional flags allow adjusting batch
   size, image resolution and learning rate for finer control.
4. **Sequential training**: For very large datasets you can train in batches
   using `training/train_sequential_yolo.py` and a list of `data.yaml` files.
   Each YAML is trained for the specified epochs before moving to the next to
   conserve GPU memory.
5. **Deploy**: Copy the resulting `.pt` model into the pipeline and update the
   detection wrapper to load it instead of the stub.
