"""FastAPI app factory for StockSage."""

from fastapi import FastAPI

from api.routes.web import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="StockSage",
        description="Local research UI for shared StockSage analysis history.",
        version="0.1.0",
    )
    app.include_router(web_router)
    return app


app = create_app()
