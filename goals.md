1. Compile historical and recent troop movement data.
2. Build a machine vision pipeline to parse satellite imagery.
3. Train an RNN/LSTM model to recognize movement patterns.
4. Highlight differences between modern and Soviet-era tactics.
5. Create tools to visualize predictions and track changes over time.
6. Integrate OSINT feeds and satellite imagery for comprehensive datasets.
7. Automate periodic model retraining as new data is ingested.
8. Provide interactive maps and alerting for real-time troop monitoring.
9. Deploy a FastAPI server for real-time prediction queries.
10. Maintain a MongoDB database for troop data and predictions.
11. Train YOLO models for vehicle detection from satellite imagery.
12. Provide hooks for secure real-time satellite feeds.
13. Automate the full data ingestion and prediction cycle with a pipeline script.

14. Automate dataset preprocessing and augmentation for YOLO training.
15. Watch directories for new satellite images and process them automatically.
16. Use Transformers and GNNs for feature refinement and anomaly scoring.
17. Cluster logged movements to predict trajectories and identify new tactics.
18. Classify BTG patterns by era and highlight doctrine shifts.
19. Develop an ASP.NET web interface connected to FastAPI for live dashboards.
20. Secure the system with multi-tier intranet communication and packet sanitization.
21. Generate battlefield heatmaps from logged movements.
22. Track cluster behavior and compute threat scores for early alerts.
23. Expand doctrine library with dynamic JSON patterns.
24. Automate OSINT image scraping and dataset organization for Russian units.
25. Train dedicated YOLO models for vehicles and troops with sequential training support.
26. Implement a script to train YOLO sequentially across multiple data.yaml files for memory efficiency.
27. Verify images and labels automatically before each training cycle. (done)
28. Log uncertain detections and allow human review without altering data.
29. Provide a simple GUI to record whether predictions are correct.
30. Monitor directories for new images and process them with anomaly scoring.
31. Combine YOLO detections with Transformer refinement and confidence blending.
32. Plot live detections on interactive maps and record confidence over time.
33. Research graph-based transformers, diffusion models and secure cloud deployment for scalable prediction services.
34. Integrate real-time satellite imagery using Sentinel Hub API.
35. Implement a QUIC-enabled Rust backend for secure data ingestion.
36. Provide start scripts to automate MongoDB startup, YOLO training and detection.
37. Build a pipeline that fetches, processes and predicts troop movements automatically.
38. Explore partnerships with cybersecurity groups like Disbalancer and Hacken.
39. Offer a user-friendly mobile or PC app delivering early warning alerts.
40. Summarize detection activity by weekday to reveal weekly patterns.
40. Analyze detection confidence distributions to highlight weak classes.
41. Provide on-the-fly UI translation using a neural translation model.
40. Fuse color histograms, HOG features and edge density for stronger troop, vehicle and drone identification.
40. Use eBPF and Scapy for inline packet inspection and sandboxed database policies.
41. Deploy Rust services with QUIC and WebAssembly modules for resilient maritime comms.
42. Add LIDAR-based detection for troops, vehicles, and drones and fuse camera and LIDAR outputs.
43. Run unsupervised detection for new movement patterns and deviations.
44. Coordinate with Brave1 and CIDT for potential field testing and government integration.
45. Deploy a YOLO inference wrapper that tags doctrine before logging. (done)
46. Update Mongo schema and backend structs with a doctrine field. (done)
47. Train the BTGTransformer on normalized movement sequences.
48. Detect deviations between predicted and actual movements with DBSCAN tagging.
49. Ingest live OSINT movement files through this pipeline.
49. Build a GUI map overlay after base functionality is stable.
50. Track unit identities over time for per-unit trajectory prediction and anomaly detection.
51. Provide a CLI to run the satellite inference pipeline for a chosen area.
52. Use environment variables to configure Sentinel Hub credentials.
53. Monitor areas continuously by periodically downloading imagery and running predictions.
54. Improve troop identification from angled or low-quality images.
55. Support live drone video streams for immediate detection.
56. Aggregate detection and feedback statistics with a meta analysis module.
56. Classify detected troops by type and uniform.
57. Identify drone models from live footage.
58. Build a simple CLI to label troop photos and train a classifier using a directory or CSV file.
59. Generate YOLO `data.yaml` files with `training/dataset_loader.py`.
60. Train detection models via `training/train_yolo.py` and integrate into the pipeline.
61. Cluster movement logs with DBSCAN using analysis/dbscan_cluster.py.
62. Provide an interactive CLI dashboard using Rich for common tasks.
63. Log detections with movement_logger.py for later analysis.
64. Score cluster threats using analysis/threat_assessment.py.
65. Encode detection density into grid tensors with analysis/state_encoder.py.
66. Classify vehicles from drone and satellite images.
67. Provide an interactive setup CLI to write environment variables into a .env file.
68. Auto-label new images, merge them into the dataset and retrain models via the self_reinforce CLI.
69. Analyze image brightness and blur levels with analysis/image_stats.py to prioritize augmentation.
70. Calculate unit speed and heading statistics with analysis/movement_stats.py.
71. Extract HOG descriptors from training images using analysis/hog_features.py.
72. Automate augmentation and training via training/train_with_augmentation.py.
73. Repeat pseudo labeling and retraining with training/self_training_loop.py.
74. Render unit, group, and battalion doctrine drilldowns together so operators can review all levels in a single report.
74. Fuse multiple classifiers into an ensemble for higher-confidence predictions.
74. Develop a unified classifier covering troops, vehicles, and drones for operator-labelled targets.
74. Mark LIDAR detections with in-cover vs exposed flags and surface them in fusion reports.
74. Mix Gaussian estimates with a PointNet-style embedding to classify fused point clouds.
74. Combine self-training with automatic augmentation using training/self_training_aug.py.
75. Integrate human-in-the-loop active learning via training/active_learning.py.
76. Capture periodic frames from webcams or videos using camera_collector.py for dataset expansion.
77. Store human feedback decisions in MongoDB for future retraining.
78. Calibrate detector confidence using isotonic regression with analysis/confidence_calibrator.py.
79. Provide a prompt-based training wizard CLI to simplify YOLO model training.
80. Automate dataset splitting, augmentation, and training with training/auto_dataset_trainer.py.
81. Extend the operator dashboard with training, self-reinforcement and configuration options.
82. Translate CLI prompts and GUI labels based on the `UI_LANG` setting.
83. Correlate detection and classification outputs into a fused confidence score.
84. Expand the dashboard with drone feed streaming and camera capture options.
85. Provide a CLI to summarize recent detections for quick operator reports.
86. Add a Responsible Use policy and defer licensing decisions to Ukrainian authorities.
87. Enforce authentication, TLS, audit logging, rate limits, and geofenced access; disable anonymous endpoints.
88. Output detection confidence and uncertainty by default and provide blurred or aggregated heatmaps for external sharing. (done)
89. Offer an offline synthetic demo and dataset for end-to-end testing without live feeds. (done)
90. Pin dependencies and mirror packages offline, provide secret scanning, ship a .env.example, and support Docker/Compose deployment. (.env.example added)
91. Publish a Model Card and operational runbook describing data sources, evaluations, and alert handling. (done)
92. Run a hyperparameter search over batch size, learning rate, and image size to tune YOLO training.
93. Provide a browser-based GUI at `/gui` for querying detections and predictions.
94. Expand the operator dashboard with detection map, meta analysis, and movement statistics options.
95. Add a dedicated training page in the operator dashboard for self-reinforcement and advanced training utilities.
96. Provide a map page in the operator dashboard to visualize troop positions and access analysis tools like heatmaps, clustering, meta analysis, and movement statistics.
97. Allow selecting start/end dates for map and analysis tools in the operator dashboard.
98. Score clustered movements with a threat assessment feature in the dashboard.
99. Enrich threat scoring with nearest strategic site, approach direction and categorical levels.
100. Forecast short-term movement using a constant-velocity Kalman predictor.
101. Incorporate site-specific weighting and ETA estimates in threat assessment. (done)
102. Train a classifier on cluster features to predict threat levels automatically.
103. Automatically discover new imagery input sources using a ChatGPT-powered background thread.
104. Persist discovered imagery sources in a JSON catalog and verify accessibility.
105. Provide a help screen in the operator dashboard summarizing available tasks.
106. Allow switching the UI language from the dashboard without restarting.
107. Display current configuration settings from the operator dashboard.
108. Allow dashboard language selection via a `--lang` command-line flag. (done)
109. Provide a Ukrainian-language README for operators. (done)
110. Seed a built-in space imagery catalog and CLI for Russian troops, tanks, and Russian/Iranian drone identification drills.
110. Surface cross-method analysis cohesion by combining anomaly, burst, change-point, volatility, detection-streak, and interarrival outputs with a shared report and dashboard option, and allow extra analysis specs to be injected programmatically.
110. Detect anomalous spikes in detection counts via analysis/anomaly_detector.py and the anomaly_report CLI.
111. Summarize detection trends over time with detection_trends.py and the trend_report CLI. (done)
112. Analyze class co-occurrence patterns using analysis/cooccurrence.py and the cooccurrence_report CLI.
113. Detect bursty activity by z-scoring time buckets via analysis/burst_detector.py and the burst_report CLI.
114. Measure time-lag correlations between classes using analysis/lag_correlation.py and the lag_report CLI.
115. Summarize hourly detection activity using analysis/hourly_activity.py and the activity_report CLI.
116. Smooth daily detection counts with analysis/moving_average.py and view them via the moving_report CLI.
117. Measure detection volatility with analysis/detection_volatility.py and view it via the volatility_report CLI.
118. Compute average and median time between detections with analysis/interarrival.py and interarrival_report CLI.
119. Identify peak detection hours and weekdays using analysis/peak_times.py and the peak_report CLI.
120. Detect daily count change points via analysis/change_point.py and the changepoint_report CLI.
121. Measure detection class diversity via analysis/class_diversity.py and the diversity_report CLI.
122. Flag anomalous unit speeds via analysis/speed_anomaly.py and the speed_report CLI.
123. Flag anomalous unit accelerations via analysis/acceleration_anomaly.py and the acceleration_report CLI.
124. Provide image-based detection for troops, vehicles, and drones via camera_detector.py and fuse with LIDAR results.
125. Expose `detect_fused_objects` to run both camera and LIDAR detectors for all classes.
126. Accept `--image` and `--pointcloud` flags in fusion_report for direct file inputs. (done)
127. Allow specifying training paths, classes, epochs, and augmentation via CLI flags in train_wizard. (done)
128. Add `--area` and `--limit` flags to the detection report CLI for non-interactive summaries.
129. Add `--hours` and `--z` flags to the acceleration_report CLI for non-interactive runs.
130. Pin dependencies and verify package integrity; maintain offline mirrors so seized infrastructure can't weaponize dependency downloads.
131. Automatically install GPU packages after CPU dependencies when a GPU is detected in scripts/setup.sh.
132. Export recent detections to GeoJSON for GIS integration via analysis/geojson_export.py and the export_geojson CLI.
133. Compute longest detection streaks per class with analysis/detection_streaks.py and the streak_report CLI.
134. Automate sensor classifier training via training/sensor_auto_trainer.py and the train_sensor CLI.
135. Cross-check image and point cloud detections with analysis/pointcloud_coanalysis.py and the coanalysis_report CLI.
136. Train sensor models for all CSV files in a directory via `train_sensor --dir`.
137. Run coanalysis_report on raw image and point cloud files, fusing detections without intermediate JSON.
138. Generate point clouds from images with analysis/image_pointcloud.py for sensor matching.
139. Train sensor classifiers from image-derived point clouds via `train_sensor --images` and `--labels`.
140. Export image point clouds to CSV from coanalysis_report using `--export`.
141. Fuse Bluetooth RSSI detections with camera and LIDAR data via bluetooth_detector.py, fusion_report, and coanalysis_report.
142. Generate 3D point clouds from images including intensity for richer sensor matching.
143. Train fused sensor models combining sensor CSV features with image-derived point clouds via sensor_pointcloud_trainer and train_sensor_pointcloud CLI.
144. Add dashboard shortcuts for coanalysis reports and sensor pointcloud training to improve operator workflows.
145. Identify entities by fitting Gaussians to labeled point clouds and matching fused image/sensor clouds against them.
146. Rank Gaussian matches with probabilities and list top candidates via `gaussian_match_report --top`.
147. Incrementally update Gaussian models with new point-cloud data via `gaussian_pointcloud_update.py` and `update_gaussian_model` CLI.
148. Weight sensor confidences with configurable reliability factors using `fuse_sensor_confidences` in analysis/sensor_certainty.py, applying them in sensor_fusion.py and exposing weights through the sensor_reliability_report CLI.
149. Fit Gaussian mixture models for multi-modal sensor features via `gaussian_mixture_trainer.py` and review matches with `gaussian_mixture_report`.
150. Convert acoustic feature logs into detections and train an acoustic classifier via `acoustic_trainer.py` and the `train_acoustic` CLI.
151. Train and deploy a ResNet-based image classifier with `train_resnet_identifier` and classify images via `resnet_classify`.
151. Train fused Gaussian models from image and sensor point clouds via `train_fused_gaussian.py` and match with `fused_gaussian_report`.
152. Provide a Gaussian Naive Bayes classifier for fused image and sensor point clouds with `train_gaussian_nb.py` and `gaussian_nb_report`.
153. Experiment with Gaussian KDE fusion by training via `train_gaussian_kde.py` and reporting matches with `gaussian_kde_report`.
154. Train Gaussian Process classifiers from fused image and sensor point clouds via `train_gaussian_process.py` and review probabilities with `gaussian_process_report`.
155. Register training items with unique identifiers via `item_catalog` and list them sorted by classifier.
156. Store confidence scores for each training image in the item catalog. (done)
157. Allow analysts to append new target labels to the unified classifier by adding output neurons via `extend_unified_model.py`.
158. Classify targets with Vision Transformer embeddings via `vit_identifier.py` and train models using `train_vit_identifier.py`.
159. Perform zero-shot image classification with CLIP via `clip_identifier.py` and `clip_classify` CLI.
160. Classify images with an ORB bag-of-visual-words model via `orb_bow_trainer.py` and report matches with `orb_bow_report`.
161. Classify targets with Swin Transformer embeddings via `swin_identifier.py`; train models using `train_swin_identifier.py` and run predictions with `swin_classify.py`.
162. Classify targets with ConvNeXt embeddings via `convnext_identifier.py`; train with `train_convnext_identifier.py` and classify with `convnext_classify.py`.
163. Analyze correlation between model confidences using `prediction_correlation.py` and `prediction_correlation_report.py`.
164. Classify images using fused color, Lab, HOG, texture, and edge features via `feature_fused_identifier.py` and `train_feature_fused_identifier` CLI.
165. Measure classifier consensus using `cohesion_analyzer.py` and display results with the `cohesion_report` CLI.
166. Compute confidence-weighted consensus in `cohesion_analyzer.py` and surface it through `cohesion_report`.
167. Expose acceleration, speed, diversity, streak, volatility, activity, interarrival, trend, and peak-time reports via an analysis submenu in the operator dashboard.
168. Expose anomaly, burst, change-point, co-occurrence, lag-correlation, moving-average, and weekly-activity reports in the dashboard analysis submenu.
169. Integrate imagery source discovery and catalog listing into the operator dashboard.
170. Provide a confidence-summary report and expose it through the dashboard analysis submenu.
171. Add prediction-correlation and sensor-reliability reports to the dashboard analysis submenu.
172. Offer uncertainty heatmap generation and GeoJSON export from the dashboard map tools.
173. Provide dataset verification and demo data generation options in the dashboard training menu.
174. Add a confidence calibration option to the dashboard training menu so feedback CSVs can tune detector certainty.
175. Support a `RESOLUTION_SCALE` setting to produce higher-resolution point clouds and image features on capable systems.
176. Allow a `FEATURE_RICHNESS` setting to boost histogram bins, HOG detail, and point-cloud density for high-memory analysis.
177. Provide a `HIGH_MEMORY_MODE` switch that unlocks multi-scale histograms, multi-resolution HOG, LBP textures, Lab histograms, Gabor responses, Fourier coefficients, GLCM metrics, augmented-view histograms, Hu moments, channel covariance summaries, wavelet energies, Lab grid stats, EfficientNet embeddings, and sub-pixel point clouds for ultra-rich analysis on top-tier hardware.
178. Add an OBIEE-style object drilldown with per-object average speeds and optional Twilio SMS alerts to the operator dashboard.
179. Provide doctrine-aware, time-bucketed movement drilldowns for units, groups, and battalions via CLI and dashboard reports.
