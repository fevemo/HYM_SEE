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

        # tracks which single pump is running for Switch (1, 2, or None)
        self._active_pump = None
        self._active_dir  = 'B'

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
        # Thresholding controls
        # ==================================================
        layout.addWidget(QLabel("Threshold (mask < value)"))

        thr_row = QHBoxLayout()
        self.thr_slider = QSlider(Qt.Horizontal)
        self.thr_slider.setMinimum(0)
        self.thr_slider.setMaximum(255)
        self.thr_slider.setValue(50)

        self.thr_edit = QLineEdit("50")
        self.thr_edit.setFixedWidth(60)

        thr_row.addWidget(self.thr_slider)
        thr_row.addWidget(self.thr_edit)
        layout.addLayout(thr_row)

        layout.addWidget(QLabel("Max allowed mask area (pixels)"))
        self.area_limit_edit = QLineEdit("5000")
        layout.addWidget(self.area_limit_edit)

        self.area_label = QLabel("Mask area: 0 px")
        layout.addWidget(self.area_label)

        # exposed for refresh()
        self.threshold = 50
        self.area_limit = 5000
        self.last_area = 0

        # ==================================================
        # Pump controls
        # ==================================================

        layout.addWidget(QLabel("Top pump speed (µL/s)"))

        self.pump2_speed = QLineEdit("1.0")
        layout.addWidget(self.pump2_speed)

        layout.addWidget(QLabel("Bottom pump speed (µL/s)"))

        self.pump1_speed = QLineEdit("1.0")
        layout.addWidget(self.pump1_speed)

        self.run_p1_fwd  = QPushButton("▶ Fwd")
        self.run_p1_bwd  = QPushButton("◀ Bwd")
        self.run_p2_fwd  = QPushButton("▶ Fwd")
        self.run_p2_bwd  = QPushButton("◀ Bwd")
        self.run_both_fwd = QPushButton("▶ Fwd")
        self.run_both_bwd = QPushButton("◀ Bwd")
        self.stop_all    = QPushButton("Stop all pumps")
        self.switch_btn  = QPushButton("Switch pump")

        p2_row = QHBoxLayout()
        p2_row.addWidget(QLabel("Top pump"))
        p2_row.addWidget(self.run_p2_bwd)
        p2_row.addWidget(self.run_p2_fwd)
        layout.addLayout(p2_row)

        p1_row = QHBoxLayout()
        p1_row.addWidget(QLabel("Bottom pump"))
        p1_row.addWidget(self.run_p1_bwd)
        p1_row.addWidget(self.run_p1_fwd)
        layout.addLayout(p1_row)

        both_row = QHBoxLayout()
        both_row.addWidget(QLabel("Both"))
        both_row.addWidget(self.run_both_bwd)
        both_row.addWidget(self.run_both_fwd)
        layout.addLayout(both_row)

        layout.addWidget(self.switch_btn)
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

        self.run_p1_fwd.clicked.connect(
            lambda: self.run_pump(1, 'B')
        )

        self.run_p1_bwd.clicked.connect(
            lambda: self.run_pump(1, 'F')
        )

        self.run_p2_fwd.clicked.connect(
            lambda: self.run_pump(2, 'B')
        )

        self.run_p2_bwd.clicked.connect(
            lambda: self.run_pump(2, 'F')
        )

        self.run_both_fwd.clicked.connect(
            lambda: self.run_both_pumps('B')
        )

        self.run_both_bwd.clicked.connect(
            lambda: self.run_both_pumps('F')
        )

        self.switch_btn.clicked.connect(
            self.switch_pump
        )

        self.stop_all.clicked.connect(
            self.stop_pumps
        )

        self.pump1_speed.editingFinished.connect(
            self.set_pump1_speed
        )

        self.pump2_speed.editingFinished.connect(
            self.set_pump2_speed
        )

        self.thr_slider.valueChanged.connect(
            self.thr_slider_changed
        )

        self.thr_edit.returnPressed.connect(
            self.thr_edit_changed
        )

        self.area_limit_edit.editingFinished.connect(
            self.area_limit_changed
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
    def set_pump1_speed(self):

        if self.pump is None:
            return

        try:
            speed = float(self.pump1_speed.text())
            self.pump.set_speed(1, speed, "uL", blocking=True)
        except ValueError:
            pass

    def set_pump2_speed(self):

        if self.pump is None:
            return

        try:
            speed = float(self.pump2_speed.text())
            self.pump.set_speed(2, speed, "uL", blocking=True)
        except ValueError:
            pass

    def run_pump(self, pump_id, direction):

        if self.pump is None:
            return

        self._active_pump = pump_id
        self._active_dir  = direction

        self.pump.run_continuous(
            [pump_id],
            direction=direction,
            blocking=True
        )

    def run_both_pumps(self, direction):

        if self.pump is None:
            return

        self._active_pump = None  # both running, switch not meaningful
        self.pump.run_continuous(
            [1, 2],
            direction=direction,
            blocking=True
        )

    def switch_pump(self):
        """Stop the running pump and start the other one."""

        if self.pump is None:
            return

        if self._active_pump is None:
            print("Switch: no single pump is active.")
            return

        other = 2 if self._active_pump == 1 else 1
        direction = self._active_dir

        self.pump.stop(blocking=True)
        self._active_pump = other
        self.pump.run_continuous(
            [other],
            direction=direction,
            blocking=True
        )

    def stop_pumps(self):

        if self.pump is None:
            return

        self.pump.stop(blocking=True)


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

    mask_layer = viewer.add_labels(
        np.zeros((2048, 3072), dtype=np.uint8),
        name="Mask",
        opacity=0.5,
    )
    # start green
    mask_layer.color = {0: "transparent", 1: "green"}

    widget = ControlWidget(cam)

    viewer.window.add_dock_widget(
        widget,
        area="right"
    )

    # ------------------------------------------------------
    widget.timer = QTimer()

    # track current mask color so we don't reassign every frame
    mask_state = {"color": "green"}

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

        # ---- thresholding ----
        mask = (img < widget.threshold).astype(np.uint8)
        mask_layer.data = mask

        area = int(mask.sum())
        widget.last_area = area

        new_color = "red" if area > widget.area_limit else "green"
        if new_color != mask_state["color"]:
            mask_layer.color = {0: "transparent", 1: new_color}
            mask_state["color"] = new_color

        widget.area_label.setText(
            f"Mask area: {area} px ({new_color})"
        )

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