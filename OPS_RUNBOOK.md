# Operations Runbook

## Purpose
Guide analysts through setup, monitoring, and alert handling for the troop
prediction system.

## Setup
1. `bash scripts/start.sh` installs dependencies and launches the API.
2. Run `python -m app.cli.configure` to generate a `.env` file with Sentinel and
   MongoDB credentials.
3. Ensure `mongod` and `uvicorn` are running before accepting data.
4. Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` to
   `.env` when SMS alerts should be available from the dashboard.

## Monitoring
- Use `python -m app.cli.dashboard` for a translated menu of common tasks.
- Generate heatmaps with `python -m app.analysis.heatmap AREA` to visualize
  activity.
- View interactive maps at `/gui/` when the server is running.

## Alert Handling
1. Detections and predictions are stored in MongoDB.
2. `analysis/threat_assessment.py` assigns basic threat scores; review clusters
   flagged as high.
3. Confirm detections through the feedback GUI and log decisions for retraining.
4. Use the dashboard's “Object drilldown & alerts” option to aggregate object
   speeds and, when Twilio is configured, push SMS summaries to duty phones.

## Security
- `scripts/start.sh` downloads dependencies; verify package hashes or use trusted mirrors to prevent supply-chain attacks if infrastructure is compromised.

## Troubleshooting
- Rerun `scripts/start.sh` if dependencies are missing.
- Check environment variables in `.env` when Sentinel downloads fail.
- Inspect server logs for authentication or database errors.
