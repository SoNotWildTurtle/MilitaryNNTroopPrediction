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

Оскільки під час цього кроку завантажуються пакети, перевіряйте їхні хеші або використовуйте внутрішні дзеркала, щоб уникнути атак ланцюга постачання у разі захоплення інфраструктури.

Скрипт спочатку встановлює залежності для CPU. Якщо виявлено GPU, після цього автоматично завантажуються пакети з підтримкою CUDA, такі як PyTorch і повний TensorFlow.

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
    - `detection/lidar_detector.py` – виявлення військ, техніки та дронів за LIDAR‑даними з позначкою укриття
    - `detection/camera_detector.py` – виявлення військ, техніки та дронів з камер
    - `detection/acoustic_detector.py` – перетворює журнали акустичних ознак у виявлення
    - `detection/sensor_fusion.py` – поєднання виявлень з камер і LIDAR; `detect_fused_objects` запускає обидва сенсори для піхоти, техніки та дронів
    - `detection/clip_identifier.py` – нульовий класифікатор зображень на основі CLIP
    - `detection/unified_identifier.py` – єдиний класифікатор для піхоти, техніки та дронів
    - `cli/extend_unified_model.py` – додає нову ціль до об'єднаного класифікатора, розширюючи вихідний шар за міткою оператора
    Результати виявлення містять поле `doctrine` і зберігаються у колекції `detections`. Прогнози траєкторій зберігаються у `predictions`.

Крок злиття впевненостей об’єднує оцінки детектора з класифікаторами військ, дронів і техніки для підвищення довіри до кожного визначення.
Модуль LIDAR забезпечує електромагнітне виявлення, позначає чи об'єкти під укриттям, а модуль злиття сенсорів поєднує результати камер і LIDAR для підвищення впевненості.
Злиття сенсорів тепер застосовує ваги надійності для камер, LIDAR і Bluetooth та повертає рівень невизначеності для кожного класу.

### Каталог об'єктів
Відстежуйте кожне навчальне зображення з його класом та оцінкою впевненості:

```bash
python -m app.cli.item_catalog --add ITEM_ID CLASS SCORE
python -m app.cli.item_catalog --list
```

Елементи зберігаються у CSV-файлі, щоб оператори могли впорядковувати їх за класом і переглядати впевненість моделі. `pseudo_labeler` автоматично реєструє кожне позначене зображення з його оцінкою.

### Розширення об'єднаного класифікатора
Збільшуйте модель, коли потрібно відстежувати новий клас:

```bash
python -m app.cli.extend_unified_model
```

CLI запитає шлях до збереженої моделі та нову мітку. Додається випадково ініціалізований нейрон, після чого модель можна донавчити на нових зображеннях.

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

