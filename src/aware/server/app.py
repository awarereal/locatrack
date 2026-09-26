"""
Aware FastAPI application.

Main API server for location sharing.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from aware import __version__
from aware.config import settings
from aware.server.routes import auth, circles, devices, locations, lookups, tracking


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    from aware.db.engine import init_db

    await init_db()
    yield
    # Shutdown
    from aware.db.engine import close_db

    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Aware API",
    description="Consent-based location sharing and OSINT lookup API",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    if settings.debug:
        import traceback

        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Health check
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "environment": settings.environment,
    }


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(devices.router, prefix="/devices", tags=["Devices"])
app.include_router(locations.router, prefix="/locations", tags=["Locations"])
app.include_router(circles.router, prefix="/circles", tags=["Circles"])
app.include_router(lookups.router, prefix="/lookup", tags=["Lookups"])
app.include_router(tracking.router, prefix="/track", tags=["Tracking Links"])


# Short URL redirect for tracking links
@app.get("/t/{code}")
async def track_redirect(code: str) -> RedirectResponse:
    """Redirect short tracking URL to the capture page."""
    return RedirectResponse(url=f"/track/page/{code}", status_code=302)


# Root endpoint
@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "Aware API",
        "version": __version__,
        "docs": "/docs",
    }
