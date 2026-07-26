from __future__ import annotations

import argparse
import subprocess
import tempfile
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


def render(path: Path, pixels: int) -> None:
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
    font = QFont("Helvetica Neue")
    font.setBold(True)
    font.setPixelSize(round(pixels * 0.34))
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "P4")

    painter.setPen(QColor(255, 255, 255, 95))
    painter.drawRoundedRect(rect, pixels * 0.22, pixels * 0.22)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"could not save {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    QGuiApplication([])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ps4ffpsc-icon-") as temporary:
        iconset = Path(temporary) / "AppIcon.iconset"
        iconset.mkdir()
        variants = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]
        for pixels, name in variants:
            render(iconset / name, pixels)
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(args.output)],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
