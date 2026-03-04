"""
The Resolved Brief — FastAPI Backend
=========================================
Phase 1: Walkthrough + Supabase session persistence
Uses httpx for direct Supabase REST API calls (compatible with sb_secret_ keys)
"""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ═══ CONFIG ═══
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

print(f"SUPABASE_URL = {SUPABASE_URL}")
print(f"SUPABASE_KEY length = {len(SUPABASE_KEY)}, starts with = {SUPABASE_KEY[:15]}...")

# ═══ SUPABASE REST CLIENT (direct HTTP) ═══
class SupabaseREST:
    """Simple REST client for Supabase using httpx. Works with sb_secret_ keys."""
    
    def __init__(self, url: str, key: str):
        self.base_url = f"{url}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def select(self, table: str, columns: str = "*", filters: dict = None) -> list:
        url = f"{self.base_url}/{table}?select={columns}"
        if filters:
            for k, v in filters.items():
                url += f"&{k}=eq.{v}"
        r = httpx.get(url, headers=self.headers, timeout=10)
        if r.status_code >= 400:
            raise Exception(f"Supabase select error {r.status_code}: {r.text}")
        return r.json()
    
    def insert(self, table: str, data: dict) -> list:
        url = f"{self.base_url}/{table}"
        r = httpx.post(url, headers=self.headers, json=data, timeout=10)
        if r.status_code >= 400:
            raise Exception(f"Supabase insert error {r.status_code}: {r.text}")
        return r.json()
    
    def update(self, table: str, data: dict, filters: dict = None) -> list:
        url = f"{self.base_url}/{table}"
        if filters:
            for k, v in filters.items():
                url += f"?{k}=eq.{v}"
        r = httpx.patch(url, headers=self.headers, json=data, timeout=10)
        if r.status_code >= 400:
            raise Exception(f"Supabase update error {r.status_code}: {r.text}")
        return r.json()


# ═══ INIT SUPABASE ═══
db = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        db = SupabaseREST(SUPABASE_URL, SUPABASE_KEY)
        # Test connection
        test = httpx.get(
            f"{SUPABASE_URL}/rest/v1/sessions?limit=1",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        print(f"Supabase connection test: status={test.status_code}")
        if test.status_code < 400:
            print("Supabase connected successfully!")
        else:
            print(f"Supabase connection issue: {test.text}")
    except Exception as e:
        print(f"Supabase connection failed: {e}")
else:
    print("WARNING: Missing SUPABASE_URL or SUPABASE_KEY")


# ═══ WALKTHROUGH DEFINITION ═══
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
    answers: dict

class HomeworkToggle(BaseModel):
    question_id: str

class SectionComplete(BaseModel):
    section_id: str


# ═══ HELPERS ═══
def calculate_progress(answers: dict, homework: list) -> int:
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
app = FastAPI(title="The Resolved Brief", version="3.0")

templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=templates_dir)


# ═══ ROUTES: FRONTEND ═══

@app.get("/", response_class=HTMLResponse)
@app.get("/walkthrough", response_class=HTMLResponse)
async def walkthrough(request: Request):
    return templates.TemplateResponse("walkthrough.html", {
        "request": request,
        "walkthrough": json.dumps(WALKTHROUGH),
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    })


# ═══ ROUTES: SESSION API ═══

