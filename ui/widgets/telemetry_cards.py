"""Compact fixed-size metric grid for the right telemetry column (no layout jump)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Fixed card geometry (px) — stable row height on 13" displays
CARD_HEIGHT = 88
CARD_V_SPACING = 8
CARD_H_SPACING = 8
LABEL_PT = 10
VALUE_PT = 16


class _ElideValueLabel(QLabel):
    """Single-line value; elides on the right when text would overflow."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._full = "—"
        self.setWordWrap(False)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        f = QFont("Consolas", VALUE_PT)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(f)
        self.setStyleSheet("color: #80deea; font-weight: bold;")
        self.setMinimumHeight(22)
        self.setMaximumHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._apply_elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        w = max(self.width() - 4, 40)
        elided = QFontMetrics(self.font()).elidedText(
            self._full, Qt.TextElideMode.ElideRight, w
        )
        super().setText(elided)


def _title_label(text: str, tooltip: str = "") -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(False)
    f = QFont("Segoe UI", LABEL_PT)
    lb.setFont(f)
    lb.setStyleSheet("color: #9e9e9e;")
    lb.setMinimumHeight(16)
    lb.setMaximumHeight(18)
    if tooltip:
        lb.setToolTip(tooltip)
    return lb


def _metric_cell(title: str, tooltip: str = "") -> tuple[QFrame, _ElideValueLabel]:
    fr = QFrame()
    fr.setObjectName("telemetryMetricCard")
    fr.setFixedHeight(CARD_HEIGHT)
    fr.setStyleSheet(
        "#telemetryMetricCard { background-color: #2a2a2a; border: 1px solid #3d5c66; "
        "border-radius: 4px; padding: 6px 8px; }"
    )
    fr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if tooltip:
        fr.setToolTip(tooltip)
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    tl = _title_label(title, tooltip)
    val = _ElideValueLabel()
    lay.addWidget(tl)
    lay.addWidget(val)
    lay.addStretch()
    return fr, val


class TelemetryCardsPanel(QWidget):
    """
    3×3 fixed-height metric grid only.
    Status / estimation disclaimer live in the parent right column (main_window).
    """

    RT_TOOLTIP = (
        "3300 mAh nominal × 0.85 usable; rolling-average current first, "
        "then instantaneous. Runtime = mAh ÷ mA."
    )
    ENERGY_TOOLTIP = "Auxiliary: (mAh/1000)×V. Runtime does not use Wh."

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(CARD_H_SPACING)
        grid.setVerticalSpacing(CARD_V_SPACING)

        for c in range(3):
            grid.setColumnStretch(c, 1)

        self._z3_f, self._z3 = _metric_cell("Zone3 (°C)")
        self._cur_f, self._cur = _metric_cell("Current (mA)")
        self._avg_f, self._avg = _metric_cell("Roll. avg (mA)")
        self._pct_f, self._pct = _metric_cell("Battery (%)")
        self._volt_f, self._volt = _metric_cell("Voltage (V)")
        self._ts_f, self._ts = _metric_cell("Last update")
        self._est_rem_f, self._est_rem = _metric_cell("Remaining", self.RT_TOOLTIP)
        self._est_full_f, self._est_full = _metric_cell("Full", self.RT_TOOLTIP)

        self._en_f = QFrame()
        self._en_f.setObjectName("telemetryMetricCard")
        self._en_f.setFixedHeight(CARD_HEIGHT)
        self._en_f.setStyleSheet(
            "#telemetryMetricCard { background-color: #2a2a2a; border: 1px solid #3d5c66; "
            "border-radius: 4px; padding: 6px 8px; }"
        )
        self._en_f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._en_f.setToolTip(self.ENERGY_TOOLTIP)
        en_lay = QVBoxLayout(self._en_f)
        en_lay.setContentsMargins(0, 0, 0, 0)
        en_lay.setSpacing(2)
        en_lay.addWidget(_title_label("Energy (Wh)", self.ENERGY_TOOLTIP))
        self._en_main = _ElideValueLabel()
        self._en_sub = QLabel("")
        self._en_sub.setWordWrap(False)
        self._en_sub.setFont(QFont("Consolas", 11))
        self._en_sub.setStyleSheet("color: #78909c;")
        self._en_sub.setMinimumHeight(16)
        self._en_sub.setMaximumHeight(18)
        self._en_sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        en_lay.addWidget(self._en_main)
        en_lay.addWidget(self._en_sub)
        en_lay.addStretch()

        grid.addWidget(self._z3_f, 0, 0)
        grid.addWidget(self._cur_f, 0, 1)
        grid.addWidget(self._avg_f, 0, 2)
        grid.addWidget(self._pct_f, 1, 0)
        grid.addWidget(self._volt_f, 1, 1)
        grid.addWidget(self._ts_f, 1, 2)
        grid.addWidget(self._est_rem_f, 2, 0)
        grid.addWidget(self._est_full_f, 2, 1)
        grid.addWidget(self._en_f, 2, 2)

    def update_metrics(
        self,
        z3: str,
        cur: str,
        avg: str,
        pct: str,
        volt: str,
        ts: str,
        est_runtime_remaining: str,
        est_runtime_full: str,
        energy_main_wh: str,
        energy_sub_full_wh: str,
    ) -> None:
        self._z3.set_full_text(z3)
        self._cur.set_full_text(cur)
        self._avg.set_full_text(avg)
        self._pct.set_full_text(pct)
        self._volt.set_full_text(volt)
        self._ts.set_full_text(ts)
        self._est_rem.set_full_text(est_runtime_remaining)
        self._est_full.set_full_text(est_runtime_full)
        self._en_main.set_full_text(energy_main_wh)
        self._en_sub.setText(energy_sub_full_wh)
        self._en_sub.setVisible(bool(energy_sub_full_wh.strip()))
