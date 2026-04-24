# #!/usr/bin/env python3
# """
# hik_camera_gui.py
# =================

# Napari GUI for Hikrobot camera

# Features
# --------
# - Live image layer
# - Live minus reference layer
# - Exposure control
# - Choose save folder
# - Save current frame
# - Register reference image
# - Reference saved as TIFF
# - Reference filename stores:
#     reference number
#     exposure at acquisition
# """

# import numpy as np
# import napari

# from pathlib import Path
# from datetime import datetime
# from tifffile import imwrite

# from qtpy.QtWidgets import (
#     QWidget,
#     QVBoxLayout,
#     QLabel,
#     QSlider,
#     QLineEdit,
#     QHBoxLayout,
#     QPushButton,
#     QFileDialog,
# )

# from qtpy.QtCore import Qt, QTimer

# from hik_camera_api import HikCameraController


# # ==========================================================
# # GUI Widget
# # ==========================================================
# class ControlWidget(QWidget):

#     def __init__(self, camera):
#         super().__init__()

#         self.camera = camera

#         self.min_exp = 1
#         self.max_exp = 1000
#         self.default_exp = 200

#         self.save_folder = Path.cwd()

#         self.reference = None
#         self.reference_index = 1

#         layout = QVBoxLayout()

#         # --------------------------------------------------
#         # Exposure title
#         title = QLabel("Exposure (µs)")
#         layout.addWidget(title)

#         # --------------------------------------------------
#         # Exposure row
#         row = QHBoxLayout()

#         self.slider = QSlider(Qt.Horizontal)
#         self.slider.setMinimum(self.min_exp)
#         self.slider.setMaximum(self.max_exp)
#         self.slider.setValue(self.default_exp)
#         self.slider.setSingleStep(5)

#         self.edit = QLineEdit(str(self.default_exp))
#         self.edit.setFixedWidth(80)
#         self.edit.setAlignment(Qt.AlignCenter)

#         row.addWidget(self.slider)
#         row.addWidget(self.edit)

#         layout.addLayout(row)

#         # --------------------------------------------------
#         # Folder label
#         self.folder_label = QLabel(
#             f"Save folder:\n{self.save_folder}"
#         )
#         layout.addWidget(self.folder_label)

#         # --------------------------------------------------
#         # Buttons
#         self.folder_button = QPushButton(
#             "Choose Folder"
#         )
#         layout.addWidget(self.folder_button)

#         self.save_button = QPushButton(
#             "Save Frame (.tiff)"
#         )
#         layout.addWidget(self.save_button)

#         self.ref_button = QPushButton(
#             "Register Reference"
#         )
#         layout.addWidget(self.ref_button)

#         self.ref_label = QLabel(
#             "Reference: None"
#         )
#         layout.addWidget(self.ref_label)

#         self.setLayout(layout)

#         # --------------------------------------------------
#         # Signals
#         self.slider.valueChanged.connect(
#             self.slider_changed
#         )

#         self.edit.returnPressed.connect(
#             self.edit_changed
#         )

#         self.folder_button.clicked.connect(
#             self.choose_folder
#         )

#         self.save_button.clicked.connect(
#             self.save_frame
#         )

#         self.ref_button.clicked.connect(
#             self.register_reference
#         )

#     # ------------------------------------------------------
#     # Exposure slider moved
#     def slider_changed(self, value):

#         self.edit.setText(str(value))
#         self.camera.set_exposure(value)

#     # ------------------------------------------------------
#     # Manual exposure typing
#     def edit_changed(self):

#         try:
#             value = int(self.edit.text())

#             if value < self.min_exp:
#                 value = self.min_exp

#             if value > self.max_exp:
#                 value = self.max_exp

#             self.slider.setValue(value)
#             self.camera.set_exposure(value)

#         except ValueError:
#             self.edit.setText(
#                 str(self.slider.value())
#             )

#     # ------------------------------------------------------
#     # Choose save folder
#     def choose_folder(self):

#         folder = QFileDialog.getExistingDirectory(
#             self,
#             "Choose Save Folder",
#             str(self.save_folder)
#         )

#         if folder:
#             self.save_folder = Path(folder)

#             self.folder_label.setText(
#                 f"Save folder:\n{self.save_folder}"
#             )

