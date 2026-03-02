"""
Family Crisis Playbook — FastAPI Backend
=========================================
Phase 1: Walkthrough + Supabase session persistence
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ═══ SUPABASE CLIENT ═══
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ═══ WALKTHROUGH DEFINITION ═══
# Load the question structure (source of truth)
WALKTHROUGH_PATH = os.path.join(os.path.dirname(__file__), "walkthrough_definition.json")
with open(WALKTHROUGH_PATH, "r") as f:
    WALKTHROUGH = json.load(f)

SECTIONS = WALKTHROUGH["sections"]
ALL_QUESTION_IDS = []
for section in SECTIONS:
    for card in section["cards"]:
        for q in card["questions"]:
            ALL_QUESTION_IDS.append(q["id"])

TOTAL_QUESTIONS = len(ALL_QUESTION_IDS)


# ═══ PYDANTIC MODELS ═══
class SessionStart(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None


class AnswerSubmit(BaseModel):
    answers: dict  # { "Q1": "Yes", "Q2": "some text" }


class HomeworkToggle(BaseModel):
    question_id: str


class SectionComplete(BaseModel):
    section_id: str


# ═══ HELPERS ═══
def calculate_progress(answers: dict, homework: list) -> int:
    """Calculate progress percentage from answers + homework items."""
    done = 0
    for qid in ALL_QUESTION_IDS:
        if qid in answers and answers[qid] and str(answers[qid]).strip():
            done += 1
        elif qid in homework:
            done += 1
    return min(100, round((done / TOTAL_QUESTIONS) * 100)) if TOTAL_QUESTIONS > 0 else 0


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ═══ APP ═══
app = FastAPI(title="Family Crisis Playbook", version="3.0")

# Serve static files (CSS, JS if needed)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# ═══ ROUTES: FRONTEND ═══

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to walkthrough."""
    return templates.TemplateResponse("walkthrough.html", {
        "request": request,
        "walkthrough": json.dumps(WALKTHROUGH),
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    })


@app.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough(request: Request):
    """Serve the walkthrough frontend."""
    return templates.TemplateResponse("walkthrough.html", {
        "request": request,
        "walkthrough": json.dumps(WALKTHROUGH),
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    })


# ═══ ROUTES: SESSION API ═══

