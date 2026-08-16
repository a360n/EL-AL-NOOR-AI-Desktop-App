#!/usr/bin/env python3
"""
EL AL-NOOR AI - EfficientNet ONNX AI Inference Engine
-------------------------------------------------------
Runs batch inference (144 cells, 3, 224, 224) using ONNX Runtime.
Uses ImageNet mean/std normalization and calibrated defect thresholding:
  - Binary classifier: [Class 0: Defective, Class 1: Healthy]
  - Calibrated logit threshold: accurately filters false positive noise on healthy cells.
Outputs standardized aiinfo.json dictionary matching EL AL-NOOR AI MVP specifications.
"""

import os
import io
import json
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple, Optional

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False


class SolarCellAIEngine:
    """
    Inference Engine using trained EfficientNet-B0 ONNX model for 144-cell solar panels.
    """

    def __init__(self, onnx_model_path: Optional[str] = None):
        self.session = None
        self.input_name = None
        self.output_name = None
        self.onnx_model_path = None
        self.class_names = ['Defective', 'Healthy']

        # ImageNet Normalization Constants
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)

        self._load_model(onnx_model_path)

    def _load_model(self, custom_path: Optional[str] = None):
        if custom_path and os.path.exists(custom_path):
            found_path = custom_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            possible_paths = [
                os.path.join(base_dir, "models", "efficientnet_solar_cell.onnx"),
                os.path.join(base_dir, "efficientnet_solar_cell.onnx"),
                "/Users/alial-khazali/Documents/el file/efficientnet_solar_cell.onnx",
                "/Users/alial-khazali/Documents/el file/EL_ALNOOR_AI_App/models/efficientnet_solar_cell.onnx",
            ]
            found_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    found_path = p
                    break

        if not found_path or not HAS_ORT:
            if not found_path:
                print(f"⚠️ Warning: ONNX model file not found in search paths.")
            return

        self.onnx_model_path = found_path
        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(found_path, opts)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            print(f"✅ ONNX AI Engine initialized with model: {found_path}")
        except Exception as e:
            print(f"❌ Failed to load ONNX model: {e}")

    def is_ready(self) -> bool:
        return self.session is not None

    def predict_panel_cells(
        self,
        cells_dict: Dict[str, Any],
        panel_id: str = "Unknown",
        serial_number: str = "Unknown",
        defect_threshold: float = 7.0
    ) -> Dict[str, Any]:
        """
        Runs batch inference on 144 cells.
        Uses calibrated logit difference thresholding to accurately detect real defects
        while completely avoiding false positives on clean/healthy cells.
        """
        if not self.is_ready():
            self._load_model()
            if not self.is_ready():
                raise RuntimeError("AI Model is not loaded. Please verify efficientnet_solar_cell.onnx exists.")

        cell_keys = list(cells_dict.keys())
        cells_batch = []

        for k in cell_keys:
            cdata = cells_dict[k]
            if "png_bytes" in cdata:
                pil_cell = Image.open(io.BytesIO(cdata["png_bytes"])).convert("RGB")
            elif "patch_bgr" in cdata:
                bgr = cdata["patch_bgr"]
                rgb = bgr[:, :, ::-1]
                pil_cell = Image.fromarray(rgb)
            else:
                raise ValueError(f"No image data found for cell {k}")

            if pil_cell.size != (224, 224):
                pil_cell = pil_cell.resize((224, 224), Image.BICUBIC)

            arr = np.array(pil_cell, dtype=np.float32) / 255.0  # (224, 224, 3)
            arr = arr.transpose(2, 0, 1)                         # (3, 224, 224)
            cells_batch.append(arr)

        batch_np = np.stack(cells_batch, axis=0)                # (144, 3, 224, 224)
        batch_normalized = (batch_np - self.mean) / self.std

        # Run ONNX batch inference
        outputs = self.session.run([self.output_name], {self.input_name: batch_normalized})[0]

        # Softmax probabilities
        exp_out = np.exp(outputs - np.max(outputs, axis=1, keepdims=True))
        probs = exp_out / np.sum(exp_out, axis=1, keepdims=True)
        
        # Logit difference: logit(Defective) - logit(Healthy)
        logit_diffs = outputs[:, 0] - outputs[:, 1]

        defective_cells = []
        cells_detail = {}
        defective_count = 0
        healthy_count = 0

        for i, cell_id in enumerate(cell_keys):
            logit_diff = float(logit_diffs[i])
            is_defective = bool(logit_diff >= defect_threshold)
            label = "Defective" if is_defective else "Healthy"
            
            defective_prob = float(probs[i][0]) * 100.0
            healthy_prob = float(probs[i][1]) * 100.0
            conf = defective_prob if is_defective else healthy_prob

            if is_defective:
                defective_count += 1
                defective_cells.append({
                    "cell": cell_id,
                    "confidence": round(conf, 2),
                    "defect_probability": round(defective_prob, 2),
                    "logit_diff": round(logit_diff, 2),
                    "status": "Defective"
                })
            else:
                healthy_count += 1

            cells_detail[cell_id] = {
                "cell": cell_id,
                "status": label,
                "is_defective": is_defective,
                "confidence": round(conf, 2),
                "defective_prob": round(defective_prob, 2),
                "healthy_prob": round(healthy_prob, 2),
                "logit_diff": round(logit_diff, 2)
            }

        panel_status = "FAIL (معيب)" if defective_count > 0 else "PASS (سليم)"
        avg_confidence = float(np.mean([cells_detail[k]["confidence"] for k in cell_keys]))

        result = {
            "panel_id": panel_id,
            "serial_number": serial_number,
            "panel_status": panel_status,
            "is_defective": defective_count > 0,
            "defective_count": defective_count,
            "healthy_count": healthy_count,
            "total_cells": len(cell_keys),
            "average_confidence": round(avg_confidence, 2),
            "defective_cells": [d["cell"] for d in defective_cells],
            "defects_detail": defective_cells,
            "cells_detail": cells_detail,
            "model_version": "EfficientNet-B0 (Calibrated)",
        }

        return result

    def save_aiinfo_json(self, analysis_result: Dict[str, Any], output_dir: str) -> str:
        """Saves aiinfo.json into panel output directory."""
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "aiinfo.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)
        return json_path
