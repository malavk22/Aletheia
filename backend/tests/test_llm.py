import logging
import re
from collections import Counter
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.core.config import settings
from app.qa import llm

MAIN = "main-model"
FALLBACK = "fallback-model"


def gemini_error(code: int, retry_delay: str | None = None) -> errors.APIError:
    status = {
        400: "INVALID_ARGUMENT",
        403: "PERMISSION_DENIED",
        429: "RESOURCE_EXHAUSTED",
        500: "INTERNAL",
        503: "UNAVAILABLE",
    }
    body = {"error": {"code": code, "message": "test", "status": status[code]}}
    if retry_delay is not None:
        # The shape Gemini sends with a 429 (seen in the server log).
        body["error"]["details"] = [
            {"@type": "type.googleapis.com/google.rpc.Help", "links": []},
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": []},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay},
        ]
    return (errors.ServerError if code >= 500 else errors.ClientError)(code, body)


class FakeModels:
    """Stands in for Gemini's `client.models`: remembers each call and gives
    back the next outcome, a reply text or an error to raise."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


@pytest.fixture
def fake_gemini(monkeypatch):
    def install(*outcomes):
        models = FakeModels(outcomes)
        monkeypatch.setattr(settings, "gemini_api_key", "test-key")
        monkeypatch.setattr(settings, "llm_model", MAIN)
        monkeypatch.setattr(settings, "llm_fallback_model", FALLBACK)
        monkeypatch.setattr(llm, "_client", lambda: SimpleNamespace(models=models))
        return models

    return install


def test_generate_sends_instructions_and_prompt(fake_gemini):
    models = fake_gemini("The notice period is 30 days [1].")

    reply = llm.generate("Answer only from the passages.", "When can I leave?")

    assert reply == "The notice period is 30 days [1]."
    [call] = models.calls
    assert call.model == MAIN
    assert call.contents == "When can I leave?"
    assert call.config.system_instruction == "Answer only from the passages."


def test_generate_without_key_fails_clearly():
    # conftest removes the key for every test.
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        llm.generate("instructions", "question")


@pytest.mark.parametrize("code", [429, 503])
def test_busy_main_model_falls_back(fake_gemini, code):
    models = fake_gemini(gemini_error(code), "From the fallback [1].")

    assert llm.generate("instructions", "question") == "From the fallback [1]."
    assert [call.model for call in models.calls] == [MAIN, FALLBACK]
    # The fallback gets the same rules and prompt.
    assert models.calls[1].contents == "question"
    assert models.calls[1].config.system_instruction == "instructions"


def test_other_errors_do_not_fall_back(fake_gemini):
    # A bad request would fail the same way on the fallback model.
    models = fake_gemini(gemini_error(400))

    with pytest.raises(llm.LLMError, match="400"):
        llm.generate("instructions", "question")
    assert len(models.calls) == 1


def test_both_models_busy_is_llm_error(fake_gemini):
    models = fake_gemini(gemini_error(503), gemini_error(429))

    with pytest.raises(llm.LLMError, match="429"):
        llm.generate("instructions", "question")
    assert len(models.calls) == 2


@pytest.mark.parametrize("fallback", [None, MAIN])
def test_no_fallback_when_unset_or_same_model(fake_gemini, monkeypatch, fallback):
    models = fake_gemini(gemini_error(503))
    monkeypatch.setattr(settings, "llm_fallback_model", fallback)

    with pytest.raises(llm.LLMError, match="503"):
        llm.generate("instructions", "question")
    assert len(models.calls) == 1


def test_generate_empty_reply_is_empty_text(fake_gemini):
    # Gemini gives no text when a reply is blocked.
    fake_gemini(None)

    assert llm.generate("instructions", "question") == ""


SCHEMA = {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]}


def test_generate_json_asks_for_json_with_the_schema_and_parses_it(fake_gemini):
    models = fake_gemini('{"days": 30}')

    result = llm.generate_json("Extract the notice period.", "Notice is 30 days.", SCHEMA)

    assert result == {"days": 30}
    [call] = models.calls
    assert call.config.response_mime_type == "application/json"
    assert call.config.response_json_schema == SCHEMA
    assert call.config.system_instruction == "Extract the notice period."


def test_plain_generate_does_not_ask_for_json(fake_gemini):
    models = fake_gemini("text")

    llm.generate("instructions", "question")

    assert models.calls[0].config.response_mime_type is None


def test_generate_json_with_invalid_json_is_llm_error(fake_gemini):
    # E.g. a reply cut off in the middle.
    fake_gemini('{"days": 3')

    with pytest.raises(llm.LLMError, match="invalid JSON"):
        llm.generate_json("instructions", "text", SCHEMA)


def test_generate_json_falls_back_when_busy(fake_gemini):
    models = fake_gemini(gemini_error(503), '{"days": 30}')

    assert llm.generate_json("instructions", "text", SCHEMA) == {"days": 30}
    assert [call.model for call in models.calls] == [MAIN, FALLBACK]
    assert models.calls[1].config.response_json_schema == SCHEMA


# What kind of failure it was: decides whether people are told to try again.


def failure():
    """The LLMError that generate raises with the fake installed."""
    with pytest.raises(llm.LLMError) as caught:
        llm.generate("instructions", "question")
    return caught.value


@pytest.mark.parametrize(
    "delay, seconds",
    [("55s", 55), ("56638s", 56638), ("1.5s", 2)],
)
def test_a_usage_limit_says_how_long_to_wait(fake_gemini, monkeypatch, delay, seconds):
    fake_gemini(gemini_error(429, delay))
    monkeypatch.setattr(settings, "llm_fallback_model", None)

    error = failure()

    assert (error.kind, error.retry_after) == (llm.LIMIT, seconds)


def test_a_usage_limit_without_a_wait_has_no_retry_time(fake_gemini, monkeypatch):
    fake_gemini(gemini_error(429))
    monkeypatch.setattr(settings, "llm_fallback_model", None)

    error = failure()

    assert (error.kind, error.retry_after) == (llm.LIMIT, None)


@pytest.mark.parametrize("code", [500, 503])
def test_a_server_error_is_temporary_not_a_limit(fake_gemini, monkeypatch, code):
    # A 503 means Gemini is busy or down; it says nothing about a limit.
    fake_gemini(gemini_error(code))
    monkeypatch.setattr(settings, "llm_fallback_model", None)

    error = failure()

    assert (error.kind, error.retry_after) == (llm.TEMPORARY, None)


@pytest.mark.parametrize("code", [400, 403])
def test_a_rejected_request_or_key_is_refused(fake_gemini, code):
    fake_gemini(gemini_error(code))

    assert failure().kind == llm.REFUSED


def test_no_key_is_refused():
    # conftest removes the key for every test.
    assert failure().kind == llm.REFUSED


def test_an_unusable_reply_is_temporary(fake_gemini):
    fake_gemini('{"days": 3')

    with pytest.raises(llm.LLMError) as caught:
        llm.generate_json("instructions", "text", SCHEMA)

    assert caught.value.kind == llm.TEMPORARY


@pytest.mark.parametrize(
    "main, fallback, kind, retry_after",
    [
        # Both over a limit: the sooner wait, when one of them answers again.
        (gemini_error(429, "56638s"), gemini_error(429, "55s"), llm.LIMIT, 55),
        (gemini_error(429, "40s"), gemini_error(429, "56638s"), llm.LIMIT, 40),
        (gemini_error(429), gemini_error(429, "55s"), llm.LIMIT, 55),
        (gemini_error(429), gemini_error(429), llm.LIMIT, None),
        # One busy: trying again soon may work.
        (gemini_error(429, "56638s"), gemini_error(503), llm.TEMPORARY, None),
        (gemini_error(503), gemini_error(429, "55s"), llm.TEMPORARY, None),
        # The main model comes back after its wait, even if the fallback
        # was refused (a wrong fallback model name, say).
        (gemini_error(429, "55s"), gemini_error(400), llm.LIMIT, 55),
        (gemini_error(503), gemini_error(403), llm.TEMPORARY, None),
    ],
)
def test_when_both_models_fail_the_one_back_soonest_decides(
    fake_gemini, main, fallback, kind, retry_after
):
    models = fake_gemini(main, fallback)

    error = failure()

    assert (error.kind, error.retry_after) == (kind, retry_after)
    assert len(models.calls) == 2
    # Both failures stay in the message, for the server log.
    assert str(main.code) in str(error) and str(fallback.code) in str(error)


# The log line for each call.


@pytest.fixture
def gemini_log(monkeypatch, caplog):
    # The test run's migrations switch off loggers that already exist (see
    # test_startup); a fresh count for each test.
    monkeypatch.setattr(llm.logger, "disabled", False)
    monkeypatch.setattr(llm, "calls_since_start", Counter())
    caplog.set_level(logging.INFO, logger="app.qa.llm")
    return caplog


def logged(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.qa.llm"]


def test_a_call_is_logged_with_its_model_count_and_time(fake_gemini, gemini_log):
    fake_gemini("An answer.")

    llm.generate("Be brief.", "The secret contract text")

    [line] = logged(gemini_log)
    assert re.fullmatch(rf"Gemini {MAIN} call 1: ok after \d+ ms", line)
    # Never the prompt: it holds the documents' text.
    assert "secret" not in gemini_log.text


def test_a_limit_and_the_fallback_are_logged(fake_gemini, gemini_log):
    fake_gemini(gemini_error(429), "An answer.")

    llm.generate("Be brief.", "Question")

    lines = logged(gemini_log)
    assert re.fullmatch(rf"Gemini {MAIN} call 1: limit \(HTTP 429\) after \d+ ms", lines[0])
    assert lines[1] == f"Gemini {MAIN} failed (limit): trying {FALLBACK}"
    assert re.fullmatch(rf"Gemini {FALLBACK} call 1: ok after \d+ ms", lines[2])


def test_no_connection_is_logged_too(fake_gemini, gemini_log):
    fake_gemini(ConnectionError("offline"))

    with pytest.raises(ConnectionError):
        llm.generate("Be brief.", "Question")

    [line] = logged(gemini_log)
    assert re.fullmatch(rf"Gemini {MAIN} call 1: ConnectionError after \d+ ms", line)


def test_calls_are_counted_per_model(fake_gemini, gemini_log):
    fake_gemini("One.", "Two.", gemini_error(503), "Three.")

    for _ in range(3):
        llm.generate("Be brief.", "Question")

    assert llm.calls_since_start == {MAIN: 3, FALLBACK: 1}
    assert re.fullmatch(rf"Gemini {MAIN} call 3: temporary \(HTTP 503\) after \d+ ms", logged(gemini_log)[2])
