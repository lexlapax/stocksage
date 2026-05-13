"""FastAPI app factory for StockSage."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes.web import router as web_router
from api.templates import PROJECT_ROOT


def create_app() -> FastAPI:
    app = FastAPI(
        title="StockSage",
        description="Local research UI for shared StockSage analysis history.",
        version="0.1.0",
    )
    app.mount(
        "/static",
        StaticFiles(directory=PROJECT_ROOT / "web" / "static"),
        name="static",
    )
    app.include_router(web_router)
    return app


app = create_app()
