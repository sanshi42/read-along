import pytest

from read_along.ids import (
    generate_material_id,
    generate_paragraph_id,
    generate_sentence_id,
)


# -- Material ID ------------------------------------------------------------

def test_material_id_is_deterministic() -> None:
    first = generate_material_id("url", "https://example.com/article")
    second = generate_material_id("url", "https://example.com/article")

    assert first == second


def test_material_id_differs_by_source_type() -> None:
    pdf_id = generate_material_id("pdf", "file.pdf")
    url_id = generate_material_id("url", "file.pdf")

    assert pdf_id != url_id


def test_material_id_differs_by_source_uri() -> None:
    a = generate_material_id("url", "https://a.example.com")
    b = generate_material_id("url", "https://b.example.com")

    assert a != b


def test_material_id_format() -> None:
    mid = generate_material_id("url", "https://example.com")

    assert mid.startswith("mat_")
    assert len(mid) == 12  # 'mat_' + 8 hex chars


def test_material_id_handles_unicode_uri() -> None:
    mid = generate_material_id("url", "https://例子.com/文章")

    assert mid.startswith("mat_")
    assert len(mid) == 12


# -- Paragraph ID -----------------------------------------------------------

def test_paragraph_id_is_deterministic() -> None:
    first = generate_paragraph_id("mat_a1b2c3d4", 12)
    second = generate_paragraph_id("mat_a1b2c3d4", 12)

    assert first == second


def test_paragraph_id_differs_by_material() -> None:
    a = generate_paragraph_id("mat_a1b2c3d4", 1)
    b = generate_paragraph_id("mat_z9y8x7w6", 1)

    assert a != b


def test_paragraph_id_differs_by_index() -> None:
    a = generate_paragraph_id("mat_a1b2c3d4", 0)
    b = generate_paragraph_id("mat_a1b2c3d4", 1)

    assert a != b


def test_paragraph_id_format() -> None:
    pid = generate_paragraph_id("mat_a1b2c3d4", 7)

    assert pid == "mat_a1b2c3d4_p_00007"


def test_paragraph_id_zero_index() -> None:
    assert generate_paragraph_id("mat_a1b2c3d4", 0) == "mat_a1b2c3d4_p_00000"


def test_paragraph_id_large_index() -> None:
    pid = generate_paragraph_id("mat_a1b2c3d4", 99999)

    assert pid == "mat_a1b2c3d4_p_99999"


def test_paragraph_id_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        generate_paragraph_id("mat_a1b2c3d4", -1)


# -- Sentence ID ------------------------------------------------------------

def test_sentence_id_is_deterministic() -> None:
    first = generate_sentence_id("mat_a1b2c3d4", 256)
    second = generate_sentence_id("mat_a1b2c3d4", 256)

    assert first == second


def test_sentence_id_differs_by_material() -> None:
    a = generate_sentence_id("mat_a1b2c3d4", 1)
    b = generate_sentence_id("mat_z9y8x7w6", 1)

    assert a != b


def test_sentence_id_differs_by_index() -> None:
    a = generate_sentence_id("mat_a1b2c3d4", 0)
    b = generate_sentence_id("mat_a1b2c3d4", 1)

    assert a != b


def test_sentence_id_format() -> None:
    sid = generate_sentence_id("mat_a1b2c3d4", 123)

    assert sid == "mat_a1b2c3d4_s_0000123"


def test_sentence_id_zero_index() -> None:
    assert generate_sentence_id("mat_a1b2c3d4", 0) == "mat_a1b2c3d4_s_0000000"


def test_sentence_id_large_index() -> None:
    sid = generate_sentence_id("mat_a1b2c3d4", 9999999)

    assert sid == "mat_a1b2c3d4_s_9999999"


def test_sentence_id_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        generate_sentence_id("mat_a1b2c3d4", -1)


# -- Cross-entity consistency -----------------------------------------------

def test_ids_are_globally_unique() -> None:
    mid = generate_material_id("url", "https://example.com")

    paragraph_ids = {
        generate_paragraph_id(mid, i) for i in range(10)
    }
    sentence_ids = {
        generate_sentence_id(mid, i) for i in range(10)
    }

    # Material ID differs from any paragraph or sentence ID.
    assert mid not in paragraph_ids
    assert mid not in sentence_ids

    # Paragraph and sentence IDs do not overlap for the same index.
    assert not paragraph_ids & sentence_ids


def test_ids_are_non_empty_and_non_numeric() -> None:
    mid = generate_material_id("pdf", "example.pdf")
    pid = generate_paragraph_id(mid, 0)
    sid = generate_sentence_id(mid, 0)

    for identifier in (mid, pid, sid):
        assert len(identifier) > 0
        assert not identifier.isdigit()
