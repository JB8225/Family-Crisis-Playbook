"""
Resolved Family — FastAPI Backend
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

# ═══ SUPABASE REST CLIENT ═══
import httpx as _httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

print(f"SUPABASE_URL = {SUPABASE_URL}")
print(f"SUPABASE_KEY length = {len(SUPABASE_KEY)}, starts with = {SUPABASE_KEY[:15]}...")

class SupabaseREST:
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
app = FastAPI(title="Resolved Family", version="3.0")

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

import glob as _glob
print(f"CWD: {os.getcwd()}")
print(f"__file__: {os.path.abspath(__file__)}")
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
    return templates.TemplateResponse("walkthrough.html", {
        "request": request,
        "walkthrough": json.dumps(WALKTHROUGH),
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    })

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
    try:
        result = supabase.table("sessions").insert({
            "email": data.email,
            "first_name": data.first_name,
            "last_activity_at": now_iso(),
        })
        session = result.data[0]
        return {"session_id": session["session_id"], "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.get("/api/session/{session_id}")
async def session_get(session_id: str):
    try:
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
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
    try:
        result = supabase.table("sessions").select(
            "answers_json, homework_items"
        ).eq("session_id", session_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        current = result.data[0]
        answers = current["answers_json"] or {}
        homework = current["homework_items"] or []

        for qid, value in data.answers.items():
            answers[qid] = value
            if qid in homework and value and str(value).strip():
                homework.remove(qid)

        snapshot = {qid: value for qid, value in answers.items() if qid.startswith("S")}
        progress = calculate_progress(answers, homework)

        # ─── FIX 1: Sync Q46 (primary email) to the email column ───
        update_payload = {
            "answers_json": answers,
            "homework_items": homework,
            "homework_count": len(homework),
            "snapshot_results": snapshot,
            "progress_percent": progress,
            "last_activity_at": now_iso(),
        }
        if "Q46" in data.answers and data.answers["Q46"] and str(data.answers["Q46"]).strip():
            update_payload["email"] = data.answers["Q46"].strip()
            print(f"Synced Q46 email to session column: {data.answers['Q46'].strip()}")

        supabase.table("sessions").update(update_payload).eq("session_id", session_id).execute()

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
    try:
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = result.data[0]
        answers = session["answers_json"] or {}
        homework = session["homework_items"] or []

        section_stats = []
        for section in SECTIONS:
            section_qids = [q["id"] for card in section["cards"] for q in card["questions"]]
            done = sum(
                1 for qid in section_qids
                if (qid in answers and answers[qid] and str(answers[qid]).strip()) or qid in homework
            )
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
    return {"status": "ok", "version": "3.0", "product": "Resolved Family"}


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

# ═══ CLAUDE API — ENHANCED NARRATIVE + ACTION GUIDE GENERATION ═══

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Known bereavement/estate department numbers (verified)
KNOWN_BEREAVEMENT_NUMBERS = {
    "chase": "1-888-356-0023",
    "bank of america": "1-800-432-1000 (ask for Estate Services)",
    "wells fargo": "1-800-869-3557 (ask for Estate Services)",
    "fidelity": "1-800-343-3548",
    "vanguard": "1-800-662-7447",
    "charles schwab": "1-800-435-4000 (ask for Estate Services)",
    "schwab": "1-800-435-4000 (ask for Estate Services)",
    "social security": "1-800-772-1213",
    "ssa": "1-800-772-1213",
    "medicare": "1-800-633-4227",
    "metlife": "1-800-638-5433",
    "northwestern mutual": "1-800-388-8123",
    "state farm": "1-800-732-5246",
    "allstate": "1-800-255-7828",
    "tiaa": "1-800-842-2252",
    "nationwide": "1-877-669-6877",
    "prudential": "1-800-778-2255",
    "irs": "1-800-829-1040",
}

ENHANCED_AI_PROMPT = """You are writing the personalized content for "The Resolved Brief" — a printed family crisis document prepared by {name}.

A grieving family member will open this document, possibly at a hospital, possibly overwhelmed, possibly with a lawyer on the phone. Every section must be immediately actionable — not just informative. Warm tone, plain English, zero jargon.

