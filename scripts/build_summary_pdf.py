import re
import sys

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from emporio.config import ROOT

REPO = "https://github.com/Vininic/emporio-da-musica-agent"
NAME = "Vinícius Nicoluci Espíndola"
CAREER = "AI Engineer – Full-Stack para Aplicações com IA Generativa"
INK = HexColor("#171B29")
ACCENT = HexColor("#344E97")
MUTED = HexColor("#5A6275")

BODY = ParagraphStyle(
    "body", fontName="Helvetica", fontSize=9.6, leading=13.4, textColor=INK, spaceAfter=5
)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=INK)
SUB = ParagraphStyle("sub", parent=BODY, textColor=MUTED, spaceAfter=8)
HEAD = ParagraphStyle(
    "head",
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=ACCENT,
    spaceBefore=9,
    spaceAfter=3,
)


def eval_runs() -> list[tuple[str, str, str]]:
    runs = []
    for line in (ROOT / "evals" / "HISTORY.md").read_text("utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"\d+/\d+", cells[3]):
            runs.append((cells[0], cells[2], cells[3]))
    return runs


def bullets(items: list[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, BODY), leftIndent=10) for item in items],
        bulletType="bullet",
        bulletFontSize=6,
        bulletOffsetY=-2,
        leftIndent=10,
    )


def main() -> None:
    live = sys.argv[1] if len(sys.argv) > 1 else None
    latest = [run for run in eval_runs() if "/57" in run[2]][-1]
    links = f'Repository: <a href="{REPO}" color="#344E97">{REPO}</a>'
    if live:
        links += f'<br/>Live demo: <a href="{live}" color="#344E97">{live}</a>'

    story = [
        Paragraph("Empório da Música: customer service agent", TITLE),
        Paragraph(f"{NAME} | {CAREER}", SUB),
        Paragraph(links, BODY),
        Paragraph("What it is", HEAD),
        Paragraph(
            "Amadeus is a customer service agent for a fictional instrument store, in Portuguese and English. "
            "It searches the catalog, quotes prices, checks orders after verifying identity, explains store policy, "
            "gives hours and location, and opens tickets for the team. Answers carry real visual blocks rendered "
            "from tool output: product cards, order timeline, return verdict, quote, ticket, store hours.",
            BODY,
        ),
        Paragraph("Key decisions", HEAD),
        bullets(
            [
                "<b>Python computes, the model talks.</b> Prices, installments, hours, shipping and return windows live in tested code, because the data has traps: expired promotions, tiers that differ from the manual, contradictions.",
                "<b>No text-to-SQL.</b> Tools run fixed, parameterized queries, since customer data sits in the same database.",
                "<b>Identity in code.</b> Order number and phone, with the phone required to come from the customer, and limits per session and per order.",
                '<b>Hybrid retrieval.</b> BM25 plus vectors with rank fusion: "warm tone" needs vectors, "GD20" needs keywords.',
                "<b>A guard on every answer.</b> Money, percentages, contact details and claimed actions are checked against what the tools returned, with one correction round and a safe fallback.",
                "<b>Evals as code.</b> Every data trap has a case, and every full run is kept in the repository, failures included.",
                "<b>Simple to run.</b> One command, no vector database server, no front-end build, no agent framework hiding the loop.",
            ]
        ),
        Paragraph("Measured results", HEAD),
        Paragraph(
            f"{latest[2].split('/')[1]} live cases in two languages. The latest full run scored <b>{latest[2]}</b> on {latest[1]}. "
            "Scores vary between runs and models, so the full history is in <font name='Courier'>evals/HISTORY.md</font>. "
            "181 offline tests need no API key.",
            BODY,
        ),
        Paragraph(
            "A separate agent with no shared context attacked the running system and reviewed the code, producing 23 findings. "
            "The worst let a customer imitate an internal message to get a false price past the guard. It found what a perfect "
            "eval score had not. The report and the state of each finding are in <font name='Courier'>vault/reviews</font>.",
            BODY,
        ),
        Paragraph("Known limitations", HEAD),
        bullets(
            [
                "The lite models keep facts through tools and the guard, but behavior varies between runs.",
                "The guard does not tie a value to its product, and a wrong statement with no number can pass.",
                "Text streams before the guard runs, so a rejected answer can show for a moment.",
                "Rate limits and lockouts are in memory, per serverless instance. Tickets are local and nobody receives them.",
                "Product images are third-party thumbnails, acceptable for a prototype only.",
            ]
        ),
        Paragraph("How coding assistants were used", HEAD),
        Paragraph(
            "Claude Code wrote nearly all the code and documents. I directed the project, made the product and identity decisions, "
            "reviewed the results and rejected what was not good enough. The workflow: audit the data by script before any agent "
            "exists, write decisions down with who made them, turn each trap into an eval case, keep rules for the assistant in a "
            "versioned file, and have a second agent attack the result. "
            "<font name='Courier'>vault/ai-log.md</font> records what actually happened, including where the assistant was wrong.",
            BODY,
        ),
    ]

    output = ROOT / "delivery" / f"{NAME} - {CAREER}.pdf"
    output.parent.mkdir(exist_ok=True)
    SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.5 * cm,
        title="Empório da Música: customer service agent",
        author=NAME,
    ).build(story)
    print(output)


if __name__ == "__main__":
    main()
