import pytest

from read_along.ids import (
    generate_material_id,
    generate_paragraph_id,
    generate_sentence_id,
    generate_source_id,
)

# -- 材料 ID ---------------------------------------------------------------


def test_material_id_is_deterministic() -> None:
    first = generate_material_id('a' * 64)
    second = generate_material_id('a' * 64)

    assert first == second


def test_material_id_differs_by_content_hash() -> None:
    a = generate_material_id('a' * 64)
    b = generate_material_id('b' * 64)

    assert a != b


def test_material_id_format() -> None:
    mid = generate_material_id('a' * 64)

    assert mid.startswith('mat_')
    assert len(mid) == 20  # 'mat_' + 16 个十六进制字符


def test_source_id_is_deterministic() -> None:
    first = generate_source_id('url', 'https://example.com/article')
    second = generate_source_id('url', 'https://example.com/article')

    assert first == second
    assert first.startswith('src_')


# -- 段落 ID ---------------------------------------------------------------


def test_paragraph_id_is_deterministic() -> None:
    first = generate_paragraph_id('mat_a1b2c3d4', 12)
    second = generate_paragraph_id('mat_a1b2c3d4', 12)

    assert first == second


def test_paragraph_id_differs_by_material() -> None:
    a = generate_paragraph_id('mat_a1b2c3d4', 1)
    b = generate_paragraph_id('mat_z9y8x7w6', 1)

    assert a != b


def test_paragraph_id_differs_by_index() -> None:
    a = generate_paragraph_id('mat_a1b2c3d4', 0)
    b = generate_paragraph_id('mat_a1b2c3d4', 1)

    assert a != b


def test_paragraph_id_format() -> None:
    pid = generate_paragraph_id('mat_a1b2c3d4', 7)

    assert pid == 'mat_a1b2c3d4_p_00007'


def test_paragraph_id_zero_index() -> None:
    assert generate_paragraph_id('mat_a1b2c3d4', 0) == 'mat_a1b2c3d4_p_00000'


def test_paragraph_id_large_index() -> None:
    pid = generate_paragraph_id('mat_a1b2c3d4', 99999)

    assert pid == 'mat_a1b2c3d4_p_99999'


def test_paragraph_id_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match='必须为非负数'):
        generate_paragraph_id('mat_a1b2c3d4', -1)


# -- 句子 ID ---------------------------------------------------------------


def test_sentence_id_is_deterministic() -> None:
    first = generate_sentence_id('mat_a1b2c3d4', 256)
    second = generate_sentence_id('mat_a1b2c3d4', 256)

    assert first == second


def test_sentence_id_differs_by_material() -> None:
    a = generate_sentence_id('mat_a1b2c3d4', 1)
    b = generate_sentence_id('mat_z9y8x7w6', 1)

    assert a != b


def test_sentence_id_differs_by_index() -> None:
    a = generate_sentence_id('mat_a1b2c3d4', 0)
    b = generate_sentence_id('mat_a1b2c3d4', 1)

    assert a != b


def test_sentence_id_format() -> None:
    sid = generate_sentence_id('mat_a1b2c3d4', 123)

    assert sid == 'mat_a1b2c3d4_s_0000123'


def test_sentence_id_zero_index() -> None:
    assert generate_sentence_id('mat_a1b2c3d4', 0) == 'mat_a1b2c3d4_s_0000000'


def test_sentence_id_large_index() -> None:
    sid = generate_sentence_id('mat_a1b2c3d4', 9999999)

    assert sid == 'mat_a1b2c3d4_s_9999999'


def test_sentence_id_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match='必须为非负数'):
        generate_sentence_id('mat_a1b2c3d4', -1)


# -- 跨实体一致性 ----------------------------------------------------------


def test_ids_are_globally_unique() -> None:
    mid = generate_material_id('a' * 64)

    paragraph_ids = {generate_paragraph_id(mid, i) for i in range(10)}
    sentence_ids = {generate_sentence_id(mid, i) for i in range(10)}

    # 材料 ID 与任意段落或句子 ID 均不相同。
    assert mid not in paragraph_ids
    assert mid not in sentence_ids

    # 相同索引下的段落和句子 ID 不重叠。
    assert not paragraph_ids & sentence_ids


def test_ids_are_non_empty_and_non_numeric() -> None:
    mid = generate_material_id('a' * 64)
    pid = generate_paragraph_id(mid, 0)
    sid = generate_sentence_id(mid, 0)

    for identifier in (mid, pid, sid):
        assert len(identifier) > 0
        assert not identifier.isdigit()
