import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest import TestCase, mock

# Provide lightweight stubs for optional dependencies so alert tests can run
# without installing heavy imaging or ML packages in the CI environment.

class _DummyImage:
    def convert(self, *_args, **_kwargs):
        return self

    def save(self, *_args, **_kwargs):
        return None


def _image_open(_path):
    return _DummyImage()


class _Enhancer:
    def __init__(self, image):
        self._image = image

    def enhance(self, *_args, **_kwargs):
        return self._image


fake_pil = ModuleType("PIL")
fake_image_module = ModuleType("PIL.Image")
fake_image_module.open = _image_open
fake_enhance_module = ModuleType("PIL.ImageEnhance")
fake_enhance_module.Contrast = lambda image: _Enhancer(image)
fake_enhance_module.Sharpness = lambda image: _Enhancer(image)
fake_imagetk_module = ModuleType("PIL.ImageTk")
fake_imagetk_module.PhotoImage = object
fake_imagedraw_module = ModuleType("PIL.ImageDraw")
fake_imagedraw_module.Draw = lambda image: _Enhancer(image)

fake_pil.Image = fake_image_module
fake_pil.ImageEnhance = fake_enhance_module
fake_pil.ImageTk = fake_imagetk_module
fake_pil.ImageDraw = fake_imagedraw_module

sys.modules.setdefault("PIL", fake_pil)
sys.modules.setdefault("PIL.Image", fake_image_module)
sys.modules.setdefault("PIL.ImageEnhance", fake_enhance_module)
sys.modules.setdefault("PIL.ImageTk", fake_imagetk_module)
sys.modules.setdefault("PIL.ImageDraw", fake_imagedraw_module)

fake_troop_training = ModuleType("app.utils.troop_training_cli")
fake_troop_training.train_classifier = lambda *args, **kwargs: None
sys.modules.setdefault("app.utils.troop_training_cli", fake_troop_training)


class _DummyMongoClient:
    def __init__(self, *_args, **_kwargs) -> None:
        self._dbs = {}

    def __getitem__(self, name: str):
        self._dbs.setdefault(name, {})
        return self._dbs[name]


fake_pymongo = ModuleType("pymongo")
fake_pymongo.MongoClient = _DummyMongoClient
sys.modules.setdefault("pymongo", fake_pymongo)

fake_detection = ModuleType("app.detection")
fake_detection.__path__ = []  # mark as package-like
fake_yolo = ModuleType("app.detection.yolo")
fake_yolo.detect_vehicles = lambda *args, **kwargs: []
setattr(fake_detection, "yolo", fake_yolo)
sys.modules.setdefault("app.detection", fake_detection)
sys.modules.setdefault("app.detection.yolo", fake_yolo)

fake_training = ModuleType("app.training")
fake_training.__path__ = []
fake_item_catalog = ModuleType("app.training.item_catalog")
fake_item_catalog.register_item = lambda *args, **kwargs: None
setattr(fake_training, "item_catalog", fake_item_catalog)
sys.modules.setdefault("app.training", fake_training)
sys.modules.setdefault("app.training.item_catalog", fake_item_catalog)

from app.alerts import (
    create_rule,
    evaluate_detections,
    list_events,
    list_presets,
    list_rules,
)
from app.config import settings
from app.utils import email_alerts


class AlertWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tempdir.name)
        self.original_values = {
            "DATA_DIR": settings.DATA_DIR,
            "EMAIL_SMTP_HOST": settings.EMAIL_SMTP_HOST,
            "EMAIL_SMTP_PORT": settings.EMAIL_SMTP_PORT,
            "EMAIL_SMTP_USERNAME": settings.EMAIL_SMTP_USERNAME,
            "EMAIL_SMTP_PASSWORD": settings.EMAIL_SMTP_PASSWORD,
            "EMAIL_FROM_ADDRESS": settings.EMAIL_FROM_ADDRESS,
            "EMAIL_USE_TLS": settings.EMAIL_USE_TLS,
        }
        settings.DATA_DIR = self.data_dir
        settings.EMAIL_SMTP_HOST = "smtp.example.com"
        settings.EMAIL_SMTP_PORT = 587
        settings.EMAIL_SMTP_USERNAME = "user"
        settings.EMAIL_SMTP_PASSWORD = "pass"
        settings.EMAIL_FROM_ADDRESS = "ops@example.com"
        settings.EMAIL_USE_TLS = True

    def tearDown(self) -> None:
        for key, value in self.original_values.items():
            setattr(settings, key, value)
        self.tempdir.cleanup()

    def _rules_path(self) -> Path:
        return settings.DATA_DIR / "alert_rules.json"

    def test_create_rule_persists_to_storage(self) -> None:
        rule = create_rule(
            {
                "name": "Troop activity",
                "area": "alpha",
                "labels": ["troop"],
                "sms_recipients": ["+15551234567"],
                "email_recipients": ["ops@example.com"],
                "min_confidence": 0.6,
            }
        )

        self.assertTrue(self._rules_path().exists())
        stored = json.loads(self._rules_path().read_text())
        self.assertEqual(stored[0]["id"], rule["id"])
        self.assertEqual(list_rules()[0]["name"], "Troop activity")

    @mock.patch("app.utils.email_alerts.send_alert")
    @mock.patch("app.utils.twilio_alerts.send_alert")
    @mock.patch("app.utils.twilio_alerts.is_configured", return_value=True)
    def test_evaluate_detections_triggers_notifications(
        self, mock_twilio_config, mock_twilio_send, mock_email_send
    ) -> None:
        rule = create_rule(
            {
                "name": "Drone watch",
                "area": "sector-7",
                "labels": ["drone"],
                "sms_recipients": ["+15550001111"],
                "email_recipients": ["intel@example.com"],
                "min_confidence": 0.4,
            }
        )

        detections = [
            {"class": "drone", "confidence": 0.82, "lat": 10.0, "lon": 20.0},
            {"class": "troop", "confidence": 0.91},
        ]

        triggered = evaluate_detections("sector-7", detections)

        self.assertEqual(triggered, [rule["id"]])
        mock_email_send.assert_called_once()
        mock_twilio_send.assert_called_once()
        mock_twilio_config.assert_called_once()
        events = list_events()
        self.assertTrue(events, "Expected alert event to be recorded")
        self.assertEqual(events[0]["rule_id"], rule["id"])
        self.assertEqual(events[0]["match_count"], 1)

    def test_email_alert_requires_configuration(self) -> None:
        settings.EMAIL_SMTP_HOST = ""
        settings.EMAIL_FROM_ADDRESS = ""

        with self.assertRaises(email_alerts.EmailConfigurationError):
            email_alerts.send_alert("Subject", "Body", ["ops@example.com"])

    @mock.patch("smtplib.SMTP")
    def test_email_alert_sends_when_configured(self, mock_smtp) -> None:
        recipients = ["ops@example.com", "watch@example.com"]

        result = email_alerts.send_alert("Subject", "Body", recipients)

        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
        client = mock_smtp.return_value.__enter__.return_value
        client.starttls.assert_called_once()
        client.login.assert_called_once_with("user", "pass")
        client.send_message.assert_called_once()
        self.assertEqual(result, {addr: "sent" for addr in recipients})

    def test_presets_available(self) -> None:
        presets = list_presets()
        self.assertTrue(any(preset["labels"] == ["drone"] for preset in presets))

