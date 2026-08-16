#!/usr/bin/env python3
"""
EL AL-NOOR AI - Visual Overlay & Annotation Engine
----------------------------------------------------
Draws crisp, high-precision red 'X' defect markers and confidence badges
directly on the natural 1:2 aspect ratio panel image (MH = 2 * MW).
Each of the 144 cells (6 cols x 24 rows) has exact rectangular coordinates:
  - Cell Width:  CH = MW / 6.0
  - Cell Height: CW = MH / 24.0
  - Cell Box:    [x = c * CH, y = r * CW, w = CH, h = CW]

Markers are placed STRICTLY on defective cells:
  - For AI Panel: Placed only on cells listed in aiinfo.json['defective_cells'].
  - For Human Panel: Placed only on cells listed in info.json['defective_cells'].
Healthy cells remain 100% clean and natural without any distortion or duplication.
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
        w: int,
        h: int,
        color: Tuple[int, int, int] = (0, 0, 235),  # Vivid Bright Red (BGR)
        thickness: int = 4,
        label: Optional[str] = None,
        confidence: Optional[float] = None,
    ):
        """
        Draws a prominent, high-precision red X, border, and badge on a defective cell.
        """
        # 1. Bounding border around cell perimeter
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        # 2. Diagonal X lines crossing the cell with neat margin
        inset_x = int(w * 0.10)
        inset_y = int(h * 0.10)
        cv2.line(
            img,
            (x + inset_x, y + inset_y),
            (x + w - inset_x, y + h - inset_y),
            color,
            thickness + 2,
            cv2.LINE_AA
        )
        cv2.line(
            img,
            (x + w - inset_x, y + inset_y),
            (x + inset_x, y + h - inset_y),
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
            font_scale = max(0.6, w / 450.0)
            text_thickness = max(1, int(thickness / 2))

            (tw, th), baseline = cv2.getTextSize(text, font, font_scale, text_thickness)
            
            # Badge background pill
            tx = x + 8
            ty = y + th + 10
            cv2.rectangle(
                img,
                (tx - 4, ty - th - 6),
                (tx + tw + 6, ty + baseline + 4),
                (15, 15, 15), # Dark slate pill background
                -1
            )
            cv2.rectangle(
                img,
                (tx - 4, ty - th - 6),
                (tx + tw + 6, ty + baseline + 4),
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
    def render_annotated_panel(
        cls,
        base_panel_bgr: np.ndarray,
        defective_cell_ids: List[str],
        cell_confidence_map: Optional[Dict[str, float]] = None,
        x_color: Tuple[int, int, int] = (0, 0, 235),
    ) -> np.ndarray:
        """
        Annotates the natural 1:2 panel image with defect markers.
        Calculates exact rectangular positions for 6 columns x 24 rows:
          ch = panel_width / 6.0
          cw = panel_height / 24.0
        """
        annotated = base_panel_bgr.copy()
        mh, mw = annotated.shape[:2]

        ch = mw / 6.0   # Cell width (X axis, 6 columns A-F)
        cw = mh / 24.0  # Cell height (Y axis, 24 rows 1-24)

        cols = ['A', 'B', 'C', 'D', 'E', 'F']

        # Normalize defective cell IDs set
        norm_defect_set: Set[str] = {
            normalize_cell_id(cid) for cid in defective_cell_ids if cid
        }

        # If no defects, return clean panel directly
        if not norm_defect_set:
            return annotated

        thickness = max(2, int(mw / 600.0))

        for r_idx in range(24):      # Rows 1 to 24
            for c_idx in range(6):   # Columns A to F
                col_name = cols[c_idx]
                row_name = r_idx + 1
                cell_id = f"{col_name}{row_name}"
                norm_cid = normalize_cell_id(cell_id)

                # Only draw if cell is marked defective
                if norm_cid in norm_defect_set or cell_id in norm_defect_set:
                    x = int(round(c_idx * ch))
                    y = int(round(r_idx * cw))
                    x2 = int(round((c_idx + 1) * ch))
                    y2 = int(round((r_idx + 1) * cw))
                    w = x2 - x
                    h = y2 - y

                    conf = cell_confidence_map.get(norm_cid, cell_confidence_map.get(cell_id)) if cell_confidence_map else None
                    cls.draw_defect_x(
                        annotated,
                        x=x,
                        y=y,
                        w=w,
                        h=h,
                        color=x_color,
                        thickness=thickness,
                        label=norm_cid,
                        confidence=conf
                    )

        return annotated

    @classmethod
    def save_annotated_panels(
        cls,
        base_panel_bgr: np.ndarray,
        human_defects: List[str],
        ai_defects: List[str],
        ai_confidence_map: Dict[str, float],
        output_dir: str,
        panel_id: str,
    ) -> Tuple[str, str]:
        """
        Generates and saves:
          1. {panel_id}_human_overlay.png (natural panel with red X on human defects)
          2. {panel_id}_ai_overlay.png (natural panel with red X on AI defects)
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Human Ground Truth Annotated Panel
        human_img = cls.render_annotated_panel(
            base_panel_bgr=base_panel_bgr,
            defective_cell_ids=human_defects,
            x_color=(0, 0, 235),  # Red
        )
        human_path = os.path.join(output_dir, f"{panel_id}_human_overlay.png")
        cv2.imwrite(human_path, human_img)

        # 2. AI Diagnosis Annotated Panel
        ai_img = cls.render_annotated_panel(
            base_panel_bgr=base_panel_bgr,
            defective_cell_ids=ai_defects,
            cell_confidence_map=ai_confidence_map,
            x_color=(0, 0, 245),  # Bright Red
        )
        ai_path = os.path.join(output_dir, f"{panel_id}_ai_overlay.png")
        cv2.imwrite(ai_path, ai_img)

        return human_path, ai_path
