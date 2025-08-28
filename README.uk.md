# Визначення пересування військ за допомогою нейронних мереж

[Read in English](README.md)

Цей репозиторій містить базову реалізацію застосунку машинного зору, що прогнозує пересування військ на основі супутникових зображень та даних OSINT.

## Структура
- `app/` – Python-пакет із основними модулями
  - `config.py` – налаштування конфігурації
  - `database.py` – допоміжні функції для MongoDB
  - `data_ingestion.py` – отримання OSINT та супутникових даних
  - `detection/` – обгортки над YOLO
  - `models/` – моделі для прогнозування траєкторій
  - `pipeline/` – сценарії, що поєднують отримання, виявлення та прогнозування
  - `api/` – ендпоінти FastAPI
- `scripts/` – скрипти встановлення та запуску
- `notes.md` – проектні нотатки
- `dev_notes.md` – технічні нотатки
- `goals.md` – дорожня карта
- `MODEL_CARD.md` – опис моделі та сфера застосування
- `OPS_RUNBOOK.md` – процедурні інструкції та обробка тривог

## Використання
Запустіть `scripts/start.sh`, щоб встановити залежності та підняти API:

```bash
bash scripts/start.sh
```

Встановіть `UI_LANG` або використайте ключ `--lang` (наприклад, `--lang uk`), щоб перекласти текст панелі для українських операторів під час запуску інтерактивних CLI.

Після запуску сервер доступний за адресою `http://localhost:8000` з такими ендпоінтами:

- `POST /predict/{area}` – запуск виявлення та прогнозу для області
- `GET /detections/{area}?limit=10` – отримання останніх виявлень
- `GET /predictions/{area}?limit=10` – отримання прогнозів траєкторій

Працюючий сервер також надає мінімальний веб-інтерфейс за шляхом `/gui/`. Відкрийте `http://localhost:8000/gui/` у браузері, щоб переглядати виявлення та прогнози без командного рядка.

Додаткові модулі обробляють знімки Sentinel Hub та CLI-сценарії:
- `satellite/` – завантаження зображень Sentinel та конвеєр інференсу
  - `movement_history.py` – запити до MongoDB щодо останніх позицій підрозділів
  - `pipeline/run_real_time_pipeline.py` – CLI для отримання зображень та запуску виявлення
  - `pipeline/realtime.py` – збереження виявлень і прогнозів у MongoDB
  - `detection/ground_troop.py` – покращене виявлення наземних військ на складних зображеннях
  - `drones/live_feed.py` – обробка відео з дронів у реальному часі
  Результати виявлення містять поле `doctrine` і зберігаються у колекції `detections`. Прогнози траєкторій зберігаються у `predictions`.

Крок злиття впевненостей об’єднує оцінки детектора з класифікаторами військ, дронів і техніки для підвищення довіри до кожного визначення.

## Середовище
Конвеєр може отримувати зображення з Sentinel Hub. Перед запуском встановіть такі змінні середовища:

```
export SENTINEL_CLIENT_ID="your-client-id"
export SENTINEL_CLIENT_SECRET="your-secret"
export SENTINEL_INSTANCE_ID="your-instance-id"
export OPENAI_API_KEY="your-openai-key"
export SOURCE_CATALOG="sources.json"
```

Якщо змінні не задані, будуть використані тестові зображення.

Файл `.env.example` містить список необхідних змінних; скопіюйте його в `.env` та налаштуйте значення для свого середовища.

Щоб запустити автономний конвеєр з командного рядка:

```bash
python -m app.pipeline.run_real_time_pipeline AREA path/to/model
```

## Утиліти

Кілька скриптів допомагають з підготовкою даних та автоматизацією:

- `utils/dataset_augmentation.py` – створення аугментованих зображень за допомогою Albumentations. Використання: `python -m app.utils.dataset_augmentation SRC DST -n 5`.
- `analysis/movement_predictor.py` – прогноз наступної позиції за допомогою фільтра Калмана з постійною швидкістю.
- `analysis/hog_features.py` – отримання дескрипторів HOG.
- `analysis/feature_fusion.py` – поєднання кольорових гістограм, HOG та густини країв для багатших ознак.
- `analysis/confidence_stats.py` – обчислення статистики впевненості за класами.
  - `analysis/confidence_calibrator.py` – калібрування впевненості детектора через ізотонну регресію.
  - `analysis/confidence_fusion.py` – злиття впевненостей детектора та класифікаторів.
  - `analysis/meta_analysis.py` – агреговані звіти щодо виявлень, точності відгуків та кластерів.
    - `analysis/cooccurrence.py` – підрахунок, як часто класи з’являються разом у події виявлення.
    - `analysis/burst_detector.py` – виявлення інтервалів з незвично високою кількістю виявлень.
    - `analysis/lag_correlation.py` – оцінка кореляції між класами з різними часовими зсувами.
