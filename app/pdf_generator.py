"""
The Resolved Brief — PDF Generator
===================================
Generates a personalized, professional Resolved Brief from walkthrough answers.
Matches the exact brand design: navy/gold/cream, R badge, section headers.

v2: Added action guide rendering — phone numbers, steps, timelines, gotchas.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, Frame, PageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import json, os
from datetime import datetime

# ═══ BRAND COLORS ═══
NAVY = HexColor("#1B2A3D")
DARK_NAVY = HexColor("#152233")
GOLD = HexColor("#C9A84C")
CREAM = HexColor("#F5F0E8")
WARM_WHITE = HexColor("#FDFBF7")
LIGHT_GRAY = HexColor("#E0DCD4")
MID_GRAY = HexColor("#8A8578")
DARK_GRAY = HexColor("#4A4A4A")
FIELD_DOT = HexColor("#C8C3BA")
RED_ACCENT = HexColor("#C0392B")
ACTION_BG = HexColor("#EEF2F7")       # Soft blue-gray for action guide blocks
ACTION_BORDER = HexColor("#1B2A3D")   # Navy border
STEP_NUM_BG = HexColor("#C9A84C")     # Gold step numbers
WATCH_OUT_BG = HexColor("#FFF3CD")    # Warm yellow for watch-out
WATCH_OUT_BORDER = HexColor("#E6AC00")

W, H = letter  # 612 x 792

# ═══ MOCK DATA ═══
MOCK = {
    "name": "Michael Thompson",
    "date": datetime.now().strftime("%B %d, %Y"),
    "answers": {
        "S1": "Yes", "S1A": "3-5 years ago", "S1B": "Yes",
        "S2": "Yes", "S3": "No", "S4": "Yes", "S5": "No",
        "S6": "2-3", "S7": "No", "S8": "With some digging",
        "S9": "Most of them", "S10": "Yes", "S11": "No", "S12": "No",
        "Q1": "Sarah Thompson (wife)", "Q2": "Yes", "Q3": "James Thompson (brother)",
        "Q4": "High blood pressure, mild asthma", "Q5": "Lisinopril 10mg, Albuterol inhaler as needed",
        "Q6": "Penicillin", "Q7": "Dr. Emily Chen, Northwestern Medical",
        "Q8": "Dr. Raj Patel - cardiologist", "Q9": "Blue Cross Blue Shield through employer",
        "Q10": "Wallet", "Q12": "Full resuscitation", "Q13": "Yes",
        "Q14": "Chase (checking + savings), Ally (savings)", "Q15": "Checking,Savings,Money Market",
        "Q16": "Sarah Thompson (joint on Chase)", "Q17": "401(k),Roth IRA",
        "Q18": "Fidelity (401k through work), Vanguard (Roth IRA)",
        "Q19": "Schwab brokerage account",
        "Q20": "Wells Fargo mortgage", "Q21": "Toyota Financial (car loan)",
        "Q22": "Chase Sapphire, Amex Blue Cash", "Q23": "Filing cabinet,Computer or cloud",
        "Q24": "No",
        "Q25": "Chase checking", "Q26": "Ally savings, HSA through employer",
        "Q27": "Employer paycheck",
        "Q28": "Mortgage, electric (ComEd), internet (Xfinity), car insurance (State Farm), Netflix, Spotify",
        "Q29": "Water bill quarterly", "Q30": "Netflix, Spotify, NYT, gym, iCloud",
        "Q31": "Property tax (June + Sept), car registration (October)",
        "Q32": "Yes - both", "Q33": "MetLife (employer), Northwestern Mutual (private)",
        "Q34": "$500K employer + $250K private", "Q35": "Sarah Thompson",
        "Q36": "Yes - through employer", "Q37": "No", "Q38": "State Farm homeowners",
        "Q39": "State Farm auto", "Q40": "$1M umbrella through State Farm",
        "Q41": "Filing cabinet", "Q42": "John Davis, State Farm, 312-555-0847",
        "Q43": "Password manager app", "Q44": "1Password",
        "Q45": "In the sealed envelope",
        "Q46": "michael.t@gmail.com", "Q47": "Yes - someone knows the code",
        "Q48": "No - only I can access it", "Q49": "Venmo,Zelle",
        "Q50": "No", "Q51": "iCloud,Google Photos", "Q52": "Google Drive,iCloud",
        "Q53": "Cremation", "Q54": "Scatter ashes at Lake Michigan",
        "Q55": "Celebration of life",
        "Q56": "Play What a Wonderful World by Louis Armstrong. Keep it casual.",
        "Q57": "College roommate Dave Brennan, old boss Linda Park",
        "Q58": "Grandfather's watch to Jake, guitar collection to brother James",
        "Q59": "Donate clothes to Goodwill, sell the boat",
        "Q60": "To Sarah - you made every single day better. To Jake and Emma - be kind, work hard, and never stop being curious. I'm proud of who you're becoming."
    },
    "homework": ["S3", "S5", "S7", "S11", "S12", "Q48"],
    "ai_narratives": {}
}

def generate_sample_narratives(data):
    A = data["answers"]
    return {
        "financial": {
            "narrative": "Michael's primary banking is consolidated through Chase, with a joint checking account shared with Sarah and a separate savings account at Ally. Retirement planning is well-structured across a Fidelity 401(k) and Vanguard Roth IRA, with additional investments at Schwab. Financial documents are split between a filing cabinet and cloud storage.",
            "action_guide": "INSTITUTION: Chase Bank | PHONE: 1-888-356-0023 | STEP 1: Call the Estate Services line and identify yourself as next of kin or executor | STEP 2: Request information on all accounts held under the deceased's name | STEP 3: Ask about joint account access for Sarah Thompson and next steps for transferring ownership | HAVE READY: Death certificate (certified copy), your photo ID, Social Security number of deceased | TIMELINE: Joint account access is typically immediate. Individual account transfers take 2-4 weeks | WATCH OUT: Do not close joint accounts until you speak with an estate attorney — tax implications vary\n\nINSTITUTION: Fidelity (401k) | PHONE: 1-800-343-3548 | STEP 1: Call Fidelity and report the death — ask for the Beneficiary Services team | STEP 2: Request the beneficiary claim packet — Sarah Thompson is the named beneficiary | STEP 3: Complete and return the packet with a certified death certificate | HAVE READY: Death certificate, beneficiary's ID, beneficiary's Social Security number | TIMELINE: Beneficiary claims typically process in 30-60 days | WATCH OUT: Do not roll over the 401k until you understand the inherited IRA rules — a mistake here can trigger significant taxes\n\nINSTITUTION: Vanguard (Roth IRA) | PHONE: 1-800-662-7447 | STEP 1: Call Vanguard and notify them of the death | STEP 2: Ask for the inherited IRA options for the named beneficiary | STEP 3: Complete the transfer paperwork | HAVE READY: Death certificate, beneficiary ID | TIMELINE: 30-60 days | WATCH OUT: Inherited Roth IRA rules differ from traditional IRA — withdrawals may still be tax-free but timing rules apply",
        },
        "income": {
            "narrative": "Income flows primarily through Chase checking via employer paycheck. Most recurring bills are on autopay, which is ideal — but those autopay cards must stay active or bills will start bouncing. The water bill is paid manually on a quarterly basis. Key annual payments to watch: property tax in June and September, car registration in October.",
            "action_guide": "INSTITUTION: Employer / HR Department | PHONE: Call HR directly | STEP 1: Notify HR of the death and ask about the final paycheck | STEP 2: Ask about any accrued PTO payout and life insurance through the employer | STEP 3: Request information about pension or 401k continuation | HAVE READY: Death certificate, employee ID if known | TIMELINE: Final paycheck typically issued within 1-2 pay cycles | WATCH OUT: Autopay bills will keep charging — go through the autopay list and cancel or transfer each one individually. Do not cancel cards until autopays are moved",
        },
        "insurance": {
            "narrative": "Michael's insurance coverage is stronger than most. Life insurance totals $750,000 across MetLife (employer) and Northwestern Mutual (private), with Sarah as beneficiary on both. Disability coverage exists through the employer. All policies are filed in the filing cabinet, and agent John Davis at State Farm handles home, auto, and umbrella.",
            "action_guide": "INSTITUTION: MetLife (Life Insurance — Employer Policy) | PHONE: 1-800-638-5433 | STEP 1: Call MetLife and ask for the Life Insurance Claims department | STEP 2: Provide the policy number if available, or identify through the employer | STEP 3: Complete and return the beneficiary claim form | HAVE READY: Death certificate (certified), beneficiary ID, policy number if available | TIMELINE: Life insurance claims typically pay within 30-60 days | WATCH OUT: If the death was within 2 years of the policy start date, the insurer may contest the claim — this is called the contestability period\n\nINSTITUTION: Northwestern Mutual (Private Life Insurance) | PHONE: 1-800-388-8123 | STEP 1: Call Northwestern Mutual and request the Claims department | STEP 2: Provide the policy number (located in the filing cabinet) | STEP 3: Submit the claim with a certified death certificate | HAVE READY: Death certificate, beneficiary ID, policy documents | TIMELINE: 30-60 days | WATCH OUT: Keep the policy in force (premium paid) until the claim is processed — a lapsed policy can complicate the claim\n\nINSTITUTION: State Farm (Home, Auto, Umbrella) | PHONE: 1-800-732-5246 | STEP 1: Call agent John Davis directly at 312-555-0847 | STEP 2: Notify State Farm of the death and discuss policy continuation | STEP 3: Transfer home and auto policies to the surviving spouse if applicable | HAVE READY: Death certificate, policy numbers | TIMELINE: Policy transfers are typically completed within 1-2 weeks | WATCH OUT: Do not let home or auto insurance lapse — coverage gaps can leave you unprotected and affect future rates",
        },
        "digital": {
            "narrative": "Password management is handled through 1Password, with the master password stored in the sealed envelope — good setup. Michael's primary email is a Gmail account. The main gap is computer access — only Michael can currently get in. Financial apps include Venmo and Zelle. Photos are backed up across iCloud and Google Photos.",
            "action_guide": "INSTITUTION: Gmail / Google Account | PHONE: No direct phone — use google.com/accounts/recovery | STEP 1: Start with the primary email account — it is the key to resetting everything else | STEP 2: Use Google's Inactive Account process or submit a deceased user request at support.google.com | STEP 3: Once in, use the email to reset passwords for financial accounts one at a time | HAVE READY: Death certificate (digital copy), your own photo ID | TIMELINE: Google's deceased user process takes 4-8 weeks | WATCH OUT: Do not delete the Google account — it may hold 2-factor authentication codes, documents, and photos that you will need\n\nINSTITUTION: 1Password (Password Manager) | PHONE: No phone — use 1password.com/support | STEP 1: Retrieve the master password from the sealed envelope | STEP 2: Log in to 1Password and export the vault or access credentials one by one | STEP 3: Use the stored passwords to access financial accounts, email, and other services | HAVE READY: Master password from sealed envelope | TIMELINE: Immediate once you have the master password | WATCH OUT: The Emergency Kit (account key + master password) is required — without both, the vault is unrecoverable",
        },
        "medical": {
            "narrative": "Sarah Thompson is the medical decision maker and she knows she's been chosen. James Thompson serves as backup. Michael has high blood pressure and mild asthma — Lisinopril and Albuterol. Critical allergy: penicillin. Dr. Emily Chen at Northwestern Medical is primary care, Dr. Raj Patel handles cardiology. The gap: no living will or advance directive exists.",
            "action_guide": "INSTITUTION: Blue Cross Blue Shield (Health Insurance) | PHONE: Call the member services number on the insurance card | STEP 1: Notify BCBS of the death and ask about any outstanding claims | STEP 2: Ask about COBRA continuation coverage if dependents need continued coverage | STEP 3: Cancel the policy once all claims are settled | HAVE READY: Death certificate, member ID number, insurance card | TIMELINE: Outstanding claims are typically resolved within 60-90 days | WATCH OUT: Do not cancel health insurance until all outstanding medical bills are resolved — some claims arrive months after treatment\n\nINSTITUTION: Dr. Emily Chen — Primary Care (Northwestern Medical) | PHONE: Call the practice directly | STEP 1: Notify the practice of the death | STEP 2: Request medical records if needed for insurance claims or legal purposes | STEP 3: Cancel any upcoming appointments | HAVE READY: Death certificate, patient ID | TIMELINE: Medical records requests take up to 30 days under HIPAA | WATCH OUT: Medicare and insurance companies need to be notified separately — the doctor's office does not automatically report the death to either",
        },
    }


def _parse_action_guide(action_guide_text: str) -> list:
    """
    Parse the pipe-delimited action guide string into a list of institution dicts.
    Format: INSTITUTION: name | PHONE: ... | STEP 1: ... | STEP 2: ... | STEP 3: ... | HAVE READY: ... | TIMELINE: ... | WATCH OUT: ...
    Blocks are separated by blank lines.
    """
    if not action_guide_text or not action_guide_text.strip():
        return []

    blocks = []
    raw_blocks = [b.strip() for b in action_guide_text.strip().split("\n\n") if b.strip()]

    for raw in raw_blocks:
        # Flatten any internal newlines within a block
        flat = " ".join(raw.splitlines())
        parts = [p.strip() for p in flat.split("|") if p.strip()]

        block = {}
        for part in parts:
            for key in ["INSTITUTION", "PHONE", "STEP 1", "STEP 2", "STEP 3",
                        "HAVE READY", "TIMELINE", "WATCH OUT"]:
                prefix = key + ":"
                if part.upper().startswith(prefix):
                    block[key] = part[len(prefix):].strip()
                    break

        if block.get("INSTITUTION"):
            blocks.append(block)

    return blocks


class ResolvedBriefBuilder:
    """Builds a Resolved Brief PDF matching the brand design templates."""

    def __init__(self, data):
        self.data = data
        self.A = data["answers"]
        self.name = data["name"]
        self.date = data["date"]
        self.hw = data.get("homework", [])
        self.narratives = data.get("ai_narratives", {})

        # Support both old format (string values) and new format (dict with narrative + action_guide)
        if not self.narratives:
            self.narratives = generate_sample_narratives(data)
        else:
            # If any section is still a plain string (old format), wrap it
            for k, v in self.narratives.items():
                if isinstance(v, str):
                    self.narratives[k] = {"narrative": v, "action_guide": ""}

        self.story = []
        self._setup_styles()

    def _setup_styles(self):
        self.s = {
            "section_sub": ParagraphStyle("section_sub", fontName="Helvetica", fontSize=11, leading=15, textColor=MID_GRAY, spaceAfter=16),
            "narrative": ParagraphStyle("narrative", fontName="Helvetica", fontSize=10.5, leading=16, textColor=DARK_GRAY, spaceAfter=18, leftIndent=4, rightIndent=4),
            "field_label": ParagraphStyle("field_label", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=DARK_NAVY, spaceBefore=4, spaceAfter=1),
            "field_value": ParagraphStyle("field_value", fontName="Helvetica", fontSize=10.5, leading=15, textColor=DARK_GRAY, spaceAfter=8, leftIndent=4),
            "field_empty": ParagraphStyle("field_empty", fontName="Helvetica-Oblique", fontSize=10, leading=14, textColor=FIELD_DOT, spaceAfter=8, leftIndent=4),
            "helper": ParagraphStyle("helper", fontName="Helvetica-Oblique", fontSize=9, leading=13, textColor=MID_GRAY, spaceAfter=4, leftIndent=4),
            "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MID_GRAY),
            "cover_title": ParagraphStyle("cover_title", fontName="Times-Bold", fontSize=42, leading=48, textColor=NAVY, alignment=TA_CENTER),
            "cover_sub": ParagraphStyle("cover_sub", fontName="Helvetica", fontSize=13, leading=18, textColor=MID_GRAY, alignment=TA_CENTER),
            "cover_name": ParagraphStyle("cover_name", fontName="Helvetica-Bold", fontSize=16, leading=22, textColor=NAVY, alignment=TA_CENTER),
            "checklist_cat": ParagraphStyle("cl_cat", fontName="Times-Bold", fontSize=13, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=4),
            "wish_message": ParagraphStyle("wish_msg", fontName="Helvetica-Oblique", fontSize=11.5, leading=18, textColor=DARK_NAVY, leftIndent=12, rightIndent=12, spaceBefore=8, spaceAfter=8),
        }

    def _get(self, qid, default=""):
        val = self.A.get(qid, default)
        if val and "," in val and qid in ("Q15","Q17","Q23","Q27","Q44","Q49","Q51","Q52"):
            val = val.replace(",", ", ")
        return val or default

    def _page_header(self, c, title, section_num=None, is_break_glass=False):
        c.setFillColor(NAVY)
        c.rect(0, H - 72, W, 72, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(0, H - 74, W, 2, fill=1, stroke=0)

        if is_break_glass:
            c.setFillColor(GOLD)
            c.setFont("Times-Bold", 32)
            c.drawCentredString(W/2, H - 48, "FAMILY EMERGENCY CARD")
            c.setFillColor(WARM_WHITE)
            c.setFont("Helvetica", 11)
            c.drawCentredString(W/2, H - 64, "Your family's quick-reference in a crisis")
        else:
            cx, cy = 52, H - 36
            c.setFillColor(GOLD)
            c.circle(cx, cy, 18, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Times-Bold", 16)
            c.drawCentredString(cx, cy - 6, "R")
            c.setFillColor(white)
            c.setFont("Times-Bold", 22)
            c.drawString(80, H - 48, title)
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(W - 36, H - 42, "CONFIDENTIAL")

        c.setFillColor(CREAM)
        c.rect(0, 0, W, H - 74, fill=1, stroke=0)

    def _page_footer(self, c, section_label):
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawString(36, 24, "\u00A9 2026 Resolved \u00B7 ResolvedFamily.com \u00B7 Confidential")
        c.drawRightString(W - 36, 24, section_label)

    def _draw_action_guide(self, c, blocks, y_start, min_y=50):
        """
        Draw the action guide blocks onto the canvas.
        Returns the y position after drawing.
        Each block = one institution with phone, steps, have ready, timeline, watch out.
        """
        from reportlab.lib.utils import simpleSplit
        y = y_start

        # Section header for the action guide
        c.setFillColor(NAVY)
        c.rect(36, y - 2, W - 72, 24, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 2, 3, 26, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y + 5, "ACTION GUIDE  —  What to do next")
        y -= 30

        for block in blocks:
            if y < min_y + 100:
                break

            institution = block.get("INSTITUTION", "")
            phone = block.get("PHONE", "")
            steps = [block.get("STEP 1", ""), block.get("STEP 2", ""), block.get("STEP 3", "")]
            steps = [s for s in steps if s]
            have_ready = block.get("HAVE READY", "")
            timeline = block.get("TIMELINE", "")
            watch_out = block.get("WATCH OUT", "")

            # Institution header bar
            c.setFillColor(ACTION_BG)
            c.rect(36, y - 4, W - 72, 22, fill=1, stroke=0)
            c.setStrokeColor(ACTION_BORDER)
            c.setLineWidth(1.5)
            c.rect(36, y - 4, W - 72, 22, fill=0, stroke=1)
            c.setLineWidth(0.5)

            # Institution name
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(46, y + 3, institution)

            # Phone — right aligned in same bar
            if phone:
                c.setFillColor(GOLD)
                c.setFont("Helvetica-Bold", 9)
                phone_label = f"CALL: {phone}"
                c.drawRightString(W - 46, y + 3, phone_label)

            y -= 26

            # Steps — circle vertically centered with first line of text
            STEP_TEXT_X = 68        # text starts here
            STEP_TEXT_W = W - 112   # text wraps within this width (leaving right margin)
            CIRCLE_X    = 50        # center of gold circle
            LINE_H      = 14        # line height for wrapped step text

            for i, step in enumerate(steps, 1):
                if y < min_y:
                    break
                step_lines = simpleSplit(step, "Helvetica", 10, STEP_TEXT_W)[:3]
                block_h = len(step_lines) * LINE_H

                # Gold circle — vertically centered on the text block
                circle_cy = y - (block_h / 2) + LINE_H / 2
                c.setFillColor(GOLD)
                c.circle(CIRCLE_X, circle_cy, 7, fill=1, stroke=0)
                c.setFillColor(white)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(CIRCLE_X, circle_cy - 3, str(i))

                # Step text lines
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica", 10)
                for li, sl in enumerate(step_lines):
                    c.drawString(STEP_TEXT_X, y - (li * LINE_H), sl)

                y -= block_h + 6  # gap between steps

            y -= 4  # small gap before HAVE READY row

            # Have Ready + Timeline — fixed column widths, text clipped to column
            if have_ready or timeline:
                # Column layout: left col takes ~55%, right col takes ~45%
                LEFT_LABEL_X  = 42
                LEFT_VALUE_X  = 112
                LEFT_COL_END  = 36 + int((W - 72) * 0.54)   # where left col ends
                RIGHT_START   = LEFT_COL_END + 6
                RIGHT_LABEL_X = RIGHT_START + 6
                RIGHT_VALUE_X = RIGHT_START + 68
                RIGHT_COL_END = W - 42

                left_value_w  = LEFT_COL_END - LEFT_VALUE_X - 6
                right_value_w = RIGHT_COL_END - RIGHT_VALUE_X - 6

                row_h = 18
                c.setFillColor(LIGHT_GRAY)
                c.rect(36, y - 4, W - 72, row_h, fill=1, stroke=0)

                # Left: HAVE READY
                if have_ready:
                    c.setFillColor(DARK_NAVY)
                    c.setFont("Helvetica-Bold", 8.5)
                    c.drawString(LEFT_LABEL_X, y + 2, "HAVE READY:")
                    c.setFillColor(DARK_GRAY)
                    c.setFont("Helvetica", 8.5)
                    ready_lines = simpleSplit(have_ready, "Helvetica", 8.5, left_value_w)
                    c.drawString(LEFT_VALUE_X, y + 2, ready_lines[0] if ready_lines else "")

                # Right: TIMELINE
                if timeline:
                    # Divider line between columns
                    c.setStrokeColor(MID_GRAY)
                    c.setLineWidth(0.5)
                    c.line(RIGHT_START, y - 4, RIGHT_START, y + row_h - 4)

                    c.setFillColor(DARK_NAVY)
                    c.setFont("Helvetica-Bold", 8.5)
                    c.drawString(RIGHT_LABEL_X, y + 2, "TIMELINE:")
                    c.setFillColor(DARK_GRAY)
                    c.setFont("Helvetica", 8.5)
                    tl_lines = simpleSplit(timeline, "Helvetica", 8.5, right_value_w)
                    c.drawString(RIGHT_VALUE_X, y + 2, tl_lines[0] if tl_lines else "")

                y -= row_h + 4

            # Watch Out — yellow box, text fully contained within box margins
            if watch_out:
                WATCH_LABEL_X = 46
                WATCH_TEXT_X  = 132
                WATCH_TEXT_W  = W - 72 - (WATCH_TEXT_X - 36) - 10  # stay inside right edge
                LINE_H_W      = 13

                watch_lines = simpleSplit(watch_out, "Helvetica", 9, WATCH_TEXT_W)
                # Cap at 3 lines to avoid runaway boxes
                watch_lines = watch_lines[:3]
                box_h = max(20, len(watch_lines) * LINE_H_W + 10)

                c.setFillColor(WATCH_OUT_BG)
                c.rect(36, y - box_h + 14, W - 72, box_h, fill=1, stroke=0)
                c.setStrokeColor(WATCH_OUT_BORDER)
                c.setLineWidth(1)
                c.rect(36, y - box_h + 14, W - 72, box_h, fill=0, stroke=1)
                c.setLineWidth(0.5)

                c.setFillColor(WATCH_OUT_BORDER)
                c.setFont("Helvetica-Bold", 8.5)
                c.drawString(WATCH_LABEL_X, y + 2, "\u26A0  WATCH OUT:")

                c.setFillColor(HexColor("#5D4B00"))
                c.setFont("Helvetica", 9)
                for li, wl in enumerate(watch_lines):
                    c.drawString(WATCH_TEXT_X, y + 2 - (li * LINE_H_W), wl)

                y -= box_h + 4

            y -= 14  # Space between institution blocks

        return y

    def build_cover(self, c):
        c.setFillColor(NAVY)
        c.rect(0, H * 0.45, W, H * 0.55, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(0, H * 0.45 - 2, W, 4, fill=1, stroke=0)
        c.setFillColor(CREAM)
        c.rect(0, 0, W, H * 0.45 - 2, fill=1, stroke=0)

        cx, cy = W/2, H * 0.78
        c.setFillColor(GOLD)
        c.circle(cx, cy, 36, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Times-Bold", 32)
        c.drawCentredString(cx, cy - 11, "R")

        c.setFillColor(WARM_WHITE)
        c.setFont("Helvetica", 12)
        c.drawCentredString(W/2, H * 0.70, "THE")
        c.setFont("Times-Bold", 44)
        c.drawCentredString(W/2, H * 0.63, "RESOLVED")
        c.drawCentredString(W/2, H * 0.56, "BRIEF")

        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(W/2 - 60, H * 0.535, W/2 + 60, H * 0.535)

        c.setFillColor(HexColor("#A0A0A0"))
        c.setFont("Helvetica", 13)
        c.drawCentredString(W/2, H * 0.50, "The most important document your family will ever need.")

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(W/2, H * 0.36, "PREPARED FOR")
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(W/2 - 100, H * 0.345, W/2 + 100, H * 0.345)
        c.setFont("Helvetica", 14)
        c.setFillColor(DARK_NAVY)
        c.drawCentredString(W/2, H * 0.32, self.name)
        c.setFont("Helvetica", 10)
        c.setFillColor(MID_GRAY)
        c.drawCentredString(W/2, H * 0.295, self.date)

        sections_left = ["Financial Overview", "Insurance & Benefits", "Medical & Emergency", "Family Emergency Card"]
        sections_right = ["Income & Bills", "Digital Life & Access", "Final Wishes", "Follow-Up Checklist"]
        y_start = H * 0.22
        c.setFont("Helvetica", 11)
        for i, (left, right) in enumerate(zip(sections_left, sections_right)):
            y = y_start - (i * 24)
            c.setFillColor(GOLD)
            c.circle(80, y + 4, 4, fill=1, stroke=0)
            c.circle(W/2 + 20, y + 4, 4, fill=1, stroke=0)
            c.setFillColor(NAVY)
            c.drawString(92, y, left)
            c.drawString(W/2 + 32, y, right)

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(W/2, 36, "\u00A9 2026 Resolved \u00B7 ResolvedFamily.com")
        c.setFont("Helvetica", 7)
        c.drawCentredString(W/2, 24, "This document is confidential and intended only for the named individual and their designated contacts.")

    def build_section_page(self, c, title, subtitle, section_num, narrative_key, fields_by_card, continuation_page=False):
        """
        Build a section page: header → narrative → action guide → field cards.
        If action guide is long, it may push fields to render lower or on next page.
        """
        from reportlab.lib.utils import simpleSplit

        self._page_header(c, title, section_num)
        self._page_footer(c, f"Section {section_num} of 7")

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 11)
        c.drawString(36, H - 100, subtitle)

        y = H - 125

        # Pull narrative and action guide from new format
        section_data = self.narratives.get(narrative_key, {})
        if isinstance(section_data, dict):
            narrative_text = section_data.get("narrative", "")
            action_guide_text = section_data.get("action_guide", "")
        else:
            # Old plain-string format fallback
            narrative_text = str(section_data)
            action_guide_text = ""

        # ── PART A: Narrative intro ──
        if narrative_text:
            # Light cream box behind narrative
            narrative_lines = simpleSplit(narrative_text, "Helvetica", 10.5, W - 88)
            box_h = len(narrative_lines) * 15 + 16
            c.setFillColor(HexColor("#F0EDE5"))
            c.rect(36, y - box_h + 10, W - 72, box_h, fill=1, stroke=0)
            c.setStrokeColor(GOLD)
            c.setLineWidth(2)
            c.line(36, y - box_h + 10, 36, y + 10)  # Gold left border
            c.setLineWidth(0.5)

            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 10.5)
            for line in narrative_lines:
                if y < 60:
                    break
                c.drawString(46, y, line)
                y -= 15
            y -= 14

        # ── PART B: Action Guide ──
        if action_guide_text:
            action_blocks = _parse_action_guide(action_guide_text)
            if action_blocks:
                y -= 6
                y = self._draw_action_guide(c, action_blocks, y, min_y=60)
                y -= 10

        # ── PART C: Field Cards ──
        for card_title, fields in fields_by_card:
            if y < 120:
                break

            # Card header bar
            c.setFillColor(NAVY)
            c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
            c.setFillColor(GOLD)
            c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Times-Bold", 13)
            c.drawString(50, y + 4, card_title)
            y -= 32

            for label, value in fields:
                if y < 50:
                    break
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica-Bold", 9.5)
                c.drawString(46, y, f"{label}:")

                val = str(value) if value and str(value).strip() else ""
                if val:
                    c.setFillColor(DARK_GRAY)
                    c.setFont("Helvetica", 10)
                    val_lines = simpleSplit(val, "Helvetica", 10, W - 220)
                    for vl in val_lines[:3]:
                        c.drawString(200, y, vl)
                        y -= 14
                else:
                    c.setFillColor(FIELD_DOT)
                    c.setFont("Helvetica", 9)
                    c.drawString(200, y, ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .")
                    y -= 14

                c.setStrokeColor(LIGHT_GRAY)
                c.setLineWidth(0.5)
                c.line(42, y + 6, W - 42, y + 6)
                y -= 6

            y -= 12

    def build(self, output_path):
        """Build the complete Resolved Brief PDF."""
        c = canvas.Canvas(output_path, pagesize=letter)

        # ═══ PAGE 1: COVER ═══
        self.build_cover(c)
        c.showPage()

        # ═══ PAGE 2: INTRODUCTION LETTER ═══
        from reportlab.lib.utils import simpleSplit
        self._page_header(c, "Before You Begin")
        self._page_footer(c, "Introduction")

        y = H - 110
        first = self.name.split()[0] if self.name else "your loved one"

        c.setFillColor(GOLD)
        c.setFont("Times-Bold", 16)
        intro = "If you are reading this, someone who loves you took the time to make sure you would never have to figure this out alone."
        for line in simpleSplit(intro, "Times-Bold", 16, W - 100):
            c.drawString(50, y, line)
            y -= 22
        y -= 16

        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 11)
        paras = [
            f"This is {first}'s Resolved Brief \u2014 the most important document your family will ever need. It covers their finances, insurance, medical wishes, and final instructions. Every section was built from their own words, organized so you can find what you need quickly.",
            "",
            "Here is what to do:",
            "",
        ]
        for para in paras:
            if para == "":
                y -= 8
                continue
            for line in simpleSplit(para, "Helvetica", 11, W - 100):
                c.drawString(50, y, line)
                y -= 17
            y -= 6

        steps = [
            ("1", "Start with the Family Emergency Card", "It covers the first 24 hours on one page. Who to call, what to access, where everything is."),
            ("2", "Work through each section as you need it", "You do not have to read it all at once. Each section stands on its own."),
            ("3", "Use the Action Guide in each section", "Every section includes step-by-step instructions, phone numbers, and what to have ready before you call."),
            ("4", "Check the Follow-Up Checklist", "Some items were flagged to address later. This list tells you what still needs attention."),
            ("5", "Look for the sealed envelope", "Passwords, PINs, and account numbers are written by hand on the Emergency Card and sealed separately."),
        ]

        for num, title, detail in steps:
            c.setFillColor(GOLD)
            c.circle(68, y - 2, 12, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(68, y - 6, num)
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(90, y, title)
            y -= 18
            c.setFillColor(MID_GRAY)
            c.setFont("Helvetica", 10.5)
            for dl in simpleSplit(detail, "Helvetica", 10.5, W - 140):
                c.drawString(90, y, dl)
                y -= 15
            y -= 12

        # Emergency Card note — navy callout box
        y -= 10
        note_text = "The Family Emergency Card is the last page of this document. Print it separately, fill in the sensitive details by hand, seal it in an envelope, and keep it with this Brief — or store it somewhere your family knows to look."
        note_lines = simpleSplit(note_text, "Helvetica", 10, W - 130)
        note_h = len(note_lines) * 14 + 16
        c.setFillColor(NAVY)
        c.rect(50, y - note_h + 10, W - 100, note_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(50, y - note_h + 10, 3, note_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(62, y, "ℹ  FAMILY EMERGENCY CARD")
        y -= 14
        c.setFillColor(white)
        c.setFont("Helvetica", 10)
        for line in note_lines:
            c.drawString(62, y, line)
            y -= 14
        y -= 10

        c.setFillColor(GOLD)
        c.setFont("Times-Bold", 14)
        c.drawString(50, y, "They took care of this so you wouldn't have to figure it out alone.")
        y -= 30
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(50, y, W - 50, y)
        y -= 20
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, y, f"Prepared for the family of {self.name}")
        c.drawString(50, y - 16, f"{self.date}")

        c.showPage()

        # ═══ PAGE 3: FINANCIAL OVERVIEW ═══
        self.build_section_page(c, "Financial Overview",
            "Where the money lives \u2014 banks, investments, and debts", 1, "financial",
            [
                ("Bank Accounts", [
                    ("Primary Bank", self._get("Q14")),
                    ("Account Types", self._get("Q15")),
                    ("Joint Account Holder", self._get("Q16")),
                ]),
                ("Investments & Retirement", [
                    ("Retirement Accounts", self._get("Q17")),
                    ("Held At", self._get("Q18")),
                    ("Brokerage Accounts", self._get("Q19")),
                ]),
                ("Debts & Documents", [
                    ("Mortgage/Rent", self._get("Q20")),
                    ("Loans", self._get("Q21")),
                    ("Credit Cards", self._get("Q22")),
                    ("Documents Location", self._get("Q23")),
                    ("Safe Deposit Box", self._get("Q24")),
                ]),
            ])
        c.showPage()

        # ═══ PAGE 4: INCOME & BILLS ═══
        self.build_section_page(c, "Income & Bills",
            "What comes in, what goes out \u2014 so nothing gets missed", 2, "income",
            [
                ("Income Sources", [
                    ("Primary Account", self._get("Q25")),
                    ("Other Accounts", self._get("Q26")),
                    ("Income Sources", self._get("Q27")),
                ]),
                ("Bills & Payments", [
                    ("Bills on Autopay", self._get("Q28")),
                    ("Manual Bills", self._get("Q29")),
                    ("Annual Payments", self._get("Q31")),
                ]),
                ("Subscriptions & Memberships", [
                    ("Active Subscriptions", self._get("Q30")),
                ]),
            ])
        c.showPage()

        # ═══ PAGE 5: INSURANCE & BENEFITS ═══
        self.build_section_page(c, "Insurance & Benefits",
            "Your safety net \u2014 what's covered and where the policies are", 3, "insurance",
            [
                ("Life Insurance", [
                    ("Provider", self._get("Q33")),
                    ("Coverage Amount", self._get("Q34")),
                    ("Beneficiary", self._get("Q35")),
                    ("Policy Type", self._get("Q32")),
                ]),
                ("Other Coverage", [
                    ("Disability Insurance", self._get("Q36")),
                    ("Long-Term Care", self._get("Q37")),
                    ("Home/Renters", self._get("Q38")),
                    ("Auto Insurance", self._get("Q39")),
                ]),
                ("Policy Locations", [
                    ("Documents Kept At", self._get("Q41")),
                    ("Agent/Broker", self._get("Q42")),
                    ("Other Policies", self._get("Q40")),
                ]),
            ])
        c.showPage()

        # ═══ PAGE 6: DIGITAL LIFE & ACCESS ═══
        self.build_section_page(c, "Digital Life & Access",
            "How your family gets into your accounts when they need to", 4, "digital",
            [
                ("Passwords & Access", [
                    ("Password Manager", self._get("Q44", self._get("Q43"))),
                    ("Master Password Location", self._get("Q45")),
                    ("Primary Email", self._get("Q46")),
                ]),
                ("Device Access", [
                    ("Phone Access", self._get("Q47")),
                    ("Computer Access", self._get("Q48")),
                    ("Financial Apps", self._get("Q49")),
                ]),
                ("Digital Assets & Storage", [
                    ("Cryptocurrency", self._get("Q50")),
                    ("Photos Stored At", self._get("Q51")),
                    ("Cloud Storage", self._get("Q52")),
                ]),
            ])
        c.showPage()

        # ═══ PAGE 7: MEDICAL & EMERGENCY ═══
        self.build_section_page(c, "Medical & Emergency",
            "Who makes decisions and what they need to know", 5, "medical",
            [
                ("Decision Makers", [
                    ("Healthcare Proxy", self._get("Q1")),
                    ("This Person Knows", self._get("Q2")),
                    ("Backup Contact", self._get("Q3")),
                ]),
                ("Medical Information", [
                    ("Conditions", self._get("Q4")),
                    ("Medications", self._get("Q5")),
                    ("Allergies", self._get("Q6")),
                    ("Primary Doctor", self._get("Q7")),
                ]),
                ("End-of-Life Preferences", [
                    ("Resuscitation Preference", self._get("Q12")),
                    ("Organ Donor", self._get("Q13")),
                    ("Health Insurance", self._get("Q9")),
                ]),
            ])
        c.showPage()

        # ═══ PAGE 8: FINAL WISHES ═══
        self.build_section_page(c, "Final Wishes",
            "These are the exact words and wishes they left for you.", 6, "wishes",
            [
                ("Arrangements", [
                    ("Burial / Cremation", self._get("Q53")),
                    ("Specific Wishes", self._get("Q54")),
                ]),
                ("Service & Celebration", [
                    ("Type of Service", self._get("Q55")),
                    ("Specific Requests", self._get("Q56")),
                    ("People to Notify", self._get("Q57")),
                ]),
                ("Personal Belongings", [
                    ("Items for Specific People", self._get("Q58")),
                    ("Donate / Sell / Destroy", self._get("Q59")),
                ]),
            ])

        msg = self._get("Q60")
        if msg:
            c.setFillColor(GOLD)
            c.setFont("Times-Bold", 12)
            c.drawString(42, 180, "Your Words")
            c.setStrokeColor(GOLD)
            c.setLineWidth(0.5)
            c.line(42, 175, W - 42, 175)
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Oblique", 11)
            lines = simpleSplit(msg, "Helvetica-Oblique", 11, W - 100)
            y = 158
            for line in lines[:8]:
                c.drawString(50, y, line)
                y -= 16

        c.showPage()

        # ═══ PAGE 9: FAMILY EMERGENCY CARD ═══
        self._page_header(c, "", is_break_glass=True)
        self._page_footer(c, "Family Emergency Card")

        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(36, H - 100, "If something happens, start here.")

        y = H - 130

        # First 24 Hours header
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y + 4, "FIRST 24 HOURS")
        y -= 30

        steps_24 = []
        steps_24.append(f"1.  Call {self._get('Q1', '(primary emergency contact)')}")
        steps_24.append("2.  Locate the Resolved Brief and the sealed envelope")
        agent = self._get("Q42", "")
        if agent:
            steps_24.append(f"3.  Call insurance agent: {agent}")
        if self._get("Q44", self._get("Q43", "")):
            steps_24.append(f"{len(steps_24)+1}.  Access password manager using sealed envelope instructions")
        income = self._get("Q27", "")
        if "employer" in income.lower():
            steps_24.append(f"{len(steps_24)+1}.  Contact employer / HR")
        elif "self" in income.lower():
            steps_24.append(f"{len(steps_24)+1}.  Notify business clients / partners")
        doctor = self._get("Q7", "")
        if doctor:
            steps_24.append(f"{len(steps_24)+1}.  Contact primary doctor: {doctor}")

        c.setFont("Helvetica", 10)
        for step in steps_24:
            c.setFillColor(DARK_NAVY)
            c.drawString(46, y, step)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(42, y - 6, W - 42, y - 6)
            y -= 20

        y -= 16

        col1_x, col2_x = 36, W/2 + 10
        col_w = W/2 - 46

        c.setFillColor(NAVY)
        c.rect(col1_x, y - 4, col_w, 24, fill=1, stroke=0)
        c.rect(col2_x, y - 4, col_w, 24, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col1_x + 10, y + 2, "Key Contacts")
        c.drawString(col2_x + 10, y + 2, "Critical Access")
        y -= 28

        contacts = [
            ("Healthcare Proxy:", self._get("Q1")),
            ("Insurance Agent:", self._get("Q42")),
            ("Primary Doctor:", self._get("Q7")),
        ]
        access = [
            ("Phone Passcode:", self._get("Q47")),
            ("Computer Password:", self._get("Q48")),
            ("Email Access:", self._get("Q46")),
            ("Password Manager:", self._get("Q44", self._get("Q43"))),
        ]

        for i, ((cl, cv), (al, av)) in enumerate(zip(contacts, access)):
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(col1_x + 8, y, cl)
            c.drawString(col2_x + 8, y, al)
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            c.drawString(col1_x + 8, y - 12, cv[:35] + "..." if len(cv) > 38 else cv)
            c.drawString(col2_x + 8, y - 12, av[:35] + "..." if len(av) > 38 else av)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(col1_x + 4, y - 18, col1_x + col_w - 4, y - 18)
            c.line(col2_x + 4, y - 18, col2_x + col_w - 4, y - 18)
            y -= 28

        for al, av in access[len(contacts):]:
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(col2_x + 8, y, al)
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            c.drawString(col2_x + 8, y - 12, av[:35] + "..." if len(av) > 38 else av)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(col2_x + 4, y - 18, col2_x + col_w - 4, y - 18)
            y -= 28

        y -= 20
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y + 4, "SENSITIVE ACCESS — FILL IN BY HAND, SEAL IN ENVELOPE")
        y -= 32

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(46, y, "Write these in by hand. Do not type or store digitally. Seal this page in an envelope.")
        y -= 18

        handwrite_fields = [
            "Phone Passcode:", "Computer Password:", "Email Password:",
            "Password Manager Master Password:", "Bank PIN:",
            "Safe / Lockbox Combination:", "Other:", "Other:",
        ]
        c.setFont("Helvetica-Bold", 9.5)
        for field in handwrite_fields:
            c.setFillColor(DARK_NAVY)
            c.drawString(46, y, field)
            c.setStrokeColor(LIGHT_GRAY)
            c.setLineWidth(0.5)
            c.setDash(2, 2)
            c.line(250, y - 2, W - 46, y - 2)
            c.setDash()
            c.line(42, y - 10, W - 42, y - 10)
            y -= 22

        y -= 8
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(W/2, max(y, 40), "Keep this card with The Resolved Brief folder. Review and update every 6 months.")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(RED_ACCENT)
        c.drawCentredString(W/2, max(y - 14, 28), "THIS PAGE CONTAINS SENSITIVE INFORMATION — STORE SECURELY")

        c.showPage()

        # ═══ PAGE 10: FOLLOW-UP CHECKLIST ═══
        self._page_header(c, "Follow-Up Checklist")
        self._page_footer(c, "Checklist")

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(36, H - 96, "Items to address \u2014 you don't have to be perfect, just keep going")
        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica", 10)
        c.drawString(36, H - 114, "These are the items flagged during your session. Check them off as you go.")

        y = H - 145

        categories = {
            "Legal Documents": [
                "Create or update your will",
                "Set up healthcare proxy / power of attorney",
                "Create or update living will / advance directive",
                "Review and update beneficiaries on all accounts",
            ],
            "Financial": [
                "Organize financial documents in one location",
                "Set up joint access or POD on key accounts",
                "Review life insurance coverage and beneficiaries",
            ],
            "Digital": [
                "Set up password manager emergency access",
                "Store master password in Master File",
                "Enable legacy contacts on Apple / Google accounts",
            ],
            "Personal": [
                "Have the conversation with your healthcare proxy",
                "Tell someone where The Resolved Brief is kept",
                "Review and update every 6 months",
                "Share The Resolved Brief with family members",
            ],
        }

        for cat, items in categories.items():
            if y < 100:
                break
            c.setFillColor(CREAM)
            c.rect(42, y - 6, W - 84, 22, fill=1, stroke=0)
            c.setStrokeColor(GOLD)
            c.setLineWidth(1)
            c.line(42, y - 6, 42, y + 16)
            c.setFillColor(NAVY)
            c.setFont("Times-Bold", 12)
            c.drawString(52, y, cat)
            y -= 26

            for item in items:
                if y < 50:
                    break
                c.setStrokeColor(MID_GRAY)
                c.setLineWidth(0.75)
                c.rect(52, y - 2, 12, 12, fill=0, stroke=1)
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica", 10)
                c.drawString(72, y, item)
                y -= 22

            y -= 8

        c.setFillColor(NAVY)
        c.setFont("Times-Bold", 12)
        c.drawCentredString(W/2, 58, "You don\u2019t have to do it all today. You already did the hard part.")

        c.showPage()
        c.save()
        print(f"Resolved Brief generated: {output_path}")


# ═══ GENERATE SAMPLE ═══
if __name__ == "__main__":
    output = "/mnt/user-data/outputs/The-Resolved-Brief-SAMPLE.pdf"
    builder = ResolvedBriefBuilder(MOCK)
    builder.build(output)
