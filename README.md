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

Because this step downloads packages, verify hashes or use internal mirrors to avoid supply-chain attacks if infrastructure is compromised.

The script installs CPU dependencies first. If a GPU is available, it automatically pulls CUDA-enabled packages such as PyTorch and full TensorFlow after the CPU setup completes.

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
  - `detection/acoustic_detector.py` – turn acoustic feature logs into troop, vehicle, or drone detections
  Detection results include a `doctrine` field and are stored in the `detections` collection. Trajectory predictions are stored in `predictions`.

A confidence fusion step correlates detector scores with troop, drone, and vehicle classifiers to raise trust in each recorded identification.
A LIDAR module provides electromagnetic-based detection, flags whether objects appear in cover, and a sensor fusion helper merges camera and LIDAR results for higher confidence.
Sensor fusion now weights camera, LIDAR, and Bluetooth scores by configurable reliability factors and reports an uncertainty value for each fused class.

### Item catalog
Track every training image with its class and confidence score:

```bash
python -m app.cli.item_catalog --add ITEM_ID CLASS SCORE
python -m app.cli.item_catalog --list
```

Items are stored in a CSV catalog so operators can sort them by classifier and review model confidence. The `pseudo_labeler` automatically registers each labeled image with its score.

### Extend unified classifier
Grow the unified target model when analysts need to track a new class:

```bash
python -m app.cli.extend_unified_model
```

The CLI prompts for a saved model path and the label of the new target. It appends a randomly initialized neuron so the classifier can be retrained with additional images.

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
- `detection/vit_identifier.py` – classify troops, vehicles, or drones using Vision Transformer embeddings; train via `python -m app.cli.train_vit_identifier`.
- `detection/resnet_identifier.py` – identify targets with ResNet embeddings; train via `python -m app.cli.train_resnet_identifier`.
- `detection/swin_identifier.py` – classify targets with Swin Transformer embeddings; train via `python -m app.cli.train_swin_identifier`.
- `info_gathering/source_catalog.py` – maintain a JSON catalog of discovered sources and deduplicate verified links.
- `cli/discover_sources.py` – run a one-off ChatGPT query and append results to the source catalog.
- `detection/ground_troop.py` – detect troops from low-quality or angled images.
- `detection/unified_identifier.py` – single classifier for troops, vehicles, and drones.
- `cli/extend_unified_model.py` – add a new target class to the unified classifier by appending an output neuron for an operator-provided label.
- `detection/troop_identifier.py` – classify detected troops by type and uniform.
- `detection/drone_identifier.py` – classify drone models from images.
- `detection/vehicle_identifier.py` – classify vehicles from images.
- `detection/lidar_detector.py` – detect troops, vehicles, and drones from LIDAR point clouds.
- `detection/camera_detector.py` – detect troops, vehicles, and drones from images.
- `detection/sensor_fusion.py` – merge camera and LIDAR detections; `detect_fused_objects` runs both sensors for troops, vehicles, and drones.
- `detection/clip_identifier.py` – zero-shot image classification using CLIP embeddings.
- `detection/tactical_wrapper.py` – tag detections with doctrine labels before
  logging.
