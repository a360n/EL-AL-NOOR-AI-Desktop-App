#!/usr/bin/env python3
"""
EL AL-NOOR AI - Visual Overlay & Annotation Engine
------------------------------------------------------
Renders crisp, high-resolution comparative annotated panels:
  1. Human Annotation Panel: Highlighted defective cells with red 'X' and border based on info.json
  2. AI Annotation Panel: Highlighted defective cells with red 'X', border, and confidence badge based on aiinfo.json
Draws directly on the clean, seamless model panel image (zero duplication, 100% natural display).
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
        inset_x = max(2, int(w * 0.08))
        inset_y = max(2, int(h * 0.08))
        cv2.line(img, (x + inset_x, y + inset_y), (x + w - inset_x, y + h - inset_y), color, thickness + 1, cv2.LINE_AA)
        cv2.line(img, (x + w - inset_x, y + inset_y), (x + inset_x, y + h - inset_y), color, thickness + 1, cv2.LINE_AA)

        # 3. Text label badge
        if label:
            text = label
            if confidence is not None:
                text += f" ({confidence:.0f}%)"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.55, min(w, h) / 160.0)
            text_thickness = max(1, int(thickness / 2))

            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, text_thickness)
            tx = x + 8
            ty = y + th + 10

            # Black badge background for maximum contrast
            cv2.rectangle(img, (tx - 3, ty - th - 5), (tx + tw + 5, ty + baseline + 3), (0, 0, 0), -1)
            cv2.putText(img, text, (tx, ty), font, font_scale, (255, 255, 255), text_thickness, cv2.LINE_AA)

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
        Draws defect annotations directly on the clean, seamless panel image.
        Zero duplication or distortion.
        """
        annotated = base_panel_bgr.copy()
        norm_defect_set = {normalize_cell_id(cid) for cid in defective_cell_ids if cid}

        # Calculate adaptive thickness based on image width
        img_w = annotated.shape[1]
        line_thickness = max(2, int(round(img_w / 800.0)))

        for cell in grid_overlay:
            cid = normalize_cell_id(cell["id"])
            x, y, w, h = cell["x"], cell["y"], cell["w"], cell["h"]

            # If defective, draw prominent X marker
            if cid in norm_defect_set:
                conf = cell_confidence_map.get(cid) if cell_confidence_map else None
                cls.draw_defect_x(
                    annotated,
                    x, y, w, h,
                    color=x_color,
                    thickness=line_thickness,
                    label=cid,
                    confidence=conf
                )

        return annotated

    @classmethod
    def save_annotated_panels(
        cls,
        model_panel_bgr: np.ndarray,
        grid_overlay: List[Dict[str, Any]],
        human_defects: List[str],
        ai_defects: List[str],
        ai_confidence_map: Dict[str, float],
        output_dir: str,
        panel_id: str,
    ) -> Tuple[str, str]:
        """
        Generates and saves both:
          1. human_overlay.png (Clean panel with Human Ground Truth X's)
          2. ai_overlay.png (Clean panel with AI Diagnosis X's & confidence badges)
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Human overlay
        human_img = cls.create_annotated_panel(
            base_panel_bgr=model_panel_bgr,
            grid_overlay=grid_overlay,
            defective_cell_ids=human_defects,
            title_tag="Human / EL File Ground Truth",
            x_color=(0, 0, 230),  # Red
        )
        human_path = os.path.join(output_dir, f"{panel_id}_human_overlay.png")
        cv2.imwrite(human_path, human_img)

        # 2. AI overlay
        ai_img = cls.create_annotated_panel(
            base_panel_bgr=model_panel_bgr,
            grid_overlay=grid_overlay,
            defective_cell_ids=ai_defects,
            title_tag="EL AL-NOOR AI Diagnosis",
            cell_confidence_map=ai_confidence_map,
            x_color=(0, 0, 240),  # Bright Red
        )
        ai_path = os.path.join(output_dir, f"{panel_id}_ai_overlay.png")
        cv2.imwrite(ai_path, ai_img)

        return human_path, ai_path
