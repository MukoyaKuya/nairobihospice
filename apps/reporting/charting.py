"""
Helpers for embedding JSON payloads inside Django templates' <script> blocks.

Django's autoescaping does not apply inside <script>, and json.dumps() leaves
``<``, ``>``, ``&`` and the Unicode line separators unescaped — a free-text
value (e.g. a patient's primary diagnosis) could otherwise break out of the
script tag. chart_json() renders those characters as \\uXXXX escapes, which
decode to identical values in JavaScript but cannot terminate a script block.
"""
import json

_SCRIPT_UNSAFE = (
    ('<', '\\u003c'),
    ('>', '\\u003e'),
    ('&', '\\u0026'),
    ('\u2028', '\\u2028'),
    ('\u2029', '\\u2029'),
)


def chart_json(data) -> str:
    """Serialize data to JSON that is safe to render with |safe inside a script tag."""
    rendered = json.dumps(data, default=str)
    for character, escape in _SCRIPT_UNSAFE:
        rendered = rendered.replace(character, escape)
    return rendered
