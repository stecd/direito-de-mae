"""Checks on what Claude is told (no API calls): privacy facts, short replies, plain-word
commands, work-type-specific rights. These guard the prompt against drifting from the code."""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import brain  # noqa: E402
import store  # noqa: E402


def test_privacy_facts_match_the_code():
    assert store.DEFAULT_KEEP_DAYS == brain.KEEP_DAYS and store.SAVED_KEEP_DAYS == brain.SAVED_KEEP_DAYS
    s = brain.SYSTEM
    assert "FATOS SOBRE VOCÊ" in s
    assert f"{store.DEFAULT_KEEP_DAYS} dias sem falar" in s and f"{store.SAVED_KEEP_DAYS} dias" in s
    assert "Não guarda o número dela" in s and "Não guarda o nome" not in s  # her name may be in what she writes
    assert "podem guardar cópias" in s and "Não diga que ninguém mais pode ver" in s  # vendors
    assert "chave é destruída" in s          # crypto-shredding
    assert "Twilio" in s and "minutos" in s   # Twilio cleanup
    assert "Mensagens temporárias" in s       # the phone is the biggest risk


def test_privacy_questions_must_not_get_nao_sei():
    assert 'não diga "não sei" sobre eles' in brain.SYSTEM
    assert "Defensoria" in brain.SYSTEM.split("\n10. ")[1].split("FATOS SOBRE VOCÊ (privacidade)")[0]  # legal part still referred


def test_no_rule_says_she_must_type_an_exact_word():
    s = brain.SYSTEM
    assert "NÃO precisa usar palavras exatas" in s
    assert "Nunca diga que ela tem que escrever uma palavra" in s
    assert "RESUMO gera o PDF" not in s  # the old wording that taught 'só se escrever RESUMO'


def test_reply_length_limit_is_stated_with_the_real_number():
    assert f"{brain.MAX_REPLY_CHARS} caracteres" in brain.SYSTEM
    assert "{MAX_REPLY_CHARS}" not in brain.SYSTEM  # interpolated, not literal
    assert brain.MAX_REPLY_CHARS <= 400


def test_rules_are_numbered_in_order():
    import re
    nums = [int(n) for n in re.findall(r"^(\d+)\. ", brain.SYSTEM.split("FATOS SOBRE")[0], re.M)]
    assert nums == list(range(len(nums)))


def test_fired_while_pregnant_keeps_employee_rights():
    s = brain.SYSTEM
    assert "demitida grávida é clt ou domestica" in s and "nunca desempregada" in s
    assert "demitida grávida CONTINUA com esses direitos" in s
    assert '"desempregada" é só para quem já estava sem emprego antes da gravidez' in s


def test_sem_carteira_and_diarista_classified_by_real_work():
    s = brain.SYSTEM
    assert "mais de 2 dias por semana na mesma casa = domestica, mesmo sem carteira" in s
    assert "diarista de até 2 dias por semana" in s
    assert "NUNCA para autônoma, diarista" not in s  # the old blanket ban on every diarista


def test_doubt_means_mention_not_silence():
    assert "NUNCA fique em silêncio" in brain.SYSTEM and "Se não tiver certeza de que um direito vale para ela, não cite" not in brain.SYSTEM


def test_work_type_is_confirmed_and_correctable():
    assert "confirme com ela" in brain.SYSTEM
    note = brain.work_type_note("autonoma")
    assert "pode estar errado" in note and "corrija" in note


def test_violated_right_beats_the_length_cap():
    assert "mesmo que passe do limite" in brain.SYSTEM


def test_known_work_type_reaches_claude():
    assert "autonoma" in brain.work_type_note("autonoma") and "regra 1" in brain.work_type_note("autonoma")
    assert brain.work_type_note(None) == "" and brain.work_type_note("bogus") == ""


def test_handler_passes_the_stored_work_type(monkeypatch):
    import app
    from test_safety import onboarded
    bot = onboarded(monkeypatch, {"reply": "ok", "work_type": "autonoma"})
    bot.msg("trabalho 2 dias por semana")
    bot.msg("e o salário-maternidade?")
    assert bot.work_types[-1] == "autonoma"  # second call knows what the first one learned
    bot.brain_out = {"reply": "ok", "work_type": "domestica"}  # she corrects: "na verdade são 3 dias"
    bot.msg("na verdade são 3 dias por semana")
    bot.brain_out = {"reply": "ok"}
    bot.msg("e agora?")
    assert bot.work_types[-1] == "domestica"
    assert "empregada doméstica" in bot.msg("meus dados")  # she can see what we understood
    store.delete(bot.uid)


def test_a_greeting_is_not_answered_twice(monkeypatch):
    from test_safety import Bot
    bot = Bot(monkeypatch)
    bot.msg("oi")
    bot.msg("1")
    bot.msg("sim")
    assert not bot.calls  # no Claude call (and no voice reply) just to say hello again
    store.delete(bot.uid)
