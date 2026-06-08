from __future__ import annotations

import hashlib


def generate_material_id(content_hash: str) -> str:
    """根据结构化正文哈希生成稳定的材料 ID。"""
    return f'mat_{content_hash[:16]}'


def generate_source_id(source_type: str, source_key: str) -> str:
    """根据来源类型和稳定来源键生成来源身份 ID。"""
    key = f'{source_type}\x00{source_key}'
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f'src_{digest}'


def generate_paragraph_id(material_id: str, index: int) -> str:
    """生成材料范围内按索引排序的段落 ID。

    ID 中包含材料 ID 以保证全局唯一，并包含补零索引，使同一材料中的段落 ID
    按字典序比较时能够自然排序。
    """
    if index < 0:
        raise ValueError(f'段落索引必须为非负数，实际为 {index}')
    return f'{material_id}_p_{index:05d}'


def generate_sentence_id(material_id: str, index: int) -> str:
    """生成材料范围内按索引排序的句子 ID。

    格式与段落 ID 相同，但考虑到预期句子数量更多，使用更宽的补零位数。
    """
    if index < 0:
        raise ValueError(f'句子索引必须为非负数，实际为 {index}')
    return f'{material_id}_s_{index:07d}'
