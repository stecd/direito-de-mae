"""Talks to Claude. Claude explains; code computes dates."""
import calendar
import json
import os
from datetime import date, timedelta
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
LAWS = (Path(__file__).parent / "laws.md").read_text()
STATUS_FILE = Path(__file__).parent / "laws_status.json"
DATE_TAG = "[DATA_ESTABILIDADE]"
LEAVE_TAG = "[DATAS_LICENCA]"
ASK_DUE = "Quando o nenê deve nascer? Me diga a data e eu calculo seus prazos."

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def job_protection_end(due: date) -> date:
    """Estabilidade da gestante: até 5 meses após o parto (ADCT art. 10, II, b)."""
    m = due.month + 5
    y = due.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    d = min(due.day, calendar.monthrange(y, m)[1])
    return date(y, m, d)


def leave_window(due: date) -> tuple[date, date]:
    """Licença-maternidade (LC 150 art. 25 + CLT 392 §1º): earliest start is 28 days
    before the birth; 120 days counted from the birth end on day 119 after it."""
    return due - timedelta(days=28), due + timedelta(days=119)


WORK_TYPES = ("clt", "domestica", "servidora", "autonoma", "desempregada", "rural")

SYSTEM = f"""Você é o Direito de Mãe, um assistente no WhatsApp para QUALQUER mulher no Brasil que está grávida, vai adotar ou acabou de ter um filho: empregada com carteira (CLT), empregada doméstica, sem carteira, diarista, autônoma, MEI, desempregada, trabalhadora rural ou servidora pública.

REGRAS:
0. Os direitos mudam conforme o tipo de trabalho (veja "Primeiro: que tipo de trabalho ela tem?" em LEIS). Se ainda não souber, pergunte de forma simples ("Você trabalha com carteira, como doméstica, por conta própria, no serviço público ou está sem trabalho?") antes de dar prazos. Quando souber, devolva em "work_type": um de clt, domestica, servidora, autonoma, desempregada, rural.
1. Responda SOMENTE com base no documento LEIS abaixo. Sempre cite o artigo (ex: "LC 150 art. 25"). Se a pergunta não estiver coberta, diga "Não sei com certeza" e indique o sindicato e a Defensoria.
2. NUNCA escreva uma data de prazo você mesma. Para o fim da estabilidade (só empregada CLT ou doméstica), escreva exatamente {DATE_TAG} e o sistema preenche. Se ela disser a data prevista do parto, devolva em "due_date" (AAAA-MM-DD). Para as datas da licença-maternidade ou do salário-maternidade (CLT, doméstica e seguradas do INSS; NÃO para servidora pública, que começa no nono mês), escreva exatamente {LEAVE_TAG}. Hoje é {{today}}.
3. Quando um direito parecer violado: diga "Não sou advogada" e indique o sindicato da categoria dela primeiro (domésticas: sindicato das domésticas / FENATRAD), depois a Defensoria Pública (contatos em LEIS).
4. Português simples, frases curtas, no máximo 4 frases. Sem markdown, sem asteriscos, sem listas.
5. Diário de provas: se ela relatar um fato, mandar um print, foto ou áudio sobre algo que aconteceu no trabalho, registre em "entry" e confirme com "Anotei: ...". Para áudios de outra pessoa (encaminhados), pergunte "Quem mandou e quando?". Se ela responder a essa pergunta, devolva os dados em "entry_update" para completar o último registro.
6. Diga que ela pode mandar print, áudio ou contar o que aconteceu, e que DOSSIÊ gera o PDF com tudo.
7. Nunca diga que o registro "prova" o caso. Ele "organiza suas provas".
8. Nunca faça "correções" nem desminta o que você já disse ou anotou. Imagens antigas não ficam visíveis, mas você as leu na hora e o resumo registrado está certo. Não comente sobre datas que você "escreveu antes". Só corrija algo se ela pedir explicitamente.

RESPONDA SÓ COM JSON, assim:
{{"reply": "texto para ela", "due_date": "AAAA-MM-DD" ou null, "work_type": "clt|domestica|servidora|autonoma|desempregada|rural" ou null, "entry": {{"date_event": "AAAA-MM-DD ou desconhecida", "source": "print|foto|áudio encaminhado|relato", "who": "quem fez/disse", "summary": "uma frase", "article": "artigo relacionado"}} ou null, "entry_update": {{campos a corrigir}} ou null}}

LEIS:
{LAWS}
"""


def law_warning(status_file: Path = STATUS_FILE) -> str:
    """If the weekly check found a change nobody has reviewed yet, tell the model to say so."""
    try:
        st = json.loads(status_file.read_text())
    except (OSError, ValueError):
        return ""
    if not st.get("law_changes"):  # layout breaks and DOU mentions go to the issue only
        return ""
    return ("\n\nAVISO DO SISTEMA: a verificação semanal das leis (" + str(st.get("checked")) + ") encontrou "
            "uma possível mudança que ainda não foi revisada. Ao falar de prazos ou valores, acrescente em uma frase "
            "que a lei pode ter mudado recentemente e que ela deve confirmar com o sindicato ou a Defensoria.")


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"reply": raw}


def entries_note(entries: list | None) -> str:
    if not entries:
        return ""
    lines = [f"- {e.get('date_event', '?')} | {e.get('source', '?')} | {e.get('summary', '')}" for e in entries[-30:]]
    return ("\n\nREGISTROS JÁ ANOTADOS (fatos confirmados; as imagens antigas não estão mais visíveis para você):\n"
            + "\n".join(lines)
            + "\nRegistros já anotados são definitivos; não os desminta nem corrija a menos que ela peça.")


def think(history: list, content: list, entries: list | None = None) -> dict:
    """history: [{"role","content"(str)}]; content: blocks for the new user turn."""
    msgs = [{"role": h["role"], "content": h["content"]} for h in history]
    msgs.append({"role": "user", "content": content})
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM.replace("{today}", date.today().isoformat()) + law_warning() + entries_note(entries),
        messages=msgs,
    )
    return _parse("".join(b.text for b in resp.content if b.type == "text"))


def fill_date(reply: str, due_iso: str | None) -> str:
    """Replace the date tags with code-computed dates. Without a due date, use the
    rule in words and ask for the date once."""
    if not due_iso:
        asked = DATE_TAG in reply or LEAVE_TAG in reply
        reply = (reply.replace(DATE_TAG, "5 meses depois do parto")
                 .replace(LEAVE_TAG, "120 dias, que podem começar até 28 dias antes do parto"))
        return f"{reply} {ASK_DUE}" if asked and ASK_DUE not in reply else reply
    due = date.fromisoformat(due_iso)
    start, end = leave_window(due)
    leave = (f"120 dias, que podem começar a partir de {start:%d/%m/%Y}; "
             f"se começar na data prevista do parto, vai até {end:%d/%m/%Y}")
    return reply.replace(DATE_TAG, f"{job_protection_end(due):%d/%m/%Y}").replace(LEAVE_TAG, leave)
