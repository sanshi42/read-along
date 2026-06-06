from pathlib import Path

from read_along.config import AppConfig
from read_along.db import initialize_database
from read_along.repository import Repository
from read_along.storage import StoragePaths


def repository(tmp_path: Path) -> Repository:
    paths = StoragePaths.from_config(AppConfig(home=tmp_path / "data"))
    initialize_database(paths)
    return Repository(paths.database)


def create_material(
    repo: Repository,
    *,
    material_id: str = "mat-1",
    updated_at: str = "2026-06-06T01:00:00Z",
) -> None:
    repo.create_material(
        material_id=material_id,
        source_type="pdf",
        source_uri=f"{material_id}.pdf",
        title=f"Material {material_id}",
        status="ready",
        content_hash=f"hash-{material_id}",
        error_message=None,
        created_at="2026-06-06T00:00:00Z",
        updated_at=updated_at,
    )


def add_paragraph(
    repo: Repository,
    *,
    paragraph_id: str,
    material_id: str,
    index: int,
) -> None:
    repo.add_paragraph(
        paragraph_id=paragraph_id,
        material_id=material_id,
        index=index,
        text=f"Paragraph {index}",
        source_label=f"Page {index}",
    )


def add_sentence(
    repo: Repository,
    *,
    sentence_id: str,
    material_id: str,
    paragraph_id: str,
    index: int,
) -> None:
    repo.add_sentence(
        sentence_id=sentence_id,
        material_id=material_id,
        paragraph_id=paragraph_id,
        index=index,
        text=f"Sentence {index}.",
        audio_status="pending",
        audio_path=None,
        error_message=None,
    )


def test_materials_persist_and_list_most_recent_first(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    create_material(repo, material_id="mat-older", updated_at="2026-06-06T01:00:00Z")
    create_material(repo, material_id="mat-newer", updated_at="2026-06-06T02:00:00Z")

    reopened_repo = Repository(repo.database)

    material = reopened_repo.get_material("mat-older")
    assert material is not None
    assert material["title"] == "Material mat-older"
    assert [row["id"] for row in reopened_repo.list_materials()] == [
        "mat-newer",
        "mat-older",
    ]


def test_missing_material_and_progress_return_none(tmp_path: Path) -> None:
    repo = repository(tmp_path)

    assert repo.get_material("missing") is None
    assert repo.get_progress("missing") is None


def test_paragraphs_and_sentences_are_read_in_index_order(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    create_material(repo)
    add_paragraph(repo, paragraph_id="paragraph-2", material_id="mat-1", index=2)
    add_paragraph(repo, paragraph_id="paragraph-1", material_id="mat-1", index=1)
    add_sentence(
        repo,
        sentence_id="sentence-2",
        material_id="mat-1",
        paragraph_id="paragraph-2",
        index=2,
    )
    add_sentence(
        repo,
        sentence_id="sentence-1",
        material_id="mat-1",
        paragraph_id="paragraph-1",
        index=1,
    )

    reopened_repo = Repository(repo.database)

    assert [row["id"] for row in reopened_repo.list_paragraphs("mat-1")] == [
        "paragraph-1",
        "paragraph-2",
    ]
    assert [row["id"] for row in reopened_repo.list_sentences("mat-1")] == [
        "sentence-1",
        "sentence-2",
    ]


def test_save_progress_inserts_and_updates_single_material_progress(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    create_material(repo)
    add_paragraph(repo, paragraph_id="paragraph-1", material_id="mat-1", index=1)
    add_sentence(
        repo,
        sentence_id="sentence-1",
        material_id="mat-1",
        paragraph_id="paragraph-1",
        index=1,
    )
    add_sentence(
        repo,
        sentence_id="sentence-2",
        material_id="mat-1",
        paragraph_id="paragraph-1",
        index=2,
    )

    repo.save_progress(
        material_id="mat-1",
        sentence_id="sentence-1",
        playback_rate=1.0,
        updated_at="2026-06-06T01:00:00Z",
    )
    repo.save_progress(
        material_id="mat-1",
        sentence_id="sentence-2",
        playback_rate=1.25,
        updated_at="2026-06-06T02:00:00Z",
    )

    progress = Repository(repo.database).get_progress("mat-1")
    assert progress == {
        "material_id": "mat-1",
        "sentence_id": "sentence-2",
        "playback_rate": 1.25,
        "updated_at": "2026-06-06T02:00:00Z",
    }
