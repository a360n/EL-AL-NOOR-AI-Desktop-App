#!/usr/bin/env python3
"""
EL AL-NOOR AI - SQL Database Manager (SQLite)
----------------------------------------------
Stores complete inspection records, metadata, operator decisions,
AI audit history, operator management, and application settings.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(app_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "el_alnoor_ai.db")

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Operators Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'مهندس جودة',
                    code TEXT UNIQUE,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Inspections Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    panel_id TEXT NOT NULL,
                    serial_number TEXT,
                    file_name TEXT,
                    timestamp TEXT,
                    original_tif_path TEXT,
                    original_el_path TEXT,
                    info_json_path TEXT,
                    aiinfo_json_path TEXT,
                    human_overlay_image_path TEXT,
                    ai_overlay_image_path TEXT,
                    cropped_cells_dir TEXT,
                    human_status TEXT,
                    ai_status TEXT,
                    human_defects TEXT,
                    ai_defects TEXT,
                    human_defects_count INTEGER DEFAULT 0,
                    ai_defects_count INTEGER DEFAULT 0,
                    ai_confidence REAL DEFAULT 0.0,
                    operator_id INTEGER,
                    operator_name TEXT,
                    match_status TEXT DEFAULT 'PENDING',
                    operator_action TEXT,
                    rating INTEGER DEFAULT 0,
                    manual_correction TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (operator_id) REFERENCES operators (id)
                )
            """)

            # Indexes for fast search
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_panel_id ON inspections (panel_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_serial ON inspections (serial_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_status ON inspections (match_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON inspections (created_at)")

            # 3. Settings Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default operators if table is empty
            cursor.execute("SELECT COUNT(*) FROM operators")
            if cursor.fetchone()[0] == 0:
                default_operators = [
                    ("المهندس/ محمد أحمد", "مهندس رقابة جودة", "ENG-001"),
                    ("المهندس/ علي الخالدي", "مهندس خط الإنتاج", "ENG-002"),
                    ("المهندسة/ سارة ناصر", "مهندسة فحص الأشعة EL", "ENG-003"),
                    ("الفني/ أحمد حسن", "فني فحص متقدم", "TECH-001"),
                ]
                cursor.executemany(
                    "INSERT INTO operators (name, role, code) VALUES (?, ?, ?)",
                    default_operators
                )

            # Seed default settings if empty
            default_settings = {
                "watch_folder": "/Users/alial-khazali/Documents/el file/EcoLAB/v3.17.2/00/00-00/00-00-00",
                "output_folder": os.path.join(os.path.dirname(self.db_path), "processed_panels"),
                "language": "ar",
                "auto_process": "true",
                "confidence_threshold": "50",
                "sound_alerts": "true"
            }
            for k, v in default_settings.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
                )

            conn.commit()

    # ==================== SETTINGS CRUD ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: Any):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                (key, str(value))
            )
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # ==================== OPERATORS CRUD ====================

    def get_operators(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM operators"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY id ASC"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def add_operator(self, name: str, role: str = "مهندس جودة", code: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if not code:
                cursor.execute("SELECT COUNT(*) FROM operators")
                code = f"ENG-{(cursor.fetchone()[0] + 1):03d}"
            cursor.execute(
                "INSERT INTO operators (name, role, code) VALUES (?, ?, ?)",
                (name.strip(), role.strip(), code.strip())
            )
            conn.commit()
            return cursor.lastrowid

    def update_operator(self, op_id: int, name: str, role: str, code: str, is_active: bool = True) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE operators SET name = ?, role = ?, code = ?, is_active = ? WHERE id = ?",
                (name.strip(), role.strip(), code.strip(), 1 if is_active else 0, op_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_operator(self, op_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Soft delete
            cursor.execute("UPDATE operators SET is_active = 0 WHERE id = ?", (op_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==================== INSPECTIONS CRUD ====================

    def save_inspection(self, data: Dict[str, Any]) -> int:
        """Inserts or updates an inspection record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if panel already exists
            cursor.execute("SELECT id FROM inspections WHERE panel_id = ? OR file_name = ?", 
                           (data.get("panel_id", ""), data.get("file_name", "")))
            existing = cursor.fetchone()

            human_defects_json = json.dumps(data.get("human_defects", []), ensure_ascii=False)
            ai_defects_json = json.dumps(data.get("ai_defects", []), ensure_ascii=False)
            manual_corr_json = json.dumps(data.get("manual_correction", {}), ensure_ascii=False) if data.get("manual_correction") else None

            # Calculate default match_status if not explicitly provided
            h_stat = "FAIL" if "FAIL" in data.get("human_status", "") else "PASS"
            a_stat = "FAIL" if "FAIL" in data.get("ai_status", "") else "PASS"
            default_match = "MATCH" if h_stat == a_stat else "MISMATCH"
            match_status = data.get("match_status", default_match)

            if existing:
                insp_id = existing["id"]
                cursor.execute("""
                    UPDATE inspections SET
                        serial_number = ?, file_name = ?, timestamp = ?,
                        original_tif_path = ?, original_el_path = ?,
                        info_json_path = ?, aiinfo_json_path = ?,
                        human_overlay_image_path = ?, ai_overlay_image_path = ?,
                        cropped_cells_dir = ?, human_status = ?, ai_status = ?,
                        human_defects = ?, ai_defects = ?,
                        human_defects_count = ?, ai_defects_count = ?,
                        ai_confidence = ?, operator_name = ?,
                        match_status = COALESCE(?, match_status)
                    WHERE id = ?
                """, (
                    data.get("serial_number"), data.get("file_name"), data.get("timestamp"),
                    data.get("original_tif_path"), data.get("original_el_path"),
                    data.get("info_json_path"), data.get("aiinfo_json_path"),
                    data.get("human_overlay_image_path"), data.get("ai_overlay_image_path"),
                    data.get("cropped_cells_dir"), data.get("human_status"), data.get("ai_status"),
                    human_defects_json, ai_defects_json,
                    len(data.get("human_defects", [])), len(data.get("ai_defects", [])),
                    data.get("ai_confidence", 0.0), data.get("operator_name"),
                    match_status, insp_id
                ))
                conn.commit()
                return insp_id
            else:
                cursor.execute("""
                    INSERT INTO inspections (
                        panel_id, serial_number, file_name, timestamp,
                        original_tif_path, original_el_path,
                        info_json_path, aiinfo_json_path,
                        human_overlay_image_path, ai_overlay_image_path,
                        cropped_cells_dir, human_status, ai_status,
                        human_defects, ai_defects,
                        human_defects_count, ai_defects_count,
                        ai_confidence, operator_id, operator_name,
                        match_status, operator_action, rating, manual_correction, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("panel_id"), data.get("serial_number"), data.get("file_name"), data.get("timestamp"),
                    data.get("original_tif_path"), data.get("original_el_path"),
                    data.get("info_json_path"), data.get("aiinfo_json_path"),
                    data.get("human_overlay_image_path"), data.get("ai_overlay_image_path"),
                    data.get("cropped_cells_dir"), data.get("human_status"), data.get("ai_status"),
                    human_defects_json, ai_defects_json,
                    len(data.get("human_defects", [])), len(data.get("ai_defects", [])),
                    data.get("ai_confidence", 0.0), data.get("operator_id"), data.get("operator_name"),
                    match_status, data.get("operator_action", "Pass to Production"),
                    data.get("rating", 0), manual_corr_json, data.get("notes", "")
                ))
                conn.commit()
                return cursor.lastrowid

    def update_operator_decision(
        self,
        inspection_id: int,
        operator_name: str,
        match_status: str,
        operator_action: str,
        rating: int = 0,
        manual_correction: Optional[Dict[str, Any]] = None,
        notes: str = ""
    ) -> bool:
        """Records operator's verified decision / agreement or manual correction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            corr_json = json.dumps(manual_correction, ensure_ascii=False) if manual_correction else None
            cursor.execute("""
                UPDATE inspections SET
                    operator_name = ?,
                    match_status = ?,
                    operator_action = ?,
                    rating = ?,
                    manual_correction = ?,
                    notes = ?
                WHERE id = ?
            """, (operator_name, match_status, operator_action, rating, corr_json, notes, inspection_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_inspections(
        self,
        search_query: str = "",
        status_filter: str = "ALL",
        match_filter: str = "ALL",
        operator_filter: str = "ALL",
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieves paginated and filtered inspection records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params = []

            if search_query:
                conditions.append("(panel_id LIKE ? OR serial_number LIKE ? OR file_name LIKE ?)")
                q = f"%{search_query}%"
                params.extend([q, q, q])

            if status_filter != "ALL":
                if status_filter == "PASS":
                    conditions.append("human_status LIKE '%PASS%'")
                elif status_filter == "FAIL":
                    conditions.append("human_status LIKE '%FAIL%'")

            if match_filter != "ALL":
                conditions.append("match_status = ?")
                params.append(match_filter)

            if operator_filter != "ALL":
                conditions.append("operator_name = ?")
                params.append(operator_filter)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Count total
            cursor.execute(f"SELECT COUNT(*) FROM inspections {where_clause}", params)
            total_count = cursor.fetchone()[0]

            # Fetch rows
            query = f"""
                SELECT * FROM inspections
                {where_clause}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(query, params + [limit, offset])
            rows = [dict(r) for r in cursor.fetchall()]

            # Parse JSON fields
            for r in rows:
                try:
                    r["human_defects"] = json.loads(r["human_defects"]) if r["human_defects"] else []
                except:
                    r["human_defects"] = []
                try:
                    r["ai_defects"] = json.loads(r["ai_defects"]) if r["ai_defects"] else []
                except:
                    r["ai_defects"] = []
                try:
                    r["manual_correction"] = json.loads(r["manual_correction"]) if r["manual_correction"] else None
                except:
                    r["manual_correction"] = None

            return rows, total_count

    def get_inspection_by_id(self, insp_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspections WHERE id = ?", (insp_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["human_defects"] = json.loads(res["human_defects"]) if res["human_defects"] else []
            except:
                res["human_defects"] = []
            try:
                res["ai_defects"] = json.loads(res["ai_defects"]) if res["ai_defects"] else []
            except:
                res["ai_defects"] = []
            try:
                res["manual_correction"] = json.loads(res["manual_correction"]) if res["manual_correction"] else None
            except:
                res["manual_correction"] = None
            return res

    def get_latest_inspection(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM inspections ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return self.get_inspection_by_id(row["id"])
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Calculates live KPI metrics for dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inspections")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE human_status LIKE '%PASS%'")
            pass_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE human_status LIKE '%FAIL%'")
            fail_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE match_status = 'MATCH'")
            match_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE match_status = 'MISMATCH'")
            mismatch_count = cursor.fetchone()[0]

            pass_pct = round((pass_count / total * 100), 1) if total > 0 else 0
            fail_pct = round((fail_count / total * 100), 1) if total > 0 else 0
            accuracy_rate = round((match_count / (match_count + mismatch_count) * 100), 1) if (match_count + mismatch_count) > 0 else 100.0

            return {
                "total": total,
                "pass_count": pass_count,
                "pass_percent": pass_pct,
                "fail_count": fail_count,
                "fail_percent": fail_pct,
                "match_count": match_count,
                "mismatch_count": mismatch_count,
                "accuracy_rate": accuracy_rate
            }

    def clear_all_inspections(self) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inspections")
            conn.commit()
            return True
