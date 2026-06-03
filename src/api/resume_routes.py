from __future__ import annotations

import asyncio
import queue
from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from src.api.sse import sse_data
from src.resume.artifacts import (
    ArtifactMeta,
    artifact_paths,
    load_meta,
    new_artifact_id,
    save_source_upload,
    write_meta,
    write_resume_exports,
)
from src.resume.extract import extract_text_from_bytes, read_upload_bytes
from src.resume.pipeline import (
    PipelineContext,
    analyze_resume_jd,
    compute_tailored_ats_match,
    draft_resume,
    refine_resume,
)
from src.schemas.resume import (
    ResumeAnalyzeResponse,
    ResumeGenerateRequest,
    ResumeRefineRequest,
    ResumeRefineResponse,
    ResumeSaveRequest,
)

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/analyze", response_model=ResumeAnalyzeResponse)
async def resume_analyze(
    jd_text: str = Form(..., min_length=20),
    file: UploadFile = File(...),
) -> ResumeAnalyzeResponse:
    try:
        raw = await read_upload_bytes(file)
        resume_text = extract_text_from_bytes(file.filename or "resume.docx", raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if len(resume_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Could not extract enough text from the file.")
    upload_id = new_artifact_id()
    save_source_upload(upload_id, file.filename or "resume.docx", raw)
    result = await analyze_resume_jd(resume_text, jd_text)
    return result.model_copy(update={"source_upload_id": upload_id})


@router.post("/generate")
async def resume_generate(body: ResumeGenerateRequest) -> StreamingResponse:
    ctx_resume = body.resume_text
    ctx_jd = body.jd_text

    async def event_gen():
        stage_q: queue.SimpleQueue[dict[str, str | float]] = queue.SimpleQueue()

        def on_stage(stage: str, message: str) -> None:
            stage_q.put({"stage": stage, "message": message})

        yield sse_data({"stage": "prepare", "message": "Starting fusion resume draft…"})
        ctx = PipelineContext(
            resume_text=ctx_resume,
            jd_text=ctx_jd,
            preferences=body.preferences,
            keywords=body.keywords,
        )
        yield sse_data({"stage": "draft", "message": "Four models debating resume drafts…"})

        draft_task = asyncio.create_task(draft_resume(ctx, on_stage=on_stage))
        while not draft_task.done():
            while not stage_q.empty():
                yield sse_data(stage_q.get())
            await asyncio.sleep(0.05)
        while not stage_q.empty():
            yield sse_data(stage_q.get())

        try:
            md = await draft_task
        except Exception as e:
            yield sse_data({"stage": "error", "message": str(e)})
            return
        yield sse_data({"stage": "ats_check", "message": "Scoring ATS match for this role…"})
        ats = compute_tailored_ats_match(
            resume_text=md,
            jd_text=ctx_jd,
            keywords=body.keywords,
            gaps=[],
        )
        yield sse_data({
            "stage": "ats_check",
            "score": round(ats.score_pct / 100.0, 3),
            "ats_match": ats.model_dump(),
        })
        aid = new_artifact_id()
        yield sse_data({"stage": "export", "message": "Writing Word and PDF documents…"})
        try:
            write_resume_exports(
                aid,
                md,
                source_text=ctx_resume,
                source_upload_id=body.source_upload_id,
            )
            write_meta(
                ArtifactMeta(
                    artifact_id=aid,
                    resume_text=ctx_resume,
                    jd_text=ctx_jd,
                    draft_markdown=md,
                    preferences=body.preferences,
                    source_upload_id=body.source_upload_id,
                )
            )
        except Exception as e:
            yield sse_data({"stage": "error", "message": str(e)})
            return
        yield sse_data({
            "stage": "complete",
            "artifact_id": aid,
            "draft_markdown": md,
            "ats_match": ats.model_dump(),
        })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/refine", response_model=ResumeRefineResponse)
async def resume_refine(body: ResumeRefineRequest) -> ResumeRefineResponse:
    try:
        meta = load_meta(body.artifact_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Artifact not found") from e

    jd = body.jd_text or meta.jd_text
    draft = body.resume_text or meta.draft_markdown
    try:
        md = await refine_resume(
            draft_markdown=draft,
            jd_text=jd,
            feedback=body.feedback,
            original_resume_text=meta.resume_text,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    aid = new_artifact_id()
    write_resume_exports(
        aid,
        md,
        source_text=meta.resume_text,
        source_upload_id=meta.source_upload_id,
    )
    write_meta(
        ArtifactMeta(
            artifact_id=aid,
            resume_text=meta.resume_text,
            jd_text=jd,
            draft_markdown=md,
            preferences=meta.preferences,
            source_upload_id=meta.source_upload_id,
        )
    )
    keywords = body.keywords or []
    ats = (
        compute_tailored_ats_match(
            resume_text=md,
            jd_text=jd,
            keywords=keywords,
            gaps=body.gaps,
        )
        if keywords
        else None
    )
    return ResumeRefineResponse(artifact_id=aid, draft_markdown=md, ats_match=ats)


@router.post("/save")
async def resume_save(body: ResumeSaveRequest) -> dict[str, str]:
    try:
        meta = load_meta(body.artifact_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Artifact not found") from e

    write_resume_exports(
        body.artifact_id,
        body.draft_markdown,
        source_text=meta.resume_text,
        source_upload_id=meta.source_upload_id,
    )
    write_meta(
        ArtifactMeta(
            artifact_id=body.artifact_id,
            resume_text=meta.resume_text,
            jd_text=meta.jd_text,
            draft_markdown=body.draft_markdown,
            preferences=meta.preferences,
            source_upload_id=meta.source_upload_id,
        )
    )
    return {"status": "ok"}


@router.get("/download/{artifact_id}")
async def resume_download(
    artifact_id: str,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
) -> FileResponse:
    try:
        meta = load_meta(artifact_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Artifact not found") from e

    docx_path, pdf_path, _ = artifact_paths(artifact_id)
    write_resume_exports(
        artifact_id,
        meta.draft_markdown,
        source_text=meta.resume_text,
        source_upload_id=meta.source_upload_id,
    )

    if format == "pdf":
        if not pdf_path.is_file():
            raise HTTPException(status_code=404, detail="PDF not found")
        return FileResponse(
            path=pdf_path,
            filename=f"resume-{artifact_id[:8]}.pdf",
            media_type="application/pdf",
        )

    if not docx_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=docx_path,
        filename=f"resume-{artifact_id[:8]}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/artifact/{artifact_id}/meta")
async def artifact_meta(artifact_id: str) -> dict:
    try:
        m = load_meta(artifact_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Artifact not found") from e
    return asdict(m)
