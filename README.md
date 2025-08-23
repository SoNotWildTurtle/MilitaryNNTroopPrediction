# Military Neural Network Troop Prediction

[Читати українською](README.uk.md)

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
- `MODEL_CARD.md` – model details and intended use
- `OPS_RUNBOOK.md` – operational procedures and alert handling

## Usage
Run `scripts/start.sh` to install dependencies and launch the API:

```bash
bash scripts/start.sh
```

Set `UI_LANG` or pass `--lang` (e.g., `--lang uk`) to translate dashboard text for Ukrainian analysts when running interactive CLIs.

This will start a local server at `http://localhost:8000` with several endpoints:

- `POST /predict/{area}` - run detection and prediction for an area
- `GET /detections/{area}?limit=10` - fetch recent detections
- `GET /predictions/{area}?limit=10` - fetch recent trajectory predictions

When the server is running, a minimal web interface is served at `/gui/`.
Open `http://localhost:8000/gui/` in a browser to query detections and
predictions without using the command line.

Additional modules handle Sentinel Hub imagery and CLI workflows:
- `satellite/` – Sentinel image download and inference pipeline
  - `movement_history.py` – query MongoDB for recent unit positions
  - `pipeline/run_real_time_pipeline.py` – CLI to fetch imagery and run detection
  - `pipeline/realtime.py` – store detections and predictions in MongoDB
  - `detection/ground_troop.py` – enhanced detection for irregular troop images
  - `drones/live_feed.py` – capture drone video streams for live inference
  Detection results include a `doctrine` field and are stored in the `detections` collection. Trajectory predictions are stored in `predictions`.

A confidence fusion step correlates detector scores with troop, drone, and vehicle classifiers to raise trust in each recorded identification.

## Environment
The pipeline can optionally fetch imagery from Sentinel Hub. Set the following
environment variables before running the scripts:

```
export SENTINEL_CLIENT_ID="your-client-id"
export SENTINEL_CLIENT_SECRET="your-secret"
export SENTINEL_INSTANCE_ID="your-instance-id"
export OPENAI_API_KEY="your-openai-key"
export SOURCE_CATALOG="sources.json"
```

If these variables are unset, placeholder images will be used instead.

A `.env.example` file lists the required variables; copy it to `.env` and
adjust the values for your environment.

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
  GUI with translated labels and record whether they are correct.
- `utils/feedback_logger.py` – store human feedback records in MongoDB for later retraining.
- `watch_directory.py` – poll a folder for new satellite images and process them
  automatically via the real-time pipeline.
- `pipeline/monitor.py` – periodically fetch imagery from Sentinel Hub and run
  detection without manual intervention.
- `cli/configure.py` – interactive setup to write environment variables to a `.env` file with localized prompts.
- `drones/live_feed.py` – capture a drone camera stream and perform live inference.
- `info_gathering/camera_collector.py` – periodically save frames from a webcam or video for later analysis.
- `info_gathering/source_finder.py` – query ChatGPT in a background thread to suggest new image or video input sources.
- `info_gathering/source_catalog.py` – maintain a JSON catalog of discovered sources and deduplicate verified links.
- `cli/discover_sources.py` – run a one-off ChatGPT query and append results to the source catalog.
- `detection/ground_troop.py` – detect troops from low-quality or angled images.
- `detection/troop_identifier.py` – classify detected troops by type and uniform.
- `detection/drone_identifier.py` – classify drone models from images.
- `detection/vehicle_identifier.py` – classify vehicles from images.
- `detection/tactical_wrapper.py` – tag detections with doctrine labels before
  logging.
- `training/dataset_loader.py` – generate YOLO data.yaml files.
- `training/train_yolo.py` – train a YOLO model from prepared datasets.
- `training/train_sequential_yolo.py` – train on multiple datasets sequentially.
- `training/train_with_augmentation.py` – augment images then train YOLO in one step.
- `training/auto_dataset_trainer.py` – split a raw dataset, augment, and train YOLO automatically.
- `training/hyperparameter_search.py` – grid-search batch size, learning rate and image size.
- `training/threat_model_trainer.py` – fit a classifier to map cluster features to threat levels.
- `analysis/dbscan_cluster.py` – cluster movement logs with DBSCAN to find
  common locations. Run as `python -m app.analysis.dbscan_cluster UNIT_ID`.