- `training/dataset_loader.py` – generate YOLO data.yaml files.
- `training/train_yolo.py` – train a YOLO model from prepared datasets.
- `training/train_sequential_yolo.py` – train on multiple datasets sequentially.
- `training/train_with_augmentation.py` – augment images then train YOLO in one step.
- `training/auto_dataset_trainer.py` – split a raw dataset, augment, and train YOLO automatically.
- `training/verify_dataset.py` – check that all images have matching labels before training.
- `training/hyperparameter_search.py` – grid-search batch size, learning rate and image size.
- `training/threat_model_trainer.py` – fit a classifier to map cluster features to threat levels.
- `training/sensor_pointcloud_trainer.py` – fuse sensor CSV features with image-derived point clouds for classifier training.
- `training/gaussian_pointcloud_trainer.py` – fit Gaussian models from labeled point clouds for entity identification.
- `training/fused_gaussian_trainer.py` – fit Gaussian models from paired image and sensor point clouds.
- `training/gaussian_nb_trainer.py` – train a Gaussian Naive Bayes model on fused image and sensor clouds.
- `training/gaussian_kde_trainer.py` – fit Gaussian kernel-density models from paired image and sensor point clouds.
- `training/gaussian_process_trainer.py` – train a Gaussian Process classifier from paired image and sensor point clouds.
- `training/pointnet_gaussian_trainer.py` – learn a PointNet encoder and Gaussian stats from labeled point clouds.
- `training/gaussian_mixture_trainer.py` – fit Gaussian mixture models to multi-modal sensor features.
- `training/orb_bow_trainer.py` – train an ORB bag-of-visual-words classifier.
- `training/resnet_trainer.py` – fit a logistic classifier on ResNet embeddings.
- `training/swin_trainer.py` – fit a logistic classifier on Swin Transformer embeddings.
- `cli/train_pointnet_gaussian.py` – fit the PointNet-Gaussian model from a CSV of point clouds.
- `cli/pointnet_gaussian_report.py` – match image and sensor point clouds using the PointNet-Gaussian model.
- `analysis/gaussian_mixture_match.py` – rank sensor features with trained Gaussian mixtures.
- `cli/gaussian_mixture_report.py` – display Gaussian mixture match probabilities for feature inputs.
- `cli/train_orb_bow.py` – train an ORB bag-of-words model from labeled images.
- `cli/orb_bow_report.py` – display ORB bag-of-words match probabilities.
- `cli/train_resnet_identifier.py` – train a ResNet-based classifier from labeled images.
- `cli/resnet_classify.py` – classify an image using a ResNet-based classifier.
- `cli/train_swin_identifier.py` – train a Swin-based classifier from labeled images.
- `cli/swin_classify.py` – classify an image using a Swin-based classifier.
- `training/gaussian_pointcloud_update.py` – incrementally update saved Gaussian models with new labeled points.
- `analysis/dbscan_cluster.py` – cluster movement logs with DBSCAN to find
  common locations. Run as `python -m app.analysis.dbscan_cluster UNIT_ID`.
- `analysis/heatmap.py` – generate detection heatmaps as PNG images.
- `analysis/geo_mapper.py` – create interactive HTML maps from stored detections.
- `analysis/geojson_export.py` – convert detection records to GeoJSON files.
- `analysis/uncertainty_heatmap.py` – blur low-confidence detections into uncertainty heatmaps.
- `movement_logger.py` – log detection records for clustering.
- `analysis/cluster_strategy_tracker.py` – cluster unit movements and generate heatmaps.
- `analysis/threat_assessment.py` – compute threat scores, weight sites by
  priority, estimate time-to-arrival, and assign threat levels for clusters.
- `analysis/state_encoder.py` – encode detections into a grid tensor for ML models.
- `analysis/image_stats.py` – compute brightness and blur metrics for training datasets.
- `analysis/movement_stats.py` – summarize average speed and heading from logged movements.
- `analysis/speed_anomaly.py` – flag units whose average speed deviates from peers.
- `analysis/acceleration_stats.py` – summarize average and max acceleration from logged movements.
- `analysis/acceleration_anomaly.py` – flag units whose acceleration deviates from peers.
- `analysis/movement_predictor.py` – forecast the next position using a constant-velocity Kalman step.
- `analysis/hog_features.py` – extract HOG descriptors from images for feature analysis.
- `analysis/feature_fusion.py` – combine color, HOG and edge features for richer descriptors.
- `analysis/orb_bow_match.py` – classify images using an ORB bag-of-visual-words model.
- `analysis/confidence_stats.py` – compute per-class detection confidence metrics from JSON logs.
  - `analysis/confidence_calibrator.py` – fit an isotonic regression model from feedback to calibrate detector confidence.
  - `analysis/confidence_fusion.py` – merge detection and classification confidences to boost overall trust.
  - `analysis/sensor_certainty.py` – `fuse_sensor_confidences` computes weighted multi-sensor confidence and uncertainty.
  - `analysis/meta_analysis.py` – aggregate detection counts, feedback accuracy, and cluster metrics for high-level reports.
