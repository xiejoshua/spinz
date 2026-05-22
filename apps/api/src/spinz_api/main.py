from fastapi import FastAPI

from spinz_api import __version__

app = FastAPI(
    title="Spinz API",
    version=__version__,
    description="Spinz backend — social album-tracking platform.",
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
