from __future__ import annotations

import math
import os
import stat
import subprocess
from pathlib import Path

import pytest

from read_along import tts
from read_along.tts import MacOSSayTTS, TTSGenerationError


def write_wav(path: Path, payload: bytes = b'audio') -> None:
    size = 4 + len(payload)
    path.write_bytes(b'RIFF' + size.to_bytes(4, 'little') + b'WAVE' + payload)


def executable(tmp_path: Path) -> Path:
    command = tmp_path / 'say'
    command.write_text('#!/bin/sh\n')
    command.chmod(0o700)
    return command


def configured_tts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MacOSSayTTS:
    command = executable(tmp_path)
    monkeypatch.setattr(tts.sys, 'platform', 'darwin')
    return MacOSSayTTS(command=command)


def successful_run(
    args: list[str],
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    write_wav(Path(args[2]))
    return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')


def test_generate_creates_private_pcm_wav_from_standard_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = executable(tmp_path)
    output_path = tmp_path / 'sentence.wav'
    captured: dict[str, object] = {}

    def fake_run(
        args: list[str],
        *,
        input: str,
        stdout: int,
        stderr: int,
        text: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured.update(
            args=args,
            input=input,
            stdout=stdout,
            stderr=stderr,
            text=text,
            timeout=timeout,
            check=check,
        )
        write_wav(Path(args[2]))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')

    monkeypatch.setattr(tts.sys, 'platform', 'darwin')
    monkeypatch.setattr(tts.subprocess, 'run', fake_run)

    result = MacOSSayTTS(command=command, timeout=12.5).generate('  忠实正文。  ', output_path)

    args = captured['args']
    assert isinstance(args, list)
    temporary_path = Path(args[2])
    assert result == output_path
    assert args == [
        str(command.resolve()),
        '--output-file',
        str(temporary_path),
        '--file-format=WAVE',
        '--data-format=LEI16@22050',
        '--input-file=-',
    ]
    assert temporary_path.parent == tmp_path
    assert temporary_path.name.startswith('.sentence.')
    assert captured['input'] == '  忠实正文。  '
    assert captured['stdout'] == subprocess.DEVNULL
    assert captured['stderr'] == subprocess.PIPE
    assert captured['text'] is True
    assert captured['timeout'] == 12.5
    assert captured['check'] is True
    assert output_path.read_bytes().startswith(b'RIFF')
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    assert list(tmp_path.glob('.sentence.*.wav')) == []


@pytest.mark.parametrize(
    ('source_text', 'tts_input'),
    [
        ('演过《奋斗》里的华子。', '演过 奋斗 里的华子。'),
        ('和“伟大的灵魂都是雌雄同体”是一个意思。', '和 伟大的灵魂都是雌雄同体 是一个意思。'),
    ],
)
def test_generate_normalizes_wrapping_punctuation_before_running_say(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_text: str,
    tts_input: str,
) -> None:
    command = executable(tmp_path)
    output_path = tmp_path / 'sentence.wav'
    captured: dict[str, object] = {}

    def fake_run(
        args: list[str],
        *,
        input: str,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured['input'] = input
        write_wav(Path(args[2]))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')

    monkeypatch.setattr(tts.sys, 'platform', 'darwin')
    monkeypatch.setattr(tts.subprocess, 'run', fake_run)

    MacOSSayTTS(command=command).generate(source_text, output_path)

    assert captured['input'] == tts_input


@pytest.mark.parametrize('timeout', [0, -1, math.inf, math.nan])
def test_constructor_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match='TTS 生成超时必须是大于零的有限数值'):
        MacOSSayTTS(timeout=timeout)


def test_is_available_requires_macos_regular_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = tmp_path / 'say'
    adapter = MacOSSayTTS(command=command)

    monkeypatch.setattr(tts.sys, 'platform', 'linux')
    assert adapter.is_available() is False

    monkeypatch.setattr(tts.sys, 'platform', 'darwin')
    assert adapter.is_available() is False

    command.mkdir()
    assert adapter.is_available() is False

    command.rmdir()
    command.write_text('#!/bin/sh\n')
    command.chmod(0o600)
    assert adapter.is_available() is False

    command.chmod(0o700)
    assert adapter.is_available() is True


def test_is_available_resolves_default_command_for_each_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = executable(tmp_path)
    found: str | None = None
    monkeypatch.setattr(tts.sys, 'platform', 'darwin')
    monkeypatch.setattr(tts.shutil, 'which', lambda name: found)
    adapter = MacOSSayTTS()

    assert adapter.is_available() is False

    found = str(command)

    assert adapter.is_available() is True


def test_generate_rejects_blank_sentence_before_running_say(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    monkeypatch.setattr(tts.subprocess, 'run', lambda *args, **kwargs: pytest.fail('不应运行 say'))

    with pytest.raises(TTSGenerationError, match='句子文本不能为空'):
        adapter.generate(' \n\t ', tmp_path / 'sentence.wav')


def test_generate_rejects_non_wav_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    with pytest.raises(TTSGenerationError, match=r'目标音频路径必须使用 \.wav 扩展名'):
        adapter.generate('正文。', tmp_path / 'sentence.aiff')


def test_generate_rejects_existing_target_without_modifying_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    output_path = tmp_path / 'sentence.wav'
    output_path.write_bytes(b'existing')

    with pytest.raises(TTSGenerationError, match='目标音频已存在'):
        adapter.generate('正文。', output_path)

    assert output_path.read_bytes() == b'existing'


def test_generate_rejects_broken_target_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    output_path = tmp_path / 'sentence.wav'
    output_path.symlink_to(tmp_path / 'missing.wav')

    with pytest.raises(TTSGenerationError, match='目标音频已存在'):
        adapter.generate('正文。', output_path)

    assert output_path.is_symlink()


@pytest.mark.parametrize('parent_kind', ['missing', 'file'])
def test_generate_rejects_invalid_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    parent_kind: str,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    parent = tmp_path / 'parent'
    if parent_kind == 'file':
        parent.write_text('not a directory')

    with pytest.raises(TTSGenerationError, match='目标音频父目录不存在或不是目录'):
        adapter.generate('正文。', parent / 'sentence.wav')


def test_generate_reports_non_macos_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts.sys, 'platform', 'linux')

    with pytest.raises(TTSGenerationError, match='当前系统不是 macOS'):
        MacOSSayTTS(command=executable(tmp_path)).generate('正文。', tmp_path / 'sentence.wav')


def test_generate_reports_unavailable_say_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tts.sys, 'platform', 'darwin')

    with pytest.raises(TTSGenerationError, match='当前系统无法使用 macOS say 命令'):
        MacOSSayTTS(command=tmp_path / 'missing').generate('正文。', tmp_path / 'sentence.wav')


def test_generate_cleans_temporary_file_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    def time_out(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=args,
            timeout=60,
            output='不可暴露的 stdout',
            stderr='不可暴露的 stderr',
        )

    monkeypatch.setattr(tts.subprocess, 'run', time_out)

    with pytest.raises(TTSGenerationError, match='macOS say 生成音频超时') as error:
        adapter.generate('不可暴露的正文。', tmp_path / 'sentence.wav')

    assert '不可暴露' not in str(error.value)
    assert list(tmp_path.glob('.sentence.*.wav')) == []


def test_generate_reports_limited_normalized_say_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    diagnostic = '  音色   不可用\n' + ('错' * 600)

    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args,
            output='不可暴露的 stdout',
            stderr=diagnostic,
        )

    monkeypatch.setattr(tts.subprocess, 'run', fail)

    with pytest.raises(TTSGenerationError) as error:
        adapter.generate('不可暴露的正文。', tmp_path / 'sentence.wav')

    message = str(error.value)
    detail = message.removeprefix('macOS say 生成音频失败：')
    assert message.startswith('macOS say 生成音频失败：音色 不可用 ')
    assert '\n' not in message
    assert len(detail) == 500
    assert detail.endswith('…')
    assert '不可暴露' not in message
    assert list(tmp_path.glob('.sentence.*.wav')) == []