#     # ------------------------------------------------------
#     # Save current frame
#     def save_frame(self):

#         if self.camera.latest is None:
#             print("No frame available.")
#             return

#         timestamp = datetime.now().strftime(
#             "%Y%m%d_%H%M%S"
#         )

#         filename = (
#             self.save_folder /
#             f"frame_{timestamp}.tiff"
#         )

#         imwrite(filename, self.camera.latest)

#         print(f"Saved frame: {filename}")

#     # ------------------------------------------------------
#     # Register reference
#     def register_reference(self):

#         if self.camera.latest is None:
#             print("No frame available.")
#             return

#         self.reference = self.camera.latest.copy()

#         exposure = self.slider.value()

#         filename = (
#             self.save_folder /
#             f"reference_"
#             f"{self.reference_index:03d}"
#             f"_exp_{exposure}us.tiff"
#         )

#         imwrite(filename, self.reference)

#         self.ref_label.setText(
#             f"Reference: #{self.reference_index}"
#         )

#         print(f"Reference saved: {filename}")

#         self.reference_index += 1


# # ==========================================================
# # Main
# # ==========================================================
# def main():

#     cam = HikCameraController()

#     cam.connect()
#     cam.set_exposure(200)
#     cam.start_live()

#     viewer = napari.Viewer()

#     # ------------------------------------------------------
#     # Live layer
#     live_layer = viewer.add_image(
#         np.zeros((2048, 3072), dtype=np.uint8),
#         name="Live"
#     )

#     # ------------------------------------------------------
#     # Subtracted layer
#     sub_layer = viewer.add_image(
#         np.zeros((2048, 3072), dtype=np.int16),
#         name="Live - Reference"
#     )

#     # ------------------------------------------------------
#     widget = ControlWidget(cam)

#     viewer.window.add_dock_widget(
#         widget,
#         area="right"
#     )

#     # ------------------------------------------------------
#     timer = QTimer()

#     first_frame = {"done": False}

#     def refresh():

#         if cam.latest is None:
#             return

#         img = cam.latest

#         # update live image
#         live_layer.data = img

#         # update subtraction
#         if widget.reference is not None:

#             diff = (
#                 img.astype(np.int16)
#                 - widget.reference.astype(np.int16)
#             )

#             sub_layer.data = diff

#         if not first_frame["done"]:
#             viewer.reset_view()
#             first_frame["done"] = True

#     timer.timeout.connect(refresh)
#     timer.start(30)

#     # ------------------------------------------------------
#     # Cleanup
#     def cleanup():
#         cam.disconnect()

#     viewer.window.qt_viewer.destroyed.connect(
#         cleanup
#     )

#     napari.run()


# # ==========================================================
# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
"""
hik_camera_gui.py
=================

Camera GUI + integrated pump controls
"""

import time
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
from poseidon_api import PoseidonController


