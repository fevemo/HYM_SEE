#!/usr/bin/env python3
"""
hik_camera_api.py
=================

Minimal Hikrobot / Hikvision USB camera API
with the same philosophy as your pump API.

Main functions
--------------
camera = HikCameraController()

camera.connect()
camera.set_exposure(200)      # µs
frame = camera.take_frame()

camera.disconnect()

Optional live mode for napari:
camera.start_live()
camera.latest
camera.stop_live()
"""

import os
import sys
import time
import threading
import numpy as np

from ctypes import *
from pathlib import Path
from typing import Optional


# ==========================================================
# SDK PATHS (adjust if needed)
# ==========================================================
os.add_dll_directory(
    r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
)

sdk_path = Path(__file__).resolve().parent / "Python" / "MvImport"
sys.path.insert(0, str(sdk_path))

from MvCameraControl_class import *
from CameraParams_header import *
from CameraParams_const import *


# ==========================================================
# Main API
# ==========================================================
class HikCameraController:
    """
    Minimal camera API.

    Methods
    -------
    connect()
    disconnect()

    set_exposure(us)

    take_frame()

    Optional:
    start_live()
    stop_live()

    latest -> most recent live frame
    """

    def __init__(self):

        self.cam = None
        self.connected = False

        self.payload_size = None
        self.buf = None
        self.frame_info = MV_FRAME_OUT_INFO_EX()

        self.running = False
        self.thread = None
        self.latest = None

        self.lock = threading.Lock()

    # ------------------------------------------------------
    # Context manager
    # ------------------------------------------------------
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ------------------------------------------------------
    # Connect
    # ------------------------------------------------------
    def connect(self):
        """
        Open first detected USB camera.
        """

        if self.connected:
            return

        deviceList = MV_CC_DEVICE_INFO_LIST()

        ret = MvCamera.MV_CC_EnumDevices(
            MV_USB_DEVICE,
            deviceList
        )

        if deviceList.nDeviceNum == 0:
            raise RuntimeError("No USB camera found.")

        self.cam = MvCamera()

        stDeviceList = cast(
            deviceList.pDeviceInfo[0],
            POINTER(MV_CC_DEVICE_INFO)
        ).contents

        self.cam.MV_CC_CreateHandle(stDeviceList)
        self.cam.MV_CC_OpenDevice()

        # disable auto exposure
        self.cam.MV_CC_SetEnumValue("ExposureAuto", 0)

        # payload size
        stParam = MVCC_INTVALUE()
        memset(byref(stParam), 0, sizeof(MVCC_INTVALUE))

        self.cam.MV_CC_GetIntValue(
            "PayloadSize",
            stParam
        )

        self.payload_size = stParam.nCurValue
        self.buf = (c_ubyte * self.payload_size)()

        self.connected = True

        print("[INFO] Camera connected.")

    # ------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------
    def disconnect(self):

        if not self.connected:
            return

        self.stop_live()

        self.cam.MV_CC_CloseDevice()
        self.cam.MV_CC_DestroyHandle()

        self.connected = False

        print("[INFO] Camera disconnected.")

    # ------------------------------------------------------
    # Exposure
    # ------------------------------------------------------
    def set_exposure(self, us: float):
        """
        Exposure in microseconds.
        """

        if not self.connected:
            raise RuntimeError("Connect first.")

        self.cam.MV_CC_SetFloatValue(
            "ExposureTime",
            float(us)
        )

    # ------------------------------------------------------
    # Single frame
    # ------------------------------------------------------
    def take_frame(self, timeout_ms=1000):
        """
        Acquire one frame and return numpy array.
        """

        if not self.connected:
            raise RuntimeError("Connect first.")

        with self.lock:

            self.cam.MV_CC_StartGrabbing()

            ret = self.cam.MV_CC_GetOneFrameTimeout(
                self.buf,
                self.payload_size,
                self.frame_info,
                timeout_ms
            )

            self.cam.MV_CC_StopGrabbing()

            if ret != 0:
                raise RuntimeError("Frame timeout.")

            img = np.ctypeslib.as_array(self.buf)

            img = img[
                :self.frame_info.nWidth *
                 self.frame_info.nHeight
            ]

            img = img.reshape(
                self.frame_info.nHeight,
                self.frame_info.nWidth
            ).copy()

            return img

    # ------------------------------------------------------
    # Live mode
    # ------------------------------------------------------
    def start_live(self):

        if self.running:
            return

        if not self.connected:
            raise RuntimeError("Connect first.")

        self.cam.MV_CC_StartGrabbing()

        self.running = True

        self.thread = threading.Thread(
            target=self._live_loop,
            daemon=True
        )

        self.thread.start()

    def _live_loop(self):

        while self.running:

            ret = self.cam.MV_CC_GetOneFrameTimeout(
                self.buf,
                self.payload_size,
                self.frame_info,
                1000
            )

            if ret == 0:

                img = np.ctypeslib.as_array(self.buf)

                img = img[
                    :self.frame_info.nWidth *
                     self.frame_info.nHeight
                ]

                img = img.reshape(
                    self.frame_info.nHeight,
                    self.frame_info.nWidth
                ).copy()

                self.latest = img

    def stop_live(self):

        if not self.running:
            return

        self.running = False
        time.sleep(0.05)

        self.cam.MV_CC_StopGrabbing()

    # ------------------------------------------------------
    # Utility
    # ------------------------------------------------------
    def wait(self, seconds):
        time.sleep(seconds)


# ==========================================================
# Example
# ==========================================================
if __name__ == "__main__":

    with HikCameraController() as cam:

        cam.set_exposure(200)

        frame = cam.take_frame()

        print(frame.shape, frame.dtype)