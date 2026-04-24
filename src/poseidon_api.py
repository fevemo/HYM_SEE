#!/usr/bin/env python3
"""
poseidon_api.py  -  Poseidon Pump serial API
=============================================

Two sending modes
-----------------
blocking=True  (default)
    Sends the command and waits for the Arduino's reply frame before returning.
    Use this for settings and for precise sequenced moves.

blocking=False  (fire-and-forget)
    Writes the bytes to the serial buffer and returns immediately without
    reading a reply.  Latency is essentially zero (just the USB write).
    Use this for start/stop automation where timing matters.

Quick start
-----------
    from poseidon_api import PoseidonController

    with PoseidonController("/dev/tty.usbmodem14101", microsteps=32) as pump:
        pump.set_speed(1, 1.0, "mL")
        pump.set_accel(1, 2.0, "mL")

        # ── fire-and-forget style (fast start / stop) ──
        pump.run_continuous(pumps=[1], direction="F", blocking=False)
        time.sleep(2.0)
        pump.stop(blocking=False)

        # ── blocking style (precise displacement) ──
        pump.move(1, 0.5, "mL", "F", blocking=True)
"""

import time
from threading import Lock
from typing import List, Optional

import serial
import serial.tools.list_ports

# ── Constants ─────────────────────────────────────────────────────────────────

BAUD_RATE = 230400

SYRINGE_OPTIONS = [
    "BD 1 mL", "BD 3 mL", "BD 5 mL",
    "BD 10 mL", "BD 20 mL", "BD 30 mL", "BD 60 mL",
]
SYRINGE_AREAS = [
    17.34206347, 57.88559215, 112.9089185,
    163.539454,  285.022957,  366.0961536, 554.0462538,
]  # mm² inner cross-section (BD plastic syringes)

# ── Conversion helpers ────────────────────────────────────────────────────────

def _mm2steps(mm: float, microsteps: int) -> float:
    """1 rev = 0.8 mm, 200 full steps/rev."""
    return mm / 0.8 * 200.0 * microsteps

def _to_steps(value: float, unit: str, area_mm2: float, microsteps: int) -> float:
    if unit == "mm":
        return _mm2steps(value, microsteps)
    if unit == "mL":
        return _mm2steps(value * 1000.0 / area_mm2, microsteps)
    if unit == "uL":
        return _mm2steps(value / area_mm2, microsteps)
    raise ValueError(f"Unknown unit '{unit}'. Use 'mm', 'mL', or 'µL'.")

# ── Serial low-level helpers ──────────────────────────────────────────────────

def _auto_port() -> Optional[str]:
    tokens = ["usbmodem", "usbserial", "wchusbserial", "ttyACM", "ttyUSB"]
    ports  = [p.device for p in serial.tools.list_ports.comports()]
    for tok in tokens:
        for p in ports:
            if tok.lower() in p.lower():
                return p
    return ports[0] if ports else None


