from fastapi import FastAPI

from auxd_api import __version__

app = FastAPI(
    title="auxd API",
    version=__version__,
    description="auxd backend — social album-tracking platform.",
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
