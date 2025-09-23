"""Tkinter GUI for human feedback on detections."""

from pathlib import Path
import csv
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

from .feedback_logger import log_feedback
from ..config import settings
from ..translation import translate_text

_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


class FeedbackApp:
    """Display predictions and record human validation."""

    def __init__(self, img_dir: Path, csv_path: Path, out_csv: Path) -> None:
        self.img_dir = img_dir
        self.records = self._load_records(csv_path)
        self.out_csv = out_csv
        self.index = 0
        self.root = tk.Tk()
        self.root.title(_t("Human Feedback"))
        self.image_label = tk.Label(self.root)
        self.image_label.pack()
        self.info_text = tk.StringVar()
        tk.Label(self.root, textvariable=self.info_text).pack()
        btns = tk.Frame(self.root)
        tk.Button(btns, text=_t("Correct"), command=self._mark_correct).pack(side=tk.LEFT)
        tk.Button(btns, text=_t("Incorrect"), command=self._mark_incorrect).pack(side=tk.LEFT)
        btns.pack()
        self._show_record()

    @staticmethod
    def _load_records(path: Path):
        with path.open() as f:
            return list(csv.DictReader(f))

    def _show_record(self) -> None:
        if self.index >= len(self.records):
            messagebox.showinfo(_t("Done"), _t("No more records"))
            self.root.quit()
            return
        rec = self.records[self.index]
        img_path = self.img_dir / rec["filename"]
        img = Image.open(img_path).resize((256, 256))
        self.photo = ImageTk.PhotoImage(img)
        self.image_label.configure(image=self.photo)
        info_lines = [f"{k}: {v}" for k, v in rec.items() if k != "filename"]
        self.info_text.set("\n".join(info_lines))

    def _save_feedback(self, correct: bool) -> None:
        rec = dict(self.records[self.index])
        rec["correct"] = str(correct)
        write_header = not self.out_csv.exists()
        with self.out_csv.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rec.keys())
            if write_header:
                writer.writeheader()
            writer.writerow(rec)
        try:
            log_feedback({**rec, "confidence": rec.get("confidence")})
        except Exception:
            pass
        self.index += 1
        self._show_record()

    def _mark_correct(self) -> None:
        self._save_feedback(True)

    def _mark_incorrect(self) -> None:
        self._save_feedback(False)


def launch_feedback_gui(img_dir: Path, pred_csv: Path, out_csv: Path) -> None:
    """Launch the feedback GUI for the given predictions."""
    app = FeedbackApp(img_dir, pred_csv, out_csv)
    app.root.mainloop()


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description=_t("Review detections with a GUI"))
    p.add_argument("img_dir", type=Path, help=_t("Directory of images"))
    p.add_argument("pred_csv", type=Path, help=_t("CSV with prediction info"))
    p.add_argument("out_csv", type=Path, help=_t("File to save feedback"))
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    launch_feedback_gui(args.img_dir, args.pred_csv, args.out_csv)


if __name__ == "__main__":
    main()