- `analysis/anomaly_detector.py` – flag detection classes with unusual spikes compared to baseline.
- `analysis/detection_trends.py` – summarize per-class detection counts by day to highlight trends.
- `analysis/moving_average.py` – compute rolling averages of daily detection counts to smooth volatility.
- `analysis/hourly_activity.py` – count detections per class by hour of day.
- `analysis/weekly_activity.py` – count detections per class by day of week.
- `analysis/cooccurrence.py` – count how often classes appear together in a detection event.
- `analysis/burst_detector.py` – flag time buckets with unusually high detection counts.
- `analysis/lag_correlation.py` – measure correlation between class counts at different time lags.
- `analysis/interarrival.py` – compute average and median hours between detections for each class.
- `analysis/peak_times.py` – find the busiest hour and weekday for each class.
- `analysis/change_point.py` – detect sudden shifts in daily detection counts.
- `analysis/class_diversity.py` – measure detection class diversity via Shannon entropy.
- `analysis/image_pointcloud.py` – convert images into 2D point clouds.
- `analysis/pointcloud_coanalysis.py` – cross-check image and point cloud detections.
- `analysis/fused_gaussian_match.py` – convert images and sensor clouds into fused point clouds and rank classes with a trained Gaussian model.
- `analysis/gaussian_nb_match.py` – classify fused image and sensor clouds with a Gaussian Naive Bayes model.
- `analysis/gaussian_kde_match.py` – classify fused image and sensor clouds with per-class Gaussian KDE models.
- `analysis/gaussian_process_match.py` – classify fused image and sensor clouds with a Gaussian Process model.
- `analysis/gaussian_pointcloud_match.py` – compare fused image and sensor point clouds with trained Gaussian models and return ranked matches with probabilities.
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
- `cli/train_wizard.py` – wizard to train a YOLO model with localized prompts and optional flags to skip questions.
- `cli/train_sensor.py` – train a simple classifier on sensor feature CSVs; supports `--dir` to train all CSVs in a folder or `--images/--labels` to learn from image-derived point clouds.
- `cli/train_sensor_pointcloud.py` – train a sensor classifier from a CSV referencing images and labels.
- `training/acoustic_trainer.py` and `cli/train_acoustic.py` – learn an acoustic classifier from sound feature CSVs.
- `cli/train_gaussian_pointcloud.py` – fit per-class Gaussian means and covariances from point-cloud CSVs.
- `cli/train_fused_gaussian.py` – train Gaussian models from CSV pairs of images and sensor clouds.
- `cli/train_gaussian_nb.py` – train a Gaussian Naive Bayes model from image and sensor pairs.
- `cli/train_gaussian_kde.py` – train a Gaussian KDE model from image and sensor pairs.
- `cli/train_gaussian_process.py` – train a Gaussian Process classifier from paired image and sensor clouds.
- `cli/gaussian_match_report.py` – rank image and sensor point clouds against trained Gaussians; use `--top` to show multiple candidates.
- `cli/fused_gaussian_report.py` – display fused Gaussian matches from an image and sensor point cloud.
- `cli/gaussian_nb_report.py` – display GaussianNB match probabilities from an image and sensor point cloud.
- `cli/gaussian_kde_report.py` – display Gaussian KDE match probabilities from an image and sensor point cloud.
- `cli/gaussian_process_report.py` – display Gaussian Process match probabilities from an image and sensor point cloud.
- `cli/update_gaussian_model.py` – merge additional point-cloud CSVs into an existing Gaussian model.
  - `training/self_training_loop.py` – run repeated self-reinforcement cycles.
