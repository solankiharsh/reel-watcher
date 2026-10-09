"""Loopback-only browser API."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .imports import parse_import
from .library import Library
from .schema import Profile


class ImportRequest(BaseModel):
    text: str = Field(max_length=10_000_000)


class PreviewRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=20)
    provider: Literal["public", "apify"] = "public"
    unit_cost: float | None = Field(default=None, gt=0, le=2, allow_inf_nan=False)
    cap: float | None = Field(default=None, gt=0, le=2, allow_inf_nan=False)


class RunRequest(BaseModel):
    preview_id: str
    approve_cost: bool = False


class BriefRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=5)
    topic: str = Field(min_length=1, max_length=500)
    overrides: Profile | None = None


def create_app(root: Path = Path("out"), *, analyzer=None, downloader=None):
    library = Library(root, analyzer, downloader)

    @asynccontextmanager
    async def lifespan(app):
        with library.session():
            yield

    app = FastAPI(title="Reel-watcher", lifespan=lifespan)
    store = library.store
    app.state.library = library
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def protect_local(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin access is not allowed."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site access is not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Item not found."}, status_code=404)

    @app.get("/api/items")
    def items(q: str = "", status: str = "", collection: str = ""):
        return [
            item
            for item in store.items()
            if (not q or q.lower() in str(item).lower())
            and (not status or item["status"] == status)
            and (not collection or collection in item["collections"])
        ]

    @app.get("/api/items/{item_id}")
    def item(item_id: str):
        return store.get(item_id)

    @app.post("/api/import")
    def import_items(body: ImportRequest):
        entries = parse_import(body.text)
        if not entries:
            raise HTTPException(422, "No Instagram reel/post links found.")
        return [
            store.add(entry["url"], title=entry["url"].split("/")[-2], **entry) for entry in entries
        ]

    @app.post("/api/upload")
    def upload(file: UploadFile, item_id: str | None = None):
        return library.upload(file.file, file.filename or "Local video", item_id)

    @app.post("/api/batches/preview")
    def preview(body: PreviewRequest):
        return library.preview(body.ids, body.provider, body.unit_cost, body.cap)

    @app.post("/api/batches/run")
    def run(body: RunRequest, background: BackgroundTasks):
        preview = library.reserve(body.preview_id, body.approve_cost)
        background.add_task(library.execute, preview)
        return {"id": preview["id"], "status": "processing"}

    @app.get("/api/status")
    def status():
        return {"running": library.running, **library.storage()}

    @app.delete("/api/items/{item_id}/media")
    def delete_media(item_id: str):
        return library.delete_media(item_id)

    @app.get("/api/items/{item_id}/media")
    def media(item_id: str):
        item = store.get(item_id)
        if not item["media"] or not (library.root / item["media"]).is_file():
            raise HTTPException(404, "Local video is not retained.")
        return FileResponse(library.root / item["media"], media_type="video/mp4")

    @app.get("/api/items/{item_id}/frames/{name}")
    def frame(item_id: str, name: str):
        item = store.get(item_id)
        if not item["media"] or name not in {
            "contact.jpg",
            *[f["file"] for f in (item["study"] or {}).get("frames", [])],
        }:
            raise HTTPException(404, "Frame is not retained.")
        path = library.root / "frames" / item_id / name
        if not path.is_file():
            raise HTTPException(404, "Frame is not retained.")
        return FileResponse(path)

    @app.get("/api/items/{item_id}/similar")
    def similar(item_id: str, mode: Literal["subject", "creative"] = "subject"):
        return library.similar(item_id, mode)

    @app.get("/api/profile")
    def profile():
        return store.document("profile", "default", Profile().model_dump())

    @app.put("/api/profile")
    def save_profile(body: Profile):
        return store.put_document("profile", "default", body.model_dump())

    @app.get("/api/briefs")
    def briefs():
        return store.documents("brief")

    @app.post("/api/briefs")
    def create_brief(body: BriefRequest):
        return library.brief(
            body.ids,
            body.topic,
            body.overrides.model_dump(exclude_unset=True) if body.overrides else {},
        )

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    return app
