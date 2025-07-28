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
- `notes.md` – project notes
- `dev_notes.md` – developer notes
- `goals.md` – high-level roadmap

## Usage
Run `scripts/start.sh` to install dependencies and launch the API:

```bash
bash scripts/start.sh
```

This will start a local server at `http://localhost:8000` with several endpoints:

- `POST /predict/{area}` - run detection and prediction for an area
- `GET /detections/{area}?limit=10` - fetch recent detections
- `GET /predictions/{area}?limit=10` - fetch recent trajectory predictions

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
environment variables before running the scripts:

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
- `cli/configure.py` – interactive setup to write environment variables to a `.env` file.
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
python -m app.cli.dashboard
python -m app.cli.configure  # create or update a .env file
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
python -m app.analysis.threat_assessment "[{"center": [30.5, 50.4], "count": 5}]"
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
