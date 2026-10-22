"""Maintain the static language variants from English and the reviewed text catalogue.

Authoring helper only: requires the already-installed beautifulsoup4 package.
The public build and CI validators remain dependency-free. Paths are script-relative.
Use --seed-legacy once to import the existing translations from the production baseline.
Use --missing to list new English strings requiring translation, then run without flags.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, Doctype, NavigableString

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "10_Working/site-translations.json"
BASELINE = "7ccf3b5514fc741380aed037156a8235057831d9"
ASSET_VERSION = "20261022-multilingual"
LANGUAGES = ("en", "it", "fr", "de", "ja", "zh")
HTML_LANG = {"en": "en-GB", "it": "it", "fr": "fr", "de": "de", "ja": "ja", "zh": "zh-Hans"}
LANGUAGE_NAMES = {"en": "English", "it": "Italiano", "fr": "Français", "de": "Deutsch", "ja": "日本語", "zh": "简体中文"}
FLAGS = {"en": "🇬🇧", "it": "🇮🇹", "fr": "🇫🇷", "de": "🇩🇪", "ja": "🇯🇵", "zh": "🇨🇳"}
PAGES = ("index.html", "services.html", "aidea.html", "review-innovation-excellence-a7c29e.html", "tools.html", "about.html", "contact.html", "privacy.html", "sharewise/index.html")
TRANSLATED_ATTRIBUTES = ("alt", "aria-label", "title", "placeholder")
META_TEXT = {"description", "og:title", "og:description", "og:image:alt", "twitter:title", "twitter:description", "twitter:image:alt"}
JSON_TEXT = {"name", "description", "jobTitle", "serviceType"}
UNCHANGED = set(LANGUAGE_NAMES.values()) | set(LANGUAGES) | set(FLAGS.values()) | {
    "ALPINNO", "GmbH", "ALPINNO GmbH", "AIdea™", "Innovation Excellence", "ShareWise",
    "Pier Paolo Monticone", "Pier Paolo Monticone, PhD", "Rowan Gibson", "Imagination Bridge",
    "LinkedIn", "PhD ETH", "MAS ETH MTEC", "PMP", "11 / 1000", "AI", "ETH Zurich",
    "CorWave", "270", "The 4 Lenses of Innovation", "Rowan Gibson · Wiley",
    "info@alpinno-solutions.ch", "EN", "IT", "FR", "DE", "JA", "ZH",
    "linkedin.com/in/pierpaolomonticone", "© 2026 ALPINNO GmbH.",
}


def normalise(value: str) -> str:
    return " ".join(value.split())


def is_text(node) -> bool:
    return isinstance(node, NavigableString) and not isinstance(node, (Comment, Doctype)) and node.parent.name not in {"script", "style"} and bool(normalise(str(node)))


def route(source: str, language: str) -> str:
    if language == "en":
        return source
    if source == "index.html":
        return language + ".html"
    if source == "sharewise/index.html":
        return "sharewise/" + language + ".html"
    return source[:-5] + "-" + language + ".html"


def canonical(source: str, language: str) -> str:
    path = route(source, language)
    return "https://alpinno-solutions.ch/" + ("" if path == "index.html" else "sharewise/" if path == "sharewise/index.html" else path)


def strings(soup):
    yield from (normalise(str(node)) for node in soup.find_all(string=is_text))
    for node in soup.find_all(True):
        for attribute in TRANSLATED_ATTRIBUTES:
            if node.get(attribute):
                yield normalise(node[attribute])
        if node.name == "meta" and (node.get("name") or node.get("property")) in META_TEXT:
            yield normalise(node.get("content", ""))
    for script in soup.select('script[type="application/ld+json"]'):
        yield from json_strings(json.loads(script.string or "{}"))


def json_strings(value):
    if isinstance(value, list):
        for item in value:
            yield from json_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in JSON_TEXT and isinstance(item, str):
                yield normalise(item)
            else:
                yield from json_strings(item)


def unchanged(value: str) -> bool:
    return value in UNCHANGED or not value or bool(re.fullmatch(r"[\d\s:/–+%×.,…↗↔↓→©®™-]+", value)) or value.startswith(("https://", "http://"))


def read_baseline(path: str):
    return BeautifulSoup(subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=ROOT).decode("utf-8"), "html.parser")


def seed_legacy():
    catalogue = {"source_language": "en", "languages": list(LANGUAGES), "translations": {}}
    text_map = catalogue["translations"]

    def add(source, target, language):
        source, target = normalise(source), normalise(target)
        if source and target and source != target and not unchanged(source):
            text_map.setdefault(source, {})[language] = target

    def pair(source, target, language):
        left = source.find_all(string=is_text, recursive=False)
        right = target.find_all(string=is_text, recursive=False)
        if len(left) == len(right):
            for a, b in zip(left, right):
                add(str(a), str(b), language)
        for attribute in TRANSLATED_ATTRIBUTES:
            if source.get(attribute) and target.get(attribute):
                add(source[attribute], target[attribute], language)
        # Match within each parent by tag and ordinal. Japanese punctuation can
        # change text-node counts without changing the enclosing content structure.
        counts = {}
        for child in source.find_all(True, recursive=False):
            index = counts.get(child.name, 0); counts[child.name] = index + 1
            alternatives = target.find_all(child.name, recursive=False)
            if index < len(alternatives):
                pair(child, alternatives[index], language)

    english_home = read_baseline("index.html")
    # The last English-only launch added an offering link absent from legacy locales.
    for link in english_home.select('#services a[href^="review-innovation-excellence"]'):
        link.decompose()
    for language in LANGUAGES[1:]:
        old_home = read_baseline(language + ".html")
        for selector in ("#services", "#AIdea", "#engagements", "#founder", "#contact", "footer", ".consent-banner"):
            pair(english_home.select_one(selector), old_home.select_one(selector), language)
        for source in ("privacy.html", "sharewise/index.html"):
            pair(read_baseline(source).select_one("main"), read_baseline(route(source, language)).select_one("main"), language)
        # Reuse existing localised metadata where the English meaning is unchanged.
        for source in ("index.html", "privacy.html", "sharewise/index.html"):
            en, local = read_baseline(source), read_baseline(route(source, language))
            for meta in en.select("meta[name], meta[property]"):
                attribute = "name" if meta.has_attr("name") else "property"
                other = local.find("meta", attrs={attribute: meta[attribute]})
                if meta[attribute] in META_TEXT and other:
                    add(meta.get("content", ""), other.get("content", ""), language)
        print(f"Imported legacy {language}")
    CATALOGUE.write_text(json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def translated(value: str, language: str, catalogue: dict) -> str:
    text = normalise(value)
    if language == "en" or unchanged(text):
        return value
    result = catalogue.get(text, {}).get(language)
    if result is None:
        raise ValueError(f"Missing {language} translation: {text}")
    leading = value[:len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()):]
    return leading + result + trailing


def local_link(value: str, source: str, language: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return value
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), parsed.path))
    if target in {".", "sharewise"}:
        target = "index.html" if target == "." else "sharewise/index.html"
    if target not in PAGES:
        return value
    relative = posixpath.relpath(route(target, language), posixpath.dirname(route(source, language)) or ".")
    return urlunsplit(("", "", relative, parsed.query, parsed.fragment))


def local_json(value, source, language, catalogue, key=""):
    if isinstance(value, dict):
        return {k: local_json(v, source, language, catalogue, k) for k, v in value.items()}
    if isinstance(value, list):
        return [local_json(v, source, language, catalogue, key) for v in value]
    if isinstance(value, str):
        if key == "inLanguage":
            return HTML_LANG[language]
        if key in JSON_TEXT:
            return translated(value, language, catalogue)
        if value.startswith("https://alpinno-solutions.ch/"):
            parsed = urlsplit(value)
            path = parsed.path.lstrip("/") or "index.html"
            if path in PAGES and parsed.fragment != "organisation":
                return canonical(path, language) + ("#" + parsed.fragment if parsed.fragment else "")
    return value


def serialize(soup):
    text = soup.decode(formatter="minimal")
    text = re.sub(r'(<(?:area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)\b[^>]*?)\s*/>', r"\1>", text)
    text = re.sub(r'\s(required|open|hidden|muted|playsinline|defer|controls|disabled|default)=""', r" \1", text)
    text = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", text)
    return text


def render(source: str, source_html: str, language: str, catalogue: dict):
    soup = BeautifulSoup(source_html, "html.parser")
    soup.html["lang"] = HTML_LANG[language]
    soup.body["data-locale-suffix"] = "" if language == "en" else "-" + language
    for option in soup.select('#contact-form select[name="topic"] option'):
        if not option.has_attr("value"):
            option["value"] = option.get_text(strip=True)
    for script in soup.select('script[type="application/ld+json"]'):
        script.string = "\n" + json.dumps(local_json(json.loads(script.string), source, language, catalogue), ensure_ascii=False, indent=2) + "\n"
    for node in list(soup.find_all(string=is_text)):
        node.replace_with(translated(str(node), language, catalogue))
    for node in soup.find_all(True):
        for attribute in TRANSLATED_ATTRIBUTES:
            if node.get(attribute):
                node[attribute] = translated(node[attribute], language, catalogue)
        if node.name == "meta" and (node.get("name") or node.get("property")) in META_TEXT:
            node["content"] = translated(node.get("content", ""), language, catalogue)
        if node.get("href"):
            node["href"] = local_link(node["href"], source, language)
        for attribute in ("href", "src"):
            if node.get(attribute):
                parsed = urlsplit(node[attribute])
                if posixpath.basename(parsed.path) in {"site-layout.css", "site.js", "innovation-excellence.css", "innovation-excellence.js"}:
                    node[attribute] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "v=" + ASSET_VERSION, parsed.fragment))
    soup.find("link", rel="canonical")["href"] = canonical(source, language)
    og_url = soup.find("meta", property="og:url")
    if og_url:
        og_url["content"] = canonical(source, language)
    for old in soup.select('link[rel="alternate"][hreflang]'):
        old.decompose()
    for code in (*LANGUAGES, "x-default"):
        link = soup.new_tag("link", rel="alternate", hreflang=HTML_LANG[code] if code != "x-default" else code, href=canonical(source, "en" if code == "x-default" else code))
        soup.head.append(link)
        soup.head.append("\n")
    nav = soup.select_one(".site-navigation")
    for old in nav.select(".language-menu, .site-language-label"):
        old.decompose()
    menu = soup.new_tag("details", attrs={"class": "language-menu"})
    summary = soup.new_tag("summary", attrs={"aria-label": translated("Choose language", language, catalogue)})
    flag = soup.new_tag("span", attrs={"aria-hidden": "true"}); flag.string = FLAGS[language]
    label = soup.new_tag("span"); label.string = language.upper()
    summary.extend([flag, label]); menu.append(summary)
    listing = soup.new_tag("ul")
    for code in LANGUAGES:
        href = posixpath.relpath(route(source, code), posixpath.dirname(route(source, language)) or ".")
        link = soup.new_tag("a", href=href, lang=HTML_LANG[code])
        if code == language:
            link["aria-current"] = "page"
        flag = soup.new_tag("span", attrs={"aria-hidden": "true"}); flag.string = FLAGS[code]
        link.extend([flag, " " + LANGUAGE_NAMES[code]])
        item = soup.new_tag("li"); item.append(link); listing.append(item)
    menu.append(listing); nav.append(menu)
    for locale in soup.select('input[name="locale"]'):
        locale["value"] = language
    return serialize(soup)


def update_sitemap():
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    xhtml = "http://www.w3.org/1999/xhtml"
    ET.register_namespace("", namespace); ET.register_namespace("xhtml", xhtml)
    root = ET.Element("{" + namespace + "}urlset")
    for source in PAGES:
        if source.startswith("sharewise/"):
            continue  # ShareWise retains its existing noindex instruction.
        for language in LANGUAGES:
            entry = ET.SubElement(root, "{" + namespace + "}url")
            ET.SubElement(entry, "{" + namespace + "}loc").text = canonical(source, language)
            ET.SubElement(entry, "{" + namespace + "}lastmod").text = "2026-10-22"
            for code in (*LANGUAGES, "x-default"):
                ET.SubElement(entry, "{" + xhtml + "}link", rel="alternate", hreflang=HTML_LANG[code] if code != "x-default" else code, href=canonical(source, "en" if code == "x-default" else code))
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(ROOT / "sitemap.xml", encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--seed-legacy", action="store_true"); parser.add_argument("--missing", action="store_true")
    args = parser.parse_args()
    if args.seed_legacy:
        if CATALOGUE.exists():
            raise ValueError("Translation catalogue already exists; refusing to replace reviewed translations")
        seed_legacy(); return
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))["translations"]
    sources = {name: (ROOT / name).read_text(encoding="utf-8") for name in PAGES}
    missing = {}
    for name, html in sources.items():
        for text in strings(BeautifulSoup(html, "html.parser")):
            absent = [lang for lang in LANGUAGES[1:] if lang not in catalogue.get(text, {})]
            if not unchanged(text) and absent:
                missing.setdefault(text, {"languages": absent, "pages": []})["pages"].append(name)
    if missing:
        if args.missing:
            print(json.dumps(missing, ensure_ascii=False, indent=2)); return
        raise ValueError(f"{len(missing)} strings require translation; run --missing")
    if args.missing:
        print("All translatable strings covered in all six languages."); return
    # Render every page before writing any, preventing partial output on missing text.
    output = {route(source, lang): render(source, html, lang, catalogue) for source, html in sources.items() for lang in LANGUAGES}
    for name, html in output.items():
        (ROOT / name).write_text(html, encoding="utf-8")
    update_sitemap()
    print(f"Updated {len(output)} language pages and reciprocal sitemap links.")


if __name__ == "__main__":
    main()
