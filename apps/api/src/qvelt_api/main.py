from fastapi import FastAPI

app = FastAPI(title="QVELT API", version="0.0.1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