def _read_frame(ser: serial.Serial, timeout_s: float = 2.0) -> Optional[str]:
    """Read one '<…>' reply frame from the Arduino."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        b = ser.read(1)
        if b == b"<":
            break
    else:
        return None
    buf = bytearray()
    while time.time() < deadline:
        b = ser.read(1)
        if b == b">":
            return buf.decode("utf-8", errors="replace")
        buf.extend(b)
    return None


# ── Main API class ────────────────────────────────────────────────────────────

class PoseidonController:
    """
    Serial API for one Poseidon controller board (up to 3 pumps).

    Parameters
    ----------
    port        : Serial port string, or None to auto-detect.
    microsteps  : Microstepping level matching the physical driver jumper (1-32).
    syringe     : Syringe name from SYRINGE_OPTIONS (for mL/µL unit conversion).
    """

    def __init__(
        self,
        port: Optional[str] = None,
        microsteps: int = 32,
        syringe: str = "BD 1 mL",
    ):
        self._port       = port or _auto_port()
        self._microsteps = microsteps
        syringe_idx      = SYRINGE_OPTIONS.index(syringe)
        self._area       = SYRINGE_AREAS[syringe_idx]
        self._ser: Optional[serial.Serial] = None
        self._lock       = Lock()   # guards concurrent serial writes from threads

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "PoseidonController":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open the serial port and wait for the Arduino to boot."""
        print(f"[INFO] Connecting to {self._port} @ {BAUD_RATE} baud…")
        self._ser = serial.Serial(
            port=self._port, baudrate=BAUD_RATE, timeout=0.1
        )
        time.sleep(2.5)  # Arduino resets on serial open
        hello = _read_frame(self._ser, timeout_s=3.0)
        print(f"[INFO] Arduino: {hello or '(no greeting)'}")

    def disconnect(self) -> None:
        """Close the serial port."""
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        print("[INFO] Disconnected.")

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ── Raw send ──────────────────────────────────────────────────────────────

    def send_raw(self, cmd: str, blocking: bool = True) -> Optional[str]:
        """
        Send a raw '<…>' command string.

        Parameters
        ----------
        cmd      : Full command string including angle brackets.
        blocking : If True, wait for and return the Arduino reply frame.
                   If False, write and return immediately (fire-and-forget).

        Returns
        -------
        Reply string (blocking) or None (fire-and-forget / timeout).
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
        if not (cmd.startswith("<") and cmd.endswith(">")):
            raise ValueError(f"Command must be wrapped in <>: {cmd}")

        print(f"[TX] {cmd}")
        with self._lock:
            self._ser.write(cmd.encode("utf-8"))
            self._ser.flush()
            if not blocking:
                return None
            reply = _read_frame(self._ser, timeout_s=2.0)

        print(f"[RX] {reply or '(no reply)'}")
        return reply

    # ── Settings ──────────────────────────────────────────────────────────────

    def set_speed(self, pump: int, value: float, unit: str = "mm",
                  blocking: bool = True) -> Optional[str]:
        """Set speed for pump 1-3 in physical units per second."""
        steps = _to_steps(value, unit, self._area, self._microsteps)
        return self.send_raw(
            f"<SETTING,SPEED,{pump},{steps:.4f},F,0.0,0.0,0.0>", blocking
        )

    def set_accel(self, pump: int, value: float, unit: str = "mm",
                  blocking: bool = True) -> Optional[str]:
        """Set acceleration for pump 1-3 in physical units per second²."""
        steps = _to_steps(value, unit, self._area, self._microsteps)
        return self.send_raw(
            f"<SETTING,ACCEL,{pump},{steps:.4f},F,0.0,0.0,0.0>", blocking
        )

    # ── Motion: fixed displacement ────────────────────────────────────────────

    def move(self, pump: int, value: float, unit: str = "mm",
             direction: str = "F", blocking: bool = True) -> Optional[str]:
        """
        Move one pump by a fixed displacement and (optionally) wait for reply.

        The Arduino moves asynchronously once the command is received;
        'blocking' here only controls whether Python waits for the serial ACK,
        not for the motor to finish.
        """
        steps  = _to_steps(value, unit, self._area, self._microsteps)
        signed = steps if direction == "F" else -steps
        d      = [0.0, 0.0, 0.0]
        d[pump - 1] = signed
        return self.send_raw(
            f"<RUN,DIST,{pump},0.0,F,{d[0]},{d[1]},{d[2]}>", blocking
        )

    def move_all(self, values: List[float], unit: str = "mm",
                 direction: str = "F", blocking: bool = True) -> Optional[str]:
        """
        Move all 3 pumps simultaneously by given displacements.
        values = [v1, v2, v3]; use 0.0 to skip a pump.
        """
        d = [
            _to_steps(v, unit, self._area, self._microsteps)
            * (1 if direction == "F" else -1)
            for v in values
        ]
        return self.send_raw(
            f"<RUN,DIST,123,0.0,F,{d[0]},{d[1]},{d[2]}>", blocking
        )

    # ── Motion: continuous (run until stop) ───────────────────────────────────

    def run_continuous(
        self,
        pumps: List[int],
        direction: str = "F",
        blocking: bool = False,
    ) -> Optional[str]:
        """
        Start one or more pumps at their configured speed indefinitely.

        The firmware treats a distance of 999999 as "run until stopped",
        which is the same behaviour as the original RUN mode.

        Parameters
        ----------
        pumps     : List of pump IDs to run, e.g. [1], [1, 3], [1, 2, 3].
        direction : 'F' forward, 'B' backward.
        blocking  : False by default - returns immediately after writing
                    the command so you can time the stop precisely.
        """
        pump_str = "".join(str(p) for p in sorted(pumps))
        sign     = 1 if direction == "F" else -1
        dist     = sign * 999999.0
        # set distance for selected pumps only
        d = [dist if (i + 1) in pumps else 0.0 for i in range(3)]
        return self.send_raw(
            f"<RUN,DIST,{pump_str},0.0,F,{d[0]},{d[1]},{d[2]}>", blocking
        )

    # ── Stop ──────────────────────────────────────────────────────────────────

    def stop(self, blocking: bool = False) -> Optional[str]:
        """
        Stop all pumps immediately.

        blocking=False by default so the stop byte hits the Arduino as fast
        as possible - the OS serial buffer is flushed right away.
        """
        return self.send_raw("<STOP,BLAH,BLAH,BLAH,F,0.0,0.0,0.0>", blocking)

    # ── Convenience ───────────────────────────────────────────────────────────

    def wait(self, seconds: float) -> None:
        """Simple time-based wait between commands."""
        time.sleep(seconds)


# ── Smoke-test / example ──────────────────────────────────────────────────────

if __name__ == "__main__":
    with PoseidonController(microsteps=32, syringe="BD 1 mL") as pump:
        stop_delay = 1
        for pump_id in [1, 2]:
            pump.set_speed(pump_id, 1, "uL")
            pump.set_accel(pump_id, 10.0, "uL")

        for i in range(10):
            print("Both pumps")
            pump.run_continuous([1,2], direction="B", blocking=False)
            time.sleep(3)
            pump.stop(blocking=False)
            time.sleep(stop_delay)
            print("Pump 1")
            pump.run_continuous([1], direction="B", blocking=False)
            time.sleep(3)
            pump.stop(blocking=False)
            time.sleep(stop_delay)
            print("Pump 2")
            pump.run_continuous([2], direction="B", blocking=False)
            time.sleep(3)
            pump.stop(blocking=False)
            time.sleep(stop_delay)

        # print("\n── Blocking: precise 0.5 mL dispense ──")
        # pump.move(2, 0.5, "mL", "F", blocking=True)
