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
from dotenv import load_dotenv

load_dotenv()

# ═══ SUPABASE REST CLIENT (bypasses library API key format check) ═══
import httpx as _httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

print(f"SUPABASE_URL = {SUPABASE_URL}")
print(f"SUPABASE_KEY length = {len(SUPABASE_KEY)}, starts with = {SUPABASE_KEY[:15]}...")

class SupabaseREST:
    """Direct REST client that works with both old JWT and new sb_secret_ keys."""
    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
    
    def table(self, name):
        return TableRef(self.base, self.headers, name)

class TableRef:
    def __init__(self, base, headers, table):
        self.url = f"{base}/{table}"
        self.headers = headers
        self._filters = []
        self._select_cols = "*"
        self._order_col = None
        self._order_desc = False
        self._limit_n = None
        self._pending_update = None
    
    def select(self, cols="*"):
        self._select_cols = cols
        return self
    
    def eq(self, col, val):
        self._filters.append(f"{col}=eq.{val}")
        return self
    
    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self
    
    def limit(self, n):
        self._limit_n = n
        return self
    
    def insert(self, data):
        r = _httpx.post(self.url, headers=self.headers, json=data, timeout=10)
        r.raise_for_status()
        return type("R", (), {"data": r.json()})()
    
    def update(self, data):
        self._pending_update = data
        return self
    
    def execute(self):
        if self._pending_update is not None:
            params = "&".join(self._filters)
            url = f"{self.url}?{params}" if params else self.url
            h = {**self.headers, "Prefer": "return=representation"}
            r = _httpx.patch(url, headers=h, json=self._pending_update, timeout=10)
            r.raise_for_status()
            self._pending_update = None
            return type("R", (), {"data": r.json()})()
        else:
            params = []
            if self._select_cols != "*":
                params.append(f"select={self._select_cols}")
            else:
                params.append("select=*")
            params.extend(self._filters)
            if self._order_col:
                direction = "desc" if self._order_desc else "asc"
                params.append(f"order={self._order_col}.{direction}")
            if self._limit_n:
                params.append(f"limit={self._limit_n}")
            url = f"{self.url}?{'&'.join(params)}"
            r = _httpx.get(url, headers=self.headers, timeout=10)
            r.raise_for_status()
            return type("R", (), {"data": r.json()})()

# Test connection
try:
    _test = _httpx.get(
        f"{SUPABASE_URL}/rest/v1/sessions?select=session_id&limit=1",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        timeout=5,
    )
    print(f"Supabase connection test: status={_test.status_code}")
    if _test.status_code == 200:
        print("Supabase connected successfully!")
    else:
        print(f"Supabase warning: {_test.text[:200]}")
except Exception as _e:
    print(f"Supabase connection failed: {_e}")

supabase = SupabaseREST(SUPABASE_URL, SUPABASE_KEY)

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
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Find template directory
import glob as _glob
print(f"CWD: {os.getcwd()}")
print(f"__file__: {os.path.abspath(__file__)}")
# List all walkthrough.html files on the system
_found = _glob.glob("/app/**/walkthrough.html", recursive=True)
print(f"All walkthrough.html files found: {_found}")

_template_dirs = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
    "/app/templates",
    "templates",
    os.path.join(os.getcwd(), "templates"),
]
_template_dir = None
for _d in _template_dirs:
    _full = os.path.join(_d, "walkthrough.html")
    exists = os.path.exists(_full)
    print(f"  Checking: {os.path.abspath(_d)} -> {exists}")
    if exists and not _template_dir:
        _template_dir = _d
        print(f"  USING: {os.path.abspath(_d)}")
if not _template_dir:
    # Last resort: use the first found file
    if _found:
        _template_dir = os.path.dirname(_found[0])
        print(f"  FALLBACK to: {_template_dir}")
    else:
        _template_dir = "templates"
        print(f"  NO TEMPLATE FOUND - defaulting to: templates")
templates = Jinja2Templates(directory=_template_dir)


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
        })

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


# ═══════════════════════════════════════════════════
# PHASE 3: SAMCART WEBHOOK + PDF GENERATION + EMAIL
# ═══════════════════════════════════════════════════

import httpx
import tempfile
import base64

# ═══ CLAUDE API — NARRATIVE GENERATION ═══

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

