from __future__ import annotations

import re
from re import Match


SUPERSCRIPT = str.maketrans(
    "0123456789+-=()ni",
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ",
)
SUBSCRIPT = str.maketrans(
    "0123456789+-=()aehijklmnoprstx",
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜₓ",
)


def _translate_or_keep(value: str, table: dict[int, str]) -> str | None:
    translated = value.translate(table)
    return translated if all(ord(character) > 127 or character.isspace() for character in translated) else None


def _replace(match: Match[str], table: dict[int, str]) -> str:
    value = match.group(1)
    return _translate_or_keep(value, table) or match.group(0)


def normalize_unicode_scripts(text: str) -> str:
    """Normalize explicit HTML/LaTeX script notation when every glyph is safe.

    Bare ``_`` and ``^`` notation is intentionally left alone because those
    characters are also common in identifiers and prose. The model prompt is
    responsible for recognizing chemical formulae such as H2O; this function
    only makes explicit script markup paste cleanly into Word.
    """
    normalized = re.sub(
        r"<sup>\s*([^<>]+?)\s*</sup>",
        lambda match: _replace(match, SUPERSCRIPT),
        text,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"<sub>\s*([^<>]+?)\s*</sub>",
        lambda match: _replace(match, SUBSCRIPT),
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\^\{([^{}]+)\}", lambda match: _replace(match, SUPERSCRIPT), normalized)
    normalized = re.sub(r"_\{([^{}]+)\}", lambda match: _replace(match, SUBSCRIPT), normalized)
    return normalized