# ==========================================================
# GUI Widget
# ==========================================================
class ControlWidget(QWidget):

    def __init__(self, camera):
        super().__init__()

        self.camera = camera

        # ---------------------------------
        # Pump controller
        self.pump = None
        try:
            self.pump = PoseidonController(port="COM5")
            self.pump.connect()
            print("Pump connected.")
        except Exception as e:
            print("Pump not connected:", e)

        self.min_exp = 1
        self.max_exp = 1000
        self.default_exp = 200

        self.save_folder = Path.cwd()

        self.reference = None
        self.reference_index = 1

        layout = QVBoxLayout()

        # ==================================================
        # Exposure
        # ==================================================
        title = QLabel("Exposure (µs)")
        layout.addWidget(title)

        row = QHBoxLayout()

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(self.min_exp)
        self.slider.setMaximum(self.max_exp)
        self.slider.setValue(self.default_exp)

        self.edit = QLineEdit(str(self.default_exp))
        self.edit.setFixedWidth(80)

        row.addWidget(self.slider)
        row.addWidget(self.edit)

        layout.addLayout(row)

        # ==================================================
        # Save folder
        # ==================================================
        self.folder_label = QLabel(
            f"Save folder:\n{self.save_folder}"
        )
        layout.addWidget(self.folder_label)

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

        # ==================================================
        # Pump controls
        # ==================================================
        layout.addWidget(QLabel("Pump 1 speed (µL/s)"))

        self.pump1_speed = QLineEdit("1.0")
        layout.addWidget(self.pump1_speed)

        layout.addWidget(QLabel("Pump 2 speed (µL/s)"))

        self.pump2_speed = QLineEdit("1.0")
        layout.addWidget(self.pump2_speed)

        self.run_p1 = QPushButton("Run pump 1")
        self.run_p2 = QPushButton("Run pump 2")
        self.run_both = QPushButton("Run both pumps")
        self.stop_all = QPushButton("Stop all pumps")

        layout.addWidget(self.run_p1)
        layout.addWidget(self.run_p2)
        layout.addWidget(self.run_both)
        layout.addWidget(self.stop_all)

        self.setLayout(layout)

        # ==================================================
        # Signals
        # ==================================================
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

        self.run_p1.clicked.connect(
            self.run_pump1
        )

        self.run_p2.clicked.connect(
            self.run_pump2
        )

        self.run_both.clicked.connect(
            self.run_both_pumps
        )

        self.stop_all.clicked.connect(
            self.stop_pumps
        )

    # ======================================================
    # Camera functions
    # ======================================================
    def slider_changed(self, value):

        self.edit.setText(str(value))
        self.camera.set_exposure(value)

    def edit_changed(self):

        try:
            value = int(self.edit.text())
            self.slider.setValue(value)
            self.camera.set_exposure(value)

        except:
            pass

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

    def save_frame(self):

        if self.camera.latest is None:
            return

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            self.save_folder /
            f"frame_{timestamp}.tiff"
        )

        imwrite(filename, self.camera.latest)

        print("Saved:", filename)

    def register_reference(self):

        if self.camera.latest is None:
            return

        self.reference = self.camera.latest.copy()

        exposure = self.slider.value()

        filename = (
            self.save_folder /
            f"reference_{self.reference_index:03d}"
            f"_exp_{exposure}us.tiff"
        )

        imwrite(filename, self.reference)

        self.ref_label.setText(
            f"Reference #{self.reference_index}"
        )

        self.reference_index += 1

    # ======================================================
    # Pump functions
    # ======================================================
    def run_pump1(self):

        if self.pump is None:
            return

        speed = float(self.pump1_speed.text())

        self.pump.set_speed(1, speed, "uL")
        self.pump.run_continuous([1],direction='B', blocking=False)

    def run_pump2(self):

        if self.pump is None:
            return

        speed = float(self.pump2_speed.text())

        self.pump.set_speed(2, speed, "uL")
        self.pump.run_continuous([2],direction='B', blocking=False)

    def run_both_pumps(self):

        if self.pump is None:
            return

        speed1 = float(self.pump1_speed.text())
        speed2 = float(self.pump2_speed.text())

        self.pump.set_speed(1, speed1, "uL")
        self.pump.set_speed(2, speed2, "uL")

        self.pump.run_continuous(
            [1, 2],
            direction='B',
            blocking=False
        )

    def stop_pumps(self):

        if self.pump is None:
            return

        self.pump.stop(blocking=False)


# ==========================================================
# Main
# ==========================================================
def launch_camera(viewer):

    cam = HikCameraController()

    cam.connect()
    cam.set_exposure(200)
    cam.start_live()

    # ------------------------------------------------------
    live_layer = viewer.add_image(
        np.zeros((2048, 3072), dtype=np.uint8),
        name="Live"
    )

    sub_layer = viewer.add_image(
        np.zeros((2048, 3072), dtype=np.int16),
        name="Live - Reference",
        visible=False
    )

    widget = ControlWidget(cam)

    viewer.window.add_dock_widget(
        widget,
        area="right"
    )

    # ------------------------------------------------------
    widget.timer = QTimer()

    def refresh():

        if cam.latest is None:
            return

        img = cam.latest

        live_layer.data = img

        if widget.reference is not None:

            diff = (
                img.astype(np.int16)
                - widget.reference.astype(np.int16)
            )

            sub_layer.data = diff

    widget.timer.timeout.connect(refresh)
    widget.timer.start(30)

    def cleanup():

        cam.disconnect()

        if widget.pump is not None:
            widget.pump.disconnect()

    viewer.window.qt_viewer.destroyed.connect(
        cleanup
    )


# ==========================================================
if __name__ == "__main__":

    viewer = napari.Viewer()
    launch_camera(viewer)
    napari.run()