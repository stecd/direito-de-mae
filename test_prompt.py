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
    assert "Não guarda o nome nem o número" in s
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


def test_employee_rights_never_for_non_employees_rule():
    s = brain.SYSTEM
    assert "NUNCA para autônoma, diarista, MEI ou desempregada" in s
    assert "diarista que trabalha até 2 dias" in s


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
    store.delete(bot.uid)