def test_generate_uses_generic_error_when_say_has_no_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=args, stderr=' \n ')

    monkeypatch.setattr(tts.subprocess, 'run', fail)

    with pytest.raises(TTSGenerationError, match=r'^macOS say 生成音频失败。$'):
        adapter.generate('正文。', tmp_path / 'sentence.wav')


def test_generate_redacts_sentence_from_say_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    sentence = '不可暴露的正文。'

    def fail(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args,
            stderr=f'无法朗读：{sentence}',
        )

    monkeypatch.setattr(tts.subprocess, 'run', fail)

    with pytest.raises(TTSGenerationError) as error:
        adapter.generate(sentence, tmp_path / 'sentence.wav')

    assert sentence not in str(error.value)
    assert '[正文已隐藏]' in str(error.value)


def test_generate_reports_command_disappearing_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    def disappear(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(tts.subprocess, 'run', disappear)

    with pytest.raises(TTSGenerationError, match='macOS say 命令在生成音频前不可用'):
        adapter.generate('正文。', tmp_path / 'sentence.wav')


@pytest.mark.parametrize('content', [b'', b'not a wav'])
def test_generate_rejects_invalid_wav_and_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    def write_invalid(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        Path(args[2]).write_bytes(content)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')

    monkeypatch.setattr(tts.subprocess, 'run', write_invalid)

    with pytest.raises(TTSGenerationError, match='macOS say 未生成有效的 WAV 音频'):
        adapter.generate('正文。', tmp_path / 'sentence.wav')

    assert not (tmp_path / 'sentence.wav').exists()
    assert list(tmp_path.glob('.sentence.*.wav')) == []


def test_generate_does_not_overwrite_target_created_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    output_path = tmp_path / 'sentence.wav'

    def create_competing_target(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        write_wav(Path(args[2]))
        output_path.write_bytes(b'concurrent')
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')

    monkeypatch.setattr(tts.subprocess, 'run', create_competing_target)

    with pytest.raises(TTSGenerationError, match='目标音频已存在'):
        adapter.generate('正文。', output_path)

    assert output_path.read_bytes() == b'concurrent'
    assert list(tmp_path.glob('.sentence.*.wav')) == []


def test_generate_wraps_temporary_file_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)

    def fail_temporary_file(*args: object, **kwargs: object) -> None:
        raise PermissionError('不可写')

    monkeypatch.setattr(tts, 'NamedTemporaryFile', fail_temporary_file)

    with pytest.raises(TTSGenerationError, match='无法创建临时音频文件'):
        adapter.generate('正文。', tmp_path / 'sentence.wav')


def test_generate_wraps_final_file_creation_failure_and_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = configured_tts(tmp_path, monkeypatch)
    monkeypatch.setattr(tts.subprocess, 'run', successful_run)

    def fail_link(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        follow_symlinks: bool = True,
    ) -> None:
        raise PermissionError('不可写')

    monkeypatch.setattr(tts.os, 'link', fail_link)

    with pytest.raises(TTSGenerationError, match='无法保存生成的 WAV 音频'):
        adapter.generate('正文。', tmp_path / 'sentence.wav')

    assert list(tmp_path.glob('.sentence.*.wav')) == []
