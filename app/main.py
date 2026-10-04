from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.api.routes import router
from app.api.workflow_routes import WorkflowError, router as workflow_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    description="Local OCR-to-ERP invoice processing API",
    version="1.0.0",
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(workflow_router)


@app.exception_handler(WorkflowError)
async def workflow_error_handler(request, exc: WorkflowError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.as_payload())


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request, exc: StarletteHTTPException) -> JSONResponse:
    is_client_error = exc.status_code < 500
    payload = {"error": {
        "code": "http_error" if is_client_error else "internal_error", "workflow": "platform",
        "message": str(exc.detail) if is_client_error else "The request could not be completed.",
        "technical_detail": None,
        "recoverable": is_client_error, "diagnostics": [],
    }}
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": {
        "code": "invalid_request", "workflow": "platform",
        "message": "The request is missing or contains invalid fields.",
        "technical_detail": None, "recoverable": True,
        "diagnostics": [str(item.get("loc", ())) + ": " + item.get("msg", "invalid") for item in exc.errors()],
    }})


@app.exception_handler(Exception)
async def unhandled_error_handler(request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error")
    return JSONResponse(status_code=500, content={"error": {
        "code": "internal_error", "workflow": "platform",
        "message": "The request could not be completed.",
        "technical_detail": None, "recoverable": False, "diagnostics": [],
    }})

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def review_ui() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/invoice", include_in_schema=False)
@app.get("/invoice/{result_path:path}", include_in_schema=False)
def invoice_ui(result_path: str = "") -> FileResponse:
    return FileResponse(static_dir / "invoice.html")


@app.get("/cdc", include_in_schema=False)
@app.get("/cdc/male", include_in_schema=False)
@app.get("/cdc/result/{result_id}", include_in_schema=False)
@app.get("/cdc/male/result/{result_id}", include_in_schema=False)
def cdc_ui(result_id: str = "") -> FileResponse:
    return FileResponse(static_dir / "cdc.html")


@app.get("/analyses", include_in_schema=False)
def analyses_ui() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
