#!/usr/bin/env python3
"""
EL AL-NOOR AI - Solar Panel EL Image Cropper Engine
------------------------------------------------------
Exact identical algorithm used in el_cropper_app and dataset generation:
  0. TIF preprocessing (even height check + adaptive tilt buffer for Col F).
  1. Aspect ratio correction (MH = 2 * MW) trimming excess width strictly from right side.
  2. Calculates base cell dimensions: CH = MW / 6.0, CW = MH / 24.0.
  3. Square patch side length: SL = 1.3 * CH (15% safety margin on each side).
  4. Clean background safety margin padding (BORDER_CONSTANT with detected panel border color).
  5. Slices 144 square cell patches (A1 to F24).
  6. Resizes all patches to 224x224 px PNG.
"""

import os
import io
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple, Optional


def process_single_image_pil(img: Image.Image) -> Image.Image:
    """
    Standard process_tif.py transformation:
    - Ensures height is even (if height is odd, subtracts 1).
    - Preserves outer cell border of Column F even when camera has perspective tilt/skew
      by adding an adaptive right-side safety tilt buffer (8% of cell width).
    """
    width, height = img.size
    new_height = height if height % 2 == 0 else height - 1
    target_max_width = new_height // 2

    base_ch = target_max_width / 6.0
    tilt_buffer = int(round(0.08 * base_ch))

    if width > target_max_width:
        new_width = min(width, target_max_width + tilt_buffer)
    else:
        new_width = width

    if new_width != width or new_height != height:
        return img.crop((0, 0, new_width, new_height))
    return img


