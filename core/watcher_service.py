#!/usr/bin/env python3
"""
EL AL-NOOR AI - Real-time Watcher & Automation Pipeline
---------------------------------------------------------
Monitors the shared watch folder connected to EcoLab EL HR tester.
When a new panel is captured (.el and .tif files):
  1. Parses .el -> generates info.json
  2. Precision Crops 144 cells (224x224) -> saves PNGs
  3. Runs EfficientNet AI model -> generates aiinfo.json
  4. Renders dual X-annotated overlays (Human vs AI)
  5. Inserts record to SQL Database
  6. Dispatches real-time WebSocket broadcast to UI
"""

import os
import time
import glob
import logging
import threading
from typing import Dict, Any, List, Set, Optional, Callable

from core.el_reader import ElFileReader
from core.cropper_engine import SolarPanelCropperEngine
from core.ai_engine import SolarCellAIEngine
from core.overlay_engine import PanelOverlayEngine
from core.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("WatcherPipeline")


class EcoLabWatcherService:
    def __init__(
        self,
        db: DatabaseManager,
        ai_engine: SolarCellAIEngine,
        on_new_inspection_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.db = db
        self.ai_engine = ai_engine
        self.on_new_inspection_callback = on_new_inspection_callback

        self.watch_folder = self.db.get_setting("watch_folder", "")
        self.output_folder = self.db.get_setting("output_folder", "")
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None

        self.processed_panel_ids: Set[str] = set()
        self._load_existing_processed_ids()

    def _load_existing_processed_ids(self):
        """Loads already inspected panels from DB to prevent re-processing."""
        try:
            rows, _ = self.db.get_inspections(limit=10000)
            for r in rows:
                if r.get("panel_id"):
                    self.processed_panel_ids.add(r["panel_id"])
                if r.get("file_name"):
                    base = os.path.splitext(r["file_name"])[0]
                    self.processed_panel_ids.add(base)
            logger.info(f"Loaded {len(self.processed_panel_ids)} previously processed panel IDs from DB.")
        except Exception as e:
            logger.error(f"Error loading existing IDs from DB: {e}")

    def start(self):
        """Starts background file listener thread."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="EcoLabWatcherThread")
        self.worker_thread.start()
        logger.info(f"🚀 EcoLab Watcher Service started on folder: {self.watch_folder}")

    def stop(self):
        """Stops background file listener."""
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        logger.info("🛑 EcoLab Watcher Service stopped.")

    def set_watch_folder(self, folder_path: str):
        self.watch_folder = folder_path.strip('"\'')
        self.db.set_setting("watch_folder", self.watch_folder)
        logger.info(f"Updated watch folder to: {self.watch_folder}")

    def _wait_for_file_stability(self, file_path: str, checks: int = 3, interval: float = 0.3) -> bool:
        """Ensures EcoLab has completely finished writing the file to disk."""
        if not os.path.exists(file_path):
            return False
        try:
            last_size = -1
            for _ in range(checks):
                if not os.path.exists(file_path):
                    return False
                size = os.path.getsize(file_path)
                if size == last_size and size > 0:
                    return True
                last_size = size
                time.sleep(interval)
            return True
        except Exception:
            return False

    def find_matching_image(self, el_path: str) -> Optional[str]:
        """Finds matching TIF/TIFF/PNG image for the given .el file."""
        folder = os.path.dirname(el_path)
        base_name = os.path.splitext(os.path.basename(el_path))[0]

        # Common EcoLab image naming schemes:
        # 1) <panel>.1.tif
        # 2) <panel>.tif
        # 3) <panel>.tiff
        # 4) <panel>.png
        candidates = [
            os.path.join(folder, f"{base_name}.1.tif"),
            os.path.join(folder, f"{base_name}.1.tiff"),
            os.path.join(folder, f"{base_name}.tif"),
            os.path.join(folder, f"{base_name}.tiff"),
            os.path.join(folder, f"{base_name}.png"),
            os.path.join(folder, f"{base_name}.jpg"),
        ]

        for cand in candidates:
            if os.path.exists(cand) and os.path.getsize(cand) > 1000:
                return cand

        # Wildcard fallback
        wildcard_matches = glob.glob(os.path.join(folder, f"{base_name}*.tif*"))
        if wildcard_matches:
            return wildcard_matches[0]

        return None

    def process_panel_pair(self, el_path: str, tif_path: str, force: bool = False) -> Optional[Dict[str, Any]]:
        """Executes the complete inspection & ML analysis pipeline for a panel."""
        panel_id = os.path.splitext(os.path.basename(el_path))[0]

        if not force and panel_id in self.processed_panel_ids:
            return None

        logger.info(f"⚙️ Processing new panel: [{panel_id}] ...")

        # 1. Ensure file write completion
        if not self._wait_for_file_stability(el_path) or not self._wait_for_file_stability(tif_path):
            logger.warning(f"File stability check pending for panel {panel_id}")
            return None

        try:
            # Prepare output directories
            app_data_dir = self.db.get_setting("output_folder", "")
            if not app_data_dir:
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                app_data_dir = os.path.join(app_dir, "data", "processed_panels")
            
            panel_out_dir = os.path.join(app_data_dir, panel_id)
            cells_out_dir = os.path.join(panel_out_dir, "cells_144")
            os.makedirs(cells_out_dir, exist_ok=True)

            # Step 1: Read .el file -> generate info.json
            reader = ElFileReader(el_path)
            el_metadata = reader.read()
            info_json_path = reader.save_info_json(panel_out_dir)

            # Step 2: Precision Cropping into 144 cells
            image_bgr = SolarPanelCropperEngine.load_image_from_path(tif_path)
            cropper_result = SolarPanelCropperEngine.process_panel(image_bgr)
            
            # Save cropped cell patches
            SolarPanelCropperEngine.save_cells_to_folder(
                cropper_result["cells"], cells_out_dir, prefix=panel_id
            )

            # Step 3: Run AI Model on 144 cells -> generate aiinfo.json
            ai_result = self.ai_engine.predict_panel_cells(
                cropper_result["cells"],
                panel_id=panel_id,
                serial_number=el_metadata["serial_number"]
            )
            aiinfo_json_path = self.ai_engine.save_aiinfo_json(ai_result, panel_out_dir)

            # Step 4: Render Overlays (Reverse Recomposition from 144 cells with Red X)
            ai_conf_map = {
                d["cell"]: d["confidence"] for d in ai_result["defects_detail"]
            }
            human_overlay_path, ai_overlay_path = PanelOverlayEngine.save_annotated_panels(
                cells_dict=cropper_result["cells"],
                human_defects=el_metadata["defective_cells"],
                ai_defects=ai_result["defective_cells"],
                ai_confidence_map=ai_conf_map,
                output_dir=panel_out_dir,
                panel_id=panel_id
            )

            # Step 5: Save Record to SQL Database
            # Get current active operator
            operators = self.db.get_operators(active_only=True)
            default_op = operators[0] if operators else {"id": 1, "name": "المهندس/ محمد أحمد"}

            db_record = {
                "panel_id": panel_id,
                "serial_number": el_metadata["serial_number"],
                "file_name": os.path.basename(tif_path),
                "timestamp": el_metadata["timestamp"],
                "original_tif_path": os.path.abspath(tif_path),
                "original_el_path": os.path.abspath(el_path),
                "info_json_path": os.path.abspath(info_json_path),
                "aiinfo_json_path": os.path.abspath(aiinfo_json_path),
                "human_overlay_image_path": os.path.abspath(human_overlay_path),
                "ai_overlay_image_path": os.path.abspath(ai_overlay_path),
                "cropped_cells_dir": os.path.abspath(cells_out_dir),
                "human_status": el_metadata["panel_status"],
                "ai_status": ai_result["panel_status"],
                "human_defects": el_metadata["defective_cells"],
                "ai_defects": ai_result["defective_cells"],
                "ai_confidence": ai_result["average_confidence"],
                "operator_id": default_op.get("id", 1),
                "operator_name": default_op.get("name", "المهندس/ محمد أحمد"),
                "operator_action": "Pass to Production" if not el_metadata["is_defective"] else "Repair",
                "rating": 3 if not el_metadata["is_defective"] else 0,
            }

            insp_id = self.db.save_inspection(db_record)
            db_record["id"] = insp_id
            self.processed_panel_ids.add(panel_id)

            logger.info(f"✅ Panel [{panel_id}] successfully analyzed and saved! (ID: {insp_id})")

            # Step 6: Dispatch live event to UI
            if self.on_new_inspection_callback:
                try:
                    self.on_new_inspection_callback(db_record)
                except Exception as cb_err:
                    logger.error(f"Callback error: {cb_err}")

            return db_record

        except Exception as e:
            logger.error(f"❌ Error analyzing panel [{panel_id}]: {e}", exc_info=True)
            return None

    def scan_folder_once(self) -> int:
        """Scans watch folder once and processes any pending panels."""
        if not self.watch_folder or not os.path.exists(self.watch_folder):
            return 0

        el_files = sorted(glob.glob(os.path.join(self.watch_folder, "*.el")))
        processed_count = 0

        for el_file in el_files:
            base_name = os.path.splitext(os.path.basename(el_file))[0]
            if base_name in self.processed_panel_ids:
                continue

            matching_tif = self.find_matching_image(el_file)
            if matching_tif:
                res = self.process_panel_pair(el_file, matching_tif)
                if res:
                    processed_count += 1

        return processed_count

    def _run_loop(self):
        """Continuous polling loop."""
        while self.is_running:
            try:
                auto_proc = self.db.get_setting("auto_process", "true").lower() == "true"
                if auto_proc and self.watch_folder and os.path.exists(self.watch_folder):
                    self.scan_folder_once()
            except Exception as e:
                logger.error(f"Error in watcher loop: {e}")

            time.sleep(1.5)
