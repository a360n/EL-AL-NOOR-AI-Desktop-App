#!/usr/bin/env python3
"""
EL AL-NOOR AI - Visual Overlay & Reverse Recomposition Engine
----------------------------------------------------------------
Performs the exact inverse operation of cropper_engine.py:
1. Takes the 144 cropped cell images (224x224 px).
2. Assembles them into a 6-column x 24-row high-resolution panel canvas.
3. Places clean, bold red 'X' markers and confidence tags STRICTLY on defective cells:
   - For AI Panel: Placed only on cells listed in aiinfo.json['defective_cells'].
   - For Human Panel: Placed only on cells listed in info.json['defective_cells'].
4. Healthy cells remain 100% clean with no markers.
"""

import os
import cv2
import numpy as np
from typing import Dict, Any, List, Set, Optional, Tuple


def normalize_cell_id(cell_id: str) -> str:
    """Standardizes cell ID e.g. 'A01' -> 'A1', 'b04' -> 'B4', 'F24' -> 'F24'."""
    if not cell_id:
        return ""
    cell_id = str(cell_id).strip().upper()
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
        cell_size: int = 224,
        color: Tuple[int, int, int] = (0, 0, 235),  # Bright Vivid Red (BGR)
        thickness: int = 4,
        label: Optional[str] = None,
        confidence: Optional[float] = None,
    ):
        """
        Draws a prominent, high-precision red X and border on a defective cell tile.
        """
        w = cell_size
        h = cell_size

        # 1. Bounding box around cell perimeter
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        # 2. Diagonal X lines crossing the cell with clean margin
        inset = int(cell_size * 0.12)
        cv2.line(
            img,
            (x + inset, y + inset),
            (x + w - inset, y + h - inset),
            color,
            thickness + 2,
            cv2.LINE_AA
        )
        cv2.line(
            img,
            (x + w - inset, y + inset),
            (x + inset, y + h - inset),
            color,
            thickness + 2,
            cv2.LINE_AA
        )

        # 3. Informative Tag Badge (e.g. 'B18 (99%)' or 'A14')
        if label:
            text = label
            if confidence is not None:
                text += f" ({confidence:.0f}%)"

            font = cv2.FONT_HERSHEY_DUPLEX
            font_scale = 0.55
            text_thickness = 1

            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, text_thickness)
            
            # Badge background pill
            tx = x + 8
            ty = y + th + 10
            cv2.rectangle(
                img,
                (tx - 3, ty - th - 5),
                (tx + tw + 5, ty + baseline + 3),
                (15, 15, 15), # Dark slate pill background
                -1
            )
            cv2.rectangle(
                img,
                (tx - 3, ty - th - 5),
                (tx + tw + 5, ty + baseline + 3),
                color,
                1
            )
            cv2.putText(
                img,
                text,
                (tx, ty),
                font,
                font_scale,
                (255, 255, 255),
                text_thickness,
                cv2.LINE_AA
            )

    @classmethod
    def reassemble_panel(
        cls,
        cells_dict: Dict[str, Any],
        defective_cell_ids: List[str],
        cell_confidence_map: Optional[Dict[str, float]] = None,
        x_color: Tuple[int, int, int] = (0, 0, 235),
        cell_size: int = 224,
    ) -> np.ndarray:
        """
        Reverse Process of cropper_engine:
        Assembles the 144 cell images in a 6-column x 24-row grid (1344 x 5376 px).
        Places defect markers strictly on cells listed in defective_cell_ids.
        """
        cols = ['A', 'B', 'C', 'D', 'E', 'F']
        panel_w = 6 * cell_size
        panel_h = 24 * cell_size

        panel_img = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)

        # Normalize defective cell IDs set
        norm_defect_set: Set[str] = {
            normalize_cell_id(cid) for cid in defective_cell_ids if cid
        }

        for r_idx in range(24):      # Rows 1 to 24
            for c_idx in range(6):   # Columns A to F
                col_name = cols[c_idx]
                row_name = r_idx + 1
                cell_id = f"{col_name}{row_name}"
                norm_cid = normalize_cell_id(cell_id)

                x = c_idx * cell_size
                y = r_idx * cell_size

                # Extract patch image
                cell_patch = None
                if cell_id in cells_dict:
                    cdata = cells_dict[cell_id]
                    if isinstance(cdata, dict):
                        if "patch_bgr" in cdata and cdata["patch_bgr"] is not None:
                            cell_patch = cdata["patch_bgr"]
                        elif "png_bytes" in cdata and cdata["png_bytes"]:
                            np_arr = np.frombuffer(cdata["png_bytes"], np.uint8)
                            cell_patch = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    elif isinstance(cdata, np.ndarray):
                        cell_patch = cdata

                if cell_patch is None or cell_patch.shape[:2] != (cell_size, cell_size):
                    cell_patch = (
                        cv2.resize(cell_patch, (cell_size, cell_size), interpolation=cv2.INTER_CUBIC)
                        if cell_patch is not None
                        else np.zeros((cell_size, cell_size, 3), dtype=np.uint8)
                    )

                # Paste cell into panel matrix
                panel_img[y:y + cell_size, x:x + cell_size] = cell_patch

                # If this cell is marked defective, draw red X
                if norm_cid in norm_defect_set or cell_id in norm_defect_set:
                    conf = cell_confidence_map.get(norm_cid, cell_confidence_map.get(cell_id)) if cell_confidence_map else None
                    cls.draw_defect_x(
                        panel_img,
                        x=x,
                        y=y,
                        cell_size=cell_size,
                        color=x_color,
                        thickness=4,
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
    ) -> Tuple[str, str]:
        """
        Reverse Process Generator:
        Assembles and saves both:
          1. {panel_id}_human_overlay.png (with red X on human-diagnosed defects from info.json)
          2. {panel_id}_ai_overlay.png (with red X & confidence on AI-diagnosed defects from aiinfo.json)
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Human Ground Truth Reassembled Panel
        human_img = cls.reassemble_panel(
            cells_dict=cells_dict,
            defective_cell_ids=human_defects,
            x_color=(0, 0, 235),  # Red
            cell_size=224
        )
        human_path = os.path.join(output_dir, f"{panel_id}_human_overlay.png")
        cv2.imwrite(human_path, human_img)

        # 2. AI Diagnosis Reassembled Panel
        ai_img = cls.reassemble_panel(
            cells_dict=cells_dict,
            defective_cell_ids=ai_defects,
            cell_confidence_map=ai_confidence_map,
            x_color=(0, 0, 245),  # Bright Red
            cell_size=224
        )
        ai_path = os.path.join(output_dir, f"{panel_id}_ai_overlay.png")
        cv2.imwrite(ai_path, ai_img)

        return human_path, ai_path
