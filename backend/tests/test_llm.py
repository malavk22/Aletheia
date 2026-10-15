from types import SimpleNamespace

import pytest
from google.genai import errors

from app.core.config import settings
from app.qa import llm

MAIN = "main-model"
FALLBACK = "fallback-model"


def gemini_error(code: int) -> errors.APIError:
    status = {400: "INVALID_ARGUMENT", 429: "RESOURCE_EXHAUSTED", 503: "UNAVAILABLE"}
    body = {"error": {"code": code, "message": "test", "status": status[code]}}
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
