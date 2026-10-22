"""Run dependency-free structural checks for the ALPINNO static website."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
HTML_FILES = tuple(sorted((*PROJECT_ROOT.glob("*.html"), *PROJECT_ROOT.glob("sharewise/*.html"))))
TEXT_EXTENSIONS = {".html", ".css", ".txt", ".xml", ".js", ".json"}
PLACEHOLDER_MARKER = "REPLACE_WITH_"
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PUBLIC_CONTACT_EMAIL = "info@alpinno-solutions.ch"
SITE_LANGUAGES = ("en", "it", "fr", "de", "ja", "zh")
HTML_LANGUAGES = {"en": "en-GB", "it": "it", "fr": "fr", "de": "de", "ja": "ja", "zh": "zh-Hans"}


def page_variant(name: str, language: str) -> str:
    if language == "en":
        return name
    if name == "index.html":
        return language + ".html"
    if name == "sharewise/index.html":
        return "sharewise/" + language + ".html"
    return name.removesuffix(".html") + "-" + language + ".html"


def page_canonical(name: str, language: str) -> str:
    name = page_variant(name, language)
    return "https://alpinno-solutions.ch/" + ("" if name == "index.html" else "sharewise/" if name == "sharewise/index.html" else name)


class SiteHTMLParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids: list[str] = []
        self.references: list[tuple[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self.h1_count = 0
        self.primary_links: list[dict[str, str]] = []
        self.canonicals: list[str] = []
        self.language = ""
        self.alternates: list[tuple[str, str]] = []
        self.language_links: list[dict[str, str]] = []
        self.robots: list[str] = []
        self._in_primary_navigation = False
        self._json_ld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "html":
            self.language = values.get("lang", "")
        if tag == "meta" and values.get("name") == "robots":
            self.robots.append(values.get("content", ""))
        if tag == "h1":
            self.h1_count += 1
        if tag == "nav" and "site-navigation" in values.get("class", "").split():
            self._in_primary_navigation = True
        if tag == "a" and self._in_primary_navigation and "brand" not in values.get("class", "").split() and "lang" not in values:
            self.primary_links.append(values)
        if tag == "a" and self._in_primary_navigation and "lang" in values:
            self.language_links.append(values)
        if tag == "link" and "canonical" in values.get("rel", "").split():
            self.canonicals.append(values.get("href", ""))
        if tag == "link" and "alternate" in values.get("rel", "").split() and values.get("hreflang"):
            self.alternates.append((values["hreflang"], values.get("href", "")))
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
        if tag == "nav":
            self._in_primary_navigation = False
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

    navigation_pages = (
        "index.html", "services.html", "aidea.html",
        "review-innovation-excellence-a7c29e.html", "tools.html", "about.html", "contact.html",
    )
    site_pages = navigation_pages + ("privacy.html", "sharewise/index.html")
    for source in site_pages:
        for language in SITE_LANGUAGES:
            name = page_variant(source, language)
            path = (PROJECT_ROOT / name).resolve()
            page = parsed_pages.get(path)
            if page is None:
                errors.append(f"Missing {language} site page: {name}")
                continue
            prefix = "../" if name.startswith("sharewise/") else ""
            if [link.get("href") for link in page.primary_links] != [prefix + page_variant(item, language) for item in navigation_pages]:
                errors.append(f"{name}: primary navigation must stay in the chosen language")
            if page.h1_count != 1:
                errors.append(f"{name}: expected one H1")
            if page.language != HTML_LANGUAGES[language]:
                errors.append(f"{name}: incorrect HTML language declaration")
            if page.canonicals != [page_canonical(source, language)]:
                errors.append(f"{name}: expected one self-referencing canonical")
            current = [link for link in page.primary_links if link.get("aria-current")]
            expected_current = prefix + page_variant("tools.html", language) if source.startswith("sharewise/") else name
            if source != "privacy.html" and (len(current) != 1 or current[0].get("href") != expected_current):
                errors.append(f"{name}: primary navigation must identify the current page or section")
            expected_alternates = [(HTML_LANGUAGES[code], page_canonical(source, code)) for code in SITE_LANGUAGES] + [("x-default", page_canonical(source, "en"))]
            if sorted(page.alternates) != sorted(expected_alternates):
                errors.append(f"{name}: expected reciprocal alternates for all six language versions")
            expected_languages = [(HTML_LANGUAGES[code], posixpath.relpath(page_variant(source, code), posixpath.dirname(name) or ".")) for code in SITE_LANGUAGES]
            if [(link.get("lang"), link.get("href")) for link in page.language_links] != expected_languages:
                errors.append(f"{name}: language switch must keep visitors on the corresponding page")
            directives = {item.strip() for item in page.robots[0].lower().split(",")} if len(page.robots) == 1 else set()
            if source.startswith("sharewise/"):
                if "noindex" not in directives:
                    errors.append(f"{name}: preserve the existing ShareWise noindex setting")
            elif not {"index", "follow"}.issubset(directives):
                errors.append(f"{name}: public page must permit indexing and following")
            if source != "privacy.html" and ("href", "mailto:" + PUBLIC_CONTACT_EMAIL) not in page.references:
                errors.append(f"{name}: missing approved direct contact email")

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
        mailto_addresses = re.findall(r'''mailto:([^\s"'<>]+)''', text)
        if any(address != PUBLIC_CONTACT_EMAIL for address in mailto_addresses):
            errors.append(f"{display}: contains an unapproved public mailto link")
        if set(EMAIL_PATTERN.findall(text)) - {PUBLIC_CONTACT_EMAIL}:
            errors.append(f"{display}: contains an unapproved public email address")
        if PLACEHOLDER_MARKER in text:
            message = f"{display}: contains an unconfigured integration placeholder"
            (errors if production else warnings).append(message)

    try:
        sitemap = ET.parse(PROJECT_ROOT / "sitemap.xml")
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "x": "http://www.w3.org/1999/xhtml"}
        entries = sitemap.findall("s:url", namespace)
        expected_urls = {page_canonical(source, language): source for source in site_pages if not source.startswith("sharewise/") for language in SITE_LANGUAGES}
        locations = [entry.findtext("s:loc", namespaces=namespace) for entry in entries]
        if len(locations) != len(set(locations)) or set(locations) != set(expected_urls):
            errors.append("sitemap.xml: list each indexable language page exactly once, preserving ShareWise noindex")
        for entry, url in zip(entries, locations):
            if url not in expected_urls:
                continue
            source = expected_urls[url]
            alternates = entry.findall("x:link", namespace)
            expected = {HTML_LANGUAGES[code]: page_canonical(source, code) for code in SITE_LANGUAGES}
            expected["x-default"] = page_canonical(source, "en")
            if len(alternates) != 7 or {link.get("hreflang"): link.get("href") for link in alternates} != expected:
                errors.append(f"sitemap.xml: missing reciprocal language links for {url}")
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
