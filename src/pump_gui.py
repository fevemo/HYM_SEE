#!/usr/bin/env python3
"""
Poseidon Pump - Simple Jog GUI
==============================
Three pump columns with Forward / Backward buttons per pump.
Keyboard shortcuts:
  Pump 1 → Up / Down arrow keys
  Pump 2 → W / S keys
  Pump 3 → I / K keys

Usage:
    python pump_gui.py [--port /dev/tty.usbmodem14101]
"""

import argparse
import sys
import time
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from poseidon_api import (
    PoseidonController,
    SYRINGE_OPTIONS,
    SYRINGE_AREAS,
    _auto_port as _find_port,
    _to_steps as _displacement_to_steps_raw,
)

PUMP_COLORS     = ["#4A90D9", "#E67E22", "#27AE60"]
PUMP_LABELS     = ["Pump 1", "Pump 2", "Pump 3"]
UNIT_OPTIONS    = ["mm", "mL", "µL"]
MICROSTEP_OPTIONS = ["1", "2", "4", "8", "16", "32"]

KEY_BINDINGS = {
    0: (QtCore.Qt.Key_Up,  QtCore.Qt.Key_Down),
    1: (QtCore.Qt.Key_W,   QtCore.Qt.Key_S),
    2: (QtCore.Qt.Key_I,   QtCore.Qt.Key_K),
}


def _displacement_to_steps(value: float, unit: str, area_mm2: float, microsteps: int) -> float:
    return _displacement_to_steps_raw(value, unit, area_mm2, microsteps)


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread - delegates to PoseidonController.send_raw (blocking)
# ─────────────────────────────────────────────────────────────────────────────

