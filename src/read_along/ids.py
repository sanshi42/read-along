from __future__ import annotations

import hashlib


def generate_material_id(source_type: str, source_uri: str) -> str:
    """Generate a stable material ID from source type and URI.

    The ID is deterministic: the same (source_type, source_uri) always
    produces the same material ID, making it safe to compute before
    content extraction begins.
    """
    key = f"{source_type}\x00{source_uri}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:8]
    return f"mat_{digest}"


def generate_paragraph_id(material_id: str, index: int) -> str:
    """Generate a paragraph ID scoped to a material and ordered by index.

    The ID embeds the material for global uniqueness and a zero-padded
    index so paragraphs sort naturally when IDs are compared
    lexicographically within the same material.
    """
    if index < 0:
        raise ValueError(f"Paragraph index must be non-negative, got {index}")
    return f"{material_id}_p_{index:05d}"


def generate_sentence_id(material_id: str, index: int) -> str:
    """Generate a sentence ID scoped to a material and ordered by index.

    Same pattern as paragraph IDs, with wider padding for the larger
    expected sentence count.
    """
    if index < 0:
        raise ValueError(f"Sentence index must be non-negative, got {index}")
    return f"{material_id}_s_{index:07d}"
