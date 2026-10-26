from fastapi import HTTPException

from app.qa.llm import LIMIT, REFUSED, LLMError


def ai_failure(error: LLMError, failed: str) -> HTTPException:
    """The reply for a request whose AI step failed. `failed` says what
    couldn't be done ("Couldn't write an answer"). The message tells the
    person whether trying again helps and, when Gemini said, when to try:
    a usage limit is 429 with Retry-After; anything else is 503. The
    details (model names, Google's reply) stay in the server log."""
    if error.kind == LIMIT:
        when = f"in {wait_in_words(error.retry_after)}" if error.retry_after is not None else "later"
        return HTTPException(
            status_code=429,
            detail=f"{failed}: the AI usage limit has been reached. Try again {when}.",
            headers={"Retry-After": str(error.retry_after)} if error.retry_after is not None else None,
        )
    if error.kind == REFUSED:
        return HTTPException(
            status_code=503,
            detail=f"{failed}: the AI service isn't set up correctly, so trying again won't help. "
            "Check the Gemini settings on the server.",
        )
    return HTTPException(status_code=503, detail=f"{failed} right now. Try again in a minute.")


def too_many(retry_after: int, what: str) -> HTTPException:
    """The reply when a rate limit is reached: 429 with Retry-After, and
    when to try again in words. `what` says what there were too many of."""
    return HTTPException(
        status_code=429,
        detail=f"Too many {what}. Try again in {wait_in_words(retry_after)}.",
        headers={"Retry-After": str(retry_after)},
    )


def wait_in_words(seconds: int) -> str:
    """'about a minute', 'about 20 minutes', 'about 16 hours'."""
    if seconds < 90:
        return "about a minute"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"about {minutes} minutes"
    hours = round(seconds / 3600)
    return "about 1 hour" if hours == 1 else f"about {hours} hours"