- `detection/feature_fused_identifier.py` – класифікує зображення, поєднуючи кольорові гістограми, HOG та щільність країв; тренуйте модель через `python -m app.cli.train_feature_fused_identifier`, класифікуйте за допомогою `python -m app.cli.feature_fused_classify`.
- `detection/ensemble_identifier.py` – усереднює результати кількох класифікаторів для узгодженого прогнозу; запустіть `python -m app.cli.ensemble_classify`.
- `utils/dataset_augmentation.py` – створення аугментованих зображень за допомогою Albumentations. Використання: `python -m app.utils.dataset_augmentation SRC DST -n 5`.
- `analysis/movement_predictor.py` – прогноз наступної позиції за допомогою фільтра Калмана з постійною швидкістю.
- `analysis/hog_features.py` – отримання дескрипторів HOG.
- `analysis/feature_fusion.py` – поєднання кольорових гістограм, HOG та густини країв для багатших ознак.
- `analysis/prediction_correlation.py` – обчислює кореляцію між впевненостями моделей.
- `analysis/cohesion_analyzer.py` – вимірює узгодженість, консенсус і зважений за впевненістю консенсус між класифікаторами.
- `analysis/orb_bow_match.py` – класифікує зображення за допомогою моделі ORB bag-of-visual-words.
- `analysis/confidence_stats.py` – обчислення статистики впевненості за класами.
  - `analysis/confidence_calibrator.py` – калібрування впевненості детектора через ізотонну регресію.
  - `analysis/confidence_fusion.py` – злиття впевненостей детектора та класифікаторів.
  - `analysis/sensor_certainty.py` – `fuse_sensor_confidences` виконує зважене об’єднання впевненостей сенсорів і оцінку невизначеності.
  - `analysis/meta_analysis.py` – агреговані звіти щодо виявлень, точності відгуків та кластерів.
  - `detection/vit_identifier.py` – класифікація військ, техніки та дронів за ознаками ViT; тренування: `python -m app.cli.train_vit_identifier`.
  - `detection/resnet_identifier.py` – класифікує цілі за ознаками ResNet; тренування: `python -m app.cli.train_resnet_identifier`.
  - `detection/swin_identifier.py` – класифікує цілі за ознаками Swin Transformer; тренування: `python -m app.cli.train_swin_identifier`.
  - `detection/convnext_identifier.py` – класифікує цілі за ознаками ConvNeXt; тренування: `python -m app.cli.train_convnext_identifier`.
    - `analysis/cooccurrence.py` – підрахунок, як часто класи з’являються разом у події виявлення.
    - `analysis/burst_detector.py` – виявлення інтервалів з незвично високою кількістю виявлень.
    - `analysis/lag_correlation.py` – оцінка кореляції між класами з різними часовими зсувами.
- `analysis/interarrival.py` – обчислює середній та медіанний час між виявленнями для кожного класу.
- `analysis/peak_times.py` – визначає найактивнішу годину та день тижня для кожного класу.
- `analysis/change_point.py` – виявляє різкі зміни добових підрахунків за класами.
- `analysis/class_diversity.py` – обчислює ентропію розподілу класів за днями.
- `analysis/image_pointcloud.py` – перетворює зображення на 2D-хмару точок.
- `analysis/pointcloud_coanalysis.py` – перевіряє узгодженість детекцій із зображень та хмари точок.
- `analysis/fused_gaussian_match.py` – перетворює зображення на хмару точок, зливає з сенсорними даними й ранжує класи за гаусовою моделлю.
- `analysis/gaussian_nb_match.py` – класифікує злиті зображення та сенсорні хмари за допомогою гаусівського наївного баєсівського класіфікатора.
- `analysis/gaussian_kde_match.py` – класифікує злиті зображення та сенсорні хмари за допомогою гаусівської KDE.
- `analysis/gaussian_process_match.py` – класифікує злиті зображення та сенсорні хмари за допомогою гаусівського процесу.
- `analysis/gaussian_pointcloud_match.py` – порівнює об'єднані зображення та сенсорні хмари з натренованими гаусовими моделями й повертає ранжовані збіги з ймовірностями.
- `analysis/hourly_activity.py` – підрахунок виявлень за класами по годинах.
- `analysis/weekly_activity.py` – підрахунок виявлень за класами по днях тижня.
- `analysis/moving_average.py` – обчислення ковзних середніх щоденних виявлень для згладжування коливань.
- `analysis/speed_anomaly.py` – визначає підрозділи з аномальною середньою швидкістю.
- `analysis/acceleration_stats.py` – підрахунок середнього та максимального прискорення за журналами руху.
- `analysis/acceleration_anomaly.py` – позначає підрозділи з аномальним прискоренням.
- `analysis/heatmap.py` – генерує теплові карти виявлень у форматі PNG.
- `analysis/geo_mapper.py` – створює інтерактивні HTML-карти збережених виявлень.
- `analysis/geojson_export.py` – конвертує записи виявлень у файли GeoJSON.
- `analysis/uncertainty_heatmap.py` – розмиває невпевнені виявлення у карти невизначеності.
    - `cli/dashboard.py` – інтерактивна панель для запуску конвеєрів, перегляду карт, аналізу й навчання. Сторінка карти генерує карти виявлень, теплові та невизначеності, кластеризує переміщення, виконує метааналіз чи статистику рухів, оцінює загрози та експортує GeoJSON. Сторінка аналізу пропонує звіти про аномалії прискорення й швидкості, різноманітність класів, серії виявлень, волатильність, погодинну активність, інтервали між виявленнями, тренди, пікові години, загальні аномалії, сплески, точки зміни, матрицю співзустрічей, лагові кореляції, ковзні середні, тижневу активність, підсумки впевненості, кореляцію прогнозів і ваги надійності сенсорів. Сторінка тренування опрацьовує самопідкріплення, автон навчання та пошук гіперпараметрів. Головне меню також транслює дронові потоки, захоплює кадри, знаходить нові джерела зображень, показує наявні джерела, налаштовує середовище, показує підсумки конфігурації, звіти виявлень і співаналізу, довідку та змінює мову.
