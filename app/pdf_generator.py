"""
The Resolved Brief — PDF Generator V5.2
========================================
Generates a personalized, professional Resolved Brief from V5.2 walkthrough data.
Maps assessment answers and data fields to the exact brand design: navy/gold/cream.

v5.2: Integrates with the new hybrid assessment + data collection walkthrough.
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
ACTION_BG = HexColor("#EEF2F7")
ACTION_BORDER = HexColor("#1B2A3D")
STEP_NUM_BG = HexColor("#C9A84C")
WATCH_OUT_BG = HexColor("#FFF3CD")
WATCH_OUT_BORDER = HexColor("#E6AC00")

W, H = letter  # 612 x 792

# ═══ MOCK DATA - V5.2 FORMAT ═══
MOCK = {
    "name": "Michael Thompson",
    "date": datetime.now().strftime("%B %d, %Y"),
    "answers": {
        # Foundation & Legal (Q1-Q8)
        "Q1": 1, "Q2": 0, "Q2_executor": "Sarah Thompson", "Q2_location": "Home safe",
        "Q3": 1, "Q4": 0, "Q5": 0, "Q5_who": "Sarah Thompson — POA & executor",
        "Q6": 0, "Q7": 0, "Q7_location": "Home safe, filing cabinet",
        "Q8": 1, "Q8_attorney": "Jennifer Lee, 555-0142",

        # Key People & Decision Makers (Q10-Q18)
        "Q10": 0, "Q10_who": "Sarah Thompson (wife)", "Q10_phone": "555-0101",
        "Q11": 0, "Q12": 0, "Q12_backup": "James Thompson (brother)",
        "Q13": 0, "Q14": 0,
        "Q14_attorney": "Jennifer Lee, 555-0142",
        "Q14_cpa": "Robert Chen, Chen & Associates, 555-0143",
        "Q14_advisor": "Michael Park, Advisors USA, 555-0144",
        "Q14_insurance": "John Davis, State Farm, 312-555-0847",
        "Q15": 0, "Q16": 0, "Q17": 0,
        "Q17_authority": "Sarah Thompson has final authority on all decisions",
        "Q18": 0,

        # Children & Dependents (Q19-Q26) - skip if not applicable
        "Q19": 2, "Q20": 2, "Q21": 2, "Q22": 2, "Q23": 2, "Q24": 2, "Q25": 2, "Q26": 2,

        # Money, Assets & Obligations (Q27-Q36)
        "Q27": 0, "Q27_primary_bank": "Chase Bank", "Q27_joint": "Yes, joint with Sarah Thompson",
        "Q28": 0, "Q28_accounts": "Chase checking, Chase savings, Ally savings, Fidelity 401k, Vanguard Roth IRA, Schwab brokerage",
        "Q29": 0, "Q29_hidden": "No hidden accounts",
        "Q30": 0, "Q30_autopay": "Mortgage (Wells Fargo), Electric (ComEd), Internet (Xfinity), Car insurance (State Farm), Netflix, Spotify",
        "Q30_manual": "Water bill (quarterly), Property tax (June & September), Car registration (October)",
        "Q31": 0, "Q31_debts": "Mortgage: Wells Fargo, $250K balance | Car loan: Toyota Financial, $18K balance | Credit cards: Chase (paid monthly), Amex (paid monthly)",
        "Q32": 0, "Q32_assets": "Home in Chicago (owner), 2008 Toyota Camry, 401k at Fidelity, Roth IRA at Vanguard",
        "Q33": 2, "Q33_business": "No business interests",
        "Q34": 0, "Q35": 0, "Q36": 0,

        # Insurance & Protection (Q37-Q44)
        "Q37": 0, "Q37_provider": "MetLife (employer) & Northwestern Mutual (private)",
        "Q37_amount": "$500,000 (MetLife) + $250,000 (Northwestern Mutual)",
        "Q37_beneficiary": "Sarah Thompson",
        "Q38": 0, "Q38_policy_location": "Filing cabinet in office",
        "Q39": 0,
        "Q40": 0, "Q40_health": "Blue Cross Blue Shield (through employer)",
        "Q40_home": "State Farm homeowners",
        "Q40_auto": "State Farm auto",
        "Q41": 0, "Q42": 0,
        "Q43": 0, "Q43_agent": "John Davis, State Farm, 312-555-0847",
        "Q44": 0,

        # Digital Life & Access (Q45-Q53)
        "Q45": 1, "Q46": 0, "Q46_email": "michael.t@gmail.com",
        "Q47": 0, "Q47_manager": "1Password",
        "Q48": 1,
        "Q49": 0, "Q49_photos": "Google Photos, iCloud Photos",
        "Q50": 0, "Q50_cloud": "Google Drive, iCloud",
        "Q51": 2, "Q51_crypto": "None",
        "Q52": 0, "Q52_apps": "Venmo, Zelle, Chase Mobile, Fidelity",
        "Q53": 1,

        # Medical & Final Wishes (Q54-Q60)
        "Q54": 0, "Q54_proxy": "Sarah Thompson", "Q54_backup": "James Thompson",
        "Q55": 0, "Q55_resuscitation": "Full resuscitation (do everything)",
        "Q55_organ": "Yes, organ donor",
        "Q56": 0, "Q56_conditions": "High blood pressure, mild asthma",
        "Q56_meds": "Lisinopril 10mg daily, Albuterol inhaler as needed",
        "Q56_allergies": "Penicillin (anaphylaxis)",
        "Q56_doctor": "Dr. Emily Chen, Northwestern Medical, 555-0200",
        "Q58": 1, "Q58_service": "Celebration of life",
        "Q58_preference": "Cremation, scatter ashes at Lake Michigan",
        "Q59": 0, "Q59_requests": "Play Louis Armstrong's 'What a Wonderful World' during celebration. Keep it casual and joyful.",
        "Q60": 1, "Q60_message": "To Sarah — you made every single day better. To Jake and Emma — be kind, work hard, and never stop being curious. I'm proud of who you're becoming.",
    },
    "homework": ["Q3", "Q5", "Q19", "Q21"],
    "ai_narratives": {}
}


def generate_sample_narratives(data):
    """Generate V5.2-aware sample narratives with action guides."""
    return {
        "foundation": {
            "narrative": "You have a will and trust in place that was reviewed recently, with Sarah as your executor. Your documents are stored securely in a home safe and filing cabinet. You've formally assigned Sarah as your power of attorney, and your estate attorney Jennifer Lee is on record. This foundation is solid.",
            "action_guide": "INSTITUTION: Jennifer Lee, Attorney at Law | PHONE: 555-0142 | STEP 1: Contact Jennifer Lee and report the death | STEP 2: Provide a certified death certificate and ask about next steps for will execution | STEP 3: Ask about any trusts, directives, or documents that need to be filed | HAVE READY: Death certificate, will location, trust documents | TIMELINE: Initial consultation within 24-48 hours | WATCH OUT: Do not attempt to change titles on property or access accounts before speaking with the attorney — there may be tax implications"
        },
        "people": {
            "narrative": "Sarah Thompson is your clearly designated point person and she knows it. Your backup is your brother James. You have professional contacts documented: Jennifer Lee (attorney), Robert Chen (CPA), Michael Park (financial advisor), and John Davis (insurance agent). Sarah has final authority on all decisions, which eliminates confusion in a crisis.",
            "action_guide": "INSTITUTION: Point Person — Sarah Thompson | PHONE: 555-0101 | STEP 1: Notify Sarah immediately and share this Resolved Brief | STEP 2: Have Sarah contact Jennifer Lee (attorney) within 24 hours | STEP 3: Sarah should coordinate with Robert Chen (CPA) for tax and financial matters | HAVE READY: This Brief, death certificate, contact information | TIMELINE: Initial coordination within 24-48 hours | WATCH OUT: Sarah is the decision maker — backup James should support, not override. Clear roles prevent family conflict."
        },
        "children": {
            "narrative": "No dependent children.",
            "action_guide": ""
        },
        "money": {
            "narrative": "Your primary banking is through Chase with joint access for Sarah. All accounts are documented: Chase (checking and savings), Ally (savings), Fidelity 401(k), Vanguard Roth IRA, and Schwab brokerage. Bills are on autopay (mortgage, utilities, insurance, subscriptions) with manual quarterly and annual payments documented. Your debts are manageable: mortgage with Wells Fargo (~$250K), car loan with Toyota Financial (~$18K), and credit cards with zero balances kept open. You own a home in Chicago and a 2008 Toyota Camry.",
            "action_guide": "INSTITUTION: Chase Bank | PHONE: 1-888-356-0023 | STEP 1: Sarah should call Chase estate services and identify herself as power of attorney / executor | STEP 2: Request full account list and ask about joint access and transfer procedures | STEP 3: Ask about automatic payments and what happens if joint account changes ownership | HAVE READY: Death certificate, Sarah's ID, account numbers | TIMELINE: Joint account access typically immediate; transfers take 2-4 weeks | WATCH OUT: Do not close autopay until you've transferred bills to Sarah's name — mortgage and insurance cannot lapse\n\nINSTITUTION: Fidelity (401k) | PHONE: 1-800-343-3548 | STEP 1: Call Fidelity and report the death; ask for Beneficiary Services | STEP 2: Confirm Sarah is the named beneficiary and request claim packet | STEP 3: Return the packet with certified death certificate | HAVE READY: Death certificate, beneficiary ID, Social Security number | TIMELINE: 30-60 days | WATCH OUT: Do not take immediate distributions — consult Robert Chen (CPA) about inherited IRA rules and tax implications\n\nINSTITUTION: Wells Fargo (Mortgage) | PHONE: 1-800-869-3557 | STEP 1: Call mortgage services and report the death | STEP 2: Discuss assumption or transfer options if Sarah wants to keep the home | STEP 3: Do NOT skip payments during transition — late payments can trigger acceleration | HAVE READY: Loan number, death certificate, Sarah's information | TIMELINE: Assumption takes 4-6 weeks; consult attorney first | WATCH OUT: If the house is in a trust, the trustee (Sarah) has different steps than if it's in individual name"
        },
        "insurance": {
            "narrative": "Your life insurance totals $750,000 across MetLife (employer, $500K) and Northwestern Mutual (private, $250K), with Sarah as beneficiary. Other coverage includes Blue Cross health insurance (through employer), State Farm homeowners and auto, plus umbrella coverage. All policies are in your filing cabinet and your agent John Davis has complete documentation.",
            "action_guide": "INSTITUTION: MetLife (Employer Life Insurance) | PHONE: 1-800-638-5433 | STEP 1: Sarah should call MetLife and report the death; ask for Claims department | STEP 2: Provide employee ID and policy number | STEP 3: Complete beneficiary claim form and return with certified death certificate | HAVE READY: Death certificate, policy number, beneficiary ID | TIMELINE: Life insurance typically pays within 30-60 days | WATCH OUT: The contestability period is 2 years from policy start — if death was within that window, the insurer may investigate the application\n\nINSTITUTION: Northwestern Mutual (Private Life Insurance) | PHONE: 1-800-388-8123 | STEP 1: Sarah should call and request Claims department | STEP 2: Provide policy number (in filing cabinet) and report the death | STEP 3: Submit claim with certified death certificate | HAVE READY: Policy documents, death certificate, beneficiary ID | TIMELINE: 30-60 days | WATCH OUT: Keep premiums current until claim is paid — lapsed policies complicate claims\n\nINSTITUTION: John Davis — Insurance Agent (State Farm) | PHONE: 312-555-0847 | STEP 1: Notify John Davis of the death | STEP 2: Discuss policy continuation for home and auto (critical for lender requirements) | STEP 3: Ask about any group insurance through other accounts that might need activation | HAVE READY: Policy numbers, death certificate | TIMELINE: 1-2 weeks for policy transfers | WATCH OUT: Home and auto insurance cannot lapse — coverage gaps affect rates and create legal liability"
        },
        "digital": {
            "narrative": "Your primary email is michael.t@gmail.com. Passwords are managed through 1Password, with the master password stored in the sealed envelope. Your Google account is the key to recovering everything else (Gmail, Photos, Drive). Your computer requires additional steps to access, but your phone has biometric unlocking. Key financial apps include Venmo, Zelle, Chase Mobile, and Fidelity.",
            "action_guide": "INSTITUTION: Gmail / Google Account | PHONE: Use google.com/accounts/recovery | STEP 1: Start with the primary email account — it is the key to resetting everything else | STEP 2: Use Google's inactive account request or submit a deceased user request at support.google.com | STEP 3: Once access is confirmed, you can reset passwords for banking and other services | HAVE READY: Death certificate, your own photo ID | TIMELINE: Google's deceased user process takes 4-8 weeks | WATCH OUT: Do not delete the Google account — it contains 2-factor codes, documents, photos, and recovery emails for many services\n\nINSTITUTION: 1Password (Password Manager) | PHONE: Use 1password.com/support | STEP 1: Retrieve the master password from the sealed envelope | STEP 2: Log in to 1Password and access stored credentials | STEP 3: Use the credentials to access financial accounts, email, and other services | HAVE READY: Master password from sealed envelope | TIMELINE: Immediate once you have the master password | WATCH OUT: The Emergency Kit (account key + master password) is required — without both, the vault is unrecoverable"
        },
        "medical": {
            "narrative": "Sarah is your healthcare proxy and she knows it. Your backup is your brother James. You have high blood pressure (Lisinopril 10mg) and mild asthma (Albuterol inhaler). Critical allergy: penicillin (anaphylaxis risk). Your primary doctor is Dr. Emily Chen at Northwestern Medical. You want full resuscitation and are an organ donor. You have Blue Cross health insurance through your employer.",
            "action_guide": "INSTITUTION: Blue Cross Blue Shield (Health Insurance) | PHONE: Call the member services number on your card | STEP 1: Notify Blue Cross of the death and ask about outstanding claims | STEP 2: Request information about COBRA continuation if Sarah needs coverage | STEP 3: Cancel the policy once claims are settled | HAVE READY: Death certificate, member ID, insurance card | TIMELINE: Outstanding claims typically resolve in 60-90 days | WATCH OUT: Do not cancel health insurance until all medical bills are settled — claims arrive months after treatment\n\nINSTITUTION: Dr. Emily Chen — Primary Care (Northwestern Medical) | PHONE: 555-0200 | STEP 1: Notify the practice of the death | STEP 2: Request medical records for insurance claims or estate purposes | STEP 3: Cancel any scheduled appointments | HAVE READY: Death certificate, patient ID | TIMELINE: Records requests take up to 30 days under HIPAA | WATCH OUT: Organ donation should be reported to Dr. Chen immediately — there may be time-sensitive requirements"
        }
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
    """Builds a Resolved Brief PDF from V5.2 walkthrough data."""

    def __init__(self, data, walkthrough_def=None):
        self.data = data
        self.A = data["answers"]
        self.name = data["name"]
        self.date = data["date"]
        self.hw = data.get("homework", [])
        self.narratives = data.get("ai_narratives", {})
        self.walkthrough_def = walkthrough_def or {}

        # Generate narratives if not provided
        if not self.narratives:
            self.narratives = generate_sample_narratives(data)
        else:
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

    def _get(self, field_id, default=""):
        """Retrieve value from answers dict, handling both assessment and data field IDs."""
        val = self.A.get(field_id, default)
        if val and "," in val and field_id in ("Q28_accounts", "Q30_autopay", "Q30_manual", "Q49_photos", "Q50_cloud", "Q52_apps"):
            val = val.replace(",", ", ")
        return val or default

    def _get_assessment_option(self, q_id):
        """Get the text option for an assessment question based on selected index."""
        if q_id not in self.A:
            return ""
        idx = self.A[q_id]
        if not isinstance(idx, int):
            return str(idx)

        # Find the question in walkthrough definition
        if self.walkthrough_def:
            for section in self.walkthrough_def.get('sections', []):
                for card in section.get('cards', []):
                    for question in card.get('questions', []):
                        if question.get('id') == q_id:
                            options = question.get('options', [])
                            if 0 <= idx < len(options):
                                return options[idx]
        return ""

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
        c.drawString(36, 24, "© 2026 Resolved · ResolvedFamily.com · Confidential")
        c.drawRightString(W - 36, 24, section_label)

    def _draw_action_guide(self, c, blocks, y_start, min_y=50):
        """Draw action guide blocks onto canvas."""
        from reportlab.lib.utils import simpleSplit
        y = y_start

        # Section header
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

            # Phone — right aligned
            if phone:
                c.setFillColor(GOLD)
                c.setFont("Helvetica-Bold", 9)
                phone_label = f"CALL: {phone}"
                c.drawRightString(W - 46, y + 3, phone_label)

            y -= 26

            # Steps
            STEP_TEXT_X = 68
            STEP_TEXT_W = W - 112
            CIRCLE_X = 50
            LINE_H = 14

            for i, step in enumerate(steps, 1):
                if y < min_y:
                    break
                step_lines = simpleSplit(step, "Helvetica", 10, STEP_TEXT_W)[:3]
                block_h = len(step_lines) * LINE_H

                circle_cy = y - (block_h / 2) + LINE_H / 2
                c.setFillColor(GOLD)
                c.circle(CIRCLE_X, circle_cy, 7, fill=1, stroke=0)
                c.setFillColor(white)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(CIRCLE_X, circle_cy - 3, str(i))

                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica", 10)
                for li, sl in enumerate(step_lines):
                    c.drawString(STEP_TEXT_X, y - (li * LINE_H), sl)

                y -= block_h + 6

            y -= 4

            # Have Ready + Timeline
            if have_ready or timeline:
                LEFT_LABEL_X = 42
                LEFT_VALUE_X = 112
                LEFT_COL_END = 36 + int((W - 72) * 0.54)
                RIGHT_START = LEFT_COL_END + 6
                RIGHT_LABEL_X = RIGHT_START + 6
                RIGHT_VALUE_X = RIGHT_START + 68
                RIGHT_COL_END = W - 42

                left_value_w = LEFT_COL_END - LEFT_VALUE_X - 6
                right_value_w = RIGHT_COL_END - RIGHT_VALUE_X - 6

                row_h = 18
                c.setFillColor(LIGHT_GRAY)
                c.rect(36, y - 4, W - 72, row_h, fill=1, stroke=0)

                if have_ready:
                    c.setFillColor(DARK_NAVY)
                    c.setFont("Helvetica-Bold", 8.5)
                    c.drawString(LEFT_LABEL_X, y + 2, "HAVE READY:")
                    c.setFillColor(DARK_GRAY)
                    c.setFont("Helvetica", 8.5)
                    ready_lines = simpleSplit(have_ready, "Helvetica", 8.5, left_value_w)
                    c.drawString(LEFT_VALUE_X, y + 2, ready_lines[0] if ready_lines else "")

                if timeline:
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

            # Watch Out
            if watch_out:
                WATCH_LABEL_X = 46
                WATCH_TEXT_X = 132
                WATCH_TEXT_W = W - 72 - (WATCH_TEXT_X - 36) - 10
                LINE_H_W = 13

                watch_lines = simpleSplit(watch_out, "Helvetica", 9, WATCH_TEXT_W)[:3]
                box_h = max(20, len(watch_lines) * LINE_H_W + 10)

                c.setFillColor(WATCH_OUT_BG)
                c.rect(36, y - box_h + 14, W - 72, box_h, fill=1, stroke=0)
                c.setStrokeColor(WATCH_OUT_BORDER)
                c.setLineWidth(1)
                c.rect(36, y - box_h + 14, W - 72, box_h, fill=0, stroke=1)
                c.setLineWidth(0.5)

                c.setFillColor(WATCH_OUT_BORDER)
                c.setFont("Helvetica-Bold", 8.5)
                c.drawString(WATCH_LABEL_X, y + 2, "⚠  WATCH OUT:")

                c.setFillColor(HexColor("#5D4B00"))
                c.setFont("Helvetica", 9)
                for li, wl in enumerate(watch_lines):
                    c.drawString(WATCH_TEXT_X, y + 2 - (li * LINE_H_W), wl)

                y -= box_h + 4

            y -= 14

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

        sections_left = ["Foundation & Legal", "Key People & Decision Makers", "Money, Assets & Obligations", "Digital Life & Access"]
        sections_right = ["Insurance & Protection", "Medical & Emergency", "Final Wishes", "Family Emergency Card"]
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
        c.drawCentredString(W/2, 36, "© 2026 Resolved · ResolvedFamily.com")
        c.setFont("Helvetica", 7)
        c.drawCentredString(W/2, 24, "This document is confidential and intended only for the named individual and their designated contacts.")

    def build_section_page(self, c, title, subtitle, section_num, narrative_key, fields_by_card):
        """Build a section page: header → narrative → action guide → field cards."""
        from reportlab.lib.utils import simpleSplit

        self._page_header(c, title, section_num)
        self._page_footer(c, f"Section {section_num} of 8")

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 11)
        c.drawString(36, H - 100, subtitle)

        y = H - 125

        # Narrative and action guide
        section_data = self.narratives.get(narrative_key, {})
        if isinstance(section_data, dict):
            narrative_text = section_data.get("narrative", "")
            action_guide_text = section_data.get("action_guide", "")
        else:
            narrative_text = str(section_data)
            action_guide_text = ""

        # Narrative intro
        if narrative_text:
            narrative_lines = simpleSplit(narrative_text, "Helvetica", 10.5, W - 88)
            box_h = len(narrative_lines) * 15 + 16
            c.setFillColor(HexColor("#F0EDE5"))
            c.rect(36, y - box_h + 10, W - 72, box_h, fill=1, stroke=0)
            c.setStrokeColor(GOLD)
            c.setLineWidth(2)
            c.line(36, y - box_h + 10, 36, y + 10)
            c.setLineWidth(0.5)

            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 10.5)
            for line in narrative_lines:
                if y < 60:
                    break
                c.drawString(46, y, line)
                y -= 15
            y -= 14

        # Action Guide
        if action_guide_text:
            action_blocks = _parse_action_guide(action_guide_text)
            if action_blocks:
                y -= 6
                y = self._draw_action_guide(c, action_blocks, y, min_y=60)
                y -= 10

        # Field Cards
        for card_title, fields in fields_by_card:
            if y < 120:
                break

            # Card header
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

        # PAGE 1: COVER
        self.build_cover(c)
        c.showPage()

        # PAGE 2: INTRODUCTION
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
            f"This is {first}'s Resolved Brief — the most important document your family will ever need. It covers finances, insurance, medical wishes, and final instructions. Every section was built from their own words, organized so you can find what you need quickly.",
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
            ("5", "Look for the sealed envelope", "Passwords, PINs, and account numbers are written by hand on the Vault Page and sealed separately."),
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

        y -= 10
        note_text = "The Vault Page is included at the end of this document. Print it separately, fill in the sensitive details by hand, seal it in an envelope, and keep it with this Brief — or store it somewhere your family knows to look."
        note_lines = simpleSplit(note_text, "Helvetica", 10, W - 130)
        note_h = len(note_lines) * 14 + 16
        c.setFillColor(NAVY)
        c.rect(50, y - note_h + 10, W - 100, note_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(50, y - note_h + 10, 3, note_h, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(62, y, "ℹ  THE VAULT PAGE")
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

        # PAGE 3: FOUNDATION & LEGAL
        self.build_section_page(c, "Foundation & Legal",
            "Documents, authority, and legal foundation", 1, "foundation",
            [
                ("Will / Trust", [
                    ("Executor/Trustee", self._get("Q2_executor")),
                    ("Document Location", self._get("Q2_location")),
                ]),
                ("Power of Attorney", [
                    ("Assigned To", self._get("Q5_who")),
                ]),
                ("Documents", [
                    ("Primary Location", self._get("Q7_location")),
                    ("Estate Attorney", self._get("Q8_attorney")),
                ]),
            ])
        c.showPage()

        # PAGE 4: KEY PEOPLE & DECISION MAKERS
        self.build_section_page(c, "Key People & Decision Makers",
            "Who steps in and who to call for help", 2, "people",
            [
                ("Primary & Backup", [
                    ("Point Person", self._get("Q10_who")),
                    ("Phone", self._get("Q10_phone")),
                    ("Backup Contact", self._get("Q12_backup")),
                ]),
                ("Professional Contacts", [
                    ("Attorney", self._get("Q14_attorney")),
                    ("CPA/Accountant", self._get("Q14_cpa")),
                    ("Financial Advisor", self._get("Q14_advisor")),
                    ("Insurance Agent", self._get("Q14_insurance")),
                ]),
                ("Authority & Roles", [
                    ("Final Decision Maker", self._get("Q17_authority")),
                ]),
            ])
        c.showPage()

        # PAGE 5: MONEY, ASSETS & OBLIGATIONS
        self.build_section_page(c, "Money, Assets & Obligations",
            "Where money lives, what you owe, and what you own", 3, "money",
            [
                ("Banking", [
                    ("Primary Bank", self._get("Q27_primary_bank")),
                    ("Joint Account Holder", self._get("Q27_joint")),
                    ("All Accounts", self._get("Q28_accounts")),
                    ("Hidden Accounts", self._get("Q29_hidden")),
                ]),
                ("Bills & Payments", [
                    ("Bills on Autopay", self._get("Q30_autopay")),
                    ("Manual Payments", self._get("Q30_manual")),
                ]),
                ("Debts & Assets", [
                    ("Debts & Obligations", self._get("Q31_debts")),
                    ("Property & Assets", self._get("Q32_assets")),
                    ("Business Interests", self._get("Q33_business")),
                ]),
            ])
        c.showPage()

        # PAGE 6: INSURANCE & PROTECTION
        self.build_section_page(c, "Insurance & Protection",
            "Coverage, policies, and where to find them", 4, "insurance",
            [
                ("Life Insurance", [
                    ("Provider(s)", self._get("Q37_provider")),
                    ("Coverage Amount", self._get("Q37_amount")),
                    ("Beneficiary", self._get("Q37_beneficiary")),
                    ("Policy Location", self._get("Q38_policy_location")),
                ]),
                ("Other Insurance", [
                    ("Health Insurance", self._get("Q40_health")),
                    ("Home/Renters", self._get("Q40_home")),
                    ("Auto Insurance", self._get("Q40_auto")),
                ]),
                ("Agent & Contact", [
                    ("Insurance Agent", self._get("Q43_agent")),
                ]),
            ])
        c.showPage()

        # PAGE 7: DIGITAL LIFE & ACCESS
        self.build_section_page(c, "Digital Life & Access",
            "How your family gets into accounts when they need to", 5, "digital",
            [
                ("Passwords & Email", [
                    ("Primary Email", self._get("Q46_email")),
                    ("Password Manager", self._get("Q47_manager")),
                ]),
                ("Digital Assets", [
                    ("Photos Stored At", self._get("Q49_photos")),
                    ("Cloud Storage", self._get("Q50_cloud")),
                    ("Cryptocurrency", self._get("Q51_crypto")),
                    ("Financial Apps", self._get("Q52_apps")),
                ]),
            ])
        c.showPage()

        # PAGE 8: MEDICAL & EMERGENCY
        self.build_section_page(c, "Medical & Emergency",
            "Who decides and what they need to know", 6, "medical",
            [
                ("Healthcare Decision Maker", [
                    ("Healthcare Proxy", self._get("Q54_proxy")),
                    ("Backup Proxy", self._get("Q54_backup")),
                ]),
                ("Medical Information", [
                    ("Conditions", self._get("Q56_conditions")),
                    ("Medications", self._get("Q56_meds")),
                    ("Allergies", self._get("Q56_allergies")),
                    ("Primary Doctor", self._get("Q56_doctor")),
                ]),
                ("End-of-Life Preferences", [
                    ("Resuscitation", self._get("Q55_resuscitation")),
                    ("Organ Donor", self._get("Q55_organ")),
                ]),
            ])
        c.showPage()

        # PAGE 9: FINAL WISHES — no narrative/action guide, verbatim data only
        self._page_header(c, "Final Wishes", section_num=7)
        self._page_footer(c, "Section 7 of 8")

        y = H - 96
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(36, y, "These are the exact words and wishes they left for you.")
        y -= 28

        # Arrangements card
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 24, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Times-Bold", 13)
        c.drawString(46, y + 2, "Arrangements")
        y -= 30

        wish_fields = [
            ("Burial / Cremation:", self._get("Q58_preference")),
            ("Service Type:", self._get("Q58_service")),
        ]
        for label, val in wish_fields:
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(46, y, label)
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 10.5)
            c.drawString(200, y, val if val else ". . . . . . . . . . . . . . . .")
            y -= 20
        y -= 8

        # Specific Requests card
        c.setFillColor(GOLD)
        c.rect(36, y - 4, W - 72, 24, fill=1, stroke=0)
        c.setFillColor(DARK_NAVY)
        c.setFont("Times-Bold", 13)
        c.drawString(46, y + 2, "Specific Requests")
        y -= 30

        requests = self._get("Q59_requests")
        if requests:
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 10.5)
            for line in simpleSplit(requests, "Helvetica", 10.5, W - 100)[:6]:
                c.drawString(46, y, line)
                y -= 16
        else:
            c.setFillColor(FIELD_DOT)
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(46, y, "No specific requests documented")
            y -= 16
        y -= 16

        # Your Words — the emotional centerpiece
        msg = self._get("Q60_message")
        if msg:
            c.setFillColor(GOLD)
            c.setFont("Times-Bold", 14)
            c.drawString(36, y, "Your Words")
            c.setStrokeColor(GOLD)
            c.setLineWidth(1)
            c.line(36, y - 6, W - 36, y - 6)
            y -= 24

            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Oblique", 11.5)
            for line in simpleSplit(msg, "Helvetica-Oblique", 11.5, W - 100)[:12]:
                c.drawString(50, y, line)
                y -= 18

        c.showPage()

        # PAGE 10: FAMILY EMERGENCY CARD
        self._page_header(c, "", is_break_glass=True)
        self._page_footer(c, "Family Emergency Card")

        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(36, H - 100, "If something happens, start here.")

        y = H - 130

        # First 24 Hours
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y + 4, "FIRST 24 HOURS")
        y -= 30

        steps_24 = []
        point_person = self._get("Q10_who", "the designated point person")
        point_phone = self._get("Q10_phone", "")
        steps_24.append(f"1.  Call {point_person} {f'at {point_phone}' if point_phone else ''}")
        steps_24.append("2.  Locate The Resolved Brief and the sealed envelope with passwords")
        agent = self._get("Q43_agent", "")
        if agent:
            steps_24.append(f"3.  Call insurance agent: {agent}")
        pm = self._get("Q47_manager", "")
        if pm:
            steps_24.append(f"{len(steps_24)+1}.  Access password manager ({pm}) using sealed envelope instructions")
        proxy = self._get("Q54_proxy", "")
        if proxy:
            steps_24.append(f"{len(steps_24)+1}.  Notify healthcare proxy: {proxy}")
        doctor = self._get("Q56_doctor", "")
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
            ("Healthcare Proxy:", self._get("Q54_proxy")),
            ("Insurance Agent:", self._get("Q43_agent")),
            ("Primary Doctor:", self._get("Q56_doctor")),
        ]
        access = [
            ("Primary Email:", self._get("Q46_email")),
            ("Password Manager:", self._get("Q47_manager")),
        ]

        max_len = max(len(contacts), len(access))
        for i in range(max_len):
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 9)
            if i < len(contacts):
                cl, cv = contacts[i]
                c.drawString(col1_x + 8, y, cl)
                c.setFillColor(DARK_GRAY)
                c.setFont("Helvetica", 9)
                c.drawString(col1_x + 8, y - 12, cv[:35] + "..." if len(cv) > 38 else cv)
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica-Bold", 9)
            if i < len(access):
                al, av = access[i]
                c.drawString(col2_x + 8, y, al)
                c.setFillColor(DARK_GRAY)
                c.setFont("Helvetica", 9)
                c.drawString(col2_x + 8, y - 12, av[:35] + "..." if len(av) > 38 else av)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(col1_x + 4, y - 18, col1_x + col_w - 4, y - 18)
            c.line(col2_x + 4, y - 18, col2_x + col_w - 4, y - 18)
            y -= 28

        y -= 20

        # VAULT PAGE SECTION
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y + 4, "THE VAULT PAGE — FILL IN BY HAND, SEAL IN ENVELOPE")
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
        c.drawCentredString(W/2, max(y, 40), "Keep The Vault Page with The Resolved Brief folder. Review and update every 6 months.")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(RED_ACCENT)
        c.drawCentredString(W/2, max(y - 14, 28), "THIS PAGE CONTAINS SENSITIVE INFORMATION — STORE SECURELY")

        c.showPage()

        # PAGE 11: WALLET EMERGENCY CARD
        # Two wallet-sized cards (3.5" x 2") on one page — cut along dotted lines
        c.setFillColor(CREAM)
        c.rect(0, 0, W, H, fill=1, stroke=0)

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(W/2, H - 40, "Cut along the dotted lines. Keep one in your wallet, give one to your emergency contact.")

        # Draw two identical wallet cards
        card_w = 3.5 * inch
        card_h = 2.25 * inch
        cards_x = (W - card_w) / 2

        for card_idx, card_top_y in enumerate([H - 70, H - 70 - card_h - 40]):
            # Dotted cut border
            c.setStrokeColor(LIGHT_GRAY)
            c.setLineWidth(0.5)
            c.setDash(3, 3)
            c.rect(cards_x, card_top_y - card_h, card_w, card_h, fill=0, stroke=1)
            c.setDash()

            # Card background
            c.setFillColor(WARM_WHITE)
            c.rect(cards_x + 1, card_top_y - card_h + 1, card_w - 2, card_h - 2, fill=1, stroke=0)

            # Navy header strip
            c.setFillColor(NAVY)
            c.rect(cards_x + 1, card_top_y - 22, card_w - 2, 21, fill=1, stroke=0)
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(W/2, card_top_y - 16, f"THE RESOLVED BRIEF  —  {self.name.upper()}")

            y = card_top_y - 36
            lx = cards_x + 12  # left margin inside card
            rx = cards_x + card_w - 12  # right margin

            # THE MOST IMPORTANT LINE — where the Brief is kept
            c.setFillColor(NAVY)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(lx, y, "THE RESOLVED BRIEF IS LOCATED AT:")
            y -= 11
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 7)
            doc_loc = self._get("Q7_location", "")
            c.drawString(lx, y, doc_loc if doc_loc else "______________________________________")
            y -= 13

            c.setFillColor(NAVY)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(lx, y, "SEALED ENVELOPE (PASSWORDS) IS AT:")
            y -= 11
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 7)
            c.drawString(lx, y, "______________________________________")
            y -= 14

            # Gold divider
            c.setStrokeColor(GOLD)
            c.setLineWidth(0.5)
            c.line(lx, y + 4, rx, y + 4)
            y -= 6

            # Two-column layout for remaining info
            mid = cards_x + card_w / 2

            # Left column
            fields_left = [
                ("Emergency Contact:", self._get("Q10_who", "")),
                ("Phone:", self._get("Q10_phone", "")),
                ("Healthcare Proxy:", self._get("Q54_proxy", "")),
                ("Organ Donor:", self._get("Q55_organ", "")),
            ]

            # Right column
            fields_right = [
                ("Attorney:", self._get("Q8_attorney", "")),
                ("Doctor:", self._get("Q56_doctor", "")),
                ("Allergies:", self._get("Q56_allergies", "None")),
                ("Medications:", self._get("Q56_meds", "None")),
            ]

            col_y = y
            for label, val in fields_left:
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica-Bold", 6)
                c.drawString(lx, col_y, label)
                c.setFillColor(DARK_GRAY)
                c.setFont("Helvetica", 6)
                # Truncate to fit
                display = val[:28] if val else "_______________"
                c.drawString(lx + 2, col_y - 8, display)
                col_y -= 18

            col_y = y
            for label, val in fields_right:
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica-Bold", 6)
                c.drawString(mid + 4, col_y, label)
                c.setFillColor(DARK_GRAY)
                c.setFont("Helvetica", 6)
                display = val[:28] if val else "_______________"
                c.drawString(mid + 6, col_y - 8, display)
                col_y -= 18

        # Instructions below both cards
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 9)
        inst_y = card_top_y - card_h - 30
        c.drawCentredString(W/2, inst_y, "Fill in the Sealed Envelope location by hand after printing.")
        c.drawCentredString(W/2, inst_y - 14, "The most important thing on this card is WHERE THE BRIEF IS KEPT.")

        c.showPage()

        # PAGE 12: FOLLOW-UP CHECKLIST
        self._page_header(c, "Follow-Up Checklist")
        self._page_footer(c, "Checklist")

        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(36, H - 96, "Items to address — you don't have to be perfect, just keep going")
        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica", 10)
        c.drawString(36, H - 114, "These are the items flagged during your session. Check them off as you go.")

        y = H - 145

        # Dynamic checklist based on answers
        categories = {
            "Legal Documents": [
                ("Create or update your will", ["Q2"]),
                ("Set up power of attorney", ["Q5"]),
                ("Create or update healthcare directive", ["Q55"]),
                ("Review beneficiaries on all accounts", ["Q35"]),
            ],
            "Financial": [
                ("Organize financial documents in one location", ["Q7"]),
                ("Set up joint access or POD on key accounts", ["Q27"]),
                ("Review and document all accounts", ["Q28"]),
            ],
            "Digital": [
                ("Set up password manager with emergency access", ["Q47"]),
                ("Store master password in sealed location", ["Q47"]),
                ("Enable legacy contacts on email/cloud accounts", ["Q46"]),
            ],
            "Medical & Insurance": [
                ("Have conversation with healthcare proxy", ["Q54"]),
                ("Review life insurance coverage and beneficiaries", ["Q37"]),
                ("Document medical conditions and allergies", ["Q56"]),
            ],
            "Personal": [
                ("Tell someone where this Brief is stored", ["Q10"]),
                ("Share Brief with key family members", ["Q10"]),
                ("Review and update every 6 months", []),
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

            for item, related_qs in items:
                if y < 50:
                    break
                # Check if this item should be flagged (score 0 or 1 on related questions)
                should_show = True
                if related_qs:
                    for qid in related_qs:
                        if qid in self.A and isinstance(self.A[qid], int):
                            if self.A[qid] >= 2:
                                should_show = False

                if should_show or not related_qs:
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
        c.drawCentredString(W/2, 58, "You don't have to do it all today. You already did the hard part.")

        c.showPage()
        c.save()
        print(f"Resolved Brief generated: {output_path}")


def generate_brief(data, output_path, walkthrough_def=None):
    """Convenience function to generate a brief from data."""
    builder = ResolvedBriefBuilder(data, walkthrough_def)
    builder.build(output_path)


if __name__ == "__main__":
    output = "/sessions/determined-upbeat-edison/mnt/Resolved/The-Resolved-Brief-SAMPLE.pdf"
    builder = ResolvedBriefBuilder(MOCK)
    builder.build(output)
