"""Build the public GitHub Pages artifact from repository source files."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WINDOWS_SCRATCH_ROOT = Path("C:/CodexSandboxOfficeQA/onedrive-safe-scratch/alpinno-website-build")
DEFAULT_OUTPUT_DIR = WINDOWS_SCRATCH_ROOT if sys.platform == "win32" else PROJECT_ROOT / "_site"
PUBLIC_FILES = (
    "index.html",
    "privacy.html",
    "404.html",
    "style.css",
    "robots.txt",
    "sitemap.xml",
    "llms.txt",
    "CNAME",
)
PUBLIC_DIRECTORIES = ("images",)


def build(clean: bool, output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    allowed_output_dirs = {
        (PROJECT_ROOT / "_site").resolve(),
        WINDOWS_SCRATCH_ROOT.resolve(),
    }
    if output_dir not in allowed_output_dirs:
        raise ValueError(f"Unsafe build output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for relative_name in PUBLIC_FILES:
        source = PROJECT_ROOT / relative_name
        if not source.is_file():
            raise FileNotFoundError(f"Required public file is missing: {relative_name}")
        shutil.copy2(source, output_dir / relative_name)

    for relative_name in PUBLIC_DIRECTORIES:
        source = PROJECT_ROOT / relative_name
        destination = output_dir / relative_name
        if not source.is_dir():
            raise FileNotFoundError(f"Required public directory is missing: {relative_name}")
        shutil.copytree(source, destination, dirs_exist_ok=True)

    file_count = sum(1 for path in output_dir.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file())
    print(f"Built {file_count} files in {output_dir}")
    print(f"Artifact size: {total_bytes / (1024 * 1024):.2f} MiB")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the previous generated artifact before building.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Build destination. Defaults outside OneDrive on Windows and to _site elsewhere.",
    )
    args = parser.parse_args()
    build(clean=args.clean, output_dir=args.output)


if __name__ == "__main__":
    main()
