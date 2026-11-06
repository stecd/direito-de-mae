"""Builds the dossiê PDF from her entries."""
from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from brain import job_protection_end

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
_TTF = {"": "Arial.ttf", "B": "Arial Bold.ttf", "I": "Arial Italic.ttf"}
UNICODE = all((FONT_DIR / f).exists() for f in _TTF.values())

NAVY = (24, 48, 89)
ROSE = (176, 48, 82)
GREY = (90, 90, 90)
LIGHT = (243, 245, 249)
LINE = (200, 205, 215)

HELP = [
    ("Sindicato / FENATRAD", "Sindicato das trabalhadoras domésticas da sua cidade - fenatrad.org.br"),
    ("Defensoria Pública", "Defensoria Pública do seu estado: atendimento jurídico gratuito"),
    ("MPT", "Denúncia ao Ministério Público do Trabalho: mpt.mp.br"),
]


def _t(s) -> str:
    """Sanitize text. With Arial TTF only strip emoji/astral chars; else latin-1."""
    s = "" if s is None else str(s)
    if UNICODE:
        return "".join(c for c in s if ord(c) <= 0xFFFF and not (0x2600 <= ord(c) <= 0x27BF))
    s = s.replace("—", "-").replace("–", "-").replace("“", '"').replace("”", '"').replace("’", "'")
    return s.encode("latin-1", "replace").decode("latin-1")


def _d(s) -> str:
    try:
        return date.fromisoformat(str(s)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(s or "-")


class _PDF(FPDF):
    fam = "Helvetica"

    def footer(self):
        self.set_y(-12)
        self.set_font(self.fam, "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, _t(f"Dossiê - Direito de Mãe  |  página {self.page_no()}/{{nb}}"), align="C")


def build(user: dict, out: Path) -> Path:
    pdf = _PDF()
    if UNICODE:
        for style, f in _TTF.items():
            pdf.add_font("Arial", style, str(FONT_DIR / f))
        pdf.fam = "Arial"
    F = pdf.fam
    pdf.alias_nb_pages()
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    w = pdf.epw
    L = pdf.l_margin

    # Header band
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 30, "F")
    pdf.set_xy(L, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(F, "B", 20)
    pdf.cell(w, 9, _t("Dossiê — Direito de Mãe"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(F, "", 9.5)
    pdf.cell(w, 6, _t(f"Registro de fatos para atendimento jurídico  |  Gerado em {date.today():%d/%m/%Y}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(36)

    # Disclaimer box
    pdf.set_fill_color(*LIGHT)
    pdf.set_draw_color(*LINE)
    pdf.set_text_color(*GREY)
    pdf.set_font(F, "I", 8.5)
    pdf.multi_cell(w, 4.6, _t("Este documento organiza relatos e provas enviados pela própria trabalhadora. "
                              "Não é parecer jurídico. As datas de registro não são certificadas."),
                   border=1, fill=True, padding=3, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    def section(title):
        pdf.set_text_color(*NAVY)
        pdf.set_font(F, "B", 13)
        pdf.cell(w, 7, _t(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(*ROSE)
        pdf.set_line_width(0.6)
        pdf.line(L, pdf.get_y(), L + 30, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(3)

    def bullet(text, bold_lead=None):
        pdf.set_text_color(30, 30, 30)
        pdf.set_font(F, "B", 10)
        pdf.set_x(L + 2)
        pdf.cell(4, 5.4, "•" if UNICODE else "-")
        body = (f"**{_t(bold_lead)}** " if bold_lead else "") + _t(text).replace("**", "")
        pdf.set_font(F, "", 10)
        pdf.multi_cell(w - 6, 5.4, body, markdown=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # Rights
    section("Direitos principais")
    due = (user.get("profile") or {}).get("due_date")
    if due:
        try:
            dd = date.fromisoformat(due)
            end = job_protection_end(dd)
            pdf.set_fill_color(252, 236, 241)
            pdf.set_draw_color(*ROSE)
            y = pdf.get_y()
            pdf.rect(L, y, w, 15, "DF")
            pdf.set_xy(L + 4, y + 2.5)
            pdf.set_text_color(*ROSE)
            pdf.set_font(F, "B", 10.5)
            pdf.cell(w / 2 - 4, 5, _t("Data prevista do parto"))
            pdf.cell(w / 2 - 4, 5, _t("Estabilidade garantida até"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(L + 4)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font(F, "B", 13)
            pdf.cell(w / 2 - 4, 6, f"{dd:%d/%m/%Y}")
            pdf.cell(w / 2 - 4, 6, f"{end:%d/%m/%Y}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_y(y + 17)
        except ValueError:
            pass
    rights = [
        ("Estabilidade da gestante:", "não pode ser dispensada sem justa causa desde a confirmação da gravidez "
         "até 5 meses após o parto (LC 150/2015 art. 25, parágrafo único; ADCT art. 10, II, b)."),
        ("Licença-maternidade:", "120 dias (LC 150/2015 art. 25)."),
        ("Salário-maternidade:", "pago diretamente pelo INSS à empregada doméstica (Lei 8.213/91 art. 73, I)."),
        ("Sem carteira assinada:", "o vínculo de emprego doméstico pode ser reconhecido (LC 150/2015 art. 1º)."),
    ]
    for lead, r in rights:
        bullet(r, lead)
    pdf.ln(3)

    # Timeline table
    section("Linha do tempo dos fatos")
    entries = user.get("entries") or []
    if not entries:
        pdf.set_font(F, "I", 10)
        pdf.set_text_color(*GREY)
        pdf.cell(w, 6, _t("Nenhum fato registrado ainda."), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_draw_color(*LINE)
        pdf.set_font(F, "", 9)
        pdf.set_text_color(30, 30, 30)
        with pdf.table(col_widths=(8, 20, 20, 24, 58, 32), line_height=4.6, padding=1.6,
                       headings_style=FontFace(family=F, emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY, size_pt=8.5), text_align="LEFT", first_row_as_headings=True) as table:
            head = table.row()
            for h in ("#", "Data", "Fonte", "Quem", "O que aconteceu", "Direito / artigo"):
                head.cell(_t(h))
            pdf.set_text_color(30, 30, 30)
            for i, e in enumerate(entries, 1):
                pdf.set_font(F, "", 8.5)
                r = table.row()
                r.cell(str(i))
                r.cell(_d(e.get("date_event")))
                r.cell(_t(e.get("source") or "-"))
                r.cell(_t(e.get("who") or "não informado"))
                extra = f"\nRegistrado em {_d(e.get('date_logged'))}"
                if e.get("file"):
                    extra += f" | arquivo: {e['file']}"
                r.cell(_t((e.get("summary") or "-") + extra))
                r.cell(_t(e.get("article") or "-"))
    pdf.ln(6)

    # Help
    section("Onde buscar ajuda (gratuito)")
    for lead, h in HELP:
        bullet(h.split(": ", 1)[-1] if ": " in h else h, lead + ":")

    pdf.output(str(out))
    return out
