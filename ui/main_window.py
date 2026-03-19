"""Main application window — layout, theming, wires services via controller."""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from models.telemetry_sample import TelemetrySample
from services.console_controller import ConsoleController, WorkflowResult, discover_adb_candidates
from services.telemetry_service import TelemetrySession, TelemetryWorker
from ui.styles import STYLESHEET
from ui.widgets.live_charts import LiveTelemetryCharts
from ui.widgets.schematic_view import SchematicView
from ui.widgets.telemetry_cards import TelemetryCardsPanel
from ui.workflow_thread import FunctionRunnerThread
from utils.logger import timestamp_message
from utils.runtime_estimator import RuntimeEstimateResult, compute_runtime_estimate
from utils.settings_manager import SettingsManager

log = logging.getLogger(__name__)


class ConnMode(Enum):
    DISCONNECTED = auto()
    USB = auto()
    TCP = auto()


class MainWindow(QWidget):
    """Tester-facing main console (embedded in QMainWindow from main.py)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ADB Wearable Test Console")
        self.resize(1280, 900)

        self._settings = SettingsManager()
        self._controller = ConsoleController(self._settings.adb_path())
        self._session = TelemetrySession()
        self._conn_mode = ConnMode.DISCONNECTED
        self._tcp_ip: str = ""
        self._busy = False
        self._workflow_op: str = ""

        self._tel_thread = None
        self._tel_worker: TelemetryWorker | None = None
        self._workflow_thread: FunctionRunnerThread | None = None
        self._last_runtime_good: tuple[RuntimeEstimateResult, float] | None = None

        self._build_ui()
        self._wire_signals()
        self._restore_settings()
        self._apply_mode_to_header()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        head = QHBoxLayout()
        self._title = QLabel("ADB Wearable Test Console")
        self._title.setObjectName("headerTitle")
        self._app_status = QLabel("Ready")
        self._app_status.setObjectName("statusOk")
        self._sel_device = QLabel("Device: —")
        self._conn_lbl = QLabel("Mode: Disconnected")
        self._tcp_info = QLabel("TCP: —")
        head.addWidget(self._title)
        head.addStretch()
        head.addWidget(QLabel("Status:"))
        head.addWidget(self._app_status)
        head.addSpacing(20)
        head.addWidget(self._sel_device)
        head.addSpacing(20)
        head.addWidget(self._conn_lbl)
        head.addSpacing(12)
        head.addWidget(self._tcp_info)
        root.addLayout(head)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_inner = QWidget()
        left_lay = QVBoxLayout(left_inner)
        left_lay.setSpacing(12)

        self._schematic = SchematicView()
        self._schematic.setMinimumHeight(240)
        left_lay.addWidget(self._schematic, stretch=0)

        left_lay.addWidget(self._build_connection_panel())
        left_lay.addWidget(self._build_diagnostics_panel())
        left_scroll.setWidget(left_inner)

        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(6, 4, 6, 4)
        right_lay.setSpacing(6)

        self._cards = TelemetryCardsPanel()
        right_lay.addWidget(self._cards, stretch=0)

        self._est_hint = QLabel("Estimate based on recent average current.")
        self._est_hint.setWordWrap(True)
        self._est_hint.setMaximumHeight(34)
        self._est_hint.setStyleSheet(
            "font-size: 10px; color: #78909c; padding: 0 2px; margin: 0;"
        )
        right_lay.addWidget(self._est_hint, stretch=0)

        status_bar = QWidget()
        status_bar.setFixedHeight(30)
        status_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sbl = QHBoxLayout(status_bar)
        sbl.setContentsMargins(0, 0, 0, 0)
        sbl.setSpacing(8)
        self._mode_line = QLabel("—")
        self._mode_line.setWordWrap(False)
        self._mode_line.setStyleSheet("font-size: 10px; color: #b0bec5;")
        self._mode_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._tel_stat_line = QLabel("—")
        self._tel_stat_line.setWordWrap(False)
        self._tel_stat_line.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._tel_stat_line.setStyleSheet("font-size: 10px; font-weight: bold; color: #9e9e9e;")
        self._tel_stat_line.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sbl.addWidget(self._mode_line, stretch=1)
        sbl.addWidget(self._tel_stat_line, stretch=0)
        right_lay.addWidget(status_bar, stretch=0)

        self._charts = LiveTelemetryCharts(max_points=450)
        right_lay.addWidget(self._charts, stretch=1)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right_w)
        splitter.setStretchFactor(0, 50)
        splitter.setStretchFactor(1, 50)

    def _build_connection_panel(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)

        adb_g = QGroupBox("ADB")
        adb_l = QGridLayout(adb_g)
        self._adb_path = QLineEdit()
        self._adb_path.setPlaceholderText("Path to adb.exe or leave blank for PATH")
        btn_auto = QPushButton("Auto-detect")
        btn_auto.setObjectName("successBtn")
        btn_ref = QPushButton("Refresh Devices")
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(280)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(self._settings.tcp_port())
        self._port_spin.setToolTip(
            "Port for adb tcpip, adb connect, and disconnect. Must match the device (often 5555)."
        )
        adb_l.addWidget(QLabel("ADB path:"), 0, 0)
        adb_l.addWidget(self._adb_path, 0, 1, 1, 3)
        adb_l.addWidget(btn_auto, 1, 0)
        adb_l.addWidget(btn_ref, 1, 1)
        adb_l.addWidget(QLabel("Device:"), 2, 0)
        adb_l.addWidget(self._device_combo, 2, 1, 1, 2)
        adb_l.addWidget(QLabel("TCP port:"), 2, 3)
        adb_l.addWidget(self._port_spin, 2, 4)
        v.addWidget(adb_g)

        wf_g = QGroupBox("Wi-Fi / ADB over TCP")
        wf_l = QGridLayout(wf_g)
        self._ssid = QLineEdit()
        self._ssid.setPlaceholderText("Network name (optional)")
        self._wifi_pass = QLineEdit()
        self._wifi_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._wifi_pass.setPlaceholderText("Password (optional)")
        self._ip_display = QLineEdit()
        self._ip_display.setReadOnly(True)
        self._ip_display.setPlaceholderText("Filled by Read device IP…")
        self._ip_display.setToolTip(
            "IP from the device. ADB over TCP uses the TCP port set in the ADB section above."
        )

        b_enable = QPushButton("Enable ADB over Wi-Fi")
        b_enable.setObjectName("successBtn")
        b_disable = QPushButton("Disable ADB over Wi-Fi")
        b_disable.setObjectName("dangerBtn")
        b_conn = QPushButton("Connect to device via IP")
        b_disconn = QPushButton("Disconnect TCP/IP session")
        b_readip = QPushButton("Read device IP")

        wf_l.addWidget(QLabel("SSID:"), 0, 0)
        wf_l.addWidget(self._ssid, 0, 1, 1, 2)
        wf_l.addWidget(QLabel("Password:"), 0, 3)
        wf_l.addWidget(self._wifi_pass, 0, 4)
        wf_l.addWidget(QLabel("IP (from device):"), 1, 0)
        wf_l.addWidget(self._ip_display, 1, 1, 1, 4)
        row2 = QHBoxLayout()
        row2.addWidget(b_enable)
        row2.addWidget(b_disable)
        row2.addWidget(b_conn)
        row2.addWidget(b_disconn)
        row2.addWidget(b_readip)
        wf_l.addLayout(row2, 2, 0, 1, 5)
        v.addWidget(wf_g)

        tel_g = QGroupBox("Telemetry")
        tel_l = QHBoxLayout(tel_g)
        self._b_start_tel = QPushButton("Start telemetry")
        self._b_start_tel.setObjectName("successBtn")
        self._b_stop_tel = QPushButton("Stop telemetry")
        self._b_stop_tel.setObjectName("dangerBtn")
        b_export = QPushButton("Export CSV")
        b_clear = QPushButton("Clear session data")
        tel_l.addWidget(self._b_start_tel)
        tel_l.addWidget(self._b_stop_tel)
        tel_l.addWidget(b_export)
        tel_l.addWidget(b_clear)
        v.addWidget(tel_g)

        self._btn_auto_adb = btn_auto
        self._btn_refresh = btn_ref
        self._btn_enable_wifi = b_enable
        self._btn_disable_wifi = b_disable
        self._btn_connect_ip = b_conn
        self._btn_disconnect_tcp = b_disconn
        self._btn_read_ip = b_readip
        self._btn_export = b_export
        self._btn_clear_session = b_clear

        return box

    def _build_diagnostics_panel(self) -> QWidget:
        outer = QGroupBox("Diagnostics")
        v = QVBoxLayout(outer)
        self._human_log = QLabel("")
        self._human_log.setWordWrap(True)
        self._human_log.setStyleSheet("color:#b0bec5;")

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(140)
        self._log.setMaximumHeight(220)
        v.addWidget(QLabel("Activity log (human-readable)"))
        v.addWidget(self._log)

        self._adv_toggle = QCheckBox("Show advanced diagnostics")
        v.addWidget(self._adv_toggle)

        self._adv_frame = QWidget()
        adv_l = QVBoxLayout(self._adv_frame)
        self._raw_out = QPlainTextEdit()
        self._raw_out.setReadOnly(True)
        self._raw_out.setMinimumHeight(120)
        adv_l.addWidget(QLabel("Raw command output / stderr"))
        adv_l.addWidget(self._raw_out)
        form = QFormLayout()
        self._manual_cmd = QLineEdit()
        self._manual_cmd.setPlaceholderText("e.g. getprop ro.build.version.release")
        self._btn_run_manual = QPushButton("Run shell command on selected target")
        form.addRow("Manual ADB shell:", self._manual_cmd)
        form.addRow(self._btn_run_manual)
        adv_l.addLayout(form)
        btn_copy = QPushButton("Copy log to clipboard")
        adv_l.addWidget(btn_copy)
        self._btn_copy_diag = btn_copy
        self._adv_frame.setVisible(False)
        v.addWidget(self._adv_frame)

        self._adv_toggle.toggled.connect(self._adv_frame.setVisible)
        return outer

    def _wire_signals(self) -> None:
        self._btn_auto_adb.clicked.connect(self._on_auto_adb)
        self._btn_refresh.clicked.connect(self._on_refresh_devices)
        self._btn_enable_wifi.clicked.connect(self._on_enable_wifi)
        self._btn_disable_wifi.clicked.connect(self._on_disable_wifi)
        self._btn_connect_ip.clicked.connect(self._on_connect_ip)
        self._btn_disconnect_tcp.clicked.connect(self._on_disconnect_tcp)
        self._btn_read_ip.clicked.connect(self._on_read_ip)
        self._b_start_tel.clicked.connect(self._on_start_telemetry)
        self._b_stop_tel.clicked.connect(self._on_stop_telemetry)
        self._btn_export.clicked.connect(self._on_export_csv)
        self._btn_clear_session.clicked.connect(self._on_clear_session)
        self._btn_run_manual.clicked.connect(self._on_manual_shell)
        self._btn_copy_diag.clicked.connect(self._on_copy_diag)
        self._device_combo.currentTextChanged.connect(self._on_device_changed)

    def _restore_settings(self) -> None:
        self._adb_path.setText(self._settings.adb_path())
        self._ssid.setText(self._settings.last_ssid())
        self._port_spin.setValue(self._settings.tcp_port())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._on_refresh_devices)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._on_stop_telemetry()
        QCoreApplication.processEvents()
        if self._tel_thread and self._tel_thread.isRunning():
            self._tel_thread.quit()
            self._tel_thread.wait(3000)
        self._settings.set_adb_path(self._adb_path.text().strip())
        self._settings.set_tcp_port(self._port_spin.value())
        self._settings.set_last_ssid(self._ssid.text().strip())
        self._settings.set_window_geometry(self.saveGeometry().data())
        self._settings.sync()
        event.accept()

    def apply_stylesheet(self) -> None:
        self.setStyleSheet(STYLESHEET)

    def _apply_controller_path(self) -> None:
        self._controller.set_adb_path(self._adb_path.text().strip())

    def _current_target_serial(self) -> str:
        t = self._device_combo.currentText().strip()
        if "\t" in t:
            t = t.split("\t", 1)[0].strip()
        return t

    def _get_adb_path_for_worker(self) -> str:
        return self._adb_path.text().strip()

    def _get_target_for_worker(self) -> str:
        return self._current_target_serial()

    def _ensure_telemetry_thread(self) -> None:
        if self._tel_thread is not None:
            return
        from PySide6.QtCore import QThread

        self._tel_thread = QThread(self)
        self._tel_worker = TelemetryWorker(
            self._get_adb_path_for_worker,
            self._get_target_for_worker,
        )
        self._tel_worker.moveToThread(self._tel_thread)
        self._tel_worker.sig_start.connect(
            self._tel_worker.start_polling, Qt.ConnectionType.QueuedConnection
        )
        self._tel_worker.sig_stop.connect(
            self._tel_worker.stop_polling, Qt.ConnectionType.QueuedConnection
        )
        self._tel_worker.sample_ready.connect(self._on_telemetry_sample)
        self._tel_worker.status_changed.connect(self._on_telemetry_status)
        self._tel_thread.start()

    @staticmethod
    def _strip_about_runtime(s: str) -> str:
        t = (s or "").strip()
        if t.startswith("about "):
            return t[6:].strip()
        return t

    @Slot(object)
    def _on_telemetry_sample(self, sample: TelemetrySample) -> None:
        self._session.add(sample)
        z3 = (
            f"{sample.zone3_temp_c:.1f}"
            if sample.zone3_temp_c is not None
            else "—"
        )
        cur = (
            f"{int(round(sample.current_ma))}"
            if sample.current_ma is not None
            else "—"
        )
        avg = (
            f"{sample.rolling_avg_100_ma:.1f}"
            if sample.rolling_avg_100_ma is not None
            else "—"
        )
        pct = (
            f"{int(round(sample.battery_percent))}"
            if sample.battery_percent is not None
            else "—"
        )
        volt = (
            f"{sample.battery_voltage_v:.3f}"
            if sample.battery_voltage_v is not None
            else "—"
        )
        ts = sample.timestamp.strftime("%H:%M:%S")
        fresh = compute_runtime_estimate(
            sample.battery_percent,
            sample.battery_voltage_v,
            sample.current_ma,
            sample.rolling_avg_100_ma,
        )
        rt = self._resolve_runtime_display(sample, fresh)
        est_rem = self._strip_about_runtime(rt.remaining_runtime)
        est_full = self._strip_about_runtime(rt.full_runtime)
        energy_main = rt.remaining_energy_wh if rt.remaining_energy_wh != "--" else "—"
        energy_sub = (
            f"Full: {rt.full_energy_wh}" if rt.full_energy_wh != "--" else ""
        )
        self._cards.update_metrics(
            z3,
            cur,
            avg,
            pct,
            volt,
            ts,
            est_rem,
            est_full,
            energy_main,
            energy_sub,
        )
        mode_txt = rt.mode_label
        self._mode_line.setToolTip(mode_txt)
        if len(mode_txt) > 72:
            mode_txt = mode_txt[:69] + "…"
        self._mode_line.setText(mode_txt)
        self._tel_stat_line.setText("OK" if sample.success else "ERROR")
        self._tel_stat_line.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: "
            f"{'#66bb6a' if sample.success else '#ef5350'};"
        )
        self._charts.append_sample(sample.current_ma, sample.rolling_avg_100_ma, sample.zone3_temp_c)
        if not sample.success and sample.notes:
            self._append_log(f"Telemetry: {sample.notes}", warn=True)

    def _resolve_runtime_display(
        self, sample: TelemetrySample, fresh: RuntimeEstimateResult
    ) -> RuntimeEstimateResult:
        """Keep last valid runtime for up to 5s when SOC exists but current briefly drops."""
        now = time.monotonic()
        if fresh.is_valid:
            self._last_runtime_good = (fresh, now)
            return fresh
        if sample.battery_percent is None:
            self._last_runtime_good = None
            return fresh
        if self._last_runtime_good is not None:
            prev, ts = self._last_runtime_good
            if prev.is_valid and (now - ts) <= 5.0:
                return prev
        return fresh

    @Slot(str)
    def _on_telemetry_status(self, s: str) -> None:
        self._append_log(f"Telemetry worker: {s}")

    def _on_start_telemetry(self) -> None:
        self._apply_controller_path()
        tgt = self._current_target_serial()
        if not tgt:
            QMessageBox.warning(self, "Telemetry", "Select a device in the dropdown first.")
            return
        self._ensure_telemetry_thread()
        assert self._tel_worker is not None
        self._tel_worker.sig_start.emit()
        self._append_log("Telemetry started (1 sample per second).")
        self._app_status.setText("Telemetry running")
        self._app_status.setObjectName("statusOk")
        self._style_repolish(self._app_status)

    def _on_stop_telemetry(self) -> None:
        if self._tel_worker:
            self._tel_worker.sig_stop.emit()
        self._append_log("Telemetry stopped.")
        self._app_status.setText("Ready")
        self._app_status.setObjectName("statusOk")
        self._style_repolish(self._app_status)

    def _on_clear_session(self) -> None:
        self._session.clear()
        self._charts.clear()
        self._last_runtime_good = None
        self._append_log("Session data cleared.")

    def _on_export_csv(self) -> None:
        if not self._session.samples:
            QMessageBox.information(self, "Export", "No telemetry samples to export.")
            return
        folder = self._settings.last_export_folder() or str(Path.home())
        name = f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export telemetry", str(Path(folder) / name), "CSV (*.csv)"
        )
        if not path:
            return
        self._settings.set_last_export_folder(str(Path(path).parent))
        self._settings.sync()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(TelemetrySession.csv_header())
                for s in self._session.samples:
                    w.writerow(s.as_csv_row())
            self._append_log(f"Exported {len(self._session.samples)} rows to {path}", ok=True)
        except OSError as e:
            QMessageBox.critical(self, "Export failed", str(e))

    @staticmethod
    def _style_repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)

    def _append_log(self, msg: str, ok: bool = False, warn: bool = False) -> None:
        line = timestamp_message(msg)
        self._log.appendPlainText(line)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())
        if ok:
            self._human_log.setObjectName("statusOk")
        elif warn:
            self._human_log.setObjectName("statusWarn")
        else:
            self._human_log.setObjectName("")
        self._human_log.setText(msg[:240])
        self._style_repolish(self._human_log)

    def _append_raw(self, text: str) -> None:
        self._raw_out.appendPlainText(text)
        self._raw_out.verticalScrollBar().setValue(self._raw_out.verticalScrollBar().maximum())

    def _log_workflow(self, wr: WorkflowResult) -> None:
        for step in wr.technical_steps:
            self._append_raw(
                f"=== {step.title} ===\nCMD: {' '.join(step.command)}\n"
                f"RC={step.returncode} timeout={step.timed_out}\n"
                f"--- stdout ---\n{step.stdout}\n--- stderr ---\n{step.stderr}\n"
            )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._app_status.setText("Busy…" if busy else "Ready")
        self._app_status.setObjectName("statusWarn" if busy else "statusOk")
        self._style_repolish(self._app_status)

    def _run_bg(self, fn, op: str = "generic") -> None:
        if self._workflow_thread and self._workflow_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait for the current operation.")
            return
        self._workflow_op = op
        self._set_busy(True)
        self._workflow_thread = FunctionRunnerThread(fn, self)
        self._workflow_thread.finished_ok.connect(self._on_workflow_done)
        self._workflow_thread.failed.connect(self._on_workflow_fail)
        self._workflow_thread.finished.connect(self._on_workflow_thread_finished)
        self._workflow_thread.start()

    @Slot()
    def _on_workflow_thread_finished(self) -> None:
        sender = self.sender()
        if sender is self._workflow_thread and self._workflow_thread is not None:
            self._workflow_thread.deleteLater()
            self._workflow_thread = None
        self._set_busy(False)

    @Slot(str)
    def _on_workflow_fail(self, err: str) -> None:
        self._append_log(f"Error: {err}", warn=True)
        QMessageBox.critical(self, "Error", err)

    @Slot(object)
    def _on_workflow_done(self, result: object) -> None:
        if not isinstance(result, WorkflowResult):
            return
        wr: WorkflowResult = result
        self._log_workflow(wr)

        if wr.devices is not None:
            self._populate_devices(wr.devices)

        op = self._workflow_op
        if wr.ok:
            self._append_log(wr.user_message, ok=True)
        else:
            self._append_log(wr.user_message, warn=True)
            if op != "refresh":
                QMessageBox.warning(self, "Operation", wr.user_message)

        if wr.ip:
            self._ip_display.setText(wr.ip)
            self._tcp_ip = wr.ip

        if op in ("connect_ip", "enable_wifi") and wr.ok:
            QTimer.singleShot(400, self._on_refresh_devices)

        if op == "enable_wifi" and wr.ok:
            self._conn_mode = ConnMode.TCP
        elif op == "disable_wifi":
            self._conn_mode = ConnMode.USB
        elif op == "connect_ip" and wr.ok:
            self._conn_mode = ConnMode.TCP
        elif op == "disconnect_tcp":
            self._conn_mode = ConnMode.USB

        self._apply_mode_to_header()
        self._settings.set_adb_path(self._adb_path.text().strip())
        self._settings.set_tcp_port(self._port_spin.value())
        self._settings.set_last_ssid(self._ssid.text().strip())
        self._settings.sync()

    def _populate_devices(self, devices: list[tuple[str, str]]) -> None:
        prev = self._current_target_serial()
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        for serial, state in devices:
            label = f"{serial}\t{state}"
            self._device_combo.addItem(label)
            idx = self._device_combo.count() - 1
            self._device_combo.setItemData(idx, state, Qt.ItemDataRole.ToolTipRole)
        self._device_combo.blockSignals(False)
        if prev:
            for i in range(self._device_combo.count()):
                if self._device_combo.itemText(i).startswith(prev):
                    self._device_combo.setCurrentIndex(i)
                    break

    def _on_device_changed(self, _t: str) -> None:
        self._apply_mode_to_header()

    def _apply_mode_to_header(self) -> None:
        t = self._current_target_serial()
        self._sel_device.setText(f"Device: {t or '—'}")
        if not t:
            self._conn_lbl.setText("Mode: Disconnected")
            self._tcp_info.setText("TCP: —")
            return
        if ":" in t:
            self._conn_lbl.setText("Mode: TCP/IP")
            self._tcp_info.setText(f"TCP: {t}")
        else:
            self._conn_lbl.setText("Mode: USB")
            ip = self._tcp_ip or self._ip_display.text().strip()
            p = self._port_spin.value()
            self._tcp_info.setText(f"TCP: {ip}:{p}" if ip else "TCP: —")

    def _on_auto_adb(self) -> None:
        cands = discover_adb_candidates()
        if cands:
            self._adb_path.setText(cands[0])
            self._settings.set_adb_path(cands[0])
            self._settings.sync()
            self._append_log(f"Auto-detected ADB: {cands[0]}", ok=True)
        else:
            self._append_log("Could not auto-detect adb.exe. Install Android platform-tools.", warn=True)

    def _on_refresh_devices(self) -> None:
        self._apply_controller_path()

        def job() -> WorkflowResult:
            self._apply_controller_path()
            _, wr = self._controller.refresh_devices()
            return wr

        self._run_bg(job, op="refresh")

    def _on_enable_wifi(self) -> None:
        self._apply_controller_path()
        serial = self._current_target_serial()
        if not serial or ":" in serial:
            QMessageBox.information(
                self,
                "Select USB device",
                "Choose a USB-attached device (not an IP:port entry) before enabling Wi-Fi ADB.",
            )
            return
        port = self._port_spin.value()

        def job() -> WorkflowResult:
            return self._controller.enable_adb_over_wifi(
                serial, port, self._ssid.text(), self._wifi_pass.text()
            )

        self._run_bg(job, op="enable_wifi")

    def _on_disable_wifi(self) -> None:
        self._apply_controller_path()
        ip = self._ip_display.text().strip() or self._tcp_ip
        port = self._port_spin.value()
        usb = self._controller.last_usb_serial() or (
            self._current_target_serial()
            if ":" not in self._current_target_serial()
            else ""
        )

        def job() -> WorkflowResult:
            return self._controller.disable_adb_over_wifi(usb, ip or None, port)

        self._run_bg(job, op="disable_wifi")

    def _on_connect_ip(self) -> None:
        self._apply_controller_path()
        ip = self._ip_display.text().strip()
        if not ip:
            text, ok = QInputDialog.getText(self, "ADB connect", "Device IP address:")
            if not ok or not text.strip():
                return
            ip = text.strip()
        port = self._port_spin.value()

        def job() -> WorkflowResult:
            return self._controller.connect_tcp_manual(ip, port)

        self._run_bg(job, op="connect_ip")

    def _on_disconnect_tcp(self) -> None:
        self._apply_controller_path()
        ip = self._ip_display.text().strip() or self._tcp_ip or None

        def job() -> WorkflowResult:
            return self._controller.disconnect_tcp(ip, self._port_spin.value())

        self._run_bg(job, op="disconnect_tcp")

    def _on_read_ip(self) -> None:
        self._apply_controller_path()
        serial = self._current_target_serial()
        if not serial:
            QMessageBox.warning(self, "Read IP", "Select a device first.")
            return

        def job() -> WorkflowResult:
            return self._controller.read_device_ip(serial)

        self._run_bg(job, op="read_ip")

    def _on_manual_shell(self) -> None:
        self._apply_controller_path()
        cmd = self._manual_cmd.text().strip()
        if not cmd:
            return
        serial = self._current_target_serial()

        def job() -> WorkflowResult:
            return self._controller.run_manual_shell(serial, cmd)

        self._run_bg(job, op="manual")

    def _on_copy_diag(self) -> None:
        text = self._log.toPlainText() + "\n\n" + self._raw_out.toPlainText()
        QGuiApplication.clipboard().setText(text)
        self._append_log("Diagnostics copied to clipboard.", ok=True)
