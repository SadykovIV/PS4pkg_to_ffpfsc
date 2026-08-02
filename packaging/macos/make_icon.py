from __future__ import annotations

import argparse
import struct
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


def write_icns(output: Path, images: list[tuple[bytes, Path]]) -> None:
    chunks: list[bytes] = []
    for icon_type, image_path in images:
        image = image_path.read_bytes()
        chunks.append(icon_type + struct.pack(">I", 8 + len(image)) + image)
    body = b"".join(chunks)
    output.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    QGuiApplication([])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ps4ffpsc-icon-") as temporary:
        icon_root = Path(temporary)
        variants = [
            (16, b"icp4"),
            (32, b"ic11"),
            (32, b"icp5"),
            (64, b"ic12"),
            (128, b"ic07"),
            (256, b"ic13"),
            (256, b"ic08"),
            (512, b"ic14"),
            (512, b"ic09"),
            (1024, b"ic10"),
        ]
        images: list[tuple[bytes, Path]] = []
        for pixels, icon_type in variants:
            image_path = icon_root / f"{icon_type.decode('ascii')}-{pixels}.png"
            render(image_path, pixels)
            images.append((icon_type, image_path))
        write_icns(args.output, images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
