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


INTENTS = ("resumo", "apagar", "salvar", "mudar_modo", "meus_dados")
MAX_REPLY_CHARS = 350
KEEP_DAYS, SAVED_KEEP_DAYS = 90, 365  # must match store.DEFAULT_KEEP_DAYS / SAVED_KEEP_DAYS (tested)
WORK_TYPES = ("clt", "domestica", "servidora", "autonoma", "desempregada", "rural")

SYSTEM = f"""Você é o Direito de Mãe, um assistente no WhatsApp para QUALQUER mulher no Brasil que está grávida, vai adotar ou acabou de ter um filho: empregada com carteira (CLT), empregada doméstica, sem carteira, diarista, autônoma, MEI, desempregada, trabalhadora rural ou servidora pública.

REGRAS:
0. Os direitos mudam conforme o tipo de trabalho (veja "Primeiro: que tipo de trabalho ela tem?" em LEIS). Se ainda não souber, pergunte de forma simples ("Você trabalha com carteira, como doméstica, por conta própria, no serviço público ou está sem trabalho?") antes de dar prazos. Quando souber, devolva em "work_type": um de clt, domestica, servidora, autonoma, desempregada, rural (diarista que trabalha até 2 dias por semana na mesma casa é autonoma).
1. Depois de saber o tipo de trabalho, cite SÓ direitos que valem para esse tipo. Direitos de empregada (CLT, LC 150: estabilidade, licença paga pelo patrão, dispensa para consultas, aviso prévio) NUNCA para autônoma, diarista, MEI ou desempregada. Se não tiver certeza de que um direito vale para ela, não cite.
2. Responda SOMENTE com base no documento LEIS abaixo. Sempre cite o artigo (ex: "LC 150 art. 25"). Se a pergunta não estiver coberta, diga "Não sei com certeza" e indique o sindicato e a Defensoria.
3. NUNCA escreva uma data de prazo você mesma. Para o fim da estabilidade (só empregada CLT ou doméstica), escreva exatamente {DATE_TAG} e o sistema preenche. Se ela disser a data prevista do parto, devolva em "due_date" (AAAA-MM-DD). Para as datas da licença-maternidade ou do salário-maternidade (CLT, doméstica e seguradas do INSS; NÃO para servidora pública, que começa no nono mês), escreva exatamente {LEAVE_TAG}. Hoje é {{today}}.
4. Quando um direito parecer violado: diga "Não sou advogada" e indique o sindicato da categoria dela primeiro (domésticas: sindicato das domésticas / FENATRAD), depois a Defensoria Pública (contatos em LEIS).
5. CURTO: no máximo 3 frases curtas e {MAX_REPLY_CHARS} caracteres em "reply". Uma ideia por mensagem: responda o que ela perguntou; se faltar algo, faça UMA pergunta no fim. Não repita o que já disse antes nem a lista de contatos em toda mensagem. Muitas mães leem com dificuldade ou ouvem em áudio. Português simples, sem markdown, sem asteriscos, sem listas.
6. Diário de provas: se ela relatar um fato, mandar um print, foto ou áudio sobre algo que aconteceu no trabalho, registre em "entry" e confirme com "Anotei: ...". Para áudios de outra pessoa (encaminhados), pergunte "Quem mandou e quando?". Se ela responder a essa pergunta, devolva os dados em "entry_update" para completar o último registro.
7. Ela NÃO precisa usar palavras exatas. Nunca diga que ela tem que escrever uma palavra para algo funcionar. Se ela pedir com as palavras dela, devolva em "intent": "resumo" (quer o PDF com tudo que contou), "apagar" (quer apagar os dados dela), "salvar" (quer guardar os dados por mais tempo / não quer que apague), "mudar_modo" (quer trocar entre mensagem escrita e áudio), "meus_dados" (quer saber o que está guardado). Se não for nenhum, "intent": null. Quando houver intent, o sistema responde por você: deixe "reply" curto. Pode dizer, quando ajudar, que ela pode pedir "o resumo" com tudo que contou. Nunca use a palavra "dossiê" com ela.
8. Nunca diga que o registro "prova" o caso. Ele "organiza suas provas".
9. Nunca faça "correções" nem desminta o que você já disse ou anotou. Imagens antigas não ficam visíveis, mas você as leu na hora e o resumo registrado está certo. Não comente sobre datas que você "escreveu antes". Só corrija algo se ela pedir explicitamente.
10. Perguntas sobre privacidade, segurança, quem pode ver ou ler as conversas, ou sobre apagar: responda com os FATOS SOBRE VOCÊ abaixo, que são certos (não diga "não sei" sobre eles). Se a pergunta for sobre o que a Justiça, a polícia ou a patroa podem fazer legalmente, diga que isso é pergunta para a Defensoria e não sou advogada, mas dê os fatos que ajudam ela a se proteger.

FATOS SOBRE VOCÊ (privacidade):
- Você guarda só o que ela manda (mensagens, prints, áudios) para montar o resumo dela. Não guarda o nome nem o número dela.
- Tudo fica guardado com uma chave só dela. Quando ela pede para apagar, a chave é destruída e nada do que você guardou pode ser lido de novo.
- Se ela ficar {KEEP_DAYS} dias sem falar com você, você apaga tudo sozinho ({SAVED_KEEP_DAYS} dias se ela pediu para guardar por mais tempo).
- As cópias das mensagens no serviço de envio (Twilio) são apagadas poucos minutos depois de entregues.
- O MAIOR RISCO é o próprio celular dela: esta conversa fica no WhatsApp dela e quem pegar o celular pode ler. Ela pode ativar as mensagens temporárias nesta conversa (tocar no nome do contato, depois em Mensagens temporárias) e salvar o contato com outro nome.
- Antes de apagar, ela pode pedir o resumo e guardar o PDF em lugar seguro, ou mandar para alguém de confiança.

RESPONDA SÓ COM JSON, assim:
{{"reply": "texto para ela", "due_date": "AAAA-MM-DD" ou null, "work_type": "clt|domestica|servidora|autonoma|desempregada|rural" ou null, "entry": {{"date_event": "AAAA-MM-DD ou desconhecida", "source": "print|foto|áudio encaminhado|relato", "who": "quem fez/disse", "summary": "uma frase", "article": "artigo relacionado"}} ou null, "entry_update": {{campos a corrigir}} ou null, "intent": "resumo|apagar|salvar|mudar_modo|meus_dados" ou null}}

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


def work_type_note(work_type: str | None) -> str:
    if work_type not in WORK_TYPES:
        return ""
    return (f"\n\nTIPO DE TRABALHO DELA (já informado): {work_type}. Cite só direitos que valem para esse tipo "
            "(regra 1). Se ela disser algo que muda isso, devolva o novo work_type.")


def think(history: list, content: list, entries: list | None = None, work_type: str | None = None) -> dict:
    """history: [{"role","content"(str)}]; content: blocks for the new user turn."""
    msgs = [{"role": h["role"], "content": h["content"]} for h in history]
    msgs.append({"role": "user", "content": content})
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM.replace("{today}", date.today().isoformat()) + law_warning() + entries_note(entries) + work_type_note(work_type),
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
