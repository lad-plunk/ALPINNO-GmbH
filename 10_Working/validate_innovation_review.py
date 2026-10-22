"""Check Innovation Excellence content, branding and public indexing eligibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_site import INNOVATION_FILES, PUBLIC_FILES, PUBLIC_SHAREWISE_FILES
from validate_site import PROJECT_ROOT


@dataclass
class Element:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Element | str] = field(default_factory=list)

    def find(self, tag: str = "", class_name: str = "", element_id: str = "") -> list[Element]:
        matches = []
        for child in self.children:
            if isinstance(child, Element):
                if ((not tag or child.tag == tag)
                    and (not class_name or class_name in child.attrs.get("class", "").split())
                    and (not element_id or child.attrs.get("id") == element_id)):
                    matches.append(child)
                matches.extend(child.find(tag, class_name, element_id))
        return matches

    def text(self) -> str:
        return " ".join(child.text() if isinstance(child, Element) else child for child in self.children)


class DocumentParser(HTMLParser):
    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.document = Element("document")
        self.stack = [self.document]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(element)
        if tag not in self.VOID_ELEMENTS:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def validate(root: Path, artifact: bool) -> list[str]:
    errors: list[str] = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    page_name = next(name for name in INNOVATION_FILES if name.endswith(".html"))
    record = json.loads((PROJECT_ROOT / "10_Working" / "innovation-review-release.json").read_text(encoding="utf-8"))
    public_url = record["public_url"]
    page_path = root / page_name
    if not page_path.is_file():
        return [f"Missing Innovation Excellence page: {page_name}"]
    html = page_path.read_text(encoding="utf-8")
    document = DocumentParser(html).document
    text = " ".join(document.text().split())
    heads = document.find("head")
    robots = [meta for head in heads for meta in head.find("meta") if meta.attrs.get("name", "").lower() == "robots"]
    check(len(robots) == 1 and {"index", "follow"}.issubset(set(robots[0].attrs.get("content", "").lower().replace(" ", "").split(","))), "Public HTML head must permit index and follow")
    for head in heads:
        for meta in head.find("meta"):
            if "name" in meta.attrs:
                directives = set(re.split(r"[\s,]+", meta.attrs.get("content", "").lower()))
                check(not {"noindex", "nofollow", "none"} & directives, "No crawler-specific meta tag may block public indexing or following")
    canonicals = [link for head in heads for link in head.find("link") if "canonical" in link.attrs.get("rel", "").split()]
    check(len(canonicals) == 1 and canonicals[0].attrs.get("href") == public_url, "Public page must have one self-referencing canonical")
    expected_alternates = {"en-GB": public_url, "x-default": public_url}
    for language in ("it", "fr", "de", "ja", "zh"):
        expected_alternates["zh-Hans" if language == "zh" else language] = public_url.removesuffix(".html") + "-" + language + ".html"
    alternate_links = [link for head in heads for link in head.find("link") if "alternate" in link.attrs.get("rel", "").split()]
    check(len(alternate_links) == 7 and {link.attrs.get("hreflang"): link.attrs.get("href") for link in alternate_links} == expected_alternates, "Advertise only the six real language variants and the default English page")
    for language in ("it", "fr", "de", "ja", "zh"):
        translated_path = root / (page_name.removesuffix(".html") + "-" + language + ".html")
        check(translated_path.is_file(), f"Missing translated offering: {language}")
        if not translated_path.is_file():
            continue
        translated = DocumentParser(translated_path.read_text(encoding="utf-8")).document
        check(len(translated.find("h1")) == 1, f"Translated offering must have one H1: {language}")
        english_times = [cell.text().strip() for panel in document.find(class_name="ie-day-panel") for cell in panel.find("th")]
        translated_times = [cell.text().strip() for panel in translated.find(class_name="ie-day-panel") for cell in panel.find("th")]
        check(english_times == translated_times, f"Translated workshop must preserve all agenda times: {language}")
        check(len(translated.find(class_name="ie-process-flow")) == 1 and len(translated.find(class_name="ie-stage-panel")) == 3, f"Translated offering must preserve the method and three stages: {language}")
        check([image.attrs.get("src") for image in translated.find("img")] == [image.attrs.get("src") for image in document.find("img")], f"Translated offering must reuse the approved images: {language}")
    check(len(document.find("h1")) == 1, "Innovation Excellence page must have one H1")
    check(not document.find(class_name="ie-review-strip") and not re.search(r"review draft|not published|awaiting approval|proposed collaboration", text, re.I), "Public page must have no review or approval-pending copy")
    titles = document.find("title")
    check(len(titles) == 1 and "ALPINNO" in titles[0].text() and "Rowan Gibson" in titles[0].text(), "Public title must identify ALPINNO's offering with Rowan Gibson")
    metadata = {meta.attrs.get("property", meta.attrs.get("name")): meta.attrs.get("content", "") for head in heads for meta in head.find("meta")}
    check(metadata.get("og:url") == public_url and "ALPINNO" in metadata.get("og:title", "") and "ALPINNO-led" in metadata.get("description", "") and "Rowan Gibson" in metadata.get("description", "") and metadata.get("og:description") == metadata.get("description"), "Public description and social metadata must describe the ALPINNO-led offering")
    check(document.find("html")[0].attrs.get("lang") == "en-GB", "Preserve the page's English language declaration")
    webpage_data = [json.loads(script.text()) for script in document.find("script") if script.attrs.get("type") == "application/ld+json"]
    check(any(item.get("@type") == "WebPage" and item.get("url") == public_url and item.get("@id") == public_url + "#webpage" for item in webpage_data), "WebPage structured data must use the public canonical URL")
    partner_links = [link for link in document.find("a") if "Imagination Bridge" in link.text()]
    check(bool(partner_links) and all(link.attrs.get("href") == "https://imaginationbridge.com/" for link in partner_links), "Partner-name and logo links must use the official Imagination Bridge homepage")
    check("Founder & President," in text and "Imagination Bridge" in text, "Preserve Rowan's approved Imagination Bridge affiliation")
    check("Founder & Managing Director," in text, "Identify Pier's ALPINNO leadership role")
    check(not document.find(class_name="ie-partner-lockup"), "Remove the joint-brand hero lockup")
    check("An ALPINNO-led offering, delivered in collaboration with Rowan Gibson." in text, "Make ALPINNO ownership explicit")
    check(not re.search(r"joint[ -]venture|exclusive partnership|guaranteed patents|guaranteed returns", text, re.I), "Do not add legal-entity, exclusivity or performance promises")
    if not record["public_launch"]["deliberate_zatory_product_mentions"]:
        check(not re.search(r"\bzatory\b", html, re.I), "No partner-brand references to Zatory are expected on this page")
    method = "Based on Rowan’s Four Lenses of Innovation. All four lenses remain fully applicable; their implementation is redesigned to leverage big data and AI, moving from an analogue approach to a digital, AI-enabled workflow."
    check(method in text, "Required Four Lenses method statement changed")
    check(not re.search(r"\b(?:EUR|USD|CHF|20[ ,]?000|70[ ,]?000)\b|€", text), "Public page must not contain internal prices")
    check(not document.find("form"), "Enquiries must reuse the existing contact form")
    ctas = document.find("a", class_name="ie-button")
    check(bool(ctas) and all(link.attrs.get("href") == "contact.html?topic=Innovation%20Excellence%20with%20Rowan%20Gibson#contact-form" for link in ctas), "Every enquiry button must use the ALPINNO contact page and select the offering")

    def portrait_order(class_name):
        groups = document.find(class_name=class_name)
        return [Path(image.attrs.get("src", "")).name for image in groups[0].find("img") if Path(image.attrs.get("src", "")).name in {"rowan-gibson.jpg", "pier-paolo-monticone.jpg"}] if groups else []

    check(portrait_order("ie-portrait-pair") == ["rowan-gibson.jpg", "pier-paolo-monticone.jpg"], "Hero portrait order must be Rowan, Pier")
    profiles = document.find(class_name="ie-expert-grid")
    check(bool(profiles) and not profiles[0].find("img"), "Lower biographies must not repeat portraits or partner logos")
    check(bool(profiles) and [node.attrs.get("class", "").split()[-1] for node in profiles[0].find("article")] == ["ie-expert-pier", "ie-expert-rowan"], "Lower text profile order must remain Pier, Rowan")
    check([node.text().strip() for node in document.find(class_name="ie-image-marker")] == ["01", "02", "03"], "Metaphor labels must remain editable HTML")

    stage_lists = document.find(class_name="ie-stage-list")
    stages = [node for node in stage_lists[0].children if isinstance(node, Element) and node.tag == "details"] if stage_lists else []
    check([node.attrs.get("id") for node in stages] == ["workshop", "validate", "scale"], "Expected three independent stages in order")
    check(all("name" not in node.attrs and "open" not in node.attrs for node in stages), "Stages must start closed and remain independently expandable")
    days = stages[0].find("details", class_name="ie-day-panel") if stages else []
    check(len(days) == 2 and len(document.find(class_name="ie-day-panel")) == 2, "Both agenda disclosures must be nested inside Strategize")
    workshop_minutes = 0
    for day_number, day in enumerate(days, 1):
        previous_end = 9 * 60
        lunch_minutes = executive_minutes = 0
        rows = day.find("tr")
        for row in rows:
            headers = row.find("th")
            times = re.fullmatch(r"\s*(\d\d):(\d\d)–(\d\d):(\d\d)\s*", headers[0].text()) if headers else None
            if not times:
                errors.append(f"Day {day_number}: invalid agenda time")
                continue
            hour1, minute1, hour2, minute2 = map(int, times.groups())
            start, end = hour1 * 60 + minute1, hour2 * 60 + minute2
            check(start == previous_end and end > start, f"Day {day_number}: agenda gap, overlap or invalid interval")
            previous_end = end
            duration = end - start
            if "Lunch" in row.text():
                lunch_minutes += duration
            else:
                workshop_minutes += duration
            if "ie-executive" in row.attrs.get("class", "").split():
                executive_minutes += duration
        check(len(rows) == 7 and previous_end == 18 * 60 and lunch_minutes == 60 and executive_minutes == 90, f"Day {day_number}: preserve 09:00-18:00, one-hour lunch and 90-minute executive participation")
    check(workshop_minutes == 960, "Workshop must total 16 hours excluding lunch")
    flows = document.find(class_name="ie-process-flow")
    steps = flows[0].find("li") if flows else []
    check(len(steps) == 7 and "Explore domains" in steps[2].text() and "Find triggers" in steps[3].text(), "Seven-step workflow must put domains before triggers")
    check("1–3 prioritised draft innovation briefs" in text and "THREE-MONTH PILOT · ONE BRIEF" in text and "subject to the brief, search and specialist IP review" in text, "Workshop outputs, one-brief pilot and target qualifications must remain explicit")
    check("targeted deployment" in text and "broader transformation" in text and "does not automatically include a full enterprise transformation" in text, "Preserve Scale scope qualifications")

    for relative_name, expected_hash in record["content_assets_sha256"].items():
        asset = root / relative_name
        check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == expected_hash, f"Asset must match its approved source bytes: {relative_name}")
    png = root / "images" / "innovation-excellence" / "innovation-ai-agile-metaphor.png"
    if png.is_file():
        header = png.read_bytes()[:26]
        check(header[:8] == b"\x89PNG\r\n\x1a\n" and header[16:20] == header[20:24] and header[25] == 6, "Metaphor must remain a square RGBA PNG")

    homepage_path = root / "index.html"
    if homepage_path.is_file():
        homepage = DocumentParser(homepage_path.read_text(encoding="utf-8")).document
        homepage_links = [link for link in homepage.find("a") if Path(unquote(urlsplit(link.attrs.get("href", "")).path)).name == page_name]
        check(any("Innovation Excellence" in link.text() and "Rowan Gibson" in link.text() for link in homepage_links), "Homepage must visibly link to ALPINNO's offering with Rowan Gibson")
    else:
        errors.append("Missing public homepage")
    try:
        sitemap = ET.parse(root / "sitemap.xml")
        locations = [node.text for node in sitemap.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        check(locations.count(public_url) == 1, "Sitemap must list the public canonical URL exactly once")
    except (ET.ParseError, FileNotFoundError) as error:
        errors.append(f"Invalid sitemap: {error}")
    llms_path = root / "llms.txt"
    check(llms_path.is_file() and llms_path.read_text(encoding="utf-8").count(public_url) == 1, "Existing llms page directory must list the public canonical URL once")
    robots_path = root / "robots.txt"
    if robots_path.is_file():
        for line in robots_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            value = value.split("#", 1)[0].strip()
            if key.strip().lower() == "disallow" and value:
                check(not ("/" + page_name).startswith(value), "robots.txt must allow crawling the public collaboration page")
    if artifact:
        allowed = set(PUBLIC_FILES) | {"sharewise/" + name for name in PUBLIC_SHAREWISE_FILES}
        unexpected = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.relative_to(root).parts[0] != "images" and path.relative_to(root).as_posix() not in allowed]
        check(not unexpected, f"Non-public files in artifact: {unexpected}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", type=Path, help="Built artifact root; defaults to the repository for source checks")
    args = parser.parse_args()
    root = args.site_root.resolve() if args.site_root else PROJECT_ROOT
    errors = validate(root, artifact=args.site_root is not None)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Innovation Excellence validation failed with {len(errors)} error(s).")
        return 1
    print("Innovation Excellence content, branding, agenda, assets and public discovery checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