- `analysis/interarrival.py` – обчислює середній та медіанний час між виявленнями для кожного класу.
- `analysis/peak_times.py` – визначає найактивнішу годину та день тижня для кожного класу.
- `analysis/change_point.py` – виявляє різкі зміни добових підрахунків за класами.
- `analysis/class_diversity.py` – обчислює ентропію розподілу класів за днями.
- `analysis/hourly_activity.py` – підрахунок виявлень за класами по годинах.
- `analysis/weekly_activity.py` – підрахунок виявлень за класами по днях тижня.
- `analysis/moving_average.py` – обчислення ковзних середніх щоденних виявлень для згладжування коливань.
- `analysis/speed_anomaly.py` – визначає підрозділи з аномальною середньою швидкістю.
    - `cli/dashboard.py` – інтерактивна панель для запуску конвеєрів, перегляду карт, навчання та звітів. Містить сторінки карти й тренування, може показувати довідку, конфігурацію, звіти та змінювати мову на льоту.
- `utils/pseudo_labeler.py` – створення YOLO-розмітки для нових зображень.
- `cli/self_reinforce.py` – розмітка нових зображень, об’єднання їх із датасетом та повторне навчання детектора.
- `cli/train_wizard.py` – майстер навчання YOLO з локалізованими підказками.
- `training/self_training_loop.py` – повторні цикли самопідкріплення.
- `training/self_training_aug.py` – самопідкріплення з аугментацією.
- `training/active_learning.py` – активне навчання з людським зворотним зв’язком.
- `translation/translator.py` – переклад тексту панелі заданою мовою.
- `cli/report.py` – підсумок останніх виявлень за класами та впевненістю.
- `cli/generate_demo_data.py` – створення синтетичного датасету.
- `cli/anomaly_report.py` – список аномалій виявлень.
- `cli/trend_report.py` – відображення тенденцій виявлень.
- `cli/moving_report.py` – показ ковзних середніх за класами.
- `cli/volatility_report.py` – показ коливань кількості виявлень.
- `cli/speed_report.py` – виявлення аномальних швидкостей підрозділів.
- `cli/interarrival_report.py` – показ середнього та медіанного часу між виявленнями.
- `cli/peak_report.py` – список пікової години та дня тижня для кожного класу.
- `cli/diversity_report.py` – показ різноманітності класів виявлень.
- `cli/activity_report.py` – активність за годинами для кожного класу.
- `cli/weekly_report.py` – активність за днями тижня.
- `cli/cooccurrence_report.py` – матриця спільної появи класів.
- `cli/burst_report.py` – інтервали підвищеної активності.
- `cli/lag_report.py` – кореляції зі зсувом у часі.

Приклади використання:

```bash
python -m app.cli.dashboard
python -m app.cli.configure  # створення або оновлення файлу .env
python -m app.utils.dataset_augmentation images/raw images/augmented -n 5
python -m app.info_gathering.camera_collector 0 collected_frames --interval 2
python -m app.cli.discover_sources "List public drone video feeds" --verify
python -m app.watch_directory data/sentinel path/to/model kyiv
python -m app.pipeline.monitor kyiv models/trajectory.h5 --interval 600
python -m app.drones.live_feed 0 --model models/trajectory.h5 \
    --troop-model troop_model.h5 --classify-drones --classify-vehicles
python -m app.utils.troop_training_cli images/train troop_model.h5 --csv troop_labels.csv
python -m app.utils.human_feedback_viewer images/train predictions.csv feedback.csv
python -m app.cli.report
python -m app.cli.anomaly_report
python -m app.cli.trend_report
python -m app.cli.activity_report
python -m app.cli.weekly_report
python -m app.cli.volatility_report
python -m app.cli.speed_report
python -m app.cli.interarrival_report
python -m app.cli.changepoint_report
python -m app.cli.peak_report
python -m app.cli.cooccurrence_report
python -m app.cli.burst_report
python -m app.cli.lag_report
python -m app.cli.diversity_report
python -m app.cli.generate_demo_data
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
python -m app.analysis.change_point --days 30 --z 2.0
python -m app.cli.dashboard --lang uk  # запуск панелі українською
python -m app.analysis.threat_assessment "[{\"center\": [30.5, 50.4], \"count\": 5, \"avg_speed\": 40, \"heading\": 90}]"
python -m app.detection.tactical_wrapper sample.jpg
python -m app.training.dataset_loader /data/train/images /data/val/images \
    --classes troop vehicle -o data.yaml
python -m app.training.train_yolo /data/train/images /data/val/images yolo_model.pt \
    --classes troop vehicle --epochs 50
python -m app.training.train_with_augmentation /data/train/images /data/val/images yolo_aug.pt \
    --classes troop vehicle --n-aug 5 --epochs 50
python -m app.training.train_sequential_yolo dataset1.yaml dataset2.yaml yolo_model.pt \
    --classes troop vehicle --epochs 50
```
