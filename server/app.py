#!/usr/bin/env python3
"""
EL AL-NOOR AI - Backend API & WebSocket Server
------------------------------------------------
FastAPI server serving the UI, providing REST endpoints, and streaming
live inspection results via WebSocket.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database import DatabaseManager
from core.ai_engine import SolarCellAIEngine
from core.watcher_service import EcoLabWatcherService

logger = logging.getLogger("EL_Server")

app = FastAPI(title="EL AL-NOOR AI Desktop Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# App directory paths
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
UI_DIR = os.path.join(APP_DIR, "ui")

# Global instances
db = DatabaseManager()
ai_engine = SolarCellAIEngine()

# Connected WebSocket clients
active_websockets: List[WebSocket] = []
event_loop: Optional[asyncio.AbstractEventLoop] = None


def broadcast_to_clients(event_data: Dict[str, Any]):
    """Thread-safe WebSocket broadcaster."""
    global event_loop
    if not active_websockets:
        return

    msg_str = json.dumps(event_data, ensure_ascii=False)

    async def _send_all():
        disconnected = []
        for ws in active_websockets:
            try:
                await ws.send_text(msg_str)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in active_websockets:
                active_websockets.remove(ws)

    if event_loop and event_loop.is_running():
        asyncio.run_coroutine_threadsafe(_send_all(), event_loop)


# Initialize watcher service with broadcast callback
def on_panel_processed(panel_record: Dict[str, Any]):
    logger.info(f"📡 Broadcasting new panel to UI: {panel_record.get('panel_id')}")
    broadcast_to_clients({
        "type": "NEW_INSPECTION",
        "data": panel_record,
        "stats": db.get_stats()
    })


watcher = EcoLabWatcherService(
    db=db,
    ai_engine=ai_engine,
    on_new_inspection_callback=on_panel_processed
)


@app.on_event("startup")
async def startup_event():
    global event_loop
    event_loop = asyncio.get_running_loop()
    watcher.start()
    logger.info("⚡ EL AL-NOOR AI Server is ready.")


@app.on_event("shutdown")
def shutdown_event():
    watcher.stop()


# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial status & stats
        latest = db.get_latest_inspection()
        stats = db.get_stats()
        await websocket.send_text(json.dumps({
            "type": "INIT_STATE",
            "watcher_running": watcher.is_running,
            "watch_folder": watcher.watch_folder,
            "stats": stats,
            "latest_inspection": latest
        }, ensure_ascii=False))

        while True:
            data = await websocket.receive_text()
            # Handle any incoming ping/messages
            msg = json.loads(data)
            if msg.get("action") == "PING":
                await websocket.send_text(json.dumps({"type": "PONG"}))
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception as e:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# ==================== REST API ENDPOINTS ====================

@app.get("/api/status")
def get_system_status():
    return {
        "watcher_running": watcher.is_running,
        "watch_folder": watcher.watch_folder,
        "ai_model_ready": ai_engine.is_ready(),
        "ai_model_path": ai_engine.onnx_model_path,
        "stats": db.get_stats(),
        "active_clients": len(active_websockets)
    }


@app.get("/api/stats")
def get_stats():
    return db.get_stats()


@app.get("/api/inspections")
def list_inspections(
    q: str = Query("", description="Search panel ID or serial"),
    status: str = Query("ALL", description="ALL, PASS, FAIL"),
    match: str = Query("ALL", description="ALL, MATCH, MISMATCH, PENDING"),
    operator: str = Query("ALL", description="Operator name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    items, total = db.get_inspections(
        search_query=q,
        status_filter=status,
        match_filter=match,
        operator_filter=operator,
        limit=limit,
        offset=offset
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/inspections/latest")
def get_latest_inspection():
    latest = db.get_latest_inspection()
    if not latest:
        return JSONResponse(status_code=404, content={"detail": "No inspections found yet"})
    return latest


@app.get("/api/inspections/{insp_id}")
def get_inspection_detail(insp_id: int):
    item = db.get_inspection_by_id(insp_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return item


class DecisionPayload(BaseModel):
    operator_name: str
    match_status: str  # 'MATCH' or 'MISMATCH'
    operator_action: str  # 'Pass to Production', 'Repair', 'Scrap', 'Re-inspect'
    rating: int = 0  # 0 to 3
    manual_correction: Optional[Dict[str, Any]] = None
    notes: str = ""


@app.post("/api/inspections/{insp_id}/decision")
def submit_operator_decision(insp_id: int, payload: DecisionPayload):
    success = db.update_operator_decision(
        inspection_id=insp_id,
        operator_name=payload.operator_name,
        match_status=payload.match_status,
        operator_action=payload.operator_action,
        rating=payload.rating,
        manual_correction=payload.manual_correction,
        notes=payload.notes
    )
    if not success:
        raise HTTPException(status_code=404, detail="Failed to update inspection record")

    # Broadcast updated stats
    broadcast_to_clients({
        "type": "DECISION_UPDATED",
        "inspection_id": insp_id,
        "stats": db.get_stats()
    })
    return {"success": True, "inspection_id": insp_id}


@app.post("/api/inspections/scan-now")
def trigger_scan():
    count = watcher.scan_folder_once()
    return {"success": True, "processed_count": count, "stats": db.get_stats()}


@app.delete("/api/inspections/clear")
def clear_all():
    db.clear_all_inspections()
    watcher.processed_panel_ids.clear()
    broadcast_to_clients({
        "type": "DATABASE_CLEARED",
        "stats": db.get_stats()
    })
    return {"success": True}


# ==================== OPERATORS API ====================

@app.get("/api/operators")
def get_operators(active_only: bool = True):
    return db.get_operators(active_only=active_only)


class OperatorPayload(BaseModel):
    name: str
    role: str = "مهندس جودة"
    code: Optional[str] = None
    is_active: bool = True


@app.post("/api/operators")
def add_operator(payload: OperatorPayload):
    op_id = db.add_operator(name=payload.name, role=payload.role, code=payload.code)
    return {"success": True, "id": op_id, "operators": db.get_operators()}


@app.put("/api/operators/{op_id}")
def update_operator(op_id: int, payload: OperatorPayload):
    success = db.update_operator(
        op_id=op_id,
        name=payload.name,
        role=payload.role,
        code=payload.code or f"ENG-{op_id:03d}",
        is_active=payload.is_active
    )
    return {"success": success, "operators": db.get_operators()}


@app.delete("/api/operators/{op_id}")
def delete_operator(op_id: int):
    success = db.delete_operator(op_id)
    return {"success": success, "operators": db.get_operators()}


# ==================== SETTINGS API ====================

@app.get("/api/settings")
def get_settings():
    return db.get_all_settings()


@app.post("/api/settings")
def update_settings(settings: Dict[str, Any] = Body(...)):
    for k, v in settings.items():
        db.set_setting(k, v)
        if k == "watch_folder":
            watcher.set_watch_folder(str(v))
    return {"success": True, "settings": db.get_all_settings()}


# ==================== SIMULATOR / TEST API ====================

@app.post("/api/simulate-sample")
def simulate_sample(panel_name: str = Body("1", embed=True)):
    """
    Feeds a sample panel from EcoLAB dummy folder into the pipeline to test live without hardware.
    """
    sample_dir = "/Users/alial-khazali/Documents/el file/EcoLAB/v3.17.2/00/00-00/00-00-00"
    el_path = os.path.join(sample_dir, f"{panel_name}.el")
    tif_path = os.path.join(sample_dir, f"{panel_name}.1.tif")

    if not os.path.exists(el_path) or not os.path.exists(tif_path):
        # Find any available sample
        all_els = [f for f in os.listdir(sample_dir) if f.endswith(".el")]
        if all_els:
            base = os.path.splitext(all_els[0])[0]
            el_path = os.path.join(sample_dir, f"{base}.el")
            tif_path = os.path.join(sample_dir, f"{base}.1.tif")
        else:
            raise HTTPException(status_code=404, detail="No sample files found in EcoLAB folder")

    result = watcher.process_panel_pair(el_path, tif_path, force=True)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to process simulated panel")

    return {"success": True, "panel": result}


# ==================== AUTO UPDATER API ====================

@app.post("/api/check-update")
def trigger_update_check():
    from core.updater import check_and_apply_update
    result = check_and_apply_update()
    return result


# ==================== IMAGE FILE SERVING ====================

@app.get("/api/image")
def get_image(path: str = Query(...)):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(path)


# Mount static assets and UI
app.mount("/assets", StaticFiles(directory=os.path.join(UI_DIR, "assets")), name="assets")
app.mount("/css", StaticFiles(directory=os.path.join(UI_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(UI_DIR, "js")), name="js")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(UI_DIR, "index.html"))
