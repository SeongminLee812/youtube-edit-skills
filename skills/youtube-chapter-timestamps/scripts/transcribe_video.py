#!/usr/bin/env python3
"""Extract audio from a local media file and transcribe it with whisper.cpp."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


DEFAULT_MODEL = Path(os.environ.get("WHISPER_MODEL") or "~/.codex/models/whisper/ggml-small.bin").expanduser()


def executable(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise SystemExit(
            f"Missing executable: {name}. Install ffmpeg and whisper.cpp only after user authorization."
        )
    return found


def run(command: list[str]) -> None:
    printable = " ".join(command[:2])
    print(f"Running: {printable} ...", file=sys.stderr)
    subprocess.run(command, check=True)


def probe_duration(ffprobe: str, source: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Local video or audio file")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--language", default="ko")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-len", type=int, default=45)
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use GPU. CPU is the default because Metal allocation can fail on constrained hosts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Source media not found: {source}")

    model_arg = args.model or os.environ.get("WHISPER_MODEL") or DEFAULT_MODEL
    model = Path(model_arg).expanduser().resolve()
    if not model.is_file():
        raise SystemExit(
            f"Whisper model not found: {model}\n"
            "Pass --model or set WHISPER_MODEL after obtaining a multilingual GGML model with user authorization."
        )

    ffmpeg = executable("ffmpeg")
    ffprobe = executable("ffprobe")
    whisper = executable("whisper-cli")

    output_dir = (args.output_dir or source.with_name(f"{source.stem}_transcript")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_base = output_dir / source.stem
    duration = probe_duration(ffprobe, source)

    wav_handle = tempfile.NamedTemporaryFile(
        prefix="youtube-chapters-", suffix=".wav", dir=output_dir, delete=False
    )
    wav_path = Path(wav_handle.name)
    wav_handle.close()

    try:
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ]
        )
        command = [
            whisper,
            "-m",
            str(model),
            "-l",
            args.language,
            "-f",
            str(wav_path),
            "-ojf",
            "-osrt",
            "-otxt",
            "-of",
            str(output_base),
            "--split-on-word",
            "--max-len",
            str(args.max_len),
            "--threads",
            str(args.threads),
        ]
        if not args.gpu:
            command.append("--no-gpu")
        if args.prompt:
            command.extend(["--prompt", args.prompt])
        run(command)
    finally:
        wav_path.unlink(missing_ok=True)

    metadata = {
        "source": str(source),
        "duration_seconds": duration,
        "language": args.language,
        "model": str(model),
        "transcript_base": str(output_base),
    }
    metadata_path = output_dir / f"{source.stem}.metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

