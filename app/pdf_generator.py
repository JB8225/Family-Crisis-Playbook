"""
The Resolved Brief — PDF Generator
===================================
Generates a personalized, professional Resolved Brief from walkthrough answers.
Matches the exact brand design: navy/gold/cream, R badge, section headers.
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

W, H = letter  # 612 x 792

# ═══ MOCK DATA (will be replaced by real session data) ═══
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
    "ai_narratives": {}  # Will be filled by Claude API
}

# ═══ AI NARRATIVE PROMPTS (for future Claude API integration) ═══
# For now, generate sample narratives based on mock data
def generate_sample_narratives(data):
    A = data["answers"]
    return {
        "financial": f"Michael's primary banking is consolidated through Chase, with a joint checking account shared with Sarah and a separate savings account at Ally. Retirement planning is well-structured across a Fidelity 401(k) and Vanguard Roth IRA, with additional investments at Schwab. The main debt obligations include a Wells Fargo mortgage and a Toyota Financial car loan. Financial documents are split between a filing cabinet and cloud storage - consolidating these into one system would strengthen the family's ability to locate everything quickly.",

        "income": f"Income flows primarily through Chase checking via employer paycheck. Most recurring bills are on autopay, which is ideal - but the family should know that if something happens, these autopay cards must stay active or bills will start bouncing. The water bill is paid manually on a quarterly basis. Key annual payments to watch for: property tax in June and September, and car registration in October. These are easy to miss if no one knows to look for them.",

        "insurance": f"Michael's insurance coverage is stronger than most families we see. Life insurance totals $750,000 across both an employer plan through MetLife and a private policy with Northwestern Mutual, with Sarah as beneficiary on both. Disability coverage exists through the employer. The gap here is long-term care insurance - worth discussing with the State Farm agent. All policies are filed in the filing cabinet, and agent John Davis at State Farm handles the home, auto, and umbrella coverage.",

        "digital": f"Password management is handled through 1Password, with the master password stored in the sealed envelope - good setup. Michael's primary email is a Gmail account, and family members already know the phone passcode. The main vulnerability is computer access - only Michael can currently get in. This needs to go in the Master File. Financial apps include Venmo and Zelle. Photos are backed up across iCloud and Google Photos, with documents in Google Drive and iCloud.",

        "medical": f"Sarah Thompson is designated as the medical decision maker, and she knows she's been chosen. James Thompson (brother) serves as backup. Michael manages high blood pressure and mild asthma with Lisinopril and Albuterol. There is a penicillin allergy the hospital must know about. Dr. Emily Chen at Northwestern Medical is the primary care physician, with Dr. Raj Patel handling cardiology. Health insurance is Blue Cross Blue Shield through the employer. The critical gap: no living will or advance directive exists. Michael's resuscitation preference is full resuscitation, and he is an organ donor.",

        "wishes": ""
    }


class ResolvedBriefBuilder:
    """Builds a Resolved Brief PDF matching the brand design templates."""
    
    def __init__(self, data):
        self.data = data
        self.A = data["answers"]
        self.name = data["name"]
        self.date = data["date"]
        self.hw = data.get("homework", [])
        self.narratives = data.get("ai_narratives", {})
        if not self.narratives:
            self.narratives = generate_sample_narratives(data)
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
            "cover_the": ParagraphStyle("cover_the", fontName="Helvetica", fontSize=12, leading=16, textColor=MID_GRAY, alignment=TA_CENTER, spaceBefore=4),
            "cover_sub": ParagraphStyle("cover_sub", fontName="Helvetica", fontSize=13, leading=18, textColor=MID_GRAY, alignment=TA_CENTER),
            "cover_name": ParagraphStyle("cover_name", fontName="Helvetica-Bold", fontSize=16, leading=22, textColor=NAVY, alignment=TA_CENTER),
            "cover_section": ParagraphStyle("cover_section", fontName="Helvetica", fontSize=11, leading=20, textColor=NAVY),
            "checklist_item": ParagraphStyle("cl_item", fontName="Helvetica", fontSize=10.5, leading=18, textColor=DARK_NAVY, leftIndent=8),
            "checklist_cat": ParagraphStyle("cl_cat", fontName="Times-Bold", fontSize=13, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=4, borderPadding=0),
            "break_title": ParagraphStyle("break_title", fontName="Times-Bold", fontSize=36, leading=42, textColor=GOLD, alignment=TA_CENTER),
            "break_sub": ParagraphStyle("break_sub", fontName="Helvetica", fontSize=12, leading=16, textColor=WARM_WHITE, alignment=TA_CENTER),
            "break_field_label": ParagraphStyle("bf_label", fontName="Helvetica-Bold", fontSize=9.5, leading=14, textColor=DARK_NAVY),
            "break_field_value": ParagraphStyle("bf_value", fontName="Helvetica", fontSize=10, leading=14, textColor=DARK_GRAY),
            "wish_message": ParagraphStyle("wish_msg", fontName="Helvetica-Oblique", fontSize=11.5, leading=18, textColor=DARK_NAVY, leftIndent=12, rightIndent=12, spaceBefore=8, spaceAfter=8),
        }
    
    def _get(self, qid, default=""):
        val = self.A.get(qid, default)
        if val and "," in val and qid in ("Q15","Q17","Q23","Q27","Q44","Q49","Q51","Q52"):
            val = val.replace(",", ", ")
        return val or default
    
    def _page_header(self, c, title, section_num=None, is_break_glass=False):
        """Draw the navy header bar with R badge and title."""
        # Navy header bar
        c.setFillColor(NAVY)
        c.rect(0, H - 72, W, 72, fill=1, stroke=0)
        
        # Gold line under header
        c.setFillColor(GOLD)
        c.rect(0, H - 74, W, 2, fill=1, stroke=0)
        
        if is_break_glass:
            # Break glass has centered gold title
            c.setFillColor(GOLD)
            c.setFont("Times-Bold", 32)
            c.drawCentredString(W/2, H - 48, "FAMILY EMERGENCY CARD")
            c.setFillColor(WARM_WHITE)
            c.setFont("Helvetica", 11)
            c.drawCentredString(W/2, H - 64, "Your family's quick-reference in a crisis")
        else:
            # R badge circle
            cx, cy = 52, H - 36
            c.setFillColor(GOLD)
            c.circle(cx, cy, 18, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Times-Bold", 16)
            c.drawCentredString(cx, cy - 6, "R")
            
            # Title
            c.setFillColor(white)
            c.setFont("Times-Bold", 22)
            c.drawString(80, H - 48, title)
            
            # CONFIDENTIAL
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(W - 36, H - 42, "CONFIDENTIAL")
        
        # Cream background for body
        c.setFillColor(CREAM)
        c.rect(0, 0, W, H - 74, fill=1, stroke=0)
    
    def _page_footer(self, c, section_label):
        """Draw footer with copyright and section number."""
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawString(36, 24, "\u00A9 2026 Resolved \u00B7 ResolvedFamily.com \u00B7 Confidential")
        c.drawRightString(W - 36, 24, section_label)
    
    def _sub_header(self, title):
        """Navy sub-section header with gold left border."""
        data = [[title]]
        t = Table(data, colWidths=[W - 72])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), NAVY),
            ("TEXTCOLOR", (0,0), (-1,-1), white),
            ("FONTNAME", (0,0), (-1,-1), "Times-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 14),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LEFTPADDING", (0,0), (-1,-1), 14),
            ("LINEBELOW", (0,0), (-1,-1), 2, GOLD),
        ]))
        return t
    
    def _field_row(self, label, value):
        """A labeled field with dotted line if empty."""
        items = []
        items.append(Paragraph(f"<b>{label}:</b>", self.s["field_label"]))
        if value and str(value).strip():
            items.append(Paragraph(str(value), self.s["field_value"]))
        else:
            items.append(Paragraph("........................................................................................................", self.s["field_empty"]))
        return items
    
    def _field_table(self, fields):
        """Build a table of label: value fields with alternating background."""
        data = []
        for label, value in fields:
            v = str(value) if value and str(value).strip() else "................................................."
            data.append([f"  {label}:", v])
        
        if not data:
            return Spacer(1, 1)
        
        t = Table(data, colWidths=[2.2*inch, 4.8*inch - 72])
        styles = [
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("TEXTCOLOR", (0,0), (0,-1), DARK_NAVY),
            ("TEXTCOLOR", (1,0), (1,-1), DARK_GRAY),
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LINEBELOW", (0,0), (-1,-1), 0.5, LIGHT_GRAY),
        ]
        # Alternating row backgrounds
        for i in range(len(data)):
            if i % 2 == 1:
                styles.append(("BACKGROUND", (0,i), (-1,i), HexColor("#F0EDE5")))
        
        t.setStyle(TableStyle(styles))
        return t
    
    def build_cover(self, c):
        """Page 1: Cover page."""
        # Navy top half
        c.setFillColor(NAVY)
        c.rect(0, H * 0.45, W, H * 0.55, fill=1, stroke=0)
        
        # Gold line
        c.setFillColor(GOLD)
        c.rect(0, H * 0.45 - 2, W, 4, fill=1, stroke=0)
        
        # Cream bottom half
        c.setFillColor(CREAM)
        c.rect(0, 0, W, H * 0.45 - 2, fill=1, stroke=0)
        
        # R badge
        cx, cy = W/2, H * 0.78
        c.setFillColor(GOLD)
        c.circle(cx, cy, 36, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Times-Bold", 32)
        c.drawCentredString(cx, cy - 11, "R")
        
        # THE
        c.setFillColor(WARM_WHITE)
        c.setFont("Helvetica", 12)
        c.drawCentredString(W/2, H * 0.70, "THE")
        
        # RESOLVED BRIEF
        c.setFont("Times-Bold", 44)
        c.drawCentredString(W/2, H * 0.63, "RESOLVED")
        c.drawCentredString(W/2, H * 0.56, "BRIEF")
        
        # Gold rule
        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(W/2 - 60, H * 0.535, W/2 + 60, H * 0.535)
        
        # Subtitle
        c.setFillColor(HexColor("#A0A0A0"))
        c.setFont("Helvetica", 13)
        c.drawCentredString(W/2, H * 0.50, "Everything your family needs to know. All in one place.")
        
        # PREPARED FOR
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(W/2, H * 0.36, "PREPARED FOR")
        
        # Gold line under PREPARED FOR
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(W/2 - 100, H * 0.345, W/2 + 100, H * 0.345)
        
        # Name
        c.setFont("Helvetica", 14)
        c.setFillColor(DARK_NAVY)
        c.drawCentredString(W/2, H * 0.32, self.name)
        
        # Date
        c.setFont("Helvetica", 10)
        c.setFillColor(MID_GRAY)
        c.drawCentredString(W/2, H * 0.295, self.date)
        
        # Section list (two columns)
        sections_left = ["Financial Overview", "Insurance & Benefits", "Medical & Emergency", "Family Emergency Card"]
        sections_right = ["Income & Bills", "Digital Life & Access", "Final Wishes", "Follow-Up Checklist"]
        
        y_start = H * 0.22
        c.setFont("Helvetica", 11)
        for i, (left, right) in enumerate(zip(sections_left, sections_right)):
            y = y_start - (i * 24)
            # Gold bullets
            c.setFillColor(GOLD)
            c.circle(80, y + 4, 4, fill=1, stroke=0)
            c.circle(W/2 + 20, y + 4, 4, fill=1, stroke=0)
            # Text
            c.setFillColor(NAVY)
            c.drawString(92, y, left)
            c.drawString(W/2 + 32, y, right)
        
        # Footer
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(W/2, 36, "\u00A9 2026 Resolved \u00B7 ResolvedFamily.com")
        c.setFont("Helvetica", 7)
        c.drawCentredString(W/2, 24, "This document is confidential and intended only for the named individual and their designated contacts.")
    
    def build_section_page(self, c, title, subtitle, section_num, narrative_key, fields_by_card):
        """Build a standard section page with header, narrative, and field cards."""
        self._page_header(c, title, section_num)
        self._page_footer(c, f"Section {section_num} of 7")
        
        # Subtitle
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica", 11)
        c.drawString(36, H - 100, subtitle)
        
        # We need to use platypus for the body content, but we're drawing on canvas
        # So we'll calculate positions manually
        y = H - 125
        
        # AI Narrative
        if narrative_key in self.narratives and self.narratives[narrative_key]:
            narrative = self.narratives[narrative_key]
            # Wrap narrative text
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 10)
            
            from reportlab.lib.utils import simpleSplit
            lines = simpleSplit(narrative, "Helvetica", 10, W - 80)
            for line in lines:
                if y < 60:
                    break
                c.drawString(40, y, line)
                y -= 15
            y -= 10
        
        # Field cards
        for card_title, fields in fields_by_card:
            if y < 120:
                break
            
            # Card header (navy bar)
            c.setFillColor(NAVY)
            c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
            # Gold left accent
            c.setFillColor(GOLD)
            c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
            # Title text
            c.setFillColor(white)
            c.setFont("Times-Bold", 13)
            c.drawString(50, y + 4, card_title)
            y -= 32
            
            # Fields
            for label, value in fields:
                if y < 50:
                    break
                # Alternating background
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica-Bold", 9.5)
                c.drawString(46, y, f"{label}:")
                
                val = str(value) if value and str(value).strip() else ""
                if val:
                    c.setFillColor(DARK_GRAY)
                    c.setFont("Helvetica", 10)
                    # Handle long values with wrapping
                    from reportlab.lib.utils import simpleSplit
                    max_val_width = W - 220
                    val_lines = simpleSplit(val, "Helvetica", 10, max_val_width)
                    for vl in val_lines[:3]:
                        c.drawString(200, y, vl)
                        y -= 14
                else:
                    # Dotted line for empty
                    c.setFillColor(FIELD_DOT)
                    c.setFont("Helvetica", 9)
                    c.drawString(200, y, ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .")
                    y -= 14
                
                # Separator line
                c.setStrokeColor(LIGHT_GRAY)
                c.setLineWidth(0.5)
                c.line(42, y + 6, W - 42, y + 6)
                y -= 6
            
            y -= 12  # Space between cards
    
    def build(self, output_path):
        """Build the complete Resolved Brief PDF."""
        c = canvas.Canvas(output_path, pagesize=letter)
        
        # ═══ PAGE 1: COVER ═══
        self.build_cover(c)
        c.showPage()
        
        # ═══ PAGE 2: INTRODUCTION LETTER ═══
        self._page_header(c, "Before You Begin")
        self._page_footer(c, "Introduction")
        
        y = H - 110
        
        # Opening line
        c.setFillColor(GOLD)
        c.setFont("Times-Bold", 16)
        from reportlab.lib.utils import simpleSplit
        
        intro_opening = f"If you are reading this, someone who loves you took the time to make sure you would never have to figure this out alone."
        lines = simpleSplit(intro_opening, "Times-Bold", 16, W - 100)
        for line in lines:
            c.drawString(50, y, line)
            y -= 22
        
        y -= 16
        
        # Main body paragraphs
        c.setFillColor(DARK_GRAY)
        c.setFont("Helvetica", 11)
        
        paragraphs = [
            f"This is {self.name.split()[0] if self.name else 'your loved one'}'s Resolved Brief \u2014 a complete guide to everything you need to know about their finances, insurance, medical wishes, and final instructions. Every section was built from their own words, organized so you can find what you need quickly.",
            "",
            "Here is what to do:",
            "",
        ]
        
        for para in paragraphs:
            if para == "":
                y -= 8
                continue
            lines = simpleSplit(para, "Helvetica", 11, W - 100)
            for line in lines:
                c.drawString(50, y, line)
                y -= 17
            y -= 6
        
        # Steps with gold numbers
        steps = [
            ("1", "Start with the Family Emergency Card", "It covers the first 24 hours on one page. Who to call, what to access, where everything is."),
            ("2", "Work through each section as you need it", "You do not have to read it all at once. Each section stands on its own."),
            ("3", "Check the Follow-Up Checklist", "Some items were flagged to address later. This list tells you what still needs attention."),
            ("4", "Look for the sealed envelope", "The sensitive information \u2014 passwords, PINs, account numbers \u2014 is written by hand on the Family Emergency Card. It should be sealed separately."),
        ]
        
        for num, title, detail in steps:
            # Gold number circle
            c.setFillColor(GOLD)
            c.circle(68, y - 2, 12, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 11)
            c.drawCentredString(68, y - 6, num)
            
            # Step title
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(90, y, title)
            y -= 18
            
            # Step detail
            c.setFillColor(MID_GRAY)
            c.setFont("Helvetica", 10.5)
            detail_lines = simpleSplit(detail, "Helvetica", 10.5, W - 140)
            for dl in detail_lines:
                c.drawString(90, y, dl)
                y -= 15
            y -= 12
        
        # Closing line
        y -= 10
        c.setFillColor(GOLD)
        c.setFont("Times-Bold", 14)
        closing = "You have got this. They made sure of it."
        c.drawString(50, y, closing)
        
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
        
        # ═══ PAGE 3: INCOME & BILLS ═══
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
        
        # ═══ PAGE 4: INSURANCE & BENEFITS ═══
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
        
        # ═══ PAGE 5: DIGITAL LIFE & ACCESS ═══
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
        
        # ═══ PAGE 6: MEDICAL & EMERGENCY ═══
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
        
        # ═══ PAGE 7: FINAL WISHES ═══
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
        
        # Personal message - draw below if space allows
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
            from reportlab.lib.utils import simpleSplit
            lines = simpleSplit(msg, "Helvetica-Oblique", 11, W - 100)
            y = 158
            for line in lines[:8]:
                c.drawString(50, y, line)
                y -= 16
        
        c.showPage()
        
        # ═══ PAGE 8: FAMILY EMERGENCY CARD ═══
        self._page_header(c, "", is_break_glass=True)
        self._page_footer(c, "Family Emergency Card")
        
        # "If something happens, start here."
        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(36, H - 100, "If something happens, start here.")
        
        y = H - 130
        
        # FIRST 24 HOURS box
        c.setFillColor(NAVY)
        c.rect(36, y - 4, W - 72, 28, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(36, y - 6, 3, 32, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, y + 4, "FIRST 24 HOURS")
        y -= 30
        
        steps = [
            f"1.  Call {self._get('Q1', '(primary emergency contact)')}",
            "2.  Locate the Resolved Brief folder",
            f"3.  Call insurance agent: {self._get('Q42', '')}",
            "4.  Access password manager using Master File instructions",
            "5.  Contact employer / HR",
        ]
        c.setFont("Helvetica", 10)
        for step in steps:
            c.setFillColor(DARK_NAVY)
            c.drawString(46, y, step)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(42, y - 6, W - 42, y - 6)
            y -= 20
        
        y -= 16
        
        # Two-column: Key Contacts + Critical Access
        col1_x, col2_x = 36, W/2 + 10
        col_w = W/2 - 46
        
        # Key Contacts header
        c.setFillColor(NAVY)
        c.rect(col1_x, y - 4, col_w, 24, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col1_x + 10, y + 2, "Key Contacts")
        
        # Critical Access header
        c.rect(col2_x, y - 4, col_w, 24, fill=1, stroke=0)
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
        
        c.setFont("Helvetica-Bold", 9)
        for i, ((cl, cv), (al, av)) in enumerate(zip(contacts, access)):
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(col1_x + 8, y, cl)
            c.drawString(col2_x + 8, y, al)
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            # Truncate long values
            cv_short = cv[:35] + "..." if len(cv) > 38 else cv
            av_short = av[:35] + "..." if len(av) > 38 else av
            c.drawString(col1_x + 8, y - 12, cv_short)
            c.drawString(col2_x + 8, y - 12, av_short)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(col1_x + 4, y - 18, col1_x + col_w - 4, y - 18)
            c.line(col2_x + 4, y - 18, col2_x + col_w - 4, y - 18)
            y -= 28
        
        # Remaining access items
        for al, av in access[len(contacts):]:
            c.setFillColor(DARK_NAVY)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(col2_x + 8, y, al)
            c.setFillColor(DARK_GRAY)
            c.setFont("Helvetica", 9)
            av_short = av[:35] + "..." if len(av) > 38 else av
            c.drawString(col2_x + 8, y - 12, av_short)
            c.setStrokeColor(LIGHT_GRAY)
            c.line(col2_x + 4, y - 18, col2_x + col_w - 4, y - 18)
            y -= 28
        
        # SENSITIVE ACCESS - FILL IN BY HAND
        y = y - 20
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
            "Phone Passcode:",
            "Computer Password:",
            "Email Password:",
            "Password Manager Master Password:",
            "Bank PIN:",
            "Safe / Lockbox Combination:",
            "Other:",
            "Other:",
        ]
        
        c.setFont("Helvetica-Bold", 9.5)
        for field in handwrite_fields:
            c.setFillColor(DARK_NAVY)
            c.drawString(46, y, field)
            # Dotted line for handwriting
            c.setStrokeColor(LIGHT_GRAY)
            c.setLineWidth(0.5)
            c.setDash(2, 2)
            c.line(250, y - 2, W - 46, y - 2)
            c.setDash()
            c.setStrokeColor(LIGHT_GRAY)
            c.line(42, y - 10, W - 42, y - 10)
            y -= 22

        # Footer note
        y -= 8
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(W/2, max(y, 40), "Keep this card with The Resolved Brief folder. Review and update every 6 months.")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(RED_ACCENT)
        c.drawCentredString(W/2, max(y - 14, 28), "THIS PAGE CONTAINS SENSITIVE INFORMATION — STORE SECURELY")
        
        c.showPage()
        
        # ═══ PAGE 9: FOLLOW-UP CHECKLIST ═══
        self._page_header(c, "Follow-Up Checklist")
        self._page_footer(c, "Checklist")
        
        c.setFillColor(MID_GRAY)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(36, H - 96, "Items to address \u2014 you don't have to be perfect, just keep going")
        
        c.setFillColor(DARK_NAVY)
        c.setFont("Helvetica", 10)
        c.drawString(36, H - 114, "These are the items you flagged during your session. Check them off as you go.")
        
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
            # Category header
            c.setFillColor(CREAM)
            c.rect(42, y - 6, W - 84, 22, fill=1, stroke=0)
            c.setStrokeColor(GOLD)
            c.setLineWidth(1)
            c.line(42, y - 6, 42, y + 16)  # Gold left border
            c.setFillColor(NAVY)
            c.setFont("Times-Bold", 12)
            c.drawString(52, y, cat)
            y -= 26
            
            for item in items:
                if y < 50:
                    break
                # Checkbox
                c.setStrokeColor(MID_GRAY)
                c.setLineWidth(0.75)
                c.rect(52, y - 2, 12, 12, fill=0, stroke=1)
                # Item text
                c.setFillColor(DARK_NAVY)
                c.setFont("Helvetica", 10)
                c.drawString(72, y, item)
                y -= 22
            
            y -= 8
        
        # Bottom encouragement
        c.setFillColor(NAVY)
        c.setFont("Times-Bold", 12)
        c.drawCentredString(W/2, 58, "You don't have to do it all today. You already did the hard part.")
        
        c.showPage()
        c.save()
        print(f"Resolved Brief generated: {output_path}")


# ═══ GENERATE SAMPLE ═══
if __name__ == "__main__":
    output = "/mnt/user-data/outputs/The-Resolved-Brief-SAMPLE.pdf"
    builder = ResolvedBriefBuilder(MOCK)
    builder.build(output)