@app.post("/api/session/start")
async def session_start(data: SessionStart):
    """Create a new walkthrough session."""
    try:
        result = supabase.table("sessions").insert({
            "email": data.email,
            "first_name": data.first_name,
            "last_activity_at": now_iso(),
        }).execute()

        session = result.data[0]
        return {
            "session_id": session["session_id"],
            "status": "created",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.get("/api/session/{session_id}")
async def session_get(session_id: str):
    """Get full session state (for resuming)."""
    try:
        result = supabase.table("sessions").select("*").eq(
            "session_id", session_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = result.data[0]
        return {
            "session_id": session["session_id"],
            "email": session["email"],
            "first_name": session["first_name"],
            "progress_percent": session["progress_percent"],
            "last_section_completed": session["last_section_completed"],
            "answers": session["answers_json"],
            "homework": session["homework_items"],
            "homework_count": session["homework_count"],
            "snapshot_results": session["snapshot_results"],
            "walkthrough_completed": session["walkthrough_completed"],
            "purchase_status": session["purchase_status"],
            "pdf_generated": session["pdf_generated"],
            "pdf_url": session["pdf_url"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/answer")
async def session_answer(session_id: str, data: AnswerSubmit):
    """Save answers for one or more questions."""
    try:
        # Get current session
        result = supabase.table("sessions").select(
            "answers_json, homework_items"
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        current = result.data[0]
        answers = current["answers_json"] or {}
        homework = current["homework_items"] or []

        # Merge new answers
        for qid, value in data.answers.items():
            answers[qid] = value
            # If they answered it, remove from homework
            if qid in homework and value and str(value).strip():
                homework.remove(qid)

        # Extract snapshot results (S1-S12)
        snapshot = {}
        for qid, value in answers.items():
            if qid.startswith("S"):
                snapshot[qid] = value

        progress = calculate_progress(answers, homework)

        # Update session
        supabase.table("sessions").update({
            "answers_json": answers,
            "homework_items": homework,
            "homework_count": len(homework),
            "snapshot_results": snapshot,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        return {
            "status": "saved",
            "progress_percent": progress,
            "homework_count": len(homework),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/homework")
async def session_homework(session_id: str, data: HomeworkToggle):
    """Toggle a question as homework (deferred)."""
    try:
        result = supabase.table("sessions").select(
            "answers_json, homework_items"
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        current = result.data[0]
        answers = current["answers_json"] or {}
        homework = current["homework_items"] or []

        qid = data.question_id
        if qid in homework:
            homework.remove(qid)
        else:
            homework.append(qid)
            # Clear the answer if deferring
            answers[qid] = ""

        progress = calculate_progress(answers, homework)

        supabase.table("sessions").update({
            "answers_json": answers,
            "homework_items": homework,
            "homework_count": len(homework),
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        return {
            "status": "toggled",
            "question_id": qid,
            "is_homework": qid in homework,
            "progress_percent": progress,
            "homework_count": len(homework),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/section-complete")
async def section_complete(session_id: str, data: SectionComplete):
    """Mark a section as completed."""
    try:
        result = supabase.table("sessions").select(
            "answers_json, homework_items"
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        current = result.data[0]
        answers = current["answers_json"] or {}
        homework = current["homework_items"] or []
        progress = calculate_progress(answers, homework)

        supabase.table("sessions").update({
            "last_section_completed": data.section_id,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        # Phase 2: Send webhook to GHL here
        # await send_ghl_webhook("section_complete", session_id)

        return {
            "status": "section_completed",
            "section_id": data.section_id,
            "progress_percent": progress,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/complete")
async def walkthrough_complete(session_id: str):
    """Mark the entire walkthrough as completed."""
    try:
        result = supabase.table("sessions").select(
            "answers_json, homework_items"
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        current = result.data[0]
        answers = current["answers_json"] or {}
        homework = current["homework_items"] or []
        progress = calculate_progress(answers, homework)

        supabase.table("sessions").update({
            "walkthrough_completed": True,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        # Phase 2: Send webhook to GHL here
        # await send_ghl_webhook("walkthrough_complete", session_id)

        return {
            "status": "walkthrough_completed",
            "progress_percent": progress,
            "homework_count": len(homework),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/summary")
async def session_summary(session_id: str):
    """Get completion stats for the summary screen."""
    try:
        result = supabase.table("sessions").select("*").eq(
            "session_id", session_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = result.data[0]
        answers = session["answers_json"] or {}
        homework = session["homework_items"] or []

        # Calculate per-section completion
        section_stats = []
        for section in SECTIONS:
            section_qids = []
            for card in section["cards"]:
                for q in card["questions"]:
                    section_qids.append(q["id"])

            done = 0
            for qid in section_qids:
                if (qid in answers and answers[qid] and str(answers[qid]).strip()) or qid in homework:
                    done += 1

            pct = round((done / len(section_qids)) * 100) if section_qids else 0
            section_stats.append({
                "section_id": section["section_id"],
                "title": section["title"],
                "icon": section["icon"],
                "percent": pct,
            })

        # Build homework detail list
        hw_details = []
        for qid in homework:
            for section in SECTIONS:
                for card in section["cards"]:
                    for q in card["questions"]:
                        if q["id"] == qid:
                            hw_details.append({
                                "id": qid,
                                "prompt": q["prompt"],
                                "tip": q.get("follow_up_tip", ""),
                                "section": section["title"],
                            })

        answered_count = sum(
            1 for qid in ALL_QUESTION_IDS
            if qid in answers and answers[qid] and str(answers[qid]).strip() and qid not in homework
        )

        return {
            "answered": answered_count,
            "homework_count": len(homework),
            "total_sections": len(SECTIONS),
            "progress_percent": session["progress_percent"],
            "sections": section_stats,
            "homework_details": hw_details,
            "walkthrough_completed": session["walkthrough_completed"],
            "purchase_status": session["purchase_status"],
            "pdf_generated": session["pdf_generated"],
            "pdf_url": session["pdf_url"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══ HEALTH CHECK ═══

@app.get("/health")
async def health():
    """Health check for Railway."""
    return {"status": "ok", "version": "3.0", "product": "Family Crisis Playbook"}


# ═══ RUN ═══

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
