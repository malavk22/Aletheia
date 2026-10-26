import json
import logging
import math
import time
from collections import Counter
from functools import lru_cache
from threading import Lock
from typing import Any

from google import genai
from google.genai import errors, types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Calls made to each model since the server started: the log shows how fast
# the free daily quota (20 a model) is being used. Counted under a lock, as
# requests run in parallel.
calls_since_start: Counter[str] = Counter()
_count_lock = Lock()

# "Too many requests" (free limit) and "busy": worth trying another model.
# Other errors (bad key, bad request) would fail the same way on any model.
TRY_FALLBACK = {429, 503}


# Why a call failed, so people can be told whether trying again helps.
LIMIT = "limit"  # a usage limit was reached (429); fine again after a wait
TEMPORARY = "temporary"  # busy, down, or an unusable reply; try again soon
REFUSED = "refused"  # no key, key or request rejected; trying again won't help


class LLMError(Exception):
    """The answer could not be written: no API key, or the call to Gemini
    failed (offline, free limit reached, key rejected). `kind` says which
    sort of failure it was, and `retry_after` how many seconds Gemini said
    to wait, when it said."""

    def __init__(self, message: str, kind: str = TEMPORARY, retry_after: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


@lru_cache
def _client() -> genai.Client:
    # Made once, on first use, then kept.
    return genai.Client(api_key=settings.gemini_api_key)


def generate(instructions: str, prompt: str) -> str:
    """The model's reply to `prompt`, following `instructions`. If the main
    model is busy or over its free limit, the fallback model is tried once.
    Swapping the model provider only changes this file."""
    return _generate(instructions, prompt, schema=None)


def generate_json(instructions: str, prompt: str, schema: dict) -> Any:
    """Like generate, but the reply is JSON shaped by `schema` (a JSON
    Schema), already parsed. Gemini is told to follow the schema; the caller
    must still check the values, which can be well-formed but wrong."""
    reply = _generate(instructions, prompt, schema=schema)
    try:
        return json.loads(reply)
    except json.JSONDecodeError as error:
        # E.g. the reply was cut off before the JSON ended.
        raise LLMError(f"Gemini gave invalid JSON: {error}") from error


def _generate(instructions: str, prompt: str, schema: dict | None) -> str:
    if not settings.gemini_api_key:
        raise LLMError("No Gemini API key is set (GEMINI_API_KEY in .env).", REFUSED)
    try:
        return _logged_call(settings.llm_model, instructions, prompt, schema)
    except errors.APIError as error:
        first = _failure(error)
        fallback = settings.llm_fallback_model
        if error.code not in TRY_FALLBACK or fallback in (None, settings.llm_model):
            raise first from error
    logger.info("Gemini %s failed (%s): trying %s", settings.llm_model, first.kind, fallback)
    try:
        return _logged_call(fallback, instructions, prompt, schema)
    except errors.APIError as error:
        raise _both_failed(first, _failure(error)) from error


def _failure(error: errors.APIError) -> LLMError:
    """What a failed call means for the person waiting. Only a 429 is a
    usage limit: a 503 means Gemini is busy or down, not that a limit was
    reached."""
    message = f"Gemini could not answer: {error}"
    if error.code == 429:
        return LLMError(message, LIMIT, _retry_delay(error.details))
    if error.code is not None and error.code >= 500:
        return LLMError(message, TEMPORARY)
    return LLMError(message, REFUSED)


def _retry_delay(body: Any) -> int | None:
    """The wait Gemini asks for, in whole seconds, from the RetryInfo in its
    error ("55s", or "56638s" when a daily limit was reached); None if it
    gave none."""
    try:
        details = body["error"]["details"]
        delay = next(d["retryDelay"] for d in details if d["@type"].endswith("RetryInfo"))
        return math.ceil(float(delay.removesuffix("s")))
    except (KeyError, TypeError, StopIteration, ValueError, AttributeError):
        return None


def _both_failed(main: LLMError, fallback: LLMError) -> LLMError:
    """One failure for two models, judged by the one that can come back
    soonest: temporary if either was temporary; else a limit if either hit
    one, with the shortest wait given; refused only if both were refused."""
    message = f"{main} | fallback: {fallback}"
    kinds = (main.kind, fallback.kind)
    if TEMPORARY in kinds:
        return LLMError(message, TEMPORARY)
    if LIMIT in kinds:
        waits = [e.retry_after for e in (main, fallback) if e.kind == LIMIT and e.retry_after is not None]
        return LLMError(message, LIMIT, min(waits) if waits else None)
    return LLMError(message, REFUSED)


def _logged_call(model: str, instructions: str, prompt: str, schema: dict | None) -> str:
    """_call, with one log line: the model, the outcome, the time taken and
    how many calls that model has had since the server started. Never the
    prompt or the reply: they hold the documents' text."""
    with _count_lock:
        calls_since_start[model] += 1
        number = calls_since_start[model]
    start = time.perf_counter()
    try:
        reply = _call(model, instructions, prompt, schema)
    except errors.APIError as error:
        outcome = f"{_failure(error).kind} (HTTP {error.code})"
        logger.warning("Gemini %s call %d: %s after %d ms", model, number, outcome, _ms_since(start))
        raise
    except Exception as error:
        # Not an answer from Gemini at all (no connection, say).
        logger.warning(
            "Gemini %s call %d: %s after %d ms", model, number, type(error).__name__, _ms_since(start)
        )
        raise
    logger.info("Gemini %s call %d: ok after %d ms", model, number, _ms_since(start))
    return reply


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _call(model: str, instructions: str, prompt: str, schema: dict | None) -> str:
    # Temperature stays at its default: Google advises against lowering it
    # for Gemini 3.x models.
    config = types.GenerateContentConfig(system_instruction=instructions)
    if schema is not None:
        config.response_mime_type = "application/json"
        config.response_json_schema = schema
    response = _client().models.generate_content(model=model, contents=prompt, config=config)
    # Empty when the reply was blocked or cut off.
    return response.text or ""
