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
26. Verify images and labels automatically before each training cycle.
27. Log uncertain detections and allow human review without altering data.
28. Provide a simple GUI to record whether predictions are correct.
29. Monitor directories for new images and process them with anomaly scoring.
30. Combine YOLO detections with Transformer refinement and confidence blending.
31. Plot live detections on interactive maps and record confidence over time.
32. Research graph-based transformers, diffusion models and secure cloud deployment for scalable prediction services.
33. Integrate real-time satellite imagery using Sentinel Hub API.
34. Implement a QUIC-enabled Rust backend for secure data ingestion.
35. Provide start scripts to automate MongoDB startup, YOLO training and detection.
36. Build a pipeline that fetches, processes and predicts troop movements automatically.
37. Explore partnerships with cybersecurity groups like Disbalancer and Hacken.
38. Offer a user-friendly mobile or PC app delivering early warning alerts.
39. Use eBPF and Scapy for inline packet inspection and sandboxed database policies.
40. Deploy Rust services with QUIC and WebAssembly modules for resilient maritime comms.
41. Add LIDAR-based drone detection for ground and satellite sensors.
42. Run unsupervised detection for new movement patterns and deviations.
43. Coordinate with Brave1 and CIDT for potential field testing and government integration.
44. Deploy a YOLO inference wrapper that tags doctrine before logging.
45. Update Mongo schema and backend structs with a doctrine field.
46. Train the BTGTransformer on normalized movement sequences.
47. Detect deviations between predicted and actual movements with DBSCAN tagging.
48. Ingest live OSINT movement files through this pipeline.
49. Build a GUI map overlay after base functionality is stable.
50. Track unit identities over time for per-unit trajectory prediction and anomaly detection.
51. Provide a CLI to run the satellite inference pipeline for a chosen area.
52. Use environment variables to configure Sentinel Hub credentials.
53. Monitor areas continuously by periodically downloading imagery and running predictions.
54. Improve troop identification from angled or low-quality images.
55. Support live drone video streams for immediate detection.
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
