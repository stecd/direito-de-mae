"""Talks to Claude. Claude explains; code computes dates."""
import calendar
import json
import os
from datetime import date
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
LAWS = (Path(__file__).parent / "laws.md").read_text()
DATE_TAG = "[DATA_ESTABILIDADE]"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def job_protection_end(due: date) -> date:
    """Estabilidade da gestante: até 5 meses após o parto (ADCT art. 10, II, b)."""
    m = due.month + 5
    y = due.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    d = min(due.day, calendar.monthrange(y, m)[1])
    return date(y, m, d)


SYSTEM = f"""Você é o Direito de Mãe, um assistente no WhatsApp para trabalhadoras DOMÉSTICAS grávidas no Brasil (babá, empregada, cuidadora, diarista mensalista), com ou sem carteira assinada.

REGRAS:
1. Responda SOMENTE com base no documento LEIS abaixo. Sempre cite o artigo (ex: "LC 150 art. 25"). Se a pergunta não estiver coberta, diga "Não sei com certeza" e indique o sindicato e a Defensoria.
2. NUNCA escreva uma data de fim de estabilidade você mesma. Quando a data for relevante, escreva exatamente {DATE_TAG} e o sistema preenche. Se ela disser a data prevista do parto, devolva em "due_date" (AAAA-MM-DD). Hoje é {{today}}.
3. Quando um direito parecer violado: diga "Não sou advogada" e indique o sindicato das domésticas primeiro, depois a Defensoria Pública (contatos em LEIS).
4. Português simples, frases curtas, no máximo 4 frases. Sem markdown, sem asteriscos, sem listas.
5. Diário de provas: se ela relatar um fato, mandar um print, foto ou áudio sobre algo que aconteceu no trabalho, registre em "entry" e confirme com "Anotei: ...". Para áudios de outra pessoa (encaminhados), pergunte "Quem mandou e quando?". Se ela responder a essa pergunta, devolva os dados em "entry_update" para completar o último registro.
6. Diga que ela pode mandar print, áudio ou contar o que aconteceu, e que DOSSIÊ gera o PDF com tudo.
7. Nunca diga que o registro "prova" o caso. Ele "organiza suas provas".

RESPONDA SÓ COM JSON, assim:
{{"reply": "texto para ela", "due_date": "AAAA-MM-DD" ou null, "entry": {{"date_event": "AAAA-MM-DD ou desconhecida", "source": "print|foto|áudio encaminhado|relato", "who": "quem fez/disse", "summary": "uma frase", "article": "artigo relacionado"}} ou null, "entry_update": {{campos a corrigir}} ou null}}

LEIS:
{LAWS}
"""


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"reply": raw}


def think(history: list, content: list) -> dict:
    """history: [{"role","content"(str)}]; content: blocks for the new user turn."""
    msgs = [{"role": h["role"], "content": h["content"]} for h in history]
    msgs.append({"role": "user", "content": content})
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM.replace("{today}", date.today().isoformat()),
        messages=msgs,
    )
    return _parse("".join(b.text for b in resp.content if b.type == "text"))


def fill_date(reply: str, due_iso: str | None) -> str:
    """Replace the date tag with the code-computed date."""
    if not due_iso:
        return reply.replace(DATE_TAG, "5 meses depois do parto")
    end = job_protection_end(date.fromisoformat(due_iso))
    text = end.strftime("%d/%m/%Y")
    if DATE_TAG in reply:
        return reply.replace(DATE_TAG, text)
    return reply