- `utils/pseudo_labeler.py` – створення YOLO-розмітки для нових зображень.
- `cli/self_reinforce.py` – розмітка нових зображень, об’єднання їх із датасетом та повторне навчання детектора.
- `cli/train_wizard.py` – майстер навчання YOLO з локалізованими підказками та прапорцями для пропуску запитів.
  - `cli/train_sensor.py` – тренує простий класифікатор за CSV ознаками сенсорів; підтримує `--dir` для навчання всіх CSV у теці або `--images/--labels` для навчання на хмарі точок із зображень.
  - `cli/train_sensor_pointcloud.py` – тренує класифікатор, поєднуючи ознаки сенсорів з хмарами точок із зображень.
  - `cli/train_gaussian_pointcloud.py` – навчає гаусові моделі на CSV хмарах точок.
  - `cli/train_fused_gaussian.py` – тренує гаусові моделі з CSV, що містять зображення та сенсорні хмари.
  - `cli/train_gaussian_nb.py` – тренує гаусівський наївний баєсівський класифікатор на зображеннях і сенсорних хмарах.
  - `cli/train_gaussian_kde.py` – тренує гаусівську KDE‑модель на парах зображення й сенсорної хмари.
  - `cli/train_gaussian_process.py` – тренує класифікатор гаусівського процесу на злитих зображеннях та сенсорних хмарах.
  - `cli/gaussian_match_report.py` – ранжує зображення та сенсорні хмари за натренованими гаусовими моделями; прапорець `--top` показує кілька кандидатів.
  - `cli/fused_gaussian_report.py` – показує результати зіставлення для зображення та сенсорної хмари за гаусовою моделлю.
  - `cli/gaussian_nb_report.py` – виводить ймовірності класифікації для зображення та сенсорної хмари за допомогою GaussianNB.
  - `cli/gaussian_kde_report.py` – виводить ймовірності класифікації за допомогою гаусівської KDE.
  - `cli/gaussian_process_report.py` – виводить ймовірності класифікації за допомогою гаусівського процесу.
  - `cli/update_gaussian_model.py` – об'єднує додаткові CSV хмар точок з існуючою гаусовою моделлю.
