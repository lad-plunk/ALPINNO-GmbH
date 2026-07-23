"""Run dependency-free structural checks for the ALPINNO static website."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
HTML_FILES = tuple(sorted(PROJECT_ROOT.glob("*.html")))
TEXT_EXTENSIONS = {".html", ".css", ".txt", ".xml", ".js", ".json"}
PLACEHOLDER_MARKER = "REPLACE_WITH_"
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


class SiteHTMLParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self._json_ld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        for name in ("href", "src", "poster", "action"):
            if values.get(name):
                self.references.append((name, values[name]))
        if values.get("srcset"):
            for candidate in values["srcset"].split(","):
                self.references.append(("srcset", candidate.strip().split()[0]))
        if tag == "img":
            self.images.append(values)
        if tag == "script" and values.get("type") == "application/ld+json":
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_parts is not None:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_ld_parts is not None:
            self.json_ld.append("".join(self._json_ld_parts))
            self._json_ld_parts = None


def parse_html(path: Path) -> SiteHTMLParser:
    parser = SiteHTMLParser(path)
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def local_target(source: Path, value: str) -> tuple[Path, str] | None:
    if PLACEHOLDER_MARKER in value:
        return None
    if value.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        if value.startswith("#"):
            return source, unquote(value[1:])
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    target_path = unquote(parsed.path)
    if not target_path:
        target = source
    elif target_path.endswith("/"):
        target = (source.parent / target_path / "index.html").resolve()
    else:
        target = (source.parent / target_path).resolve()
    return target, unquote(parsed.fragment)


def validate(production: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    parsed_pages = {path.resolve(): parse_html(path) for path in HTML_FILES}

    for path, parser in parsed_pages.items():
        display = path.relative_to(PROJECT_ROOT)
        duplicate_ids = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        if duplicate_ids:
            errors.append(f"{display}: duplicate IDs: {', '.join(duplicate_ids)}")

        for image in parser.images:
            missing = [name for name in ("src", "alt", "width", "height") if name not in image]
            if missing:
                errors.append(f"{display}: image is missing {', '.join(missing)}: {image.get('src', '<unknown>')}")

        for payload in parser.json_ld:
            try:
                json.loads(payload)
            except json.JSONDecodeError as exc:
                errors.append(f"{display}: invalid JSON-LD: {exc}")

        for attribute, value in parser.references:
            resolved = local_target(path, value)
            if resolved is None:
                continue
            target, fragment = resolved
            if not target.exists():
                errors.append(f"{display}: broken local {attribute} reference: {value}")
                continue
            if fragment:
                target_page = parsed_pages.get(target.resolve())
                if target_page is None and target.suffix.lower() == ".html":
                    target_page = parse_html(target)
                if target_page is not None and fragment not in target_page.ids:
                    errors.append(f"{display}: missing fragment #{fragment} in {target.name}")

    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "_site" in path.parts:
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8")
        display = path.relative_to(PROJECT_ROOT)
        if "\u2014" in text:
            errors.append(f"{display}: contains an em dash")
        if "mailto:" in text:
            errors.append(f"{display}: contains a public mailto link")
        if EMAIL_PATTERN.search(text):
            errors.append(f"{display}: contains a public email address")
        if PLACEHOLDER_MARKER in text:
            message = f"{display}: contains an unconfigured integration placeholder"
            (errors if production else warnings).append(message)

    try:
        ET.parse(PROJECT_ROOT / "sitemap.xml")
    except (ET.ParseError, FileNotFoundError) as exc:
        errors.append(f"sitemap.xml: invalid or missing: {exc}")

    robots = PROJECT_ROOT / "robots.txt"
    if not robots.is_file() or "Sitemap:" not in robots.read_text(encoding="utf-8"):
        errors.append("robots.txt: missing sitemap declaration")

    required_public_files = {
        "index.html",
        "privacy.html",
        "404.html",
        "robots.txt",
        "sitemap.xml",
        "llms.txt",
        "CNAME",
    }
    missing_public_files = sorted(name for name in required_public_files if not (PROJECT_ROOT / name).is_file())
    if missing_public_files:
        errors.append(f"Missing public files: {', '.join(missing_public_files)}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        action="store_true",
        help="Treat unconfigured third-party integration placeholders as errors.",
    )
    args = parser.parse_args()
    errors, warnings = validate(production=args.production)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Validation failed with {len(errors)} error(s).")
        return 1
    print(f"Validation passed for {len(HTML_FILES)} HTML file(s) with {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