- `training/self_training_aug.py` – self-training loop with dataset augmentation.
- `training/active_learning.py` – active learning with human feedback during reinforcement.
- `training/sensor_auto_trainer.py` – automatically train a classifier from sensor feature CSVs.
- `translation/translator.py` – translate dashboard text to a chosen language at runtime.
- `cli/report.py` – summarize recent detections by class and confidence; accepts
  `--area` and `--limit` to skip prompts.
- `cli/generate_demo_data.py` – create a synthetic dataset for offline testing.
- `cli/anomaly_report.py` – list detection anomalies.
- `cli/trend_report.py` – show detection trends.
- `cli/moving_report.py` – show moving average detection counts.
- `cli/volatility_report.py` – show detection count volatility.
- `cli/speed_report.py` – list units with anomalous speeds.
- `cli/acceleration_report.py` – list units with anomalous accelerations; accepts
  `--hours` and `--z` to skip prompts.
- `cli/activity_report.py` – summarize detections by hour of day.
- `cli/cooccurrence_report.py` – show class co-occurrence matrix.
- `cli/burst_report.py` – list detection bursts.
- `cli/lag_report.py` – show lagged class correlations.
- `cli/weekly_report.py` – summarize detections by day of week.
- `cli/interarrival_report.py` – show average and median time between detections.
- `cli/peak_report.py` – list peak detection hour and weekday for each class.
- `cli/streak_report.py` – show longest detection streak per class.
- `cli/diversity_report.py` – show detection class diversity.
- `cli/fusion_report.py` – run camera, LIDAR, and Bluetooth detection for troops, vehicles, and drones and display fused results with cover flags; accepts `--image`, `--pointcloud`, and `--bluetooth` to skip prompts.
- `cli/sensor_reliability_report.py` – display the reliability weights used when fusing sensor scores.
  - `cli/coanalysis_report.py` – generate a point cloud from an image, compare it with sensor detections (LIDAR and optional Bluetooth logs), and list fused matches; optional `--export` saves the image point cloud to CSV for training.
- `cli/export_geojson.py` – save recent detections to a GeoJSON file for GIS tools.

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
    --troop-model troop_model.h5 --target-model target_model.h5 --classify
python -m app.utils.troop_training_cli images/train troop_model.h5 --csv troop_labels.csv
python -m app.utils.human_feedback_viewer images/train predictions.csv feedback.csv
python -m app.cli.report --area kyiv --limit 100  # summarize recent detections
python -m app.cli.coanalysis_report --image sample.jpg --pointcloud sample.pcd --bluetooth bt.csv --export sample_points.csv
python -m app.cli.train_sensor --images image_dir --labels labels.csv --out pc_model.joblib
python -m app.cli.train_sensor_pointcloud --csv sensors.csv --images image_dir --out spc_model.joblib
python -m app.cli.anomaly_report  # list detection anomalies
python -m app.cli.trend_report  # show detection trends
python -m app.cli.activity_report  # show hourly detection activity
python -m app.cli.weekly_report  # show weekly detection activity
python -m app.cli.volatility_report  # show detection volatility
python -m app.cli.speed_report  # show speed anomalies
python -m app.cli.acceleration_report --hours 12 --z 2.5  # show acceleration anomalies
python -m app.cli.interarrival_report  # show time between detections
python -m app.cli.changepoint_report  # detect daily count shifts
python -m app.cli.peak_report  # show peak detection times
python -m app.cli.streak_report  # show detection streaks
python -m app.cli.cooccurrence_report  # show class co-occurrence matrix
python -m app.cli.burst_report  # list detection bursts
python -m app.cli.lag_report  # show lagged class correlations
 python -m app.cli.coanalysis_report --image sample.jpg --pointcloud sample.pcd --bluetooth bt.csv  # fuse detections
 python -m app.cli.train_sensor --dir sensor_csvs  # train classifiers for all CSVs
