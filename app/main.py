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
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://familycrisisplaybook.com",
        "https://www.familycrisisplaybook.com",
        "https://resolvedfamily.com",
        "https://www.resolvedfamily.com",
        "http://localhost:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
3. Answers are in V5.2 format: assessment questions are stored as option indices (0=best, 1=partial, 2=gap). Data fields use IDs like Q2_executor, Q27_primary_bank, etc. — those contain the actual text values. Focus on the data_field values (the text) for building narratives.
4. If a data field is empty or missing, say "this was not documented."
5. For phone numbers: use ONLY the verified numbers listed below for institutions {first_name} actually named. For any institution NOT on this list, write: "Call their main customer service line and ask for the Estate Services or Bereavement department."
6. This is a legal document. Accuracy matters more than completeness.

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

KEY DATA FIELDS TO REFERENCE:
- Foundation: Q2_executor (executor/trustee), Q2_location (will location), Q5_who (POA), Q7_location (documents), Q8_attorney (estate attorney)
- People: Q10_who (point person), Q10_phone (their phone), Q12_backup (backup contact), Q14_attorney/Q14_cpa/Q14_advisor/Q14_insurance (professional contacts), Q17_authority (final decision maker)
- Money: Q27_primary_bank (primary bank), Q27_joint (joint account holder), Q28_accounts (all accounts), Q30_autopay/Q30_manual (bills), Q31_debts, Q32_assets, Q33_business
- Insurance: Q37_provider/Q37_amount/Q37_beneficiary (life insurance), Q40_health/Q40_home/Q40_auto, Q43_agent
- Digital: Q46_email, Q47_manager (password manager), Q49_photos, Q50_cloud, Q51_crypto, Q52_apps
- Medical: Q54_proxy/Q54_backup (healthcare proxy), Q56_conditions/Q56_meds/Q56_allergies/Q56_doctor

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
  "foundation": {{"narrative": "...", "action_guide": "..."}},
  "people": {{"narrative": "...", "action_guide": "..."}},
  "money": {{"narrative": "...", "action_guide": "..."}},
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
        "foundation": {
            "narrative": f"{first} documented the legal foundation — will, power of attorney, and where everything is stored. The details below tell you exactly who's in charge and where to find the documents.",
            "action_guide": f"INSTITUTION: Estate Attorney | PHONE: See attorney contact below | STEP 1: Contact the estate attorney and report the death | STEP 2: Provide a certified death certificate and ask about next steps for will execution | STEP 3: Ask about any trusts, directives, or documents that need to be filed | HAVE READY: Death certificate, will location, trust documents | TIMELINE: Initial consultation within 24-48 hours | WATCH OUT: Do not attempt to change titles on property or access accounts before speaking with the attorney — there may be tax implications",
        },
        "people": {
            "narrative": f"{first} identified the key people who should step in and what roles they play. The contacts below include the point person, backup, and professional advisors who can help coordinate everything.",
            "action_guide": f"INSTITUTION: Point Person | PHONE: See contact below | STEP 1: Notify the point person immediately and share this Resolved Brief | STEP 2: Have them contact the attorney and financial advisor within 24-48 hours | STEP 3: The point person should coordinate with the backup contact for tax and financial matters | HAVE READY: This Brief, death certificate, contact information | TIMELINE: Initial coordination within 24-48 hours | WATCH OUT: Clear roles prevent family conflict — the backup should support, not override, the point person's decisions",
        },
        "money": {
            "narrative": f"If you are reading this, {first} wanted you to know exactly where the money is. Everything below documents the banks, accounts, debts, and financial obligations that matter. Take your time with this section.",
            "action_guide": guide,
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
    Creates a paid session and returns walkthrough URL.
    PDF generation happens AFTER the walkthrough via /generate-brief.
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

        # ─── Find or create a session for this paid customer ───
        if not session_id:
            print(f"No session_id in webhook, searching by email: {email}")
            result = supabase.table("sessions").select("session_id").eq(
                "email", email
            ).order("created_at", desc=True).limit(1).execute()

            if result.data:
                session_id = result.data[0]["session_id"]
                print(f"Found session by email: {session_id}")
            else:
                # No existing session — create one for this paid customer
                print(f"Creating new paid session for {email}")
                first_name = name.split()[0] if name and name != "Valued Customer" else ""
                result = supabase.table("sessions").insert({
                    "email": email,
                    "first_name": first_name,
                    "purchase_status": "paid",
                    "last_activity_at": now_iso(),
                }).execute()
                session_id = result.data[0]["session_id"]
                print(f"Created new session: {session_id}")

        # ─── Mark session as paid (do NOT generate PDF yet) ───
        supabase.table("sessions").update({
            "purchase_status": "paid",
            "email": email,
            "first_name": name.split()[0] if name and name != "Valued Customer" else None,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        walkthrough_url = f"/walkthrough?session_id={session_id}"
        print(f"Session {session_id} marked as paid. Walkthrough URL: {walkthrough_url}")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "session_id": session_id,
                "email": email,
                "walkthrough_url": walkthrough_url,
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


# ═══ FREE FLOW: START — create/find session, return session_id ═══

class FreeStartRequest(BaseModel):
    email: str
    first_name: Optional[str] = None

@app.post("/api/free/start")
async def free_start(data: FreeStartRequest):
    """
    Called by /free/ page form on submit.
    Finds existing session by email or creates a new one.
    Returns session_id so frontend can redirect to walkthrough.
    """
    try:
        email = data.email.strip().lower()
        first_name = (data.first_name or "").strip()

        # Look for most recent session with this email
        result = supabase.table("sessions").select("session_id, first_name").eq(
            "email", email
        ).order("created_at", desc=True).limit(1).execute()

        if result.data:
            session_id = result.data[0]["session_id"]
            # Update name if provided and not already set
            if first_name and not result.data[0].get("first_name"):
                supabase.table("sessions").update({
                    "first_name": first_name,
                    "last_activity_at": now_iso(),
                }).eq("session_id", session_id).execute()
            print(f"Free flow: found existing session {session_id} for {email}")
        else:
            # Create new session
            insert_result = supabase.table("sessions").insert({
                "email": email,
                "first_name": first_name or None,
                "purchase_status": "free",
                "last_activity_at": now_iso(),
            }).execute()
            session_id = insert_result.data[0]["session_id"]
            print(f"Free flow: created new session {session_id} for {email}")

        return JSONResponse(
            status_code=200,
            content={"status": "ok", "session_id": session_id}
        )

    except Exception as e:
        print(f"Free start error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# ═══ FREE FLOW: GENERATE — called at end of walkthrough ═══

class FreeBriefRequest(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None

@app.post("/api/session/{session_id}/free-brief")
async def free_brief(session_id: str, data: FreeBriefRequest = FreeBriefRequest()):
    """
    Called by walkthrough completion screen (free flow).
    Saves answers, marks session as free, generates + emails PDF immediately.
    """
    try:
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if not result.data:
            return JSONResponse(status_code=404, content={"status": "error", "error": "Session not found."})

        session = result.data[0]

        # Prevent duplicate generation
        if session.get("pdf_generated"):
            return JSONResponse(status_code=200, content={
                "status": "success",
                "message": "Your Resolved Brief was already sent — check your inbox (and spam folder)."
            })

        email = data.email or session.get("email")
        name = data.first_name or session.get("first_name") or (email.split("@")[0] if email else "Friend")

        if not email:
            return JSONResponse(status_code=400, content={"status": "error", "error": "No email found for this session."})

        # Mark as free/paid so generate_resolved_brief doesn't block
        supabase.table("sessions").update({
            "purchase_status": "free",
            "email": email,
            "first_name": name.split()[0] if name else None,
            "walkthrough_completed": True,
            "last_activity_at": now_iso(),
        }).eq("session_id", session_id).execute()

        print(f"Generating free brief for {email} (session: {session_id})")
        status = await generate_resolved_brief(session_id, email, name)

        if status in ("sent", "generated_not_sent"):
            return JSONResponse(status_code=200, content={"status": "success"})
        else:
            return JSONResponse(status_code=200, content={
                "status": "error",
                "error": "Generation failed — please try again or contact support."
            })

    except Exception as e:
        print(f"Free brief error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


# ═══ PDF GENERATION — called after walkthrough completion ═══

class GenerateBriefRequest(BaseModel):
    answers: Optional[dict] = None  # walkthrough answers from frontend localStorage
    email: Optional[str] = None     # override (for testing)
    name: Optional[str] = None      # override (for testing)

@app.post("/api/session/{session_id}/generate-brief")
async def generate_brief_endpoint(session_id: str, data: GenerateBriefRequest = GenerateBriefRequest()):
    """
    Generate the Resolved Brief PDF after walkthrough completion.
    Called by the walkthrough CTA button — receives answers from frontend,
    saves them to Supabase, then generates + emails the PDF.
    """
    try:
        # ─── 1. Validate session exists ───
        result = supabase.table("sessions").select("*").eq(
            "session_id", session_id
        ).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = result.data[0]

        # ─── 2. Validate session is paid or free ───
        if session.get("purchase_status") not in ("paid", "free"):
            raise HTTPException(status_code=403, detail="Session not paid. Complete purchase first.")

        # ─── 3. Prevent duplicate generation ───
        if session.get("pdf_generated"):
            return {
                "status": "already_generated",
                "message": "Your Resolved Brief has already been generated and emailed.",
                "session_id": session_id,
            }

        # ─── 4. Save answers from frontend if provided ───
        if data.answers:
            print(f"Saving {len(data.answers)} answers from frontend for session {session_id}")
            supabase.table("sessions").update({
                "answers_json": data.answers,
                "walkthrough_completed": True,
                "last_activity_at": now_iso(),
            }).eq("session_id", session_id).execute()

        # ─── 5. Pull email/name from session (or override for testing) ───
        email = data.email or session.get("email")
        name = data.name or session.get("first_name") or "Valued Customer"

        if not email:
            raise HTTPException(status_code=400, detail="No email found for this session. Please contact support.")

        # ─── 6. Generate + email the PDF ───
        print(f"Generating Resolved Brief for {email} (session: {session_id})")
        status = await generate_resolved_brief(session_id, email, name)

        return {
            "status": "success" if status else "error",
            "message": "Your Resolved Brief is on its way to your inbox!" if status else "Generation failed — our team has been notified.",
            "pdf_status": status or "failed",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Generate brief error: {e}")
        import traceback
        traceback.print_exc()
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

    # Grade color — matches V2 scorecard tiers
    if label in ("Excellent", "Strong", "Low Confusion"):
        grade_color = "#10B981"
    elif label in ("Fair", "Good", "Some Gaps"):
        grade_color = "#F59E0B"
    else:
        grade_color = "#EF4444"

    # Enhanced action steps — detailed to-do checklists by question ID
    # Maps to the 13-question V2 scorecard
    ENHANCED_ACTIONS = {
        1: [
            "Write down the full name and phone number of the person who would step in if something happened to you tonight.",
            "Tell that person they're the one — don't assume they know.",
            "Give them a one-page summary: where your important docs are, who to call first, and what needs to happen in the first 48 hours.",
            "If you don't have a clear answer, pick someone today. It doesn't have to be perfect — it has to exist.",
        ],
        2: [
            "Write a simple 'First 24 Hours' sheet: bank to call, insurance company, employer HR, mortgage company, pediatrician.",
            "Include account numbers or at least institution names so they're not guessing.",
            "Put it in a sealed envelope and tell your person where it is.",
            "If your answer was 'they'd figure it out' — that's not a plan. That's a hope.",
        ],
        3: [
            "Name a backup person — someone outside your household who could step in if both you and your partner were out of the picture.",
            "Talk to that person directly. Tell them what you'd need them to handle — kids, finances, medical decisions.",
            "Make sure this person knows where your key documents are (or at least who to call).",
            "If you have minor children, this is your future guardian conversation. Don't skip it.",
        ],
        4: [
            "Have the conversation. Sit down with your designated person and say: 'If something happens to me, you're the one I'm counting on.'",
            "Walk them through the basics — where to find your documents, who your attorney or financial advisor is, what accounts exist.",
            "If you haven't told them, it doesn't count. A name on paper means nothing if they don't know they're on it.",
        ],
        5: [
            "Write down your phone's passcode — PIN, pattern, or password — and store it in a sealed envelope.",
            "If you use Face ID or fingerprint, the backup PIN still exists. Document it.",
            "Consider adding a trusted family member's fingerprint or face to your phone's biometrics.",
            "Note which authenticator app you use (Google Authenticator, Authy, etc.) — your family needs this for banking and email 2FA codes.",
            "Your phone is the gateway to everything. If they can't unlock it, they're locked out of your entire digital life.",
        ],
        6: [
            "Write down every email address you use, the provider (Gmail, Outlook, Yahoo), and the password or where it's stored.",
            "Document how to get past 2FA — authenticator app, backup codes, or recovery phone number.",
            "Set up Google's Inactive Account Manager or Apple's Legacy Contact — these give a designated person access after inactivity.",
            "Your email is the master key. Almost every account can be reset through it. No email access = no access to anything.",
        ],
        7: [
            "Pick a system: password manager (1Password, Bitwarden), a physical notebook, or an encrypted file.",
            "If you use a password manager, write down the master password and store it separately from your devices.",
            "Include recovery codes, backup emails, and security question answers for critical accounts.",
            "Tell one trusted person where this information lives — not the passwords, just the location.",
            "Test it: could someone who's never used your system actually get in? If not, add clearer instructions.",
        ],
        8: [
            "Make a list of every digital account that matters — cloud storage, social media, subscriptions, photo libraries.",
            "Note which ones have irreplaceable content (photos, legal docs, business files).",
            "Set up shared folders or legacy contacts where platforms allow it (Google, Apple, Facebook).",
            "If everything lives on your laptop and nobody has the password — it's gone. Document access now.",
        ],
        9: [
            "List every bank account, credit union, and investment account. Include the institution, account type, and customer service number.",
            "Note whether each account is individual, joint, or has a payable-on-death beneficiary.",
            "Document any automatic payments coming out of each account — mortgage, utilities, insurance, subscriptions.",
            "Check beneficiary designations — without them, your family may need probate court just to access basic funds.",
            "Store this list in a sealed envelope and tell one person where it is.",
        ],
        10: [
            "List every account: checking, savings, 401(k), IRA, brokerage, HSA, crypto, business accounts.",
            "For each one, write down: institution name, approximate purpose, how to access it (website, phone, advisor).",
            "Verify beneficiaries on every retirement and investment account — an outdated designation overrides your will.",
            "If you've changed jobs, check for orphaned 401(k)s at former employers.",
            "Your family doesn't need exact balances — they need to know the accounts exist and how to reach them.",
        ],
        11: [
            "Confirm you have life insurance. Write down the company, policy number, death benefit amount, and type (term vs. whole).",
            "Verify your beneficiary is current — divorce, remarriage, and new kids can make your existing designation outdated.",
            "Locate the actual policy document or download it from your provider's website.",
            "Write down the claims phone number. Life insurance doesn't pay automatically — someone has to call and file.",
            "If you have employer coverage, confirm whether it ends when you leave or retire.",
        ],
        12: [
            "Name your healthcare proxy — the person who makes medical decisions if you can't speak for yourself.",
            "Have a real conversation with them: Do you want life support? Resuscitation? Long-term care if you're in a coma?",
            "Write it down. Consider filing a Healthcare Power of Attorney (most states have free forms online).",
            "Give a copy to your proxy, your spouse, and your primary care doctor.",
            "Tell at least one other family member who your proxy is — hospitals move fast and won't wait for people to figure it out.",
        ],
        13: [
            "Be honest with yourself about this answer. If it's not a confident 'yes' — you have work to do.",
            "The Resolved Brief walks you through every area: finances, insurance, medical wishes, digital access, final instructions.",
            "It takes about 20 minutes. You answer the questions, it builds the document.",
            "Print a copy. Save it digitally. Tell one person where it is. That's it — you're done.",
        ],
    }

    # Build gap items HTML
    gap_items_html = ""
    for i, gap in enumerate(gaps):
        gap_id = gap.get('id')
        enhanced = ENHANCED_ACTIONS.get(gap_id)

        if enhanced:
            checklist_html = ""
            for step in enhanced:
                checklist_html += f'<li style="font-size: 14px; color: #4B5563; line-height: 1.6; margin-bottom: 6px; padding-left: 4px;">{step}</li>'
            action_block = f"""
            <div style="margin-left: 36px; margin-top: 8px; padding: 16px 20px; background: rgba(16,185,129,0.06); border-radius: 6px; border: 1px solid rgba(16,185,129,0.2);">
                <p style="font-size: 13px; font-weight: 700; color: #10B981; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 10px;">✅ Your To-Do List</p>
                <ol style="margin: 0; padding-left: 20px;">{checklist_html}</ol>
            </div>"""
        else:
            action_block = f"""
            <div style="margin-left: 36px; margin-top: 8px; padding: 12px 16px; background: rgba(16,185,129,0.06); border-radius: 6px; border: 1px solid rgba(16,185,129,0.2);">
                <p style="font-size: 13px; font-weight: 700; color: #10B981; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 6px;">✅ What To Do</p>
                <p style="font-size: 15px; color: #4B5563; line-height: 1.6; margin: 0;">{gap.get('actionStep', '')}</p>
            </div>"""

        gap_items_html += f"""
        <div style="margin-bottom: 24px; padding: 20px 24px; background: #fff; border: 1.5px solid #E8E5DE; border-left: 4px solid #EF4444; border-radius: 8px;">
            <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px;">
                <span style="font-family: Georgia, serif; font-size: 18px; font-weight: 700; color: #D4913B; min-width: 24px;">{i+1}.</span>
                <p style="font-size: 16px; font-weight: 700; color: #1B3A5C; margin: 0; line-height: 1.4;">{gap.get('text', '')}</p>
            </div>
            <div style="margin-left: 36px; padding: 12px 16px; background: #FEF9F0; border-radius: 6px; border: 1px solid rgba(212,145,59,0.2);">
                <p style="font-size: 13px; font-weight: 700; color: #D4913B; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 6px;">⚠ Why This Matters</p>
                <p style="font-size: 15px; color: #4B5563; line-height: 1.6; margin: 0;">{gap.get('gapTip', '')}</p>
            </div>{action_block}
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
            <p style="font-size: 15px; color: #6B7280; margin: 0 0 4px;">Hi {first} — here's your full breakdown.</p>
            <p style="font-size: 13px; color: #9CA3AF; margin: 0 0 12px;">💡 Save this report: On iPhone, tap the share icon → Print → Save as PDF. On desktop, File → Print → Save as PDF.</p>
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
                <a href="https://familycrisisplaybook.com/free/" style="display: inline-block; font-size: 17px; font-weight: 700; padding: 16px 32px; border-radius: 8px; background: linear-gradient(135deg, #D4913B, #BF7E2F); color: #1B3A5C; text-decoration: none; letter-spacing: 0.3px;">START MY RESOLVED BRIEF — FREE →</a>
                <p style="font-size: 13px; color: rgba(255,255,255,0.4); margin: 16px 0 0;">20 minutes. One document. Done.</p>
            </div>

            <!-- SHARE -->
            <div style="padding: 24px; background: #F0EDE5; border-radius: 12px; text-align: center; margin-bottom: 24px;">
                <p style="font-size: 15px; color: #4B5563; line-height: 1.6; margin: 0 0 16px;">Know someone who should take this? Share the scorecard — it takes 5 minutes and it could change everything for their family.</p>
                <div style="margin-top: 8px;">
                    <a href="sms:&body=I%20just%20took%20this%20and%20I%27m%20glad%20I%20did.%205%20minutes%20and%20you%27ll%20know%20exactly%20what%20your%20family%20would%20need%20if%20something%20happened%20to%20you.%20https%3A%2F%2Ffamilycrisisplaybook.com%2Fquick%2F" style="display: inline-block; padding: 10px 20px; background: #1B3A5C; color: #fff; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 700; margin: 4px;">📲 Text a Friend</a>
                    <a href="mailto:?subject=You%20need%20to%20take%20this%20%E2%80%94%205%20minutes&body=I%20just%20took%20this%20and%20I%27m%20glad%20I%20did.%205%20minutes%20and%20you%27ll%20know%20exactly%20what%20your%20family%20would%20need%20if%20something%20happened%20to%20you.%0A%0Ahttps%3A%2F%2Ffamilycrisisplaybook.com%2Fquick%2F" style="display: inline-block; padding: 10px 20px; background: #D4913B; color: #fff; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 700; margin: 4px;">✉️ Email a Friend</a>
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
