"""阅读材料 API 视图装配。"""

from __future__ import annotations

import sqlite3

from read_along.material_errors import MaterialLibraryError
from read_along.models import (
    Material,
    MaterialDetail,
    MaterialNavigation,
    MaterialNavigationItem,
    MaterialSummary,
    ParagraphDetail,
    PlaybackPosition,
    PlaybackTimePosition,
    Sentence,
)
from read_along.playback_position import playback_time_position as derive_playback_time_position
from read_along.repository import Repository


class MaterialViewBuilder:
    """从 repository rows 装配阅读材料响应模型。"""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def summary(
        self,
        connection: sqlite3.Connection,
        material: Material,
    ) -> MaterialSummary:
        """装配书架材料摘要。"""
        sources = self.repository.list_sources(connection, material.id)
        if not sources or not sources[0].is_primary:
            raise MaterialLibraryError('阅读材料缺少主来源')
        progress = self.repository.get_progress(connection, material.id)
        return MaterialSummary(
            **material.model_dump(),
            primary_source=sources[0],
            progress=progress,
            playback_position=self.playback_position(connection, material.id),
            playback_time_position=self.playback_time_position(connection, material.id),
        )

    def detail(
        self,
        connection: sqlite3.Connection,
        material: Material,
    ) -> MaterialDetail:
        """装配单篇阅读材料详情。"""
        sources = self.repository.list_sources(connection, material.id)
        if not sources or not sources[0].is_primary:
            raise MaterialLibraryError('阅读材料缺少主来源')

        sentences_by_paragraph: dict[str, list[Sentence]] = {}
        for sentence in self.repository.list_sentences(connection, material.id):
            sentences_by_paragraph.setdefault(sentence.paragraph_id, []).append(sentence)
        paragraphs = [
            ParagraphDetail(
                **paragraph.model_dump(),
                sentences=sentences_by_paragraph.get(paragraph.id, []),
            )
            for paragraph in self.repository.list_paragraphs(connection, material.id)
        ]
        return MaterialDetail(
            **material.model_dump(),
            primary_source=sources[0],
            sources=sources,
            progress=self.repository.get_progress(connection, material.id),
            playback_position=self.playback_position(connection, material.id),
            playback_time_position=self.playback_time_position(connection, material.id),
            navigation=self.navigation(connection, material.id),
            paragraphs=paragraphs,
        )

    def playback_position(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> PlaybackPosition | None:
        """装配阅读材料的句子位置。"""
        position = self.repository.get_playback_position(connection, material_id)
        if position is None:
            return None
        sentence_index, sentence_count = position
        return PlaybackPosition(
            sentence_index=sentence_index,
            sentence_count=sentence_count,
        )

    def playback_time_position(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> PlaybackTimePosition | None:
        """装配阅读材料的朗读时间位置。"""
        progress = self.repository.get_progress(connection, material_id)
        if progress is None:
            return None
        return derive_playback_time_position(
            self.repository.list_sentences(connection, material_id),
            progress,
        )

    def navigation(
        self,
        connection: sqlite3.Connection,
        material_id: str,
    ) -> MaterialNavigation:
        """按材料创建顺序装配上一篇/下一篇导航。"""
        materials = self.repository.list_materials_by_creation(connection)
        current_index = next((index for index, material in enumerate(materials) if material.id == material_id), None)
        if current_index is None:
            return MaterialNavigation(first=None, previous=None, next=None, last=None)
        first_material = materials[0] if materials else None
        last_material = materials[-1] if materials else None
        previous_material = materials[current_index - 1] if current_index > 0 else None
        next_material = materials[current_index + 1] if current_index < len(materials) - 1 else None
        return MaterialNavigation(
            first=MaterialNavigationItem.model_validate(first_material.model_dump()) if first_material else None,
            previous=(
                MaterialNavigationItem.model_validate(previous_material.model_dump()) if previous_material else None
            ),
            next=MaterialNavigationItem.model_validate(next_material.model_dump()) if next_material else None,
            last=MaterialNavigationItem.model_validate(last_material.model_dump()) if last_material else None,
        )
