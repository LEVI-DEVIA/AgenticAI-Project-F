from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from time import time
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from src.agent.agent_ia import DEFAULT_LINK, run_agent

app = FastAPI(
    title="AgentAI-Project-F",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


JOBS: dict[str, dict] = {}


def _count_csv_rows(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return sum(1 for _ in reader)


@app.post("/jobs")
async def create_job(file: UploadFile = File(...)):
    if file.content_type not in {
        "text/csv",
        "application/vnd.ms-excel",
        "application/csv",
    }:
        if not (file.filename or "").lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Le fichier doit être un CSV")

    backend_dir = Path(__file__).resolve().parents[2]
    upload_dir = backend_dir / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    job_id = (file.filename or 'upload.csv').replace('/', '_')
    out_path = upload_dir / job_id
    content = await file.read()
    out_path.write_bytes(content)

    total = _count_csv_rows(out_path)
    if total <= 0:
        raise HTTPException(status_code=400, detail="CSV vide")

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "created_at": time(),
        "csv_path": str(out_path),
        "total": total,
        "submitted": 0,
        "failed": 0,
        "errors": [],
        "rows": [
            {"index": i, "status": "pending", "error": None} for i in range(total)
        ],
    }

    if not DEFAULT_LINK:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["errors"].append(
            {"row_index": None, "error": "DEFAULT_LINK manquant"}
        )
        raise HTTPException(status_code=500, detail="DEFAULT_LINK manquant")

    def on_row_done(row_index: int, ok: bool, error: str | None):
        job = JOBS.get(job_id)
        if not job:
            return
        if 0 <= row_index < len(job["rows"]):
            job["rows"][row_index]["status"] = "success" if ok else "failed"
            job["rows"][row_index]["error"] = error
        if ok:
            job["submitted"] += 1
        else:
            job["failed"] += 1
            job["errors"].append({"row_index": row_index, "error": error})

    async def runner():
        try:
            result = await run_agent(Path(out_path), on_row_done=on_row_done)
            job = JOBS.get(job_id)
            if job:
                job.update(result)
                job["status"] = (
                    "completed"
                    if job.get("failed", 0) == 0
                    else "completed_with_errors"
                )
        except Exception as e:
            job = JOBS.get(job_id)
            if job:
                job["status"] = "failed"
                job["errors"].append({"row_index": None, "error": str(e)})

    asyncio.create_task(runner())
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return job


@app.post("/submit-form")
async def submit_form(file: UploadFile = File(...)):
    job = await create_job(file)
    return {"status": "accepted", **job}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