- `training/self_training_loop.py` – повторні цикли самопідкріплення.
- `training/self_training_aug.py` – самопідкріплення з аугментацією.
- `training/active_learning.py` – активне навчання з людським зворотним зв’язком.
- `training/sensor_auto_trainer.py` – автоматично тренує класифікатор з CSV ознак сенсорів.
- `training/sensor_pointcloud_trainer.py` – поєднує ознаки сенсорів з хмарами точок із зображень для тренування класифікатора.
- `training/gaussian_pointcloud_trainer.py` – навчає гаусові моделі на позначених хмарах точок для ідентифікації об'єктів.
- `training/fused_gaussian_trainer.py` – навчає гаусові моделі на парних зображеннях і сенсорних хмарах точок.
- `training/gaussian_nb_trainer.py` – тренує гаусівський наївний баєсівський класифікатор на злитих зображеннях і сенсорних хмарах.
- `training/gaussian_kde_trainer.py` – навчає гаусівські KDE‑моделі на злитих зображеннях і сенсорних хмарах.
- `training/gaussian_process_trainer.py` – навчає класифікатор на основі гаусівського процесу на парах зображення та сенсорної хмари.
- `training/pointnet_gaussian_trainer.py` – навчає енкодер PointNet та гаусові статистики на позначених хмарах точок.
- `training/acoustic_trainer.py` та `cli/train_acoustic.py` – навчають класифікатор на акустичних ознаках.
- `training/gaussian_mixture_trainer.py` – навчає гаусові суміші для багатомодальних сенсорних ознак.
- `training/orb_bow_trainer.py` – навчає класифікатор ORB bag-of-visual-words.
- `training/resnet_trainer.py` – тренує логістичний класифікатор на ознаках ResNet.
- `training/swin_trainer.py` – тренує логістичний класифікатор на ознаках Swin Transformer.
- `training/convnext_trainer.py` – тренує логістичний класифікатор на ознаках ConvNeXt.
- `cli/train_pointnet_gaussian.py` – запускає навчання моделі PointNet–Gaussian з CSV‑файлу.
- `cli/pointnet_gaussian_report.py` – співставляє хмари точок зображень та сенсорів за допомогою моделі PointNet–Gaussian.
- `analysis/gaussian_mixture_match.py` – ранжує сенсорні ознаки за допомогою гаусових сумішей.
- `cli/gaussian_mixture_report.py` – показує ймовірності відповідності гауссової суміші.
- `cli/train_orb_bow.py` – тренує модель ORB bag-of-words на позначених зображеннях.
- `cli/orb_bow_report.py` – показує ймовірності класифікації ORB bag-of-words.
- `cli/train_resnet_identifier.py` – тренує класифікатор ResNet на позначених зображеннях.
- `cli/resnet_classify.py` – класифікує зображення за допомогою класифікатора ResNet.
- `cli/train_swin_identifier.py` – тренує класифікатор Swin на позначених зображеннях.
- `cli/swin_classify.py` – класифікує зображення за допомогою класифікатора Swin.
- `cli/train_convnext_identifier.py` – тренує класифікатор ConvNeXt на позначених зображеннях.
- `cli/convnext_classify.py` – класифікує зображення за допомогою класифікатора ConvNeXt.
- `training/gaussian_pointcloud_update.py` – оновлює збережені гаусові моделі новими позначеними точками.
- `translation/translator.py` – переклад тексту панелі заданою мовою.
- `cli/report.py` – підсумок останніх виявлень за класами та впевненістю; приймає
  `--area` та `--limit` для введення без підказок.
- `cli/generate_demo_data.py` – створення синтетичного датасету.
- `cli/anomaly_report.py` – список аномалій виявлень.
- `cli/trend_report.py` – відображення тенденцій виявлень.
- `cli/moving_report.py` – показ ковзних середніх за класами.
- `cli/volatility_report.py` – показ коливань кількості виявлень.
- `cli/speed_report.py` – виявлення аномальних швидкостей підрозділів.
- `cli/acceleration_report.py` – показує підрозділи з аномальним прискоренням; приймає
  `--hours` та `--z` для запуску без підказок.
