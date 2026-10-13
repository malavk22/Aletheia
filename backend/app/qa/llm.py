from functools import lru_cache

from google import genai
from google.genai import errors, types

from app.core.config import settings

# "Too many requests" (free limit) and "busy": worth trying another model.
# Other errors (bad key, bad request) would fail the same way on any model.
TRY_FALLBACK = {429, 503}


class LLMError(Exception):
    """The answer could not be written: no API key, or the call to Gemini
    failed (offline, free limit reached, key rejected)."""


@lru_cache
def _client() -> genai.Client:
    # Made once, on first use, then kept.
    return genai.Client(api_key=settings.gemini_api_key)


def generate(instructions: str, prompt: str) -> str:
    """The model's reply to `prompt`, following `instructions`. If the main
    model is busy or over its free limit, the fallback model is tried once.
    Swapping the model provider only changes this file."""
    if not settings.gemini_api_key:
        raise LLMError("No Gemini API key is set (GEMINI_API_KEY in .env).")
    try:
        return _call(settings.llm_model, instructions, prompt)
    except errors.APIError as error:
        fallback = settings.llm_fallback_model
        if error.code not in TRY_FALLBACK or fallback in (None, settings.llm_model):
            raise LLMError(f"Gemini could not answer: {error}") from error
    try:
        return _call(fallback, instructions, prompt)
    except errors.APIError as error:
        raise LLMError(f"Gemini could not answer: {error}") from error


def _call(model: str, instructions: str, prompt: str) -> str:
    response = _client().models.generate_content(
        model=model,
        contents=prompt,
        # Temperature stays at its default: Google advises against lowering
        # it for Gemini 3.x models.
        config=types.GenerateContentConfig(system_instruction=instructions),
    )
    # Empty when the reply was blocked or cut off.
    return response.text or ""
