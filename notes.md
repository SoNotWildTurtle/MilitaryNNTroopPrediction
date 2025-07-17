This project explores Russian troop movements using a neural network.
The goal is to compare modern activity with Soviet-era patterns by training on historical and current data. Initial discussions outlined the following process:
- Gather data from archives, satellite images and OSINT sources.
- Clean and normalize troop data.
- Engineer features (movement speed, routes, logistics, etc.).
- Train an RNN/LSTM model to detect trends and significant tactical shifts.

- Expand dataset using OSINT sources with geospatial context and troop morale info.
- Use satellite imagery from providers such as Maxar and Planet Labs, processing with CNNs for asset detection.
- Fuse imagery features with movement records to improve predictions.

- Store parsed troop data in MongoDB for geospatial queries and predictions.
- Build a FastAPI service to expose latest movements and model predictions.
- Apply YOLO-based machine vision to satellite images for troop and vehicle detection.
- Provide hooks for secure real-time satellite APIs so cleared users can feed classified imagery.

- Automated dataset preprocessing and YOLO training pipeline with augmentation.
- Public satellite data sources include NASA, Sentinel-2, Landsat and Maxar; integrate government feeds when possible.
- OSINT data from DeepStateMap, ACLED, LiveUAmap and GDELT enrich movement history.
- Unsupervised clustering and Transformer/GNN models help identify emerging tactics.
- Secure deployment relies on containerized services and intranet packet sanitization following the Alien Marketplace approach.
- Movement logs are clustered with DBSCAN and visualized on heatmaps
  using `analysis/dbscan_cluster.py`. The companion `analysis/heatmap.py`
  script renders detection coordinates as PNG overlays for quick review.
- state_encoder.py builds a grid tensor from recent detections to visualize density over time and feed models.
- cluster_strategy_tracker.py monitors macro behavior and threat_assessment.py scores potential danger levels.
- Trajectory prediction uses doctrine sequences with LSTM/Transformer models to forecast next moves.
- doctrine_matcher and emerging_tactic_detector compare live sequences to era-tagged patterns and flag new tactics.
- An ASP.NET dashboard displays maps and doctrine status via FastAPI bridging.
- Research recommends hypergraph Transformers and secure cloud deployment for multi-agent prediction.
- Scripts automate building a Russian military dataset, organizing categories and training YOLO models.
- Detection results are stored in MongoDB and can be refined with a Transformer-based feature module.
- Similarity checks and anomaly logs support human verification without moving images.
- human_feedback_viewer.py lets analysts confirm detections via a simple GUI before logging feedback.
- watch_directory.py processes new images automatically for continuous analysis.
- Test-time augmentation and confidence logging monitor model drift.
- geo_mapper.py plots troop detections on interactive maps and saves an HTML file for review.
- Research notes outline graph and diffusion models, curriculum and contrastive learning, and secure cloud MLOps.

- setup.sh and start.bat scripts install dependencies, create dataset folders and run the pipeline automatically.
- start.sh starts MongoDB, preprocesses the dataset, trains YOLO models, launches FastAPI and begins satellite detection.
- dataset_augmentation.py uses Albumentations to expand training images.
- enhanced_image_processing.py sharpens satellite images for more reliable detection.
- troop_transformer.py implements an attention-based model predicting future coordinates.
- run_real_time_pipeline.py fetches satellite images, runs detection and transformer prediction in one loop.
- Secure network design uses multi-tier segmentation, packet scrubbing with Scapy or eBPF, sandboxed database access and zero-trust authentication.
- Cybersecurity partnerships were identified with Disbalancer and Hacken along with Ukrainian programs Brave1 and the Center for Innovation and Development of Defense Technologies.
- Recommended stack for maritime systems includes Rust with QUIC transport, WebAssembly modules, eBPF monitoring and DevSecOps pipelines.
- Comprehensive requirements outline a seven-phase roadmap covering infrastructure setup, machine vision training, trajectory prediction, sensor fusion, edge deployment, secure communications, web dashboard and field testing.
- Planned features include LIDAR-based drone detection and a mobile/desktop alert application for civilians.

- Tactical wrapper standardizes YOLO results, attaches a doctrine tag and posts to the backend.
- MongoDB schema updated with a doctrine field per image.
- BTGTrajectoryDataset builds relative movement sequences for the BTGTransformer model.
- Deviation detection compares predicted vs actual positions, logging anomalies and clustering unknown patterns with DBSCAN.

- Satellite imagery is retrieved via Sentinel Hub WMS using OAuth tokens and a bounding box over areas of interest.
- satellite_inference_pipeline.py downloads the image, runs YOLO, tags doctrine and sends metadata to the backend.
- movement_history.py pulls recent coordinates from Mongo so trajectory_prediction.py can forecast the next grid point.
- Anomaly detection triggers if predicted paths diverge from doctrine, enabling early alerts.
- A cross-platform alert app and LIDAR drone detection remain long-term priorities.
- satellite_inference_pipeline.py downloads Sentinel images and runs YOLO detection for doctrine tagging.
Detections and trajectory predictions are stored in MongoDB for later analysis.
The Sentinel Hub integration uses OAuth credentials supplied via environment
variables. Without them, the pipeline falls back to placeholder images.
Dataset augmentation utilities rely on Albumentations for generating additional
training data, and `watch_directory.py` monitors incoming image folders to run
the pipeline automatically.
Ground troop imagery can be difficult due to oblique angles and low quality, so
`ground_troop.py` preprocesses images and rotates them before running YOLO.
`drones/live_feed.py` captures video frames from UAVs and streams them through
the same pipeline for real-time situational awareness.
`troop_identifier.py` classifies detected troops by type and uniform, while
`drone_identifier.py` labels UAV models during live feeds.
`vehicle_identifier.py` categorizes vehicles detected in imagery.
`troop_training_cli.py` helps organize labeled troop images and train a simple classifier from command line inputs or a CSV file.
`cli/dashboard.py` provides a Rich-powered command line menu to run the pipeline, generate heatmaps and launch the feedback GUI.
`training/dataset_loader.py` creates a `data.yaml` file to configure YOLO training datasets.
`training/train_yolo.py` runs the Ultralytics training loop and exports a `.pt` model.
- movement_logger.py saves detection records for later clustering.
- cluster_strategy_tracker.py clusters movements and draws heatmaps.
- threat_assessment.py assigns a basic score based on proximity to strategic sites.