python -m app.cli.diversity_report  # show class diversity
python -m app.cli.fusion_report --image sample.jpg --pointcloud sample.pcd --bluetooth bt.csv  # fuse camera, LIDAR, and Bluetooth detections for troops, vehicles, and drones
python -m app.cli.generate_demo_data  # create a demo dataset
  python -m app.analysis.confidence_calibrator feedback.csv calib.npz
  python -m app.analysis.dbscan_cluster UNIT123 --hours 48
  python -m app.analysis.heatmap kyiv --start 2024-05-01 --end 2024-05-02 -o kyiv_heatmap.png
python -m app.analysis.uncertainty_heatmap kyiv --threshold 0.7 -o kyiv_uncertainty.png
python -m app.analysis.geo_mapper kyiv --start 2024-05-01 --end 2024-05-02 -o kyiv_map.html
python -m app.cli.export_geojson --area kyiv -o kyiv.geojson
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
  python -m app.analysis.change_point --days 30 --z 2.0
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
  python -m app.cli.train_wizard --train-dir data/train/images --val-dir data/val/images \
      --classes troop vehicle --out-model model.pt --epochs 25 --augment --n-aug 3
  python -m app.cli.train_vit_identifier --images sample1.jpg sample2.jpg --labels troop vehicle
  python -m app.cli.clip_classify sample.jpg troop vehicle drone
  python -m app.cli.train_orb_bow --images img1.jpg img2.jpg --labels troop vehicle --out orb_model.pkl
  python -m app.cli.orb_bow_report --image test.jpg --model orb_model.pkl
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
2. **Verify dataset**: Run `training.verify_dataset` to ensure each image has a
   matching label file before training.
3. **Create data configuration**: Use `training/dataset_loader.py` to generate
   the `data.yaml` file required by the Ultralytics trainer.
4. **Train the detector**: For a guided experience run
   `cli/train_wizard.py`, which prompts for paths and class names and handles
   optional augmentation. You can also pass flags like `--train-dir`,
   `--val-dir`, `--classes`, `--out-model`, `--epochs`, `--augment/--no-augment`,
   and `--n-aug` to skip prompts. Advanced users can call
   `training/train_yolo.py` directly or use `training/train_with_augmentation.py`
   to generate augmented copies before training. Optional flags let you tune
   batch size, image resolution and learning rate.
5. **Hyperparameter search**: Evaluate batches, learning rates and image sizes
   with `training.hyperparameter_search` to find the best combination.
6. **Sequential training**: For very large datasets you can train in batches
   using `training/train_sequential_yolo.py` and a list of `data.yaml` files.
   Each YAML is trained for the specified epochs before moving to the next to
   conserve GPU memory.
7. **Self-reinforcement**: Use `utils.pseudo_labeler` followed by the
   `cli.self_reinforce` script to automatically label new images, merge them into
   the dataset and retrain the model.
8. **Iterative self-training**: Run `training.self_training_loop` to repeat
   labeling and retraining for multiple cycles.
9. **Augmented self-training**: Use `training.self_training_aug` to add dataset
   augmentation during each reinforcement step.
10. **Active learning**: Run `training.active_learning` to review low-confidence
   detections with the feedback GUI before retraining.
11. **Deploy**: Copy the resulting `.pt` model into the pipeline and update the
    detection wrapper to load it instead of the stub.
12. **Threat classifier training**: Use `training.threat_model_trainer` with
    labeled cluster features to learn a model that predicts risk levels
    automatically.

## Documentation

See [MODEL_CARD.md](MODEL_CARD.md) for data sources, evaluation metrics, and
intended use. Operational procedures and alert handling are described in
[OPS_RUNBOOK.md](OPS_RUNBOOK.md).
