#!/usr/bin/env python3
"""
hik_camera_gui.py
=================

Napari GUI for Hikrobot camera

Features
--------
- Live image layer
- Live minus reference layer
- Exposure control
- Choose save folder
- Save current frame
- Register reference image
- Reference saved as TIFF
- Reference filename stores:
    reference number
    exposure at acquisition
"""

import numpy as np
import napari

from pathlib import Path
from datetime import datetime
from tifffile import imwrite

from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSlider,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
)

from qtpy.QtCore import Qt, QTimer

from hik_camera_api import HikCameraController


# ==========================================================
# GUI Widget
# ==========================================================
class ControlWidget(QWidget):

    def __init__(self, camera):
        super().__init__()

        self.camera = camera

        self.min_exp = 1
        self.max_exp = 1000
        self.default_exp = 200

        self.save_folder = Path.cwd()

        self.reference = None
        self.reference_index = 1

        layout = QVBoxLayout()

        # --------------------------------------------------
        # Exposure title
        title = QLabel("Exposure (µs)")
        layout.addWidget(title)

        # --------------------------------------------------
        # Exposure row
        row = QHBoxLayout()

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(self.min_exp)
        self.slider.setMaximum(self.max_exp)
        self.slider.setValue(self.default_exp)
        self.slider.setSingleStep(5)

        self.edit = QLineEdit(str(self.default_exp))
        self.edit.setFixedWidth(80)
        self.edit.setAlignment(Qt.AlignCenter)

        row.addWidget(self.slider)
        row.addWidget(self.edit)

        layout.addLayout(row)

        # --------------------------------------------------
        # Folder label
        self.folder_label = QLabel(
            f"Save folder:\n{self.save_folder}"
        )
        layout.addWidget(self.folder_label)

        # --------------------------------------------------
        # Buttons
        self.folder_button = QPushButton(
            "Choose Folder"
        )
        layout.addWidget(self.folder_button)

        self.save_button = QPushButton(
            "Save Frame (.tiff)"
        )
        layout.addWidget(self.save_button)

        self.ref_button = QPushButton(
            "Register Reference"
        )
        layout.addWidget(self.ref_button)

        self.ref_label = QLabel(
            "Reference: None"
        )
        layout.addWidget(self.ref_label)

        self.setLayout(layout)

        # --------------------------------------------------
        # Signals
        self.slider.valueChanged.connect(
            self.slider_changed
        )

        self.edit.returnPressed.connect(
            self.edit_changed
        )

        self.folder_button.clicked.connect(
            self.choose_folder
        )

        self.save_button.clicked.connect(
            self.save_frame
        )

        self.ref_button.clicked.connect(
            self.register_reference
        )

    # ------------------------------------------------------
    # Exposure slider moved
    def slider_changed(self, value):

        self.edit.setText(str(value))
        self.camera.set_exposure(value)

    # ------------------------------------------------------
    # Manual exposure typing
    def edit_changed(self):

        try:
            value = int(self.edit.text())

            if value < self.min_exp:
                value = self.min_exp

            if value > self.max_exp:
                value = self.max_exp

            self.slider.setValue(value)
            self.camera.set_exposure(value)

        except ValueError:
            self.edit.setText(
                str(self.slider.value())
            )

    # ------------------------------------------------------
    # Choose save folder
    def choose_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Save Folder",
            str(self.save_folder)
        )

        if folder:
            self.save_folder = Path(folder)

            self.folder_label.setText(
                f"Save folder:\n{self.save_folder}"
            )

    # ------------------------------------------------------
    # Save current frame
    def save_frame(self):

        if self.camera.latest is None:
            print("No frame available.")
            return

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            self.save_folder /
            f"frame_{timestamp}.tiff"
        )

        imwrite(filename, self.camera.latest)

        print(f"Saved frame: {filename}")

    # ------------------------------------------------------
    # Register reference
    def register_reference(self):

        if self.camera.latest is None:
            print("No frame available.")
            return

        self.reference = self.camera.latest.copy()

        exposure = self.slider.value()

        filename = (
            self.save_folder /
            f"reference_"
            f"{self.reference_index:03d}"
            f"_exp_{exposure}us.tiff"
        )

        imwrite(filename, self.reference)

        self.ref_label.setText(
            f"Reference: #{self.reference_index}"
        )

        print(f"Reference saved: {filename}")

        self.reference_index += 1


# ==========================================================
# Main
# ==========================================================
def main():

    cam = HikCameraController()

    cam.connect()
    cam.set_exposure(200)
    cam.start_live()

    viewer = napari.Viewer()

    # ------------------------------------------------------
    # Live layer
    live_layer = viewer.add_image(
        np.zeros((2048, 3072), dtype=np.uint8),
        name="Live"
    )

    # ------------------------------------------------------
    # Subtracted layer
    sub_layer = viewer.add_image(
        np.zeros((2048, 3072), dtype=np.int16),
        name="Live - Reference"
    )

    # ------------------------------------------------------
    widget = ControlWidget(cam)

    viewer.window.add_dock_widget(
        widget,
        area="right"
    )

    # ------------------------------------------------------
    timer = QTimer()

    first_frame = {"done": False}

    def refresh():

        if cam.latest is None:
            return

        img = cam.latest

        # update live image
        live_layer.data = img

        # update subtraction
        if widget.reference is not None:

            diff = (
                img.astype(np.int16)
                - widget.reference.astype(np.int16)
            )

            sub_layer.data = diff

        if not first_frame["done"]:
            viewer.reset_view()
            first_frame["done"] = True

    timer.timeout.connect(refresh)
    timer.start(30)

    # ------------------------------------------------------
    # Cleanup
    def cleanup():
        cam.disconnect()

    viewer.window.qt_viewer.destroyed.connect(
        cleanup
    )

    napari.run()


# ==========================================================
if __name__ == "__main__":
    main()