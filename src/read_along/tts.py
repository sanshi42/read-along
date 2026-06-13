from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

DIAGNOSTIC_LIMIT = 500
WAV_HEADER_SIZE = 12


class TTSGenerationError(RuntimeError):
    """单句音频生成失败。"""


class MacOSSayTTS:
    """使用 macOS say 命令生成单句 WAV 音频。"""

    def __init__(self, *, command: str | Path | None = None, timeout: float = 60.0) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('TTS 生成超时必须是大于零的有限数值')
        self.command = Path(command) if command is not None else None
        self.timeout = timeout

    def is_available(self) -> bool:
        """返回当前环境是否可使用 macOS say。"""
        return self._available_command() is not None

    def generate(self, text: str, output_path: Path) -> Path:
        """为单个句子生成 WAV 音频。"""
        output_path = Path(output_path)
        self._validate_request(text, output_path)
        command = self._command_for_generation()
        temporary_path = self._create_temporary_path(output_path)

        try:
            self._run_say(command, text, temporary_path)
            self._validate_wav(temporary_path)
            self._publish(temporary_path, output_path)
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

        return output_path

    def _validate_request(self, text: str, output_path: Path) -> None:
        if not text.strip():
            raise TTSGenerationError('句子文本不能为空。')
        if output_path.suffix.lower() != '.wav':
            raise TTSGenerationError('目标音频路径必须使用 .wav 扩展名。')
        if os.path.lexists(output_path):
            raise TTSGenerationError(f'目标音频已存在：{output_path}')
        if not output_path.parent.is_dir():
            raise TTSGenerationError(f'目标音频父目录不存在或不是目录：{output_path.parent}')

    def _command_for_generation(self) -> Path:
        if sys.platform != 'darwin':
            raise TTSGenerationError('当前系统不是 macOS，无法使用 say 生成音频。')
        command = self._available_command()
        if command is None:
            raise TTSGenerationError('当前系统无法使用 macOS say 命令。')
        return command

    def _create_temporary_path(self, output_path: Path) -> Path:
        try:
            with NamedTemporaryFile(
                dir=output_path.parent,
                prefix=f'.{output_path.stem}.',
                suffix='.wav',
                delete=False,
            ) as temporary_file:
                return Path(temporary_file.name)
        except OSError as exc:
            raise TTSGenerationError('无法创建临时音频文件。') from exc

    def _run_say(self, command: Path, text: str, temporary_path: Path) -> None:
        args = [
            str(command),
            '--output-file',
            str(temporary_path),
            '--file-format=WAVE',
            '--data-format=LEI16@22050',
            '--input-file=-',
        ]
        try:
            subprocess.run(
                args,
                input=text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout,
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise TTSGenerationError('macOS say 生成音频超时。') from exc
        except subprocess.CalledProcessError as exc:
            detail = _clean_diagnostic(exc.stderr, sensitive_text=text)
            message = f'macOS say 生成音频失败：{detail}' if detail else 'macOS say 生成音频失败。'
            raise TTSGenerationError(message) from exc
        except FileNotFoundError as exc:
            raise TTSGenerationError('macOS say 命令在生成音频前不可用。') from exc
        except OSError as exc:
            raise TTSGenerationError('无法运行 macOS say 命令。') from exc

    def _validate_wav(self, temporary_path: Path) -> None:
        try:
            with temporary_path.open('rb') as audio_file:
                header = audio_file.read(WAV_HEADER_SIZE)
        except OSError as exc:
            raise TTSGenerationError('无法读取 macOS say 生成的音频。') from exc
        if len(header) < WAV_HEADER_SIZE or header[:4] != b'RIFF' or header[8:12] != b'WAVE':
            raise TTSGenerationError('macOS say 未生成有效的 WAV 音频。')

    def _publish(self, temporary_path: Path, output_path: Path) -> None:
        try:
            temporary_path.chmod(0o600)
            os.link(temporary_path, output_path, follow_symlinks=False)
        except FileExistsError as exc:
            raise TTSGenerationError(f'目标音频已存在：{output_path}') from exc
        except OSError as exc:
            raise TTSGenerationError('无法保存生成的 WAV 音频。') from exc

    def _available_command(self) -> Path | None:
        if sys.platform != 'darwin':
            return None
        command = self.command or (Path(found) if (found := shutil.which('say')) else None)
        if command is None or not command.is_file() or not os.access(command, os.X_OK):
            return None
        return command.resolve()


def _clean_diagnostic(stderr: str | None, *, sensitive_text: str) -> str:
    diagnostic = ' '.join((stderr or '').split())
    normalized_sensitive_text = ' '.join(sensitive_text.split())
    if normalized_sensitive_text:
        diagnostic = diagnostic.replace(normalized_sensitive_text, '[正文已隐藏]')
    if len(diagnostic) <= DIAGNOSTIC_LIMIT:
        return diagnostic
    return f'{diagnostic[: DIAGNOSTIC_LIMIT - 1]}…'