- `analysis/heatmap.py` – generate detection heatmaps as PNG images.
- `analysis/geo_mapper.py` – create interactive HTML maps from stored detections.
- `movement_logger.py` – log detection records for clustering.
- `analysis/cluster_strategy_tracker.py` – cluster unit movements and generate heatmaps.
- `analysis/threat_assessment.py` – compute threat scores, weight sites by
  priority, estimate time-to-arrival, and assign threat levels for clusters.
- `analysis/state_encoder.py` – encode detections into a grid tensor for ML models.
- `analysis/image_stats.py` – compute brightness and blur metrics for training datasets.
- `analysis/movement_stats.py` – summarize average speed and heading from logged movements.
- `analysis/movement_predictor.py` – forecast the next position using a constant-velocity Kalman step.
- `analysis/hog_features.py` – extract HOG descriptors from images for feature analysis.
- `analysis/feature_fusion.py` – combine color, HOG and edge features for richer descriptors.
- `analysis/confidence_stats.py` – compute per-class detection confidence metrics from JSON logs.
  - `analysis/confidence_calibrator.py` – fit an isotonic regression model from feedback to calibrate detector confidence.
  - `analysis/confidence_fusion.py` – merge detection and classification confidences to boost overall trust.
  - `analysis/meta_analysis.py` – aggregate detection counts, feedback accuracy, and cluster metrics for high-level reports.
  - `cli/dashboard.py` – interactive operator dashboard to run pipeline tasks plus
    dedicated map and training pages. The map page generates detection maps,
    heatmaps, clusters movements, runs meta analysis or movement stats, and
    computes threat assessments. Each tool accepts a start/end date range or
    lookback hours. The training page handles self-reinforcement, auto training,
    and hyperparameter searches. The main screen also streams drone feeds,
    captures camera frames, handles configuration, displays a configuration
    summary, produces detection reports, shows a help screen, and can switch
    languages on the fly.
- `utils/pseudo_labeler.py` – create YOLO label files from new images.
- `cli/self_reinforce.py` – label fresh images, merge them into the dataset and retrain the detector.
- `cli/train_wizard.py` – prompt-based wizard to train a YOLO model with localized prompts and sensible defaults.
- `training/self_training_loop.py` – run repeated self-reinforcement cycles.
- `training/self_training_aug.py` – self-training loop with dataset augmentation.
- `training/active_learning.py` – active learning with human feedback during reinforcement.
- `translation/translator.py` – translate dashboard text to a chosen language at runtime.
- `cli/report.py` – summarize recent detections by class and confidence.
- `cli/generate_demo_data.py` – create a synthetic dataset for offline testing.

Example usage:

