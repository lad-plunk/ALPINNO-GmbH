"""Build the public English ShareWise performance and limitations note."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "sharewise" / "sharewise-technical-note_en_original_v1.pdf"

NAVY = colors.HexColor("#0b1f3a")
INK = colors.HexColor("#132238")
BLUE = colors.HexColor("#1769aa")
MIST = colors.HexColor("#f3f6f8")
PALE_BLUE = colors.HexColor("#dcecf7")
MUTED = colors.HexColor("#526173")
LINE = colors.HexColor("#d8e0e8")
WHITE = colors.white


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "Kicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
            leading=12, textColor=BLUE, spaceAfter=9, tracking=1.2,
        ),
        "title": ParagraphStyle(
            "TitleCustom", parent=base["Title"], fontName="Helvetica-Bold", fontSize=28,
            leading=32, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCustom", parent=base["Normal"], fontName="Helvetica", fontSize=15,
            leading=21, textColor=BLUE, spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "H1Custom", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=17,
            leading=22, textColor=NAVY, spaceBefore=12, spaceAfter=9,
        ),
        "h2": ParagraphStyle(
            "H2Custom", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
            leading=15, textColor=NAVY, spaceBefore=12, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "BodyCustom", parent=base["BodyText"], fontName="Helvetica", fontSize=9.8,
            leading=14.7, textColor=INK, spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "SmallCustom", parent=base["BodyText"], fontName="Helvetica", fontSize=8.3,
            leading=12.2, textColor=MUTED, spaceAfter=7,
        ),
        "table_head": ParagraphStyle(
            "TableHeadCustom", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
            leading=11, textColor=WHITE,
        ),
        "table_body": ParagraphStyle(
            "TableBodyCustom", parent=base["Normal"], fontName="Helvetica", fontSize=8.2,
            leading=11.7, textColor=INK,
        ),
        "metric": ParagraphStyle(
            "MetricCustom", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=12.5,
            leading=15, textColor=NAVY, alignment=TA_CENTER,
        ),
        "callout": ParagraphStyle(
            "CalloutCustom", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5,
            leading=15.5, textColor=NAVY,
        ),
        "bullet": ParagraphStyle(
            "BulletCustom", parent=base["BodyText"], fontName="Helvetica", fontSize=9.3,
            leading=13.8, textColor=INK, leftIndent=13, firstLineIndent=-9, spaceAfter=5,
        ),
    }


S = styles()


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullet(text: str) -> Paragraph:
    return para("&#8226; " + text, "bullet")


def callout(text: str, background: colors.Color = PALE_BLUE) -> Table:
    box = Table([[para(text, "callout")]], colWidths=[170 * mm])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (0, 0), (0, -1), 4, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return box


def page_frame(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 29 * mm, width, 29 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(20 * mm, height - 17 * mm, "ALPINNO")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 20 * mm, height - 17 * mm, "SHAREWISE  /  PRODUCT NOTE")
    canvas.setStrokeColor(LINE)
    canvas.line(20 * mm, 18 * mm, width - 20 * mm, 18 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(20 * mm, 12 * mm, "ALPINNO GmbH  |  24 September 2026  |  English v1")
    canvas.drawRightString(width - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=40 * mm, bottomMargin=26 * mm,
        title="ShareWise Core LM | Performance, use and limitations",
        author="ALPINNO GmbH",
        subject="ShareWise product performance context and responsible use",
        creator="ALPINNO GmbH",
    )

    story = [
        para("SHAREWISE CORE LM", "kicker"),
        para("Performance, use and limitations", "title"),
        para("A short guide to what the benchmark measures and how to use ShareWise responsibly.", "subtitle"),
        callout("ShareWise prepares extracted text for your review. It does not certify that a document is anonymous, compliant or safe to share."),
        Spacer(1, 10),
        para("What ShareWise is for", "h1"),
        para(
            "ShareWise is a Windows application that prepares extracted text locally before you decide whether to use an external AI service. "
            "ShareWise Core LM provides on-device suggestions about text that may identify a person or expose a secret. "
            "You can review and adjust those suggestions, add exact-match confidential terms, and optionally restore matching details locally later with a private restoration file."
        ),
        para("Appropriate use", "h2"),
        bullet("Prepare and review text from supported files or pasted text before external sharing."),
        bullet("Use the side-by-side review to find missed details and correct unwanted masking."),
        bullet("Apply your own confidentiality rules before deciding what may leave your computer."),
        para("What it is not", "h2"),
        bullet("An anonymisation, legal compliance, confidentiality or safety guarantee."),
        bullet("An automatic decision that unmarked text is safe to disclose."),
        bullet("OCR for scans, or a tool that redacts the original formatted document."),
        para(
            "ShareWise works on extracted text from text-based PDF, DOCX, PPTX, TXT, Markdown and pasted text. "
            "It does not support XLSX. Images, charts, scanned pages and complex layouts may contain information that extraction does not capture.",
            "small",
        ),
        para("Current input bounds", "h2"),
        para(
            "Per file: 25 MB, 200 PDF pages, 200,000 extracted characters and 16,000 model tokens. "
            "Oversize inputs must be split; ShareWise does not silently truncate them.",
            "small",
        ),
        PageBreak(),
        para("REFERENCE PERFORMANCE", "kicker"),
        para("What the benchmark measured", "title"),
        para(
            "The figures below describe the text-detection model integrated as ShareWise Core LM. They are the baseline row "
            "for the PII-Masking-300k test holdout, a synthetic multilingual set with labelled personal-data text. "
            "That baseline uses mapped labels and rule-based label cleanup. "
            "They are reported model-level results, not an ALPINNO-run evaluation of the complete ShareWise application."
        ),
    ]

    rows = [
        [para("Metric", "table_head"), para("Result", "table_head"), para("Plain-language meaning", "table_head")],
        [para("Token-level recall", "table_body"), para("98.0%", "metric"), para("Of the labelled sensitive-text tokens in this test, this share was detected.", "table_body")],
        [para("Token-level precision", "table_body"), para("94.0%", "metric"), para("Of the tokens flagged as sensitive, this share matched the labels.", "table_body")],
        [para("Token-level F1", "table_body"), para("96.0%", "metric"), para("A combined score that balances recall and precision.", "table_body")],
        [para("Exact-span F1", "table_body"), para("92.6%", "metric"), para("A stricter combined score that also depends on the boundaries of each detected passage.", "table_body")],
    ]
    metrics = Table(rows, colWidths=[41 * mm, 28 * mm, 101 * mm], repeatRows=1, hAlign="LEFT")
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, MIST]),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend([
        Spacer(1, 7), metrics, Spacer(1, 13),
        callout("98.0% recall does not mean 98% of documents are safe to share. The figures do not measure file extraction, ShareWise corrections, complete-document safety or your own confidentiality rules.", MIST),
        Spacer(1, 11),
        para("How to interpret the result", "h1"),
        bullet("The test counts labelled text units. One missed name or number can still matter greatly in a real document."),
        bullet("The benchmark is synthetic. Performance can change with language, layout, document type and subject matter."),
        bullet("The model's definition of sensitive text may differ from your organisation's rules. Your review and confidential-term lists help apply your own rules."),
        para(
            "A separate corrected-label analysis reported slightly higher scores after label issues were reviewed. "
            "The baseline values above are used here to avoid presenting that adjustment as a ShareWise improvement.",
            "small",
        ),
        PageBreak(),
        para("RISKS AND RESPONSIBLE USE", "kicker"),
        para("Where review matters most", "title"),
        para(
            "Automatic detection is an aid. It can miss details that should be hidden or hide ordinary text that should stay. "
            "These risks may be more consequential in medical, legal, financial, HR, education and government work."
        ),
        para("Known detection limits", "h1"),
        bullet("Uncommon names, initials, regional naming patterns and specialist identifiers may be missed."),
        bullet("Ambiguous words, public names, locations or number-like strings may be masked unnecessarily."),
        bullet("Heavy punctuation, line breaks, mixed formats and long-range references may cause missed or fragmented detections."),
        bullet("Results may vary across languages, scripts, subject areas and organisational definitions of confidential information."),
        para("ShareWise workflow limits", "h1"),
        bullet("Check that extraction captured the text you intend to review. Scans and image-only content require OCR elsewhere."),
        bullet("Review the complete prepared text, including words ShareWise did not highlight. The original formatted file is not redacted."),
        bullet("Keep restoration files private. They contain original values and are not encrypted. Optional correction memory is also stored locally without encryption and can be disabled or cleared."),
        bullet("ShareWise does not automatically send content to an AI service or to ALPINNO. Any external AI service you choose has its own terms and data handling."),
        Spacer(1, 4),
        callout("You remain responsible for deciding whether the reviewed text may be shared under your confidentiality, legal and organisational obligations."),
        Spacer(1, 10),
        para("A practical check before sharing", "h2"),
        para("1. Confirm the extracted text is complete.", "bullet"),
        para("2. Inspect both highlighted and unhighlighted text.", "bullet"),
        para("3. Adjust private terms and save the reviewed result.", "bullet"),
        para("4. Decide whether the external service is appropriate for this content.", "bullet"),
        HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=8, spaceAfter=9),
        para("This note describes the current public ShareWise workflow as of 24 September 2026. It is product information, not a certification or a guarantee of outcomes.", "small"),
    ])

    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    print(OUTPUT)


if __name__ == "__main__":
    build()
