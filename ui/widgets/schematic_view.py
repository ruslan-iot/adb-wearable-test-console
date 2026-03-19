"""Scalable device schematic with overlay labels."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)


class SchematicView(QGraphicsView):
    """
    Loads assets/device_schematic.png relative to project root / cwd.
    Overlays board-related labels; scales with viewport.
    """

    def __init__(self, assets_dir: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(QColor("#252525"))

        root = Path(__file__).resolve().parents[2]
        self._assets = assets_dir or (root / "assets")
        self._pix_item: QGraphicsPixmapItem | None = None
        self._label_items: list[QGraphicsSimpleTextItem] = []
        self._placeholder: QGraphicsSimpleTextItem | None = None
        self._load_image()

    def _load_image(self) -> None:
        path = self._assets / "device_schematic.png"
        if not path.is_file():
            self._show_placeholder("Device schematic image not loaded")
            return

        pix = QPixmap(str(path))
        if pix.isNull():
            self._show_placeholder("Device schematic image not loaded")
            return

        self._scene.clear()
        self._placeholder = None
        self._pix_item = QGraphicsPixmapItem(pix)
        self._scene.addItem(self._pix_item)
        w, h = pix.width(), pix.height()
        self._scene.setSceneRect(0, 0, w, h)

        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        pen = QPen(QColor("#00e5ff"))
        labels = [
            ("Main Board", 0.32 * w, 0.22 * h),
            ("Battery", 0.18 * w, 0.58 * h),
            ("LTE Module", 0.62 * w, 0.28 * h),
            ("PMIC / Zone3 ref.", 0.48 * w, 0.72 * h),
        ]
        self._label_items.clear()
        for text, x, y in labels:
            t = QGraphicsSimpleTextItem(text)
            t.setFont(font)
            t.setBrush(QColor("#00e5ff"))
            t.setPen(pen)
            t.setPos(x, y)
            self._scene.addItem(t)
            self._label_items.append(t)

        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _show_placeholder(self, message: str) -> None:
        self._scene.clear()
        self._pix_item = None
        self._label_items.clear()
        t = QGraphicsSimpleTextItem(message)
        t.setFont(QFont("Segoe UI", 14))
        t.setBrush(QColor("#ffca28"))
        self._scene.addItem(t)
        self._placeholder = t
        self._scene.setSceneRect(0, 0, 400, 200)
        t.setPos(20, 80)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pix_item is not None:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        elif self._placeholder is not None:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
