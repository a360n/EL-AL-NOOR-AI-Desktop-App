#!/usr/bin/env python3
"""
EL AL-NOOR AI - Visual Overlay & Inverse Reassembly Engine
------------------------------------------------------------
Performs the exact inverse process of cropper_engine.py:
  1. Reassembles the 144 cropped cell patches (224x224 px) into the full panel grid (6 cols x 24 rows).
  2. Places prominent red 'X' and border annotations ONLY on defective cells:
     - Human Overlay Panel: based on info.json ground truth
     - AI Overlay Panel: based on aiinfo.json AI diagnosis with confidence badges
  3. Clean cells remain 100% untouched without any red markers.
"""

import os
import re
import cv2
import numpy as np
from typing import Dict, Any, List, Set, Optional, Tuple


def normalize_cell_id(cell_id: str) -> str:
    """Standardizes cell ID e.g. 'A01' -> 'A1', 'b04' -> 'B4', 'B03 [manual]' -> 'B3'."""
    if not cell_id:
        return ""
    match = re.search(r'\b([A-F])(0?[1-9]|1[0-9]|2[0-4])\b', str(cell_id), re.IGNORECASE)
    if match:
        col = match.group(1).upper()
        num = int(match.group(2))
        return f"{col}{num}"
    return str(cell_id).strip().upper()


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
        confidence: Optional[float] = None
    ):
        """Draws a clean, prominent red X and bounding box on a cell."""
        # 1. Bounding box
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        # 2. Diagonal X lines
        inset_x = int(w * 0.10)
        inset_y = int(h * 0.10)
        cv2.line(img, (x + inset_x, y + inset_y), (x + w - inset_x, y + h - inset_y), color, thickness + 1, cv2.LINE_AA)
        cv2.line(img, (x + w - inset_x, y + inset_y), (x + inset_x, y + h - inset_y), color, thickness + 1, cv2.LINE_AA)

        # 3. Text label if provided
        if label:
            text = label
            if confidence is not None:
                text += f" ({confidence:.0f}%)"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.55, w / 350.0)
            text_thickness = max(1, int(thickness / 2))

            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, text_thickness)
            tx = x + 8
            ty = y + th + 10
            
            # Black badge background for high contrast
            cv2.rectangle(img, (tx - 3, ty - th - 5), (tx + tw + 5, ty + baseline + 3), (0, 0, 0), -1)
            cv2.putText(img, text, (tx, ty), font, font_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

    @classmethod
    def reassemble_from_cells(
        cls,
        cells_dict: Dict[str, Any],
        defective_cell_ids: List[str],
        cell_confidence_map: Optional[Dict[str, float]] = None,
        x_color: Tuple[int, int, int] = (0, 0, 230),
        cell_size: int = 224
    ) -> np.ndarray:
        """
        Exact inverse operation of cropper_engine.py:
        Reassembles 144 cropped square cell patches into a single 6x24 panel image (1344 x 5376 px).
        Places red X marks ONLY on cells that are in defective_cell_ids.
        """
        cols = ['A', 'B', 'C', 'D', 'E', 'F']
        panel_w = 6 * cell_size
        panel_h = 24 * cell_size

        panel_img = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
        
        # Build normalized defect set
        norm_defect_set = {normalize_cell_id(cid) for cid in defective_cell_ids if cid}

        for r_idx in range(24):      # Rows 1 to 24
            for c_idx in range(6):   # Cols A to F
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

                if cell_patch is None or cell_patch.shape[:2] != (cell_size, cell_size):
                    cell_patch = cv2.resize(cell_patch, (cell_size, cell_size)) if cell_patch is not None else np.zeros((cell_size, cell_size, 3), dtype=np.uint8)

                # Paste cell into panel grid
                panel_img[y:y+cell_size, x:x+cell_size] = cell_patch

                # If defective, place red X annotation
                if norm_cid in norm_defect_set:
                    conf = cell_confidence_map.get(norm_cid) if cell_confidence_map else None
                    cls.draw_defect_x(
                        panel_img,
                        x, y,
                        cell_size, cell_size,
                        color=x_color,
                        thickness=3,
                        label=norm_cid,
                        confidence=conf
                    )

        return panel_img

    @classmethod
    def save_annotated_panels(
        cls,
        cells_dict: Dict[str, Any],
        human_defects: List[str],
        ai_defects: List[str],
        ai_confidence_map: Dict[str, float],
        output_dir: str,
        panel_id: str,
        base_panel_bgr: Optional[np.ndarray] = None,
        grid_overlay: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, str]:
        """
        Generates and saves both:
          1. human_overlay.png (reconstructed with Human Ground Truth X's)
          2. ai_overlay.png (reconstructed with AI Diagnosis X's & confidence badges)
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Human overlay from 144 cells (Inverse Reassembly)
        human_img = cls.reassemble_from_cells(
            cells_dict=cells_dict,
            defective_cell_ids=human_defects,
            x_color=(0, 0, 230),  # Red
        )
        human_path = os.path.join(output_dir, f"{panel_id}_human_overlay.png")
        cv2.imwrite(human_path, human_img)

        # 2. AI overlay from 144 cells (Inverse Reassembly)
        ai_img = cls.reassemble_from_cells(
            cells_dict=cells_dict,
            defective_cell_ids=ai_defects,
            cell_confidence_map=ai_confidence_map,
            x_color=(0, 0, 240),  # Bright Red
        )
        ai_path = os.path.join(output_dir, f"{panel_id}_ai_overlay.png")
        cv2.imwrite(ai_path, ai_img)

        return human_path, ai_path
