"""Provider-agnostic LLM call. Gemini and Groq both expose OpenAI-compatible endpoints (free tiers),
so one code path serves both. Providers are tried in order -> automatic fallback if one is rate limited."""
import json
import os
import httpx

PROVIDERS = []
if os.getenv("GEMINI_API_KEY"):
    # Comma-separated, tried in order: older models are retired for new keys, newer ones can be overloaded.
    for m in os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.8-flash,gemini-3.5-flash").split(","):
        PROVIDERS.append(("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                          os.environ["GEMINI_API_KEY"], m.strip()))
if os.getenv("GROQ_API_KEY"):
    PROVIDERS.append(("https://api.groq.com/openai/v1/chat/completions",
                      os.environ["GROQ_API_KEY"], os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")))


async def stream(messages: list[dict]):
    """Yield reply text as it is generated. Falls back to the next model only if nothing was sent yet."""
    if not PROVIDERS:
        raise RuntimeError("No LLM key configured (set GEMINI_API_KEY and/or GROQ_API_KEY)")
    last = None
    for url, key, model in PROVIDERS:
        started = False
        try:
            body = {"model": model, "messages": messages, "temperature": 0.5, "max_tokens": 2500, "stream": True,
                    **({"reasoning_effort": os.getenv("GEMINI_REASONING", "low")} if "generativelanguage" in url else {})}
            # read=15: a model that sends nothing for 15s (overloaded / over-thinking) is skipped for the next one
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=float(os.getenv("FIRST_TOKEN_TIMEOUT", "12")), write=10, pool=10)) as client:
                async with client.stream("POST", url, headers={"Authorization": f"Bearer {key}"}, json=body) as r:
                    if r.status_code >= 400:
                        await r.aread()
                        r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        choices = json.loads(data).get("choices") or []
                        piece = choices[0].get("delta", {}).get("content") if choices else None
                        if piece:
                            started = True
                            yield piece
            if started:
                return
        except Exception as e:
            last = e
            if started:  # partial reply already sent; cannot switch models mid-answer
                return
    raise RuntimeError(f"All LLM providers failed: {last}")


async def complete(messages: list[dict]) -> str:
    if not PROVIDERS:
        raise RuntimeError("No LLM key configured (set GEMINI_API_KEY and/or GROQ_API_KEY)")
    last = None
    async with httpx.AsyncClient(timeout=45) as client:
        for url, key, model in PROVIDERS:
            try:
                r = await client.post(url, headers={"Authorization": f"Bearer {key}"},
                                      json={"model": model, "messages": messages,
                                            "temperature": 0.5, "max_tokens": 2500,
                                            **({"reasoning_effort": "low"} if "generativelanguage" in url else {})})
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except Exception as e:  # try next provider
                last = e
    raise RuntimeError(f"All LLM providers failed: {last}")