@app.post("/api/session/start")
async def session_start(data: SessionStart):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        session_id = str(uuid.uuid4())
        result = db.insert("sessions", {
            "session_id": session_id,
            "email": data.email,
            "first_name": data.first_name,
            "last_activity_at": now_iso(),
        })
        return {"session_id": session_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.get("/api/session/{session_id}")
async def session_get(session_id: str):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "*", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")
        session = rows[0]
        return {
            "session_id": session["session_id"],
            "email": session.get("email"),
            "first_name": session.get("first_name"),
            "progress_percent": session.get("progress_percent", 0),
            "last_section_completed": session.get("last_section_completed"),
            "answers": session.get("answers_json", {}),
            "homework": session.get("homework_items", []),
            "homework_count": session.get("homework_count", 0),
            "snapshot_results": session.get("snapshot_results", {}),
            "walkthrough_completed": session.get("walkthrough_completed", False),
            "purchase_status": session.get("purchase_status", "not_purchased"),
            "pdf_generated": session.get("pdf_generated", False),
            "pdf_url": session.get("pdf_url"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/answer")
async def session_answer(session_id: str, data: AnswerSubmit):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "answers_json,homework_items", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")

        current = rows[0]
        answers = current.get("answers_json") or {}
        homework = current.get("homework_items") or []

        for qid, value in data.answers.items():
            answers[qid] = value
            if qid in homework and value and str(value).strip():
                homework.remove(qid)

        snapshot = {qid: v for qid, v in answers.items() if qid.startswith("S")}
        progress = calculate_progress(answers, homework)

        db.update("sessions", {
            "answers_json": answers,
            "homework_items": homework,
            "homework_count": len(homework),
            "snapshot_results": snapshot,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }, {"session_id": session_id})

        return {"status": "saved", "progress_percent": progress, "homework_count": len(homework)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/homework")
async def session_homework(session_id: str, data: HomeworkToggle):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "answers_json,homework_items", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")

        current = rows[0]
        answers = current.get("answers_json") or {}
        homework = current.get("homework_items") or []

        qid = data.question_id
        if qid in homework:
            homework.remove(qid)
        else:
            homework.append(qid)
            answers[qid] = ""

        progress = calculate_progress(answers, homework)

        db.update("sessions", {
            "answers_json": answers,
            "homework_items": homework,
            "homework_count": len(homework),
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }, {"session_id": session_id})

        return {"status": "toggled", "question_id": qid, "is_homework": qid in homework,
                "progress_percent": progress, "homework_count": len(homework)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/section-complete")
async def section_complete(session_id: str, data: SectionComplete):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "answers_json,homework_items", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")

        current = rows[0]
        answers = current.get("answers_json") or {}
        homework = current.get("homework_items") or []
        progress = calculate_progress(answers, homework)

        db.update("sessions", {
            "last_section_completed": data.section_id,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }, {"session_id": session_id})

        return {"status": "section_completed", "section_id": data.section_id, "progress_percent": progress}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/{session_id}/complete")
async def walkthrough_complete(session_id: str):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "answers_json,homework_items", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")

        current = rows[0]
        answers = current.get("answers_json") or {}
        homework = current.get("homework_items") or []
        progress = calculate_progress(answers, homework)

        db.update("sessions", {
            "walkthrough_completed": True,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }, {"session_id": session_id})

        return {"status": "walkthrough_completed", "progress_percent": progress, "homework_count": len(homework)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/summary")
async def session_summary(session_id: str):
    if not db:
        raise HTTPException(status_code=503, detail="Database not connected")
    try:
        rows = db.select("sessions", "*", {"session_id": session_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Session not found")

        session = rows[0]
        answers = session.get("answers_json") or {}
        homework = session.get("homework_items") or []

        section_stats = []
        for section in SECTIONS:
            section_qids = [q["id"] for card in section["cards"] for q in card["questions"]]
            done = sum(1 for qid in section_qids
                      if (qid in answers and answers[qid] and str(answers[qid]).strip()) or qid in homework)
            pct = round((done / len(section_qids)) * 100) if section_qids else 0
            section_stats.append({
                "section_id": section["section_id"],
                "title": section["title"],
                "icon": section["icon"],
                "percent": pct,
            })

        hw_details = []
        for qid in homework:
            for section in SECTIONS:
                for card in section["cards"]:
                    for q in card["questions"]:
                        if q["id"] == qid:
                            hw_details.append({
                                "id": qid, "prompt": q["prompt"],
                                "tip": q.get("follow_up_tip", ""), "section": section["title"],
                            })

        answered_count = sum(1 for qid in ALL_QUESTION_IDS
                           if qid in answers and answers[qid] and str(answers[qid]).strip() and qid not in homework)

        return {
            "answered": answered_count, "homework_count": len(homework),
            "total_sections": len(SECTIONS), "progress_percent": session.get("progress_percent", 0),
            "sections": section_stats, "homework_details": hw_details,
            "walkthrough_completed": session.get("walkthrough_completed", False),
            "purchase_status": session.get("purchase_status", "not_purchased"),
            "pdf_generated": session.get("pdf_generated", False),
            "pdf_url": session.get("pdf_url"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══ HEALTH CHECK ═══
@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0", "db_connected": db is not None}


# ═══ RUN ═══
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
