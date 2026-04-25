"""F23 · /ws/signal WebSocket broadcaster."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


@router.websocket("/ws/signal")
async def ws_signal(websocket: WebSocket) -> None:
    await websocket.accept()
    bus = getattr(websocket.app.state, "run_control_bus", None)
    if bus is None:
        await websocket.close(code=1011)
        return
    q = bus.subscribe_signal()
    try:
        while True:
            envelope = await q.get()
            await websocket.send_json(envelope)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        bus.unsubscribe_signal(q)


__all__ = ["router"]