class CommandWorker(QtCore.QThread):
    reply = QtCore.pyqtSignal(str)

    def __init__(self, ctrl: PoseidonController, cmd: str, parent=None):
        super().__init__(parent)
        self._ctrl = ctrl
        self._cmd  = cmd

    def run(self):
        resp = self._ctrl.send_raw(self._cmd, blocking=True)
        self.reply.emit(resp or "(no reply)")


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class PumpWindow(QtWidgets.QMainWindow):
    def __init__(self, port: Optional[str], speed: float, accel: float):
        super().__init__()
        self._port  = port
        self._speed = speed
        self._accel = accel
        self._ctrl: Optional[PoseidonController] = None
        self._active_pump = 0
        self._workers: list = []
        self._command_in_flight = False

        # Per-pump state (index 0-2)
        self._pump_unit = ["mm", "mm", "mm"]
        self._pump_area = [SYRINGE_AREAS[0]] * 3   # default: BD 1 mL
        self._microstepping = 1

        self.setWindowTitle("Poseidon Pump Controller")
        self.setMinimumWidth(720)
        self._build_ui()
        self._apply_key_hint_labels()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QWidget()
        self.setCentralWidget(root)
        vbox = QtWidgets.QVBoxLayout(root)
        vbox.setSpacing(12)
        vbox.setContentsMargins(16, 16, 16, 16)

        # ── Connection bar ──
        conn_row = QtWidgets.QHBoxLayout()
        self._port_combo = QtWidgets.QComboBox()
        self._refresh_ports()
        if self._port:
            idx = self._port_combo.findText(self._port)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)

        self._connect_btn = QtWidgets.QPushButton("Connect")
        self._connect_btn.setFixedWidth(90)
        self._connect_btn.clicked.connect(self._toggle_connect)

        self._refresh_btn = QtWidgets.QPushButton("⟳")
        self._refresh_btn.setFixedWidth(36)
        self._refresh_btn.setToolTip("Refresh ports")
        self._refresh_btn.clicked.connect(self._refresh_ports)

        conn_row.addWidget(QtWidgets.QLabel("Port:"))
        conn_row.addWidget(self._port_combo, stretch=1)
        conn_row.addWidget(self._refresh_btn)
        conn_row.addWidget(self._connect_btn)
        vbox.addLayout(conn_row)

        # ── Settings row ──
        settings_row = QtWidgets.QHBoxLayout()

        # Microstepping
        self._microstep_combo = QtWidgets.QComboBox()
        self._microstep_combo.addItems(MICROSTEP_OPTIONS)
        self._microstep_combo.setCurrentText("1")
        self._microstep_combo.currentTextChanged.connect(self._on_microstep_changed)
        self._microstep_combo.setToolTip("Microstepping level set on the stepper driver")

        # Jog amount (in physical units per pump - shares the active pump's unit)
        self._steps_spin = QtWidgets.QDoubleSpinBox()
        self._steps_spin.setRange(0.001, 999999)
        self._steps_spin.setDecimals(3)
        self._steps_spin.setValue(1.0)
        self._steps_spin.setToolTip("Jog distance in the unit chosen per pump below")

        # Speed (in unit/s)
        self._speed_spin = QtWidgets.QDoubleSpinBox()
        self._speed_spin.setRange(0.001, 50000)
        self._speed_spin.setDecimals(4)
        self._speed_spin.setValue(self._speed)
        self._speed_spin.setSuffix("  /s")
        self._speed_spin.setToolTip("Speed in the unit chosen per pump below, per second")
        self._speed_spin.valueChanged.connect(lambda v: setattr(self, "_speed", v))

        # Accel (in unit/s²)
        self._accel_spin = QtWidgets.QDoubleSpinBox()
        self._accel_spin.setRange(0.001, 999999)
        self._accel_spin.setDecimals(4)
        self._accel_spin.setValue(self._accel)
        self._accel_spin.setSuffix("  /s²")
        self._accel_spin.setToolTip("Acceleration in the unit chosen per pump below, per second²")
        self._accel_spin.valueChanged.connect(lambda v: setattr(self, "_accel", v))

        for label, widget in [("Microsteps:", self._microstep_combo),
                               ("Jog dist:",  self._steps_spin),
                               ("Speed:",     self._speed_spin),
                               ("Accel:",     self._accel_spin)]:
            settings_row.addWidget(QtWidgets.QLabel(label))
            settings_row.addWidget(widget)

        self._send_settings_btn = QtWidgets.QPushButton("Send Settings")
        self._send_settings_btn.clicked.connect(self._send_all_settings)
        self._send_settings_btn.setEnabled(False)
        settings_row.addWidget(self._send_settings_btn)
        vbox.addLayout(settings_row)

        # ── Divider ──
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        vbox.addWidget(line)

        # ── Pump columns ──
        pump_row = QtWidgets.QHBoxLayout()
        pump_row.setSpacing(12)
        self._pump_fwd_btns: list = []
        self._pump_bwd_btns: list = []
        self._pump_radio: list = []
        self._pump_key_labels: list = []

        for i in range(3):
            col = self._make_pump_column(i)
            pump_row.addLayout(col)
            if i < 2:
                sep = QtWidgets.QFrame()
                sep.setFrameShape(QtWidgets.QFrame.VLine)
                sep.setFrameShadow(QtWidgets.QFrame.Sunken)
                pump_row.addWidget(sep)

        vbox.addLayout(pump_row)

        # ── Stop button ──
        self._stop_btn = QtWidgets.QPushButton("■  STOP ALL")
        self._stop_btn.setFixedHeight(48)
        self._stop_btn.setFont(QtGui.QFont("Arial", 14, QtGui.QFont.Bold))
        self._stop_btn.setStyleSheet("background-color: #C0392B; color: white; border-radius: 6px;")
        self._stop_btn.clicked.connect(self._stop_all)
        self._stop_btn.setEnabled(False)
        vbox.addWidget(self._stop_btn)

        # ── Status bar ──
        self.statusBar().showMessage("Not connected.")

    def _make_pump_column(self, idx: int) -> QtWidgets.QVBoxLayout:
        color = PUMP_COLORS[idx]
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)

        # Header: radio + label
        header = QtWidgets.QHBoxLayout()
        radio = QtWidgets.QRadioButton()
        radio.setChecked(idx == 0)
        radio.toggled.connect(lambda checked, i=idx: self._set_active_pump(i) if checked else None)
        self._pump_radio.append(radio)

        lbl = QtWidgets.QLabel(PUMP_LABELS[idx])
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setFont(QtGui.QFont("Arial", 15, QtGui.QFont.Bold))
        lbl.setStyleSheet(f"color: {color};")
        header.addWidget(radio)
        header.addWidget(lbl, stretch=1)
        layout.addLayout(header)

        # Forward button
        fwd = QtWidgets.QPushButton("▲  Forward")
        fwd.setFixedHeight(56)
        fwd.setFont(QtGui.QFont("Arial", 12))
        fwd.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 6px;"
            "font-weight: bold;"
        )
        fwd.clicked.connect(lambda _, i=idx: self._move(i, "F"))
        fwd.setEnabled(False)
        self._pump_fwd_btns.append(fwd)
        layout.addWidget(fwd)

        # Backward button
        bwd = QtWidgets.QPushButton("▼  Backward")
        bwd.setFixedHeight(56)
        bwd.setFont(QtGui.QFont("Arial", 12))
        bwd.setStyleSheet(
            "background-color: #555; color: white; border-radius: 6px;"
            "font-weight: bold;"
        )
        bwd.clicked.connect(lambda _, i=idx: self._move(i, "B"))
        bwd.setEnabled(False)
        self._pump_bwd_btns.append(bwd)
        layout.addWidget(bwd)

        # Syringe selector
        syringe_row = QtWidgets.QHBoxLayout()
        syringe_lbl = QtWidgets.QLabel("Syringe:")
        syringe_lbl.setStyleSheet("font-size: 11px;")
        syringe_combo = QtWidgets.QComboBox()
        syringe_combo.addItems(SYRINGE_OPTIONS)
        syringe_combo.setToolTip("Syringe inner area used for mL/µL conversion")
        syringe_combo.currentIndexChanged.connect(
            lambda ci, i=idx: self._on_syringe_changed(i, ci)
        )
        syringe_row.addWidget(syringe_lbl)
        syringe_row.addWidget(syringe_combo)
        layout.addLayout(syringe_row)

        # Unit selector
        unit_row = QtWidgets.QHBoxLayout()
        unit_lbl = QtWidgets.QLabel("Units:")
        unit_lbl.setStyleSheet("font-size: 11px;")
        unit_combo = QtWidgets.QComboBox()
        unit_combo.addItems(UNIT_OPTIONS)
        unit_combo.setToolTip("Physical unit for jog distance, speed, and accel")
        unit_combo.currentTextChanged.connect(
            lambda text, i=idx: self._on_unit_changed(i, text)
        )
        unit_row.addWidget(unit_lbl)
        unit_row.addWidget(unit_combo)
        layout.addLayout(unit_row)

        # Keyboard hint label (filled later)
        hint = QtWidgets.QLabel()
        hint.setAlignment(QtCore.Qt.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        self._pump_key_labels.append(hint)
        layout.addWidget(hint)

        return layout

    def _apply_key_hint_labels(self):
        key_names = {
            QtCore.Qt.Key_Up: "↑", QtCore.Qt.Key_Down: "↓",
            QtCore.Qt.Key_W: "W", QtCore.Qt.Key_S: "S",
            QtCore.Qt.Key_I: "I", QtCore.Qt.Key_K: "K",
        }
        for i, (fwd_key, bwd_key) in KEY_BINDINGS.items():
            self._pump_key_labels[i].setText(
                f"Keys: {key_names[fwd_key]} fwd  /  {key_names[bwd_key]} bwd"
            )

    # ── Conversion helpers ───────────────────────────────────────────────────

    def _on_microstep_changed(self, text: str):
        self._microstepping = int(text)

    def _on_syringe_changed(self, pump_idx: int, combo_idx: int):
        self._pump_area[pump_idx] = SYRINGE_AREAS[combo_idx]

    def _on_unit_changed(self, pump_idx: int, unit: str):
        self._pump_unit[pump_idx] = unit

    def _pump_jog_steps(self, pump_idx: int) -> float:
        """Convert current jog-distance spin value to integer steps for pump_idx."""
        return _displacement_to_steps(
            self._steps_spin.value(),
            self._pump_unit[pump_idx],
            self._pump_area[pump_idx],
            self._microstepping,
        )

    def _pump_speed_steps(self, pump_idx: int) -> float:
        return _displacement_to_steps(
            self._speed_spin.value(),
            self._pump_unit[pump_idx],
            self._pump_area[pump_idx],
            self._microstepping,
        )

    def _pump_accel_steps(self, pump_idx: int) -> float:
        return _displacement_to_steps(
            self._accel_spin.value(),
            self._pump_unit[pump_idx],
            self._pump_area[pump_idx],
            self._microstepping,
        )

    # ── Port helpers ─────────────────────────────────────────────────────────

    def _refresh_ports(self):
        import serial.tools.list_ports as _lp
        self._port_combo.clear()
        ports = [p.device for p in _lp.comports()]
        if ports:
            self._port_combo.addItems(ports)
        else:
            self._port_combo.addItem("(no ports found)")

    # ── Connection ───────────────────────────────────────────────────────────

    def _toggle_connect(self):
        if self._ctrl is None:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        port = self._port_combo.currentText()
        if not port or port.startswith("("):
            self.statusBar().showMessage("No valid port selected.")
            return
        try:
            self._ctrl = PoseidonController(
                port=port,
                microsteps=self._microstepping,
                syringe=SYRINGE_OPTIONS[0],
            )
            self._ctrl.connect()
            self.statusBar().showMessage(f"Connected to {port}.")
            self._connect_btn.setText("Disconnect")
            self._set_controls_enabled(True)
        except Exception as exc:
            self.statusBar().showMessage(f"Connection failed: {exc}")
            self._ctrl = None

    def _disconnect(self):
        if self._ctrl:
            try:
                self._ctrl.disconnect()
            except Exception:
                pass
            self._ctrl = None
        self._command_in_flight = False
        self._connect_btn.setText("Connect")
        self._set_controls_enabled(False)
        self.statusBar().showMessage("Disconnected.")

    def _set_controls_enabled(self, state: bool):
        for btn in self._pump_fwd_btns + self._pump_bwd_btns:
            btn.setEnabled(state)
        self._stop_btn.setEnabled(state)
        self._send_settings_btn.setEnabled(state)

    # ── Pump control ─────────────────────────────────────────────────────────

    def _set_active_pump(self, idx: int):
        self._active_pump = idx
        self.statusBar().showMessage(
            f"Keyboard now controls {PUMP_LABELS[idx]}  "
            f"(↑/↓ or W/S or I/K)"
        )

    def _move(self, pump_idx: int, direction: str):
        if not self._ctrl or not self._ctrl.connected:
            return
        raw_steps = self._pump_jog_steps(pump_idx)
        signed_steps = raw_steps if direction == "F" else -raw_steps
        d = [0.0, 0.0, 0.0]
        d[pump_idx] = signed_steps
        cmd   = f"<RUN,DIST,{pump_idx + 1},0.0,F,{d[0]},{d[1]},{d[2]}>"
        label = "FORWARD" if direction == "F" else "BACKWARD"
        unit  = self._pump_unit[pump_idx]
        self.statusBar().showMessage(
            f"{PUMP_LABELS[pump_idx]} → {label}  "
            f"{self._steps_spin.value():.3f} {unit}  ({int(abs(raw_steps))} steps)"
        )
        self._dispatch(cmd)

    def _stop_all(self):
        if not self._ctrl or not self._ctrl.connected:
            return
        self.statusBar().showMessage("Stopping all pumps…")
        # Fire-and-forget: stop reaches the Arduino as fast as possible
        self._ctrl.stop(blocking=False)

    def _send_all_settings(self):
        if not self._ctrl or not self._ctrl.connected:
            return
        self._send_settings_btn.setEnabled(False)
        self.statusBar().showMessage("Sending settings…")

        # Capture values now (on the main thread) before handing off
        speed_val  = self._speed_spin.value()
        accel_val  = self._accel_spin.value()
        pump_units = list(self._pump_unit)
        pump_areas = list(self._pump_area)
        microsteps = self._microstepping
        ctrl       = self._ctrl

        def _do_send():
            for i in range(3):
                pid  = i + 1
                unit = pump_units[i]
                ctrl._area       = pump_areas[i]
                ctrl._microsteps = microsteps
                ctrl.set_speed(pid, speed_val, unit, blocking=True)
                ctrl.set_accel(pid, accel_val, unit, blocking=True)

        worker = QtCore.QThread(parent=self)
        # Use a QObject to run the work inside the thread
        class _Runner(QtCore.QObject):
            done = QtCore.pyqtSignal()
            def run(self_):
                try:
                    _do_send()
                finally:
                    self_.done.emit()

        runner = _Runner()
        runner.moveToThread(worker)
        worker.started.connect(runner.run)

        def _on_done():
            self.statusBar().showMessage("Settings sent to all pumps.")
            self._send_settings_btn.setEnabled(True)
            worker.quit()  # ask the thread to exit; don't block with wait()

        runner.done.connect(_on_done)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        worker.start()

    def _dispatch(self, cmd: str):
        if self._command_in_flight:
            self.statusBar().showMessage("Busy - please wait for the previous command to finish.")
            return
        self._command_in_flight = True
        worker = CommandWorker(self._ctrl, cmd, parent=self)
        worker.reply.connect(lambda r: (print(f"[RX] {r}"), self.statusBar().showMessage(f"Arduino: {r}")))
        worker.finished.connect(lambda: self._on_worker_done(worker))
        self._workers.append(worker)

        # Safety net: release the lock after 5 s even if the worker hangs
        # (e.g. serial port becomes unresponsive on macOS)
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_worker_timeout(worker, timer))
        worker._timeout_timer = timer
        timer.start(5000)

        worker.start()

    def _on_worker_done(self, worker: CommandWorker):
        timer = getattr(worker, "_timeout_timer", None)
        if timer is not None:
            timer.stop()
        self._command_in_flight = False
        if worker in self._workers:
            self._workers.remove(worker)

    def _on_worker_timeout(self, worker: CommandWorker, timer: QtCore.QTimer):
        timer.stop()
        if self._command_in_flight:
            self.statusBar().showMessage("Warning: command timed out – serial may be unresponsive.")
            self._command_in_flight = False
        if worker in self._workers:
            self._workers.remove(worker)

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if not self._ctrl or not self._ctrl.connected:
            return

        key = event.key()
        if event.isAutoRepeat():
            return  # ignore key-repeat

        for pump_idx, (fwd_key, bwd_key) in KEY_BINDINGS.items():
            if key == fwd_key:
                # also update the radio button to reflect selection
                self._pump_radio[pump_idx].setChecked(True)
                self._move(pump_idx, "F")
                return
            if key == bwd_key:
                self._pump_radio[pump_idx].setChecked(True)
                self._move(pump_idx, "B")
                return

        super().keyPressEvent(event)

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._disconnect()
        event.accept()



# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poseidon Pump Jog GUI")
    p.add_argument("--port",  default=None,   help="Serial port (auto-detected if omitted)")
    p.add_argument("--speed", type=float, default=1.0,    help="Initial speed value (in chosen units/s)")
    p.add_argument("--accel", type=float, default=1.0,    help="Initial accel value (in chosen units/s²)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    port = args.port or _find_port()

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    win = PumpWindow(
        port=port,
        speed=args.speed,
        accel=args.accel,
    )
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
