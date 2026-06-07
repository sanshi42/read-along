from __future__ import annotations

import hashlib


def generate_material_id(source_type: str, source_uri: str) -> str:
    """根据来源类型和 URI 生成稳定的材料 ID。

    ID 具有确定性：相同的 (source_type, source_uri) 始终生成相同的材料 ID，
    因此可以在开始提取内容前安全计算。
    """
    key = f"{source_type}\x00{source_uri}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:8]
    return f"mat_{digest}"


def generate_paragraph_id(material_id: str, index: int) -> str:
    """生成材料范围内按索引排序的段落 ID。

    ID 中包含材料 ID 以保证全局唯一，并包含补零索引，使同一材料中的段落 ID
    按字典序比较时能够自然排序。
    """
    if index < 0:
        raise ValueError(f"段落索引必须为非负数，实际为 {index}")
    return f"{material_id}_p_{index:05d}"


def generate_sentence_id(material_id: str, index: int) -> str:
    """生成材料范围内按索引排序的句子 ID。

    格式与段落 ID 相同，但考虑到预期句子数量更多，使用更宽的补零位数。
    """
    if index < 0:
        raise ValueError(f"句子索引必须为非负数，实际为 {index}")
    return f"{material_id}_s_{index:07d}"
