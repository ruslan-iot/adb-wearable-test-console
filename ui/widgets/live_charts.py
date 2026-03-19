"""PyQtGraph live charts — three equal-height plots for compact right column."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


class LiveTelemetryCharts(QWidget):
    """Three stacked PlotWidgets; vertical stretch gives charts ~60–70% of panel."""

    CHART_MIN_HEIGHT = 128

    def __init__(self, max_points: int = 450, parent=None) -> None:
        super().__init__(parent)
        self._n = max_points
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        pg.setConfigOptions(antialias=True, foreground="w", background="#1e1e1e")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._pw_cur, self._curve_cur = self._make_plot(
            "Current (mA)", "mA", "#26c6da", "I"
        )
        self._pw_avg, self._curve_avg = self._make_plot(
            "Rolling avg (mA)", "mA", "#7cb342", "Avg"
        )
        self._pw_z, self._curve_z = self._make_plot(
            "Zone3 (°C)", "°C", "#ff9800", "T"
        )

        layout.addWidget(self._pw_cur, stretch=1)
        layout.addWidget(self._pw_avg, stretch=1)
        layout.addWidget(self._pw_z, stretch=1)

        self._xs: list[int] = []
        self._cur: list[float] = []
        self._avg: list[float] = []
        self._z: list[float] = []

    def _make_plot(
        self, title: str, left_unit: str, color: str, legend_name: str
    ) -> tuple[pg.PlotWidget, pg.PlotCurveItem]:
        pw = pg.PlotWidget()
        pw.setMinimumHeight(self.CHART_MIN_HEIGHT)
        pw.setBackground("#1e1e1e")
        pw.showGrid(x=True, y=True, alpha=0.28)
        pw.setTitle(title, color="#90a4ae", size="9pt")
        pw.setLabel("bottom", "Sample", color="#78909c", size="9pt")
        pw.setLabel("left", left_unit, color="#78909c", size="9pt")
        pw.getAxis("left").enableAutoSIPrefix(False)
        pw.getAxis("bottom").enableAutoSIPrefix(False)
        pw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pen = pg.mkPen(color=color, width=2)
        curve = pw.plot(pen=pen, name=legend_name)
        pw.addLegend()
        return pw, curve

    def append_sample(
        self,
        current_ma: float | None,
        rolling_ma: float | None,
        zone3_c: float | None,
    ) -> None:
        idx = len(self._xs)
        self._xs.append(idx)
        self._cur.append(float(current_ma) if current_ma is not None else float("nan"))
        self._avg.append(float(rolling_ma) if rolling_ma is not None else float("nan"))
        self._z.append(float(zone3_c) if zone3_c is not None else float("nan"))

        if len(self._xs) > self._n:
            self._xs = self._xs[-self._n :]
            self._cur = self._cur[-self._n :]
            self._avg = self._avg[-self._n :]
            self._z = self._z[-self._n :]
            self._xs = list(range(len(self._xs)))

        x = np.array(self._xs, dtype=float)
        self._curve_cur.setData(x, np.array(self._cur, dtype=float))
        self._curve_avg.setData(x, np.array(self._avg, dtype=float))
        self._curve_z.setData(x, np.array(self._z, dtype=float))

    def clear(self) -> None:
        self._xs.clear()
        self._cur.clear()
        self._avg.clear()
        self._z.clear()
        self._curve_cur.setData([], [])
        self._curve_avg.setData([], [])
        self._curve_z.setData([], [])