CRITICAL RULES:
1. Address the FAMILY MEMBER reading this. Refer to {first_name} by first name.
2. ONLY reference institutions and details that appear in {first_name}'s answers below. Never invent.
3. If an answer is empty, say "this was not documented."
4. For phone numbers: use ONLY the verified numbers listed below for institutions {first_name} actually named. For any institution NOT on this list, write: "Call their main customer service line and ask for the Estate Services or Bereavement department."
5. This is a legal document. Accuracy matters more than completeness.

VERIFIED BEREAVEMENT NUMBERS (only use for institutions {first_name} actually named):
- Chase Bank: 1-888-356-0023
- Bank of America: 1-800-432-1000 (ask for Estate Services)
- Wells Fargo: 1-800-869-3557 (ask for Estate Services)
- Fidelity: 1-800-343-3548
- Vanguard: 1-800-662-7447
- Charles Schwab: 1-800-435-4000 (ask for Estate Services)
- Social Security Administration: 1-800-772-1213
- Medicare: 1-800-633-4227
- MetLife (life insurance): 1-800-638-5433
- Northwestern Mutual: 1-800-388-8123
- State Farm: 1-800-732-5246
- Allstate: 1-800-255-7828
- TIAA: 1-800-842-2252
- Nationwide: 1-877-669-6877
- Prudential: 1-800-778-2255
- IRS (deceased taxpayer line): 1-800-829-1040

{first_name}'s answers:
{answers_json}

For each section, produce TWO parts:

PART A — NARRATIVE (3-4 sentences):
Warm, calm. Summarize what {first_name} set up. Gently flag anything missing.

PART B — ACTION GUIDE:
For each institution or account {first_name} named, produce one action block formatted EXACTLY like this — use the pipe character | as a field separator:

INSTITUTION: [name] | PHONE: [number or "Call main line, ask for Estate Services"] | STEP 1: [first action] | STEP 2: [second action] | STEP 3: [third action] | HAVE READY: [documents/info needed] | TIMELINE: [realistic timeframe] | WATCH OUT: [one common pitfall]

Separate multiple institution blocks with a blank line.

Return ONLY a JSON object with these exact keys:
{{
  "financial": {{"narrative": "...", "action_guide": "..."}},
  "income": {{"narrative": "...", "action_guide": "..."}},
  "insurance": {{"narrative": "...", "action_guide": "..."}},
  "digital": {{"narrative": "...", "action_guide": "..."}},
  "medical": {{"narrative": "...", "action_guide": "..."}}
}}