```bash
python -m app.cli.dashboard
python -m app.cli.configure  # create or update a .env file
python -m app.utils.dataset_augmentation images/raw images/augmented -n 5
python -m app.info_gathering.camera_collector 0 collected_frames --interval 2
python -m app.cli.discover_sources "List public drone video feeds" --verify
python -m app.watch_directory data/sentinel path/to/model kyiv
python -m app.pipeline.monitor kyiv models/trajectory.h5 --interval 600
python -m app.drones.live_feed 0 --model models/trajectory.h5 \
    --troop-model troop_model.h5 --classify-drones --classify-vehicles
python -m app.utils.troop_training_cli images/train troop_model.h5 --csv troop_labels.csv
  python -m app.utils.human_feedback_viewer images/train predictions.csv feedback.csv
python -m app.cli.report  # summarize recent detections
python -m app.cli.generate_demo_data  # create a demo dataset
  python -m app.analysis.confidence_calibrator feedback.csv calib.npz
  python -m app.analysis.dbscan_cluster UNIT123 --hours 48
  python -m app.analysis.heatmap kyiv --start 2024-05-01 --end 2024-05-02 -o kyiv_heatmap.png
python -m app.analysis.geo_mapper kyiv --start 2024-05-01 --end 2024-05-02 -o kyiv_map.html
python -m app.movement_logger UNIT123 movements.csv
python -m app.analysis.cluster_strategy_tracker UNIT123 --hours 24
python -m app.analysis.state_encoder kyiv --hours 24 --res 32 -o state.npy
python -m app.analysis.image_stats images/train -o image_stats.csv
python -m app.analysis.movement_stats UNIT123 --hours 24
python -m app.analysis.movement_predictor "[{\"lat\":50.4,\"lon\":30.5,\"timestamp\":\"2024-05-01T00:00:00\"},{\"lat\":50.41,\"lon\":30.51,\"timestamp\":\"2024-05-01T00:10:00\"}]" --dt 300
python -m app.analysis.hog_features images/train -o hog_feats.npz
  python -m app.analysis.feature_fusion sample.jpg
  python -m app.analysis.confidence_stats detections.json
  python -m app.analysis.meta_analysis --hours 48
python -m app.cli.dashboard --lang uk  # run dashboard in Ukrainian
  python -m app.analysis.threat_assessment "[{\"center\": [30.5, 50.4], \"count\": 5, \"avg_speed\": 40, \"heading\": 90}]"
  # Each result includes site weighting, an ETA in minutes, and a threat level.
  # Tag doctrine for a single image using the wrapper
python -m app.detection.tactical_wrapper sample.jpg
# Train a YOLO model after preparing a data.yaml file:
python -m app.training.dataset_loader /data/train/images /data/val/images \ 
    --classes troop vehicle -o data.yaml
python -m app.training.train_yolo /data/train/images /data/val/images yolo_model.pt \
    --classes troop vehicle --epochs 50
# Train with built-in augmentation before training
python -m app.training.train_with_augmentation /data/train/images /data/val/images yolo_aug.pt \
    --classes troop vehicle --n-aug 5 --epochs 50
# Train sequentially on multiple YAML datasets
python -m app.training.train_sequential_yolo dataset1.yaml dataset2.yaml yolo_model.pt \
    --epochs 25
# Search hyperparameters for optimal settings
python -m app.training.hyperparameter_search /data/train/images /data/val/images runs/ \
    --classes troop vehicle --epochs 10 --batches 16 32 --lrs 0.001 0.0005 --img-sizes 640 512
  python -m app.utils.pseudo_labeler images/new -o pseudo_labels --conf 0.7
  python -m app.cli.self_reinforce images/new /data/train/images /data/val/images \
      --classes troop vehicle --out-model updated_model.pt --epochs 5
  python -m app.cli.train_wizard  # guided prompts for training
  python -m app.training.self_training_loop images/new /data/train/images /data/val/images updated_model.pt \
      --classes troop vehicle --iterations 3 --epochs 5
  python -m app.training.self_training_aug images/new /data/train/images /data/val/images updated_model.pt \
      --classes troop vehicle --iterations 3 --epochs 5 --n-aug 3
  python -m app.training.active_learning images/new /data/train/images /data/val/images updated_model.pt \
      --classes troop vehicle --conf-threshold 0.5 --epochs 5 --n-aug 3
python -m app.training.threat_model_trainer clusters.csv threat_model.joblib --algo forest
python -m app.analysis.threat_model threat_model.joblib '{"distance_km":5,"count":10,"avg_speed":40,"approaching":1}'
```

## Training Methodology

1. **Prepare images**: Organize raw imagery by class. You can pre-augment the
   dataset with `utils/dataset_augmentation.py` or allow the training workflow
   to handle augmentation automatically.
2. **Create data configuration**: Use `training/dataset_loader.py` to generate
   the `data.yaml` file required by the Ultralytics trainer.
3. **Train the detector**: For a guided experience run
   `cli/train_wizard.py`, which prompts for paths and class names and handles
   optional augmentation. Advanced users can call
   `training/train_yolo.py` directly or use `training/train_with_augmentation.py`
   to generate augmented copies before training. Optional flags let you tune
   batch size, image resolution and learning rate.
4. **Hyperparameter search**: Evaluate batches, learning rates and image sizes
   with `training.hyperparameter_search` to find the best combination.
5. **Sequential training**: For very large datasets you can train in batches
   using `training/train_sequential_yolo.py` and a list of `data.yaml` files.
   Each YAML is trained for the specified epochs before moving to the next to
   conserve GPU memory.
6. **Self-reinforcement**: Use `utils.pseudo_labeler` followed by the
   `cli.self_reinforce` script to automatically label new images, merge them into
   the dataset and retrain the model.
7. **Iterative self-training**: Run `training.self_training_loop` to repeat
   labeling and retraining for multiple cycles.
8. **Augmented self-training**: Use `training.self_training_aug` to add dataset
   augmentation during each reinforcement step.
9. **Active learning**: Run `training.active_learning` to review low-confidence
   detections with the feedback GUI before retraining.
10. **Deploy**: Copy the resulting `.pt` model into the pipeline and update the
    detection wrapper to load it instead of the stub.
11. **Threat classifier training**: Use `training.threat_model_trainer` with
    labeled cluster features to learn a model that predicts risk levels
    automatically.

## Documentation

See [MODEL_CARD.md](MODEL_CARD.md) for data sources, evaluation metrics, and
intended use. Operational procedures and alert handling are described in
[OPS_RUNBOOK.md](OPS_RUNBOOK.md).
