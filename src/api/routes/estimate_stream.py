"""SSE streaming endpoint for estimate creation progress."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["estimates"])


@router.post("/stream")
async def stream_estimate(
    plans: list[UploadFile],
    project_name: str = Form(...),
    gc_name: str | None = Form(None),
    address: str | None = Form(None),
    scope_type_hints: list[str] = Form(default=[]),
) -> StreamingResponse:
    """Stream estimate creation progress as Server-Sent Events."""
    # Read all files into memory before starting the generator
    # (UploadFile objects can't be used after the request context ends)
    file_data: list[tuple[str, bytes]] = []
    for upload in plans:
        if upload.filename:
            content = await upload.read()
            file_data.append((upload.filename, content))

    async def event_generator():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        def progress_fn(event: dict) -> None:
            # Called from executor thread — thread-safe queue put
            asyncio.get_event_loop().call_soon_threadsafe(queue.put_nowait, event)

        def sse(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        yield sse({"event": "uploading", "message": "Saving files..."})

        with tempfile.TemporaryDirectory() as tmp_dir:
            saved_paths: list[Path] = []
            for filename, content in file_data:
                dest = Path(tmp_dir) / filename
                dest.write_bytes(content)
                saved_paths.append(dest)

            from src.api.routes.estimates import _persist_estimate
            from src.db.session import async_session
            from src.estimation.estimator import estimate_from_pdf

            loop = asyncio.get_running_loop()
            project_estimates = []
            error_msg = None

            for pdf_path in saved_paths:
                try:
                    future = loop.run_in_executor(
                        None,
                        lambda p=pdf_path: estimate_from_pdf(
                            str(p),
                            use_vision=True,
                            progress_fn=progress_fn,
                        ),
                    )

                    # Drain the queue while waiting for the executor
                    while not future.done():
                        try:
                            event = queue.get_nowait()
                            yield sse(event)
                        except asyncio.QueueEmpty:
                            await asyncio.sleep(0.1)

                    # Drain any remaining events
                    while not queue.empty():
                        yield sse(queue.get_nowait())

                    pe = await future
                    project_estimates.append(pe)
                except Exception as exc:
                    error_msg = str(exc)
                    break

            if error_msg or not project_estimates:
                yield sse({"event": "error", "message": error_msg or "No scopes extracted"})
                return

            # Persist to DB
            yield sse({"event": "running_models", "message": "Saving estimate..."})
            try:
                async with async_session() as db:
                    estimate_id: UUID = await _persist_estimate(
                        db,
                        project_estimates,
                        project_name=project_name,
                        gc_name=gc_name,
                        address=address,
                    )
                yield sse({"event": "done", "estimate_id": str(estimate_id)})
            except Exception as exc:
                yield sse({"event": "error", "message": f"DB error: {exc}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
