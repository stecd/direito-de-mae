"""Builds the dossiê PDF from her entries."""
from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace
from PIL import Image

from brain import job_protection_end, leave_window

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
_TTF = {"": "Arial.ttf", "B": "Arial Bold.ttf", "I": "Arial Italic.ttf"}
UNICODE = all((FONT_DIR / f).exists() for f in _TTF.values())

NAVY = (24, 48, 89)
ROSE = (176, 48, 82)
GREY = (90, 90, 90)
LIGHT = (243, 245, 249)
LINE = (200, 205, 215)
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

WORK_LABEL = {"clt": "empregada com carteira (CLT)", "domestica": "empregada doméstica",
              "servidora": "servidora pública", "autonoma": "autônoma / contribuinte individual",
              "desempregada": "desempregada", "rural": "trabalhadora rural (segurada especial)"}

_ESTAB = ("Estabilidade da gestante:", "não pode ser dispensada sem justa causa desde a confirmação da gravidez "
          "até 5 meses após o parto, mesmo no aviso prévio (ADCT art. 10, II, b; CLT art. 391-A; LC 150 art. 25).")
_LIC = ("Licença-maternidade:", "120 dias, a partir de até 28 dias antes do parto; mais tempo se houver internação "
        "ligada ao parto (CF art. 7º, XVIII; CLT art. 392, §§1º e 7º).")
_GRAV = ("Durante a gravidez:", "dispensa para pelo menos 6 consultas e exames; afastamento de trabalho insalubre "
         "(CLT art. 392, §4º; art. 394-A).")
_DISC = ("Discriminação:", "exigir teste de gravidez é crime; demissão por gravidez dá direito a reintegração "
         "ou remuneração em dobro, além de dano moral (Lei 9.029/95 arts. 2º e 4º).")
_INSS = ("Salário-maternidade (INSS):", "120 dias, a partir de 28 dias antes do parto (Lei 8.213/91 art. 71); "
         "o INSS tem 30 dias para conceder (Lei 15.415/2026).")
RIGHTS = {
    "clt": [_ESTAB, _LIC, ("Salário durante a licença:", "integral, pago pela empresa e compensado pelo INSS "
                           "(CLT art. 393; Lei 8.213/91 art. 72, §1º)."), _GRAV,
            ("Empresa Cidadã:", "mais 60 dias se a empresa participa do programa; pedir até 1 mês após o parto "
             "(Lei 11.770/2008 art. 1º)."), _DISC],
    "domestica": [_ESTAB, _LIC, ("Salário-maternidade:", "pago diretamente pelo INSS à empregada doméstica, sem "
                                 "carência (Lei 8.213/91 arts. 26, VI e 73, I)."),
                  ("Sem carteira assinada:", "o vínculo de emprego doméstico pode ser reconhecido "
                   "(LC 150/2015 art. 1º)."), _GRAV, _DISC],
    "servidora": [("Licença à gestante:", "120 dias consecutivos, a partir do primeiro dia do nono mês, ou antes "
                   "por prescrição médica (Lei 8.112/90 art. 207)."),
                  ("Prorrogação:", "o órgão pode ter programa de mais 60 dias (Lei 11.770/2008 art. 2º)."),
                  ("Amamentação:", "1 hora por dia até 6 meses (Lei 8.112/90 art. 209)."), _DISC],
    "autonoma": [_INSS, ("Carência:", "10 contribuições mensais; menos se o parto for antecipado "
                         "(Lei 8.213/91 art. 25, III e parágrafo único)."),
                 ("Valor:", "média dos últimos 12 salários de contribuição, no mínimo um salário mínimo "
                  "(Lei 8.213/91 art. 73, III).")],
    "desempregada": [_INSS, ("Qualidade de segurada:", "mantida por 12 meses após a última contribuição, até 24 "
                             "ou mais 12 se registrar o desemprego (Lei 8.213/91 art. 15)."),
                     ("Valor:", "média dos últimos 12 salários de contribuição (Lei 8.213/91 art. 73, parágrafo "
                      "único).")],
    "rural": [_INSS, ("Segurada especial:", "um salário mínimo, comprovando atividade rural nos 12 meses antes "
                      "(Lei 8.213/91 art. 39, parágrafo único).")],
    None: [_ESTAB, _LIC, _INSS, _GRAV, _DISC],
}

