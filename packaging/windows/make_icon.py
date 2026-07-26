from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
)


def render(path: Path, pixels: int = 256) -> None:
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = pixels * 0.055
    rect = QRectF(margin, margin, pixels - margin * 2, pixels - margin * 2)
    shape = QPainterPath()
    shape.addRoundedRect(rect, pixels * 0.22, pixels * 0.22)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#6C7CFF"))
    gradient.setColorAt(0.55, QColor("#4E64F4"))
    gradient.setColorAt(1.0, QColor("#3047C9"))
    painter.fillPath(shape, gradient)

    painter.setPen(QColor(255, 255, 255, 230))
    font = QFont("Segoe UI")
    font.setBold(True)
    font.setPixelSize(round(pixels * 0.34))
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "P4")

    painter.setPen(QColor(255, 255, 255, 95))
    painter.drawRoundedRect(rect, pixels * 0.22, pixels * 0.22)
    painter.end()
    if not image.save(str(path), "ICO"):
        raise RuntimeError(f"could not save {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    application = QGuiApplication([])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render(args.output)
    application.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
