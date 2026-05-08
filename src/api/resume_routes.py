from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from src.api.sse import sse_data
from src.resume.artifacts import (
    ArtifactMeta,
    artifact_paths,
    load_meta,
    new_artifact_id,
    write_docx_from_markdown,
    write_meta,
)
from src.resume.extract import extract_text_from_bytes, read_upload_bytes
from src.resume.pipeline import (
    PipelineContext,
    analyze_resume_jd,
    draft_resume,
    keyword_coverage_score,
    refine_resume,
)
from src.schemas.resume import (
    ResumeAnalyzeResponse,
    ResumeGenerateRequest,
    ResumeRefineRequest,
    ResumeRefineResponse,
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
    return await analyze_resume_jd(resume_text, jd_text)


@router.post("/generate")
async def resume_generate(body: ResumeGenerateRequest) -> StreamingResponse:
    ctx_resume = body.resume_text
    ctx_jd = body.jd_text

    async def event_gen():
        yield sse_data({"stage": "prepare", "message": "Starting resume draft…"})
        ctx = PipelineContext(
            resume_text=ctx_resume,
            jd_text=ctx_jd,
            preferences=body.preferences,
            keywords=body.keywords,
        )
        yield sse_data({"stage": "draft", "message": "Drafting tailored resume (LLM)…"})
        try:
            md = await draft_resume(ctx)
        except Exception as e:
            yield sse_data({"stage": "error", "message": str(e)})
            return
        yield sse_data({"stage": "ats_check", "message": "Checking keyword coverage…"})
        score = keyword_coverage_score(md, body.keywords)
        yield sse_data({"stage": "ats_check", "score": round(score, 3)})
        aid = new_artifact_id()
        yield sse_data({"stage": "export", "message": "Writing Word document…"})
        try:
            write_docx_from_markdown(aid, md)
            write_meta(
                ArtifactMeta(
                    artifact_id=aid,
                    resume_text=ctx_resume,
                    jd_text=ctx_jd,
                    draft_markdown=md,
                    preferences=body.preferences,
                )
            )
        except Exception as e:
            yield sse_data({"stage": "error", "message": str(e)})
            return
        yield sse_data({"stage": "complete", "artifact_id": aid})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/refine", response_model=ResumeRefineResponse)
async def resume_refine(body: ResumeRefineRequest) -> ResumeRefineResponse:
    try:
        meta = load_meta(body.artifact_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Artifact not found") from e

    jd = body.jd_text or meta.jd_text
    draft = body.resume_text or meta.draft_markdown
    try:
        md = await refine_resume(draft_markdown=draft, jd_text=jd, feedback=body.feedback)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    aid = new_artifact_id()
    write_docx_from_markdown(aid, md)
    write_meta(
        ArtifactMeta(
            artifact_id=aid,
            resume_text=meta.resume_text,
            jd_text=jd,
            draft_markdown=md,
            preferences=meta.preferences,
        )
    )
    return ResumeRefineResponse(artifact_id=aid)


@router.get("/download/{artifact_id}")
async def resume_download(artifact_id: str) -> FileResponse:
    docx_path, meta_path = artifact_paths(artifact_id)
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