- `cli/interarrival_report.py` – показ середнього та медіанного часу між виявленнями.
- `cli/peak_report.py` – список пікової години та дня тижня для кожного класу.
- `cli/streak_report.py` – показати найдовшу серію виявлень для кожного класу.
- `cli/confidence_report.py` – показ статистики впевненості за класами.
- `cli/diversity_report.py` – показ різноманітності класів виявлень.
- `cli/activity_report.py` – активність за годинами для кожного класу.
- `cli/weekly_report.py` – активність за днями тижня.
- `cli/cooccurrence_report.py` – матриця спільної появи класів.
- `cli/burst_report.py` – інтервали підвищеної активності.
- `cli/changepoint_report.py` – точки зміни в добових підрахунках.
- `cli/lag_report.py` – кореляції зі зсувом у часі.
- `cli/prediction_correlation_report.py` – показує кореляцію між впевненостями моделей.
- `cli/cohesion_report.py` – відображає консенсус, зважений консенсус і відсоток узгодження між класифікаторами.
- `cli/fusion_report.py` – запуск виявлень камери, LIDAR та Bluetooth для військ, техніки й дронів і показ злитих результатів з позначкою укриття; приймає `--image`, `--pointcloud` та `--bluetooth` для введення файлів без підказок.
- `cli/sensor_reliability_report.py` – показ вагових коефіцієнтів надійності для сенсорів.
- `cli/coanalysis_report.py` – генерує хмару точок із зображення, порівнює її з детекціями сенсорів (LIDAR та необов'язковий Bluetooth) і показує спільні збіги; опція `--export` зберігає хмару точок у CSV для тренування.
- `cli/export_geojson.py` – збереження останніх виявлень у файл GeoJSON для GIS-інструментів.

Приклади використання:

```bash
python -m app.cli.dashboard
python -m app.cli.configure  # створення або оновлення файлу .env
python -m app.utils.dataset_augmentation images/raw images/augmented -n 5
python -m app.info_gathering.camera_collector 0 collected_frames --interval 2
python -m app.cli.discover_sources "List public drone video feeds" --verify
python -m app.cli.prediction_correlation_report preds.json
python -m app.cli.cohesion_report some_image.jpg --models resnet swin vit
python -m app.watch_directory data/sentinel path/to/model kyiv
python -m app.pipeline.monitor kyiv models/trajectory.h5 --interval 600
python -m app.drones.live_feed 0 --model models/trajectory.h5 \
    --troop-model troop_model.h5 --target-model target_model.h5 --classify
python -m app.utils.troop_training_cli images/train troop_model.h5 --csv troop_labels.csv
python -m app.utils.human_feedback_viewer images/train predictions.csv feedback.csv
python -m app.cli.train_wizard  # покроковий майстер навчання
python -m app.cli.train_wizard --train-dir data/train/images --val-dir data/val/images \
    --classes troop vehicle --out-model model.pt --epochs 25 --augment --n-aug 3
python -m app.cli.train_vit_identifier --images sample1.jpg sample2.jpg --labels troop vehicle
python -m app.cli.clip_classify sample.jpg troop vehicle drone
python -m app.cli.train_orb_bow --images img1.jpg img2.jpg --labels troop vehicle --out orb_model.pkl
python -m app.cli.orb_bow_report --image test.jpg --model orb_model.pkl
python -m app.cli.report --area kyiv --limit 100
python -m app.cli.anomaly_report
python -m app.cli.trend_report
python -m app.cli.activity_report
python -m app.cli.weekly_report
python -m app.cli.volatility_report
python -m app.cli.speed_report
python -m app.cli.acceleration_report --hours 12 --z 2.5
python -m app.cli.interarrival_report
python -m app.cli.changepoint_report
python -m app.cli.peak_report
python -m app.cli.streak_report  # серії виявлень
python -m app.cli.cooccurrence_report
python -m app.cli.burst_report
python -m app.cli.lag_report
python -m app.cli.coanalysis_report --image sample.jpg --pointcloud sample.pcd --bluetooth bt.csv --export sample_points.csv  # злиття детекцій
python -m app.cli.train_sensor --images image_dir --labels labels.csv --out pc_model.joblib
python -m app.cli.train_sensor_pointcloud --csv sensors.csv --images image_dir --out spc_model.joblib
python -m app.cli.train_sensor --dir sensor_csvs  # тренувати класифікатори для всіх CSV
python -m app.cli.fusion_report --image sample.jpg --pointcloud sample.pcd --bluetooth bt.csv  # злиття виявлень камери, LIDAR і Bluetooth для військ, техніки й дронів
python -m app.cli.diversity_report
python -m app.cli.generate_demo_data
python -m app.analysis.confidence_calibrator feedback.csv calib.npz
python -m app.analysis.dbscan_cluster UNIT123 --hours 48
python -m app.analysis.heatmap kyiv --start 2024-05-01 --end 2024-05-02 -o kyiv_heatmap.png
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
python -m app.cli.confidence_report detections.json
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