class SolarPanelCropperEngine:
    """
    Precision Cropping Engine matching the training dataset pipeline exactly.
    """

    @staticmethod
    def load_image_from_path(file_path: str) -> np.ndarray:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image not found: {file_path}")

        try:
            with Image.open(file_path) as pil_img:
                pil_img = process_single_image_pil(pil_img)
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                img_np = np.array(pil_img)
                return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        except Exception:
            img = cv2.imread(file_path, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"Could not decode image at {file_path}")
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            pil_img = process_single_image_pil(pil_img)
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def load_image_from_bytes(file_bytes: bytes) -> np.ndarray:
        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            pil_img = process_single_image_pil(pil_img)
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            img_np = np.array(pil_img)
            return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        except Exception:
            np_arr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image bytes")
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            pil_img = process_single_image_pil(pil_img)
            return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @classmethod
    def process_panel(
        cls,
        image_bgr: np.ndarray,
        target_cell_size: Tuple[int, int] = (224, 224),
    ) -> Dict[str, Any]:
        """
        Executes full precision cropping pipeline on the panel image.
        Returns:
          - metadata: dict of calculated dimensions and padding
          - padded_image_bgr: clean padded image used for slicing
          - model_image_bgr: aspect-ratio corrected image
          - cells: dict of 144 cells with key 'A1'..'F24' containing png bytes, bboxes, bgr patch
          - grid_overlay: coordinate information for each cell
        """
        orig_h, orig_w = image_bgr.shape[:2]

        # Step 1: Ensure height is even
        if orig_h % 2 != 0:
            image_step1 = image_bgr[0 : orig_h - 1, :]
        else:
            image_step1 = image_bgr.copy()

        h1, w1 = image_step1.shape[:2]

        # Step 2: Aspect ratio correction (MH = 2 * MW)
        # Trims excess width strictly from the RIGHT side with adaptive tilt buffer
        if (h1 / 2.0) < w1:
            target_mw = int(round(h1 / 2.0))
            base_ch = target_mw / 6.0
            tilt_buffer = int(round(0.08 * base_ch))
            crop_right = min(w1, target_mw + tilt_buffer)
            model_img = image_step1[:, 0:crop_right]
        elif (h1 / 2.0) > w1:
            target_mh = int(round(2.0 * w1))
            model_img = image_step1[0:target_mh, :]
        else:
            model_img = image_step1.copy()

        mh, mw = model_img.shape[:2]

        # Step 3: Base cell calculations
        ch = mw / 6.0  # Horizontal cell length along X axis (6 cols A-F)
        cw = mh / 24.0  # Vertical cell length along Y axis (24 rows 1-24)

        # Step 4: Square side length SL = 1.3 * CH (15% safety margin on all sides)
        sl_float = 1.3 * ch
        sl_px = int(round(sl_float))

        # Step 5: Clean background safety margin padding
        border_sample = model_img[:5, :]
        bg_color = tuple([int(c) for c in border_sample.mean(axis=(0, 1))])

        pad_x_float = (sl_float - ch) / 2.0
        pad_y_float = (sl_float - cw) / 2.0

        pad_x = int(round(pad_x_float))
        pad_y = int(round(pad_y_float))

        padded_img = cv2.copyMakeBorder(
            model_img,
            top=pad_y,
            bottom=pad_y,
            left=pad_x,
            right=pad_x,
            borderType=cv2.BORDER_CONSTANT,
            value=bg_color,
        )

        nmh, nmw = padded_img.shape[:2]

        # Step 6 & 7: Grid slicing and resizing
        cols = ["A", "B", "C", "D", "E", "F"]
        cells_dict = {}
        grid_overlay_info = []

        for r_idx in range(24):  # Rows 1 to 24
            for c_idx in range(6):  # Cols A to F
                col_name = cols[c_idx]
                row_name = r_idx + 1
                cell_id = f"{col_name}{row_name}"

                cx = pad_x_float + (c_idx + 0.5) * ch
                cy = pad_y_float + (r_idx + 0.5) * cw

                x_start = int(round(cx - sl_float / 2.0))
                y_start = int(round(cy - sl_float / 2.0))
                x_end = x_start + sl_px
                y_end = y_start + sl_px

                x_start_clamped = max(0, x_start)
                y_start_clamped = max(0, y_start)
                x_end_clamped = min(nmw, x_end)
                y_end_clamped = min(nmh, y_end)

                patch = padded_img[
                    y_start_clamped:y_end_clamped, x_start_clamped:x_end_clamped
                ]

                if patch.size > 0:
                    resized_patch = cv2.resize(
                        patch, target_cell_size, interpolation=cv2.INTER_CUBIC
                    )
                else:
                    resized_patch = np.zeros(
                        (target_cell_size[1], target_cell_size[0], 3), dtype=np.uint8
                    )

                _, png_buf = cv2.imencode(".png", resized_patch)
                cell_png_bytes = png_buf.tobytes()

                cells_dict[cell_id] = {
                    "id": cell_id,
                    "col": col_name,
                    "row": row_name,
                    "col_idx": c_idx,
                    "row_idx": r_idx,
                    "bbox_padded": {
                        "x": x_start_clamped,
                        "y": y_start_clamped,
                        "w": x_end_clamped - x_start_clamped,
                        "h": y_end_clamped - y_start_clamped,
                    },
                    "center": {"x": cx, "y": cy},
                    "patch_bgr": resized_patch,
                    "png_bytes": cell_png_bytes,
                }

                grid_overlay_info.append(
                    {
                        "id": cell_id,
                        "x": x_start_clamped,
                        "y": y_start_clamped,
                        "w": x_end_clamped - x_start_clamped,
                        "h": y_end_clamped - y_start_clamped,
                        "cx": cx,
                        "cy": cy,
                    }
                )

        metadata = {
            "original_dimensions": {"width": orig_w, "height": orig_h},
            "model_dimensions": {"width": mw, "height": mh},
            "padded_dimensions": {"width": nmw, "height": nmh},
            "base_cell": {"CH": ch, "CW": cw},
            "padding": {"pad_x": pad_x_float, "pad_y": pad_y_float},
            "square_length_SL": sl_float,
            "square_length_px": sl_px,
            "total_cells": len(cells_dict),
            "target_cell_size": f"{target_cell_size[0]}x{target_cell_size[1]}",
            "preprocessed_by_process_tif": True,
            "crop_mode": "CLEAN_BACKGROUND_MARGIN",
        }

        return {
            "metadata": metadata,
            "padded_image_bgr": padded_img,
            "model_image_bgr": model_img,
            "grid_overlay": grid_overlay_info,
            "cells": cells_dict,
        }

    @classmethod
    def save_cells_to_folder(
        cls, cells_dict: Dict[str, Any], output_dir: str, prefix: str = ""
    ) -> List[str]:
        """Saves all 144 cell PNG images to a target folder."""
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        for cell_id, cell_data in cells_dict.items():
            fname = f"{prefix}_{cell_id}.png" if prefix else f"{cell_id}.png"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "wb") as f:
                f.write(cell_data["png_bytes"])
            saved_paths.append(fpath)
        return saved_paths
