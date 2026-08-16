#!/usr/bin/env python3
"""
EL AL-NOOR AI - Visual Overlay & Recomposition Engine
-------------------------------------------------------
Reassembles and annotates the 144 cells into full panel comparison images:
  1. Human Annotation Panel: Highlighted defective cells with red 'X' and border based on info.json
  2. AI Annotation Panel: Highlighted defective cells with red 'X' and border based on aiinfo.json
Produces crisp high-resolution PNG images for dual comparison UI and quality reports.
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, List, Set, Optional, Tuple


def normalize_cell_id(cell_id: str) -> str:
    """Standardizes cell ID e.g. 'A01' -> 'A1', 'b04' -> 'B4', 'F24' -> 'F24'."""
    cell_id = cell_id.strip().upper()
    if len(cell_id) >= 2 and cell_id[0] in "ABCDEF":
        col = cell_id[0]
        try:
            num = int(cell_id[1:])
            return f"{col}{num}"
        except ValueError:
            return cell_id
    return cell_id


class PanelOverlayEngine:

    @staticmethod
    def draw_defect_x(
        img: np.ndarray,
        x: int,
        y: int,
        w: int,
        h: int,
        color: Tuple[int, int, int] = (0, 0, 230),  # Bright Red BGR
        thickness: int = 4,
        label: Optional[str] = None,
        confidence: Optional[float] = None,
    ):
        """Draws a crisp X and bounding box on a cell."""
        # 1. Bounding box
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        # 2. Diagonal X lines
        # Inset slightly from cell borders for clean aesthetics
        inset_x = int(w * 0.10)
        inset_y = int(h * 0.10)
        cv2.line(
            img,
            (x + inset_x, y + inset_y),
            (x + w - inset_x, y + h - inset_y),
            color,
            thickness + 1,
            cv2.LINE_AA,
        )
        cv2.line(
            img,
            (x + w - inset_x, y + inset_y),
            (x + inset_x, y + h - inset_y),
            color,
            thickness + 1,
            cv2.LINE_AA,
        )

        # 3. Text label if provided
        if label:
            text = label
            if confidence is not None:
                text += f" ({confidence:.0f}%)"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.5, w / 400.0)
            text_thickness = max(1, int(thickness / 2))

            (tw, th), baseline = cv2.getTextSize(
                text, font, font_scale, text_thickness
            )
            # Background pill for text readability
            tx = x + 6
            ty = y + th + 8
            cv2.rectangle(
                img,
                (tx - 2, ty - th - 4),
                (tx + tw + 4, ty + baseline + 2),
                (0, 0, 0),
                -1,
            )
            cv2.putText(
                img,
                text,
                (tx, ty),
                font,
                font_scale,
                (255, 255, 255),
                text_thickness,
                cv2.LINE_AA,
            )

    @classmethod
    def create_annotated_panel(
        cls,
        base_panel_bgr: np.ndarray,
        grid_overlay: List[Dict[str, Any]],
        defective_cell_ids: List[str],
        title_tag: str = "",
        cell_confidence_map: Optional[Dict[str, float]] = None,
        x_color: Tuple[int, int, int] = (0, 0, 230),
    ) -> np.ndarray:
        """
        Creates an annotated panel image from the clean base image and cell coordinates.
        """
        annotated = base_panel_bgr.copy()
        norm_defect_set = {
            normalize_cell_id(cid) for cid in defective_cell_ids if cid
        }

        # Draw subtle grid lines (optional/light)
        for cell in grid_overlay:
            cid = normalize_cell_id(cell["id"])
            x, y, w, h = cell["x"], cell["y"], cell["w"], cell["h"]

            # If defective, draw prominent X
            if cid in norm_defect_set:
                conf = (
                    cell_confidence_map.get(cid)
                    if cell_confidence_map
                    else None
                )
                cls.draw_defect_x(
                    annotated,
                    x,
                    y,
                    w,
                    h,
                    color=x_color,
                    thickness=4,
                    label=cid,
                    confidence=conf,
                )

        return annotated

    @classmethod
    def reassemble_from_cells(
        cls,
        cells_dict: Dict[str, Any],
        defective_cell_ids: List[str],
        cell_confidence_map: Optional[Dict[str, float]] = None,
        x_color: Tuple[int, int, int] = (0, 0, 230),
    ) -> np.ndarray:
        """
        Reassembles 144 square cell patches into a single 6x24 panel image (1344 x 5376 px)
        with defect X annotations.
        """
        cell_size = 224
        cols = ["A", "B", "C", "D", "E", "F"]
        panel_w = 6 * cell_size
        panel_h = 24 * cell_size

        panel_img = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
        norm_defect_set = {
            normalize_cell_id(cid) for cid in defective_cell_ids if cid
        }

        for r_idx in range(24):
            for c_idx in range(6):
                col_name = cols[c_idx]
                row_name = r_idx + 1
                cell_id = f"{col_name}{row_name}"
                norm_cid = normalize_cell_id(cell_id)

                x = c_idx * cell_size
                y = r_idx * cell_size

                cell_patch = None
                if cell_id in cells_dict:
                    cdata = cells_dict[cell_id]
                    if "patch_bgr" in cdata:
                        cell_patch = cdata["patch_bgr"]
                    elif "png_bytes" in cdata:
                        np_arr = np.frombuffer(cdata["png_bytes"], np.uint8)
                        cell_patch = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if (
                    cell_patch is None
                    or cell_patch.shape[:2] != (cell_size, cell_size)
                ):
                    cell_patch = (
                        cv2.resize(cell_patch, (cell_size, cell_size))
                        if cell_patch is not None
                        else np.zeros((cell_size, cell_size, 3), dtype=np.uint8)
                    )

                panel_img[y : y + cell_size, x : x + cell_size] = cell_patch

                if norm_cid in norm_defect_set:
                    conf = (
                        cell_confidence_map.get(norm_cid)
                        if cell_confidence_map
                        else None
                    )
                    cls.draw_defect_x(
                        panel_img,
                        x,
                        y,
                        cell_size,
                        cell_size,
                        color=x_color,
                        thickness=3,
                        label=norm_cid,
                        confidence=conf,
                    )

        return panel_img

    @classmethod
    def save_annotated_panels(
        cls,
        base_panel_bgr: np.ndarray,
        grid_overlay: List[Dict[str, Any]],
        human_defects: List[str],
        ai_defects: List[str],
        ai_confidence_map: Dict[str, float],
        output_dir: str,
        panel_id: str,
    ) -> Tuple[str, str]:
        """
        Generates and saves both:
          1. human_overlay.png
          2. ai_overlay.png
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Human overlay (Red X)
        human_img = cls.create_annotated_panel(
            base_panel_bgr,
            grid_overlay,
            human_defects,
            title_tag="Human / EL File Ground Truth",
            x_color=(0, 0, 230),  # Red
        )
        human_path = os.path.join(output_dir, f"{panel_id}_human_overlay.png")
        cv2.imwrite(human_path, human_img)

        # 2. AI overlay (Red/Amber X with Confidence)
        ai_img = cls.create_annotated_panel(
            base_panel_bgr,
            grid_overlay,
            ai_defects,
            title_tag="EL AL-NOOR AI Diagnosis",
            cell_confidence_map=ai_confidence_map,
            x_color=(0, 0, 240),  # Bright Red
        )
        ai_path = os.path.join(output_dir, f"{panel_id}_ai_overlay.png")
        cv2.imwrite(ai_path, ai_img)

        return human_path, ai_path
