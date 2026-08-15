"""
Shared defensive JSON extraction for AI responses that were prompted to
return "only JSON."

Originally lived in app.campaigns.generation_service (Week 4); moved here
when app.content.repurpose_service (Week 5) needed the identical logic,
so both JSON-mode generation flows in this app share one implementation
rather than maintaining two copies that could quietly drift apart.
"""
import json
import re


def extract_json_object(raw_text: str) -> dict:
    """
    Defensive JSON extraction. Handles the common failure modes of asking
    an LLM for "only JSON":
    1. Clean JSON (the happy path) - parsed directly.
    2. JSON wrapped in a markdown code fence (```json ... ```) - fence
       stripped, then parsed.
    3. JSON with leading/trailing prose ("Here's your result: {...}") -
       the first {...} balanced region is extracted via a bracket-matching
       scan (not just the first '{' to the last '}', which would break if
       the model added trailing prose after the object) and parsed.
    Raises json.JSONDecodeError (uncaught here, deliberately - callers
    wrap this in their own domain error with the raw text attached for
    debugging) if none of these recover a valid object.
    """
    text = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found in response", text, 0)

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise json.JSONDecodeError("Unbalanced braces in response", text, start)