HELP = [
    ("Sindicato", "Sindicato da sua categoria. Domésticas: sindicato das domésticas / FENATRAD - fenatrad.org.br"),
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
        return "sem data" if not s or "descon" in str(s).lower() else str(s)


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
    profile = user.get("profile") or {}
    work_type = profile.get("work_type")
    if work_type in WORK_LABEL:
        pdf.set_font(F, "", 10)
        pdf.set_text_color(*GREY)
        pdf.cell(w, 6, _t(f"Tipo de trabalho informado: {WORK_LABEL[work_type]}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    due = profile.get("due_date")
    has_estab = work_type in (None, "clt", "domestica")
    if due and work_type == "servidora":
        pdf.set_font(F, "B", 10.5)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(w, 6, _t(f"Data prevista do parto: {_d(due)}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        due = None
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
            pdf.cell(w / 2 - 4, 5, _t("Estabilidade garantida até" if has_estab else ""), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(L + 4)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font(F, "B", 13)
            pdf.cell(w / 2 - 4, 6, f"{dd:%d/%m/%Y}")
            pdf.cell(w / 2 - 4, 6, f"{end:%d/%m/%Y}" if has_estab else "", new_x="LMARGIN", new_y="NEXT")
            pdf.set_y(y + 17)
            ls, le = leave_window(dd)
            pdf.set_font(F, "", 9.5)
            pdf.set_text_color(*GREY)
            pdf.multi_cell(w, 5, _t(f"Licença-maternidade de 120 dias: pode começar a partir de {ls:%d/%m/%Y}; "
                                    f"se começar na data prevista do parto, vai até {le:%d/%m/%Y} "
                                    "(CLT art. 392, §1º; LC 150 art. 25; Lei 8.213 art. 71)."), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        except ValueError:
            pass
    rights = RIGHTS.get(work_type, RIGHTS[None])
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
        pdf.set_fill_color(255, 255, 255)
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

    # Evidence thumbnails (images she sent, numbered like the timeline).
    # Open and shrink every image first, so an unreadable file never leaves a gap
    # or breaks the row layout, and phone photos don't bloat the PDF.
    pics = []
    for i, e in enumerate(entries, 1):
        f = e.get("file")
        if not f or Path(f).suffix.lower() not in IMAGE_EXT or not (out.parent / f).exists():
            continue
        try:
            img = Image.open(out.parent / f)
            img.load()
            img = img.convert("RGB")
            img.thumbnail((1200, 1200))
            pics.append((i, img))
        except Exception:
            continue
    if pics:
        section("Prints e fotos enviados")
        tw, th, gap = (w - 2 * 6) / 3, 62, 6
        for k, (i, img) in enumerate(pics):
            col = k % 3
            if col == 0:
                if pdf.get_y() + th + 8 > pdf.h - 18:
                    pdf.add_page()
                y0 = pdf.get_y()
            x = L + col * (tw + gap)
            pdf.image(img, x=x, y=y0, w=tw, h=th, keep_aspect_ratio=True)
            pdf.set_xy(x, y0 + th + 1)
            pdf.set_font(F, "", 8)
            pdf.set_text_color(*GREY)
            pdf.cell(tw, 4, _t(f"Registro #{i}"), align="C")
            if col == 2 or k == len(pics) - 1:
                pdf.set_xy(L, y0 + th + 8)
        pdf.ln(2)

    # Help
    section("Onde buscar ajuda (gratuito)")
    for lead, h in HELP:
        bullet(h, lead + ":")

    pdf.output(str(out))
    return out