DO NOT generate a "wishes" key. Wishes are presented verbatim.
No markdown, no backticks, just the JSON object."""


async def generate_ai_narratives(answers: dict, name: str) -> dict:
    """Call Claude API to generate personalized narratives + action guides."""
    if not ANTHROPIC_API_KEY:
        print("WARNING: No ANTHROPIC_API_KEY set, using fallback narratives")
        return generate_fallback_narratives(answers, name)

    first_name = name.split()[0] if name else "your loved one"
    prompt = ENHANCED_AI_PROMPT.format(
        name=name,
        first_name=first_name,
        answers_json=json.dumps(answers, indent=2),
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code != 200:
                print(f"Claude API error: {response.status_code} {response.text}")
                return generate_fallback_narratives(answers, name)

            data = response.json()
            text = data["content"][0]["text"].strip()

            # Strip any accidental markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]

            narratives = json.loads(text)
            print(f"Enhanced AI narratives generated for {name}")
            return narratives

    except Exception as e:
        print(f"Claude API failed: {e}, using fallback")
        return generate_fallback_narratives(answers, name)


def generate_fallback_narratives(answers: dict, name: str) -> dict:
    """Basic narratives when AI is unavailable."""
    first = name.split()[0] if name else "your loved one"
    guide = "INSTITUTION: See documented accounts above | PHONE: Call main line, ask for Estate Services | STEP 1: Gather certified copies of the death certificate (order at least 10) | STEP 2: Call the institution and identify yourself as the next of kin or executor | STEP 3: Ask what their estate/bereavement process requires and follow up in writing | HAVE READY: Death certificate, your photo ID, account info if available | TIMELINE: Varies by institution — bank accounts 1-4 weeks, retirement accounts 30-90 days | WATCH OUT: Do not close joint accounts until you understand the tax and legal implications"
    return {
        "financial": {
            "narrative": f"If you are reading this, {first} wanted you to know exactly where the money is. Everything below documents the banks, accounts, and financial relationships that matter. Take your time with this section.",
            "action_guide": guide,
        },
        "income": {
            "narrative": f"{first} mapped out where money comes in and where it goes each month so you would not have to figure it out alone. Review the details below to keep things running and cancel what's no longer needed.",
            "action_guide": "INSTITUTION: Employer/Payroll | PHONE: Call HR department directly | STEP 1: Notify HR of the death and ask about final paycheck and any accrued benefits | STEP 2: Ask about life insurance through the employer | STEP 3: Request information about pension or 401k if applicable | HAVE READY: Death certificate, employee ID if known | TIMELINE: Final paycheck typically issued within 1-2 pay cycles | WATCH OUT: Autopay bills will keep charging — freeze or cancel each one individually",
        },
        "insurance": {
            "narrative": f"{first} made sure you would know what coverage is in place and how to access it. The policy details and contact information are documented below so you can file claims without searching.",
            "action_guide": guide,
        },
        "digital": {
            "narrative": f"This section covers how to access {first}'s accounts, devices, and digital life. Start with the primary email — it is the key to resetting everything else.",
            "action_guide": "INSTITUTION: Primary Email Provider | PHONE: Use online support — Google: support.google.com/accounts, Apple: 1-800-275-2273 | STEP 1: Gain access to the primary email account first — all other resets flow through it | STEP 2: Use the email to reset passwords for financial accounts one at a time | STEP 3: Document each account as you go | HAVE READY: Death certificate for accounts that require it, your own ID | TIMELINE: Email access: immediate if you have password. Account-by-account resets: 1-2 weeks | WATCH OUT: Do not delete the email account — it may be needed to verify identity for other services",
        },
        "medical": {
            "narrative": f"If you are working with doctors or a hospital, this section has what they need. {first} documented their medical information and preferences so the right people can speak on their behalf.",
            "action_guide": "INSTITUTION: Primary Care Physician | PHONE: Call the office directly | STEP 1: Notify the practice of the death and request any outstanding referrals or prescriptions be closed | STEP 2: Request medical records if needed for insurance claims or legal purposes | STEP 3: Cancel any upcoming appointments | HAVE READY: Death certificate, patient ID or insurance card | TIMELINE: Medical records requests: 30 days under HIPAA | WATCH OUT: Medicare and insurance may need separate notification — do not assume the doctor's office handles this",
        },
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
                                <li>Fill in sensitive details — passwords, PINs, account numbers — by hand on the Emergency Card</li>
                                <li>Seal it in an envelope, put it somewhere safe, and label it</li>
                                <li>Tell one person where it is</li>
                            </ol>
                            <p>That's it. You just did what most families never do.</p>
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
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()

        if not result.data:
            print(f"Session not found: {session_id}")
            return None

        session = result.data[0]
        answers = session["answers_json"] or {}
        homework = session["homework_items"] or []

        # Generate enhanced AI narratives + action guides
        narratives = await generate_ai_narratives(answers, name)

        pdf_data = {
            "name": name,
            "date": datetime.now().strftime("%B %d, %Y"),
            "answers": answers,
            "homework": homework,
            "ai_narratives": narratives,
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        builder = ResolvedBriefBuilder(pdf_data)
        builder.build(tmp_path)

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        email_sent = await send_brief_email(email, name, pdf_bytes)

        try:
            supabase.table("sessions").update({
                "purchase_status": "paid",
                "pdf_generated": True,
                "email": email,
                "last_activity_at": now_iso(),
            }).eq("session_id", session_id).execute()
        except Exception as _ue:
            print(f"Session update note (non-critical): {_ue}")

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

        email = (
            body.get("customer", {}).get("email") or
            body.get("buyer_email") or
            body.get("email") or
            ""
        )

        name = (
            (
                body.get("customer", {}).get("first_name", "") + " " +
                body.get("customer", {}).get("last_name", "")
            ).strip() or
            body.get("buyer_name") or
            body.get("name") or
            "Valued Customer"
        )

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
            print(f"No session_id in webhook, searching by email: {email}")
            # ─── FIX 1 BENEFIT: Q46 now synced to email column, so this works ───
            result = supabase.table("sessions").select("session_id").eq(
                "email", email
            ).order("created_at", desc=True).limit(1).execute()

            if result.data:
                session_id = result.data[0]["session_id"]
                print(f"Found session by email: {session_id}")
            else:
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
# ═══════════════════════════════════════════════════
# SCORECARD REPORT EMAIL — Add to bottom of main.py
# ═══════════════════════════════════════════════════

# ═══ PYDANTIC MODEL ═══

class ScorecardReportRequest(BaseModel):
    first_name: str
    email: str
    score: int
    max_score: int
    grade_letter: str
    grade_label: str
    gaps: list  # List of {id, text, gapTip, sectionTitle, sectionIcon}
    section_scores: list  # List of {id, title, icon, pct, documented, partials, gaps}


# ═══ EMAIL BUILDER ═══

def build_scorecard_report_email(data: ScorecardReportRequest) -> str:
    """Build the personalized scorecard report HTML email."""
    first = data.first_name
    score = data.score
    max_score = data.max_score
    grade = data.grade_letter
    label = data.grade_label
    gaps = data.gaps
    sections = data.section_scores

    # Grade color
    if label in ("Excellent", "Strong"):
        grade_color = "#10B981"
    elif label in ("Fair", "Good"):
        grade_color = "#F59E0B"
    else:
        grade_color = "#EF4444"

    # Build gap items HTML
    gap_items_html = ""
    for i, gap in enumerate(gaps):
        gap_items_html += f"""
        <div style="margin-bottom: 24px; padding: 20px 24px; background: #fff; border: 1.5px solid #E8E5DE; border-left: 4px solid #EF4444; border-radius: 8px;">
            <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px;">
                <span style="font-family: Georgia, serif; font-size: 18px; font-weight: 700; color: #D4913B; min-width: 24px;">{i+1}.</span>
                <p style="font-size: 16px; font-weight: 700; color: #1B3A5C; margin: 0; line-height: 1.4;">{gap.get('text', '')}</p>
            </div>
            <div style="margin-left: 36px; padding: 12px 16px; background: #FEF9F0; border-radius: 6px; border: 1px solid rgba(212,145,59,0.2);">
                <p style="font-size: 13px; font-weight: 700; color: #D4913B; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 6px;">⚠ Why This Matters</p>
                <p style="font-size: 15px; color: #4B5563; line-height: 1.6; margin: 0;">{gap.get('gapTip', '')}</p>
            </div>
            <p style="font-size: 13px; color: #9CA3AF; margin: 8px 0 0 36px;">{gap.get('sectionIcon', '')} {gap.get('sectionTitle', '')}</p>
        </div>
        """

    # Build section scores HTML
    section_html = ""
    for sec in sections:
        pct = round(sec.get('pct', 0))
        bar_color = "#10B981" if pct >= 75 else "#F59E0B" if pct >= 45 else "#EF4444"
        section_html += f"""
        <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 15px; font-weight: 600; color: #1B3A5C;">{sec.get('icon', '')} {sec.get('title', '')}</span>
                <span style="font-size: 15px; font-weight: 700; color: {bar_color};">{pct}%</span>
            </div>
            <div style="height: 6px; background: #E8E5DE; border-radius: 6px; overflow: hidden;">
                <div style="height: 100%; width: {pct}%; background: {bar_color}; border-radius: 6px;"></div>
            </div>
            <div style="display: flex; gap: 12px; margin-top: 4px;">
                <span style="font-size: 13px; color: #10B981;">✅ {sec.get('documented', 0)}</span>
                <span style="font-size: 13px; color: #F59E0B;">⚠️ {sec.get('partials', 0)}</span>
                <span style="font-size: 13px; color: #EF4444;">🔴 {sec.get('gaps', 0)}</span>
            </div>
        </div>
        """

    # Bridge copy — dynamic based on gap count
    gap_count = len(gaps)
    if gap_count == 0:
        bridge_headline = "Your family is well covered — but can anyone else find it?"
        bridge_body = f"You scored well, {first}. But here's the question most high scorers miss: if something happened to both you and your spouse, could your kids, your parents, or your sister find everything within an hour? The Resolved Brief puts it all in one document anyone can follow."
    elif gap_count <= 3:
        bridge_headline = "A few gaps — but they're the ones that matter most."
        bridge_body = f"You've got a solid foundation, {first}. But those {gap_count} gap{'s' if gap_count > 1 else ''} above? Each one is a specific moment where your family would be stuck, guessing, or fighting. The Resolved Brief closes all of them in one sitting."
    else:
        bridge_headline = f"That's {gap_count} moments where your family would be lost."
        bridge_body = f"Each gap above isn't just a checkbox, {first} — it's a real scenario. Your family on the phone with a bank that won't talk to them. Standing in a funeral home making permanent decisions nobody agreed on. Searching for a life insurance policy nobody knew existed. The Resolved Brief closes every single one of these in about 20 minutes."

    return f"""
    <div style="font-family: Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a; background: #FAFAF7;">

        <!-- HEADER -->
        <div style="background: #1B3A5C; padding: 32px; text-align: center;">
            <p style="font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: rgba(255,255,255,0.5); margin: 0 0 8px;">RESOLVED FAMILY</p>
            <h1 style="font-family: Georgia, serif; font-size: 24px; font-weight: 700; color: #D4913B; margin: 0;">Your Family Readiness Report</h1>
        </div>

        <!-- SCORE BLOCK -->
        <div style="background: #F0EDE5; padding: 32px; text-align: center; border-bottom: 2px solid #E8E5DE;">
            <p style="font-size: 15px; color: #6B7280; margin: 0 0 8px;">Hi {first} — here's your full breakdown.</p>
            <div style="display: inline-block; width: 80px; height: 80px; border-radius: 50%; border: 3px solid {grade_color}; line-height: 80px; text-align: center; margin: 0 auto 12px;">
                <span style="font-family: Georgia, serif; font-size: 36px; font-weight: 700; color: {grade_color};">{grade}</span>
            </div>
            <p style="font-family: Georgia, serif; font-size: 32px; font-weight: 700; color: #1B3A5C; margin: 0 0 4px;">{score} / {max_score}</p>
            <p style="font-size: 14px; font-weight: 700; color: {grade_color}; text-transform: uppercase; letter-spacing: 2px; margin: 0;">{label}</p>
        </div>

        <div style="padding: 32px;">

            <!-- SECTION BREAKDOWN -->
            <h2 style="font-family: Georgia, serif; font-size: 20px; font-weight: 700; color: #1B3A5C; margin: 0 0 20px;">Section Breakdown</h2>
            {section_html}

            <!-- GAP LIST -->
            {'<h2 style="font-family: Georgia, serif; font-size: 20px; font-weight: 700; color: #1B3A5C; margin: 32px 0 8px;">🎯 What Your Family Would Face</h2><p style="font-size: 15px; color: #6B7280; margin: 0 0 20px; line-height: 1.6;">These are the specific moments where your family would be stuck, guessing, or fighting. Each one is real.</p>' + gap_items_html if gap_count > 0 else '<div style="padding: 24px; background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.2); border-radius: 8px; text-align: center; margin: 24px 0;"><p style="font-size: 16px; color: #10B981; font-weight: 600; margin: 0;">🎉 No critical gaps detected — your family has the essentials covered.</p></div>'}

            <!-- BRIDGE -->
            <div style="margin: 32px 0; padding: 28px 24px; background: #1B3A5C; border-radius: 12px; text-align: center;">
                <h2 style="font-family: Georgia, serif; font-size: 22px; font-weight: 700; color: #fff; margin: 0 0 12px; line-height: 1.3;">{bridge_headline}</h2>
                <p style="font-size: 16px; color: rgba(255,255,255,0.75); line-height: 1.7; margin: 0 0 20px;">{bridge_body}</p>
                <p style="font-size: 15px; color: rgba(255,255,255,0.6); line-height: 1.7; margin: 0 0 24px;">The Resolved Brief is a 30-minute guided session that walks you through every area your family would need — finances, insurance, medical wishes, digital access, final instructions. You answer the questions. It builds one complete, organized document your family can follow.<br/><br/><strong style="color: #D4913B;">Print a copy. Save it digitally. Done.</strong></p>
                <a href="https://familycrisisplaybook.com/session/" style="display: inline-block; font-size: 17px; font-weight: 700; padding: 16px 32px; border-radius: 8px; background: linear-gradient(135deg, #D4913B, #BF7E2F); color: #1B3A5C; text-decoration: none; letter-spacing: 0.3px;">START MY RESOLVED BRIEF — $49 →</a>
                <p style="font-size: 13px; color: rgba(255,255,255,0.4); margin: 16px 0 0;">20 minutes. One document. Done.</p>
            </div>

            <!-- SHARE COUPON -->
            <div style="padding: 24px; background: #F0EDE5; border-radius: 12px; text-align: center; margin-bottom: 24px;">
                <p style="font-size: 15px; color: #4B5563; line-height: 1.6; margin: 0 0 12px;">Share this scorecard with two people you care about and use code <strong style="color: #1B3A5C;">SHARE50</strong> — your Resolved Brief drops from $49 to <strong style="color: #10B981;">$24.50</strong>.</p>
                <div style="display: inline-block; padding: 10px 24px; background: #fff; border: 1.5px solid rgba(212,145,59,0.4); border-radius: 100px;">
                    <span style="font-family: Georgia, serif; font-size: 20px; font-weight: 700; color: #1B3A5C; letter-spacing: 1px;">SHARE50</span>
                </div>
            </div>

            <!-- CLOSING -->
            <p style="font-size: 15px; color: #6B7280; line-height: 1.7;">You took the scorecard. You saw where you stand. Most people never get this far.<br/><br/>Now finish it.</p>
            <p style="font-size: 15px; color: #4B5563; margin-top: 16px;">— JB</p>
            <p style="font-family: Georgia, serif; font-size: 18px; font-style: italic; color: #D4913B; margin-top: 24px;">"There's an envelope in my desk."</p>
            <p style="font-size: 13px; color: #9CA3AF;">Be the person who can say that.</p>

        </div>

        <!-- FOOTER -->
        <div style="padding: 20px 32px; border-top: 1px solid #E8E5DE; text-align: center;">
            <p style="font-size: 12px; color: #9CA3AF; margin: 0;">© 2026 Resolved Family · ResolvedFamily.com</p>
            <p style="font-size: 12px; color: #9CA3AF; margin: 4px 0 0;">Educational material. Not legal, financial, or medical advice.</p>
        </div>

    </div>
    """


# ═══ NEW ENDPOINT ═══

@app.post("/api/scorecard/send-report")
async def send_scorecard_report(data: ScorecardReportRequest):
    """
    Receives scorecard results after email gate submission.
    Sends personalized gap report email via Resend.
    """
    if not RESEND_API_KEY:
        print(f"WARNING: No RESEND_API_KEY — cannot send scorecard report to {data.email}")
        return JSONResponse(status_code=200, content={"status": "no_key"})

    try:
        html_content = build_scorecard_report_email(data)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "jb@resolvedfamily.com",
                    "to": [data.email],
                    "subject": f"{data.first_name}, here's your Family Readiness Report",
                    "html": html_content,
                },
            )

            if response.status_code in (200, 201):
                print(f"Scorecard report sent to {data.email}")
                return JSONResponse(status_code=200, content={"status": "sent"})
            else:
                print(f"Scorecard report email failed: {response.status_code} {response.text}")
                return JSONResponse(status_code=200, content={"status": "failed", "detail": response.text})

    except Exception as e:
        print(f"Scorecard report error: {e}")
        return JSONResponse(status_code=200, content={"status": "error", "message": str(e)})