async def generate_ai_narratives(answers: dict, name: str) -> dict:
    """Call Claude API to generate personalized narrative sections."""
    if not ANTHROPIC_API_KEY:
        print("WARNING: No ANTHROPIC_API_KEY set, using fallback narratives")
        return generate_fallback_narratives(answers, name)
    
    first_name = name.split()[0] if name else "your loved one"
        prompt = f"""You are writing personalized section introductions for a family crisis document called "The Resolved Brief" prepared by {name}.

CRITICAL: Write these as if speaking directly to the FAMILY MEMBER who is reading this document during a crisis. Use "you" to address the reader (the family) and refer to {name} by first name ({first_name}).

The tone should be warm, calm, and reassuring — like a trusted guide helping someone through a difficult moment. Start each section with a brief human moment before getting into the practical details. Highlight what's in good shape and gently flag what's missing.

Example tone: "If you're reading this section, {first_name} wanted you to know exactly where the money is. Here's what they set up..."

{first_name}'s answers:
{json.dumps(answers, indent=2)}

Return ONLY a JSON object with these keys, each containing a 3-5 sentence narrative string:
- financial (address the family, explain where the money is)
- income (address the family, explain what comes in and goes out)
- insurance (address the family, explain what's covered)
- digital (address the family, explain how to access accounts)
- medical (address the family, explain who makes decisions and what doctors need to know)
- wishes (address the family gently, explain what {first_name} wanted)

No markdown, no backticks, just the JSON object."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            
            if response.status_code != 200:
                print(f"Claude API error: {response.status_code} {response.text}")
                return generate_fallback_narratives(answers, name)
            
            data = response.json()
            text = data["content"][0]["text"]
            
            # Parse JSON from response (strip any accidental markdown)
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            
            narratives = json.loads(text)
            print(f"AI narratives generated for {name}")
            return narratives
            
    except Exception as e:
        print(f"Claude API failed: {e}, using fallback")
        return generate_fallback_narratives(answers, name)


def generate_fallback_narratives(answers: dict, name: str) -> dict:
    """Generate basic narratives without AI if API is unavailable."""
    first = name.split()[0] if name else "your loved one"
    return {
        "financial": f"If you are reading this, {first} wanted you to know exactly where the money is. Everything below documents the banks, accounts, and financial relationships that matter. Take your time with this section.",
        "income": f"{first} mapped out where money comes in and where it goes each month so you would not have to figure it out on your own. The details below will help you keep things running smoothly.",
        "insurance": f"{first} made sure you would know what insurance coverage is in place and how to access it. The policy details, coverage amounts, and agent contacts are all documented below.",
        "digital": f"This section covers how to access {first}'s accounts, devices, and digital life. Password management and device access information is here so you are not locked out when you need it most.",
        "medical": f"If you are working with doctors or a hospital, this section has everything they will need. {first} documented their medical information, decision makers, and preferences so the people who matter can speak on their behalf.",
        "wishes": f"This is the most personal section. {first} took the time to write down what they wanted, because they did not want you to have to guess. Read this when you are ready.",
    }


# ═══ EMAIL DELIVERY ═══

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "brief@resolvedfamily.com")

async def send_brief_email(to_email: str, name: str, pdf_bytes: bytes) -> bool:
    """Send the Resolved Brief PDF via email using Resend."""
    if not RESEND_API_KEY:
        print(f"WARNING: No RESEND_API_KEY set, cannot send email to {to_email}")
        return False
    
    first = name.split()[0] if name else "there"
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": FROM_EMAIL,
                    "to": [to_email],
                    "subject": f"{first}, your Resolved Brief is ready",
                    "html": f"""
                    <div style="font-family: Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1B2A3D;">
                        <div style="background: #1B2A3D; padding: 32px; text-align: center;">
                            <h1 style="color: #C9A84C; font-family: Georgia, serif; margin: 0;">THE RESOLVED BRIEF</h1>
                            <p style="color: rgba(255,255,255,0.6); margin-top: 8px;">Everything your family needs to know.</p>
                        </div>
                        <div style="padding: 32px; background: #F5F0E8;">
                            <p>Hi {first},</p>
                            <p>Your Resolved Brief is attached. This document contains everything your family needs — organized, personalized, and ready to use.</p>
                            <p><strong>What to do next:</strong></p>
                            <ol>
                                <li>Print your Resolved Brief and your Family Emergency Card</li>
                                <li>Fill in the sensitive details — passwords, PINs, account numbers — by hand on the Emergency Card</li>
                                <li>Seal it in an envelope, put it somewhere safe, and label it</li>
                                <li>Tell one person where it is</li>
                            </ol>
                            <p>That\'s it. You just did what most families never do.</p>
                            <p style="color: #C9A84C; font-style: italic; font-family: Georgia, serif; font-size: 18px; margin-top: 24px;">"There's an envelope in my desk."</p>
                            <p style="color: #8A8578; font-size: 14px;">You earned that.</p>
                        </div>
                        <div style="padding: 16px; text-align: center; color: #8A8578; font-size: 12px;">
                            <p>&copy; 2026 Resolved &middot; ResolvedFamily.com</p>
                        </div>
                    </div>
                    """,
                    "attachments": [{
                        "filename": f"The-Resolved-Brief-{first}.pdf",
                        "content": pdf_b64,
                    }],
                },
            )
            
            if response.status_code in (200, 201):
                print(f"Email sent to {to_email}")
                return True
            else:
                print(f"Email failed: {response.status_code} {response.text}")
                return False
                
    except Exception as e:
        print(f"Email send error: {e}")
        return False


# ═══ PDF GENERATION ═══

from app.pdf_generator import ResolvedBriefBuilder

async def generate_resolved_brief(session_id: str, email: str, name: str) -> Optional[str]:
    """Generate the Resolved Brief PDF for a paid customer."""
    try:
        # Get session data
        result = supabase.table("sessions").select("*").eq(
            "session_id", session_id
        ).execute()
        
        if not result.data:
            print(f"Session not found: {session_id}")
            return None
        
        session = result.data[0]
        answers = session["answers_json"] or {}
        homework = session["homework_items"] or []
        
        # Generate AI narratives
        narratives = await generate_ai_narratives(answers, name)
        
        # Build PDF data
        pdf_data = {
            "name": name,
            "date": datetime.now().strftime("%B %d, %Y"),
            "answers": answers,
            "homework": homework,
            "ai_narratives": narratives,
        }
        
        # Generate PDF to temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        builder = ResolvedBriefBuilder(pdf_data)
        builder.build(tmp_path)
        
        # Read the PDF bytes
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Send email
        email_sent = await send_brief_email(email, name, pdf_bytes)
        
        # Update session
        try:
            supabase.table("sessions").update({
                "purchase_status": "paid",
                "pdf_generated": True,
                "email": email,
                "last_activity_at": now_iso(),
            }).eq("session_id", session_id).execute()
        except Exception as _ue:
            print(f"Session update note (non-critical): {_ue}")
        
        # Cleanup temp file
        os.unlink(tmp_path)
        
        print(f"Resolved Brief generated and sent for session {session_id}")
        return "sent" if email_sent else "generated_not_sent"
        
    except Exception as e:
        print(f"Brief generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══ SAMCART WEBHOOK ENDPOINT ═══

class SamCartWebhook(BaseModel):
    """Flexible model — SamCart sends various fields."""
    class Config:
        extra = "allow"

@app.post("/api/webhook/samcart")
async def samcart_webhook(request: Request):
    """
    Receives SamCart webhook after purchase.
    Generates the Resolved Brief and emails it to the customer.
    """
    try:
        body = await request.json()
        print(f"SamCart webhook received: {json.dumps(body, indent=2)[:500]}")
        
        # Extract customer info from SamCart payload
        # SamCart sends different fields depending on configuration
        email = (
            body.get("customer", {}).get("email") or
            body.get("buyer_email") or
            body.get("email") or
            ""
        )
        
        name = (
            body.get("customer", {}).get("first_name", "") + " " +
            body.get("customer", {}).get("last_name", "") or
            body.get("buyer_name") or
            body.get("name") or
            "Valued Customer"
        ).strip()
        
        # Get session_id from custom field or URL parameter
        session_id = (
            body.get("custom_fields", {}).get("session_id") or
            body.get("session_id") or
            body.get("custom", {}).get("session_id") or
            ""
        )
        
        if not email:
            print("WARNING: No email in webhook payload")
            return JSONResponse(
                status_code=200,
                content={"status": "error", "message": "No email found in payload"}
            )
        
        if not session_id:
            # Try to find session by email
            print(f"No session_id in webhook, searching by email: {email}")
            result = supabase.table("sessions").select("session_id").eq(
                "email", email
            ).order("created_at", desc=True).limit(1).execute()
            
            if result.data:
                session_id = result.data[0]["session_id"]
                print(f"Found session by email: {session_id}")
            else:
                # Try most recent completed session without email
                result = supabase.table("sessions").select("session_id").eq(
                    "walkthrough_completed", True
                ).eq("purchase_status", "unpaid").order(
                    "last_activity_at", desc=True
                ).limit(1).execute()
                
                if result.data:
                    session_id = result.data[0]["session_id"]
                    print(f"Found most recent unpaid session: {session_id}")
                else:
                    print("ERROR: No matching session found")
                    return JSONResponse(
                        status_code=200,
                        content={"status": "error", "message": "No matching session"}
                    )
        
        # Generate and send the Resolved Brief
        result = await generate_resolved_brief(session_id, email, name)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success" if result else "error",
                "session_id": session_id,
                "email": email,
                "pdf_status": result or "failed",
            }
        )
        
    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        # Always return 200 to SamCart so it doesn't retry forever
        return JSONResponse(
            status_code=200,
            content={"status": "error", "message": str(e)}
        )


# ═══ MANUAL PDF GENERATION (for testing) ═══

class ManualBriefRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

@app.post("/api/session/{session_id}/generate-brief")
async def manual_generate_brief(session_id: str, data: ManualBriefRequest = ManualBriefRequest()):
    """Manually trigger PDF generation for testing."""
    try:
        result = supabase.table("sessions").select("email, first_name").eq(
            "session_id", session_id
        ).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = result.data[0]
        email = data.email or session.get("email") or "test@example.com"
        name = data.name or session.get("first_name") or "Test User"
        
        status = await generate_resolved_brief(session_id, email, name)
        
        return {
            "status": "success" if status else "error",
            "pdf_status": status or "failed",
            "session_id": session_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
