"""Onboarding interview: how she wants to talk (text, audio or both), then consent.

Plain functions and message texts only, so they can be tested without API keys.
Never asks about literacy: it asks a preference, and a voice-note answer counts.
"""
import re
import unicodedata

TEXT, AUDIO, BOTH = "text", "audio", "both"

WELCOME = ("Oi! Eu sou o Direito de Mãe. Explico seus direitos de grávida e mãe e guardo o que acontecer "
           "no seu trabalho, para você levar ao sindicato ou à Defensoria. Não sou advogada.")
MODE_Q = ("Como você prefere conversar comigo? Responda 1 para mensagem escrita, 2 para áudio, "
          "ou 3 para os dois. Pode responder com um áudio também.")
MODE_AGAIN = "Não entendi. Responda 1 para mensagem escrita, 2 para áudio, ou 3 para os dois."
MODE_OK = {TEXT: "Combinado, vou responder por mensagem escrita.",
           AUDIO: "Combinado, vou responder por áudio.",
           BOTH: "Combinado, vou responder com mensagem escrita e áudio."}
CONSENT_Q = ("Antes de começar: eu guardo o que você me mandar, só para montar seu resumo. Não guardo seu nome "
             "nem seu número, e tudo fica protegido com senha. Se você ficar 90 dias sem falar comigo, eu apago tudo "
             "sozinho. Você pode pedir para apagar a qualquer hora. Responda SIM para começar.")
CONSENT_AGAIN = "Para eu poder guardar suas mensagens, responda SIM. Se não quiser, responda NÃO."
CONSENT_NO = "Tudo bem. Não guardei nada. Se mudar de ideia, é só me mandar uma mensagem."
SAFETY_TIP = ("Pronto! Uma dica de segurança: se alguém pode pegar seu celular, ative as mensagens temporárias "
              "nesta conversa (toque no meu nome, depois em Mensagens temporárias) e salve meu contato com outro nome. "
              "Me conte o que está acontecendo, ou mande print ou áudio.")
MODE_CHANGE_Q = ("Como você quer que eu responda agora? 1 para mensagem escrita, 2 para áudio, ou 3 para os dois.")

_TEXT_WORDS = ("escrit", "texto", "mensage", "ler", "letra", "digit")
_AUDIO_WORDS = ("audio", "voz", "ouvir", "falad", "falar", "fala")
_BOTH_WORDS = (" dois ", " duas ", " ambos ", " ambas ", " os 2 ", " as 2 ")  # not "tudo": "tudo bem"


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", t)


def parse_mode(text: str, spoken: bool = False) -> str | None:
    """'1'/'mensagem escrita' -> text, '2'/'áudio' -> audio, '3'/'os dois' -> both.
    A voice-note answer with no clear choice means audio."""
    t = " " + norm(text) + " "
    t = re.sub(r"mensage[mn]s? de (voz|audio)", "audio", t)
    tokens = t.split()
    has_text = "1" in tokens or any(w in t for w in _TEXT_WORDS)
    has_audio = "2" in tokens or any(w in t for w in _AUDIO_WORDS)
    if "3" in tokens or any(w in t for w in _BOTH_WORDS) or (has_text and has_audio):
        return BOTH
    if has_text:
        return TEXT
    if has_audio or spoken:
        return AUDIO
    return None


_YES = {"sim", "s", "pode", "aceito", "ok", "claro", "concordo", "bora", "beleza", "isso", "quero", "uhum", "certo"}
_NO = {"nao", "n", "naum"}


def is_no(text: str) -> bool:
    tokens = norm(text).split()
    return bool(tokens) and (tokens[0] in _NO or "nao quero" in " ".join(tokens))


def is_yes(text: str) -> bool:
    tokens = norm(text).split()
    return bool(tokens) and not is_no(text) and any(w in _YES for w in tokens[:4])
