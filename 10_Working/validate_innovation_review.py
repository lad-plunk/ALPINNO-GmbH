"""Check review content, asset identity and discovery restrictions without dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from build_site import PUBLIC_FILES, PUBLIC_SHAREWISE_FILES, REVIEW_FILES
from validate_site import PROJECT_ROOT, parse_html


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

    review_name = next(name for name in REVIEW_FILES if name.endswith(".html"))
    record = json.loads((PROJECT_ROOT / "10_Working" / "innovation-review-release.json").read_text(encoding="utf-8"))
    review_path = root / review_name
    if not review_path.is_file():
        return [f"Missing review page: {review_name}"]
    html = review_path.read_text(encoding="utf-8")
    document = DocumentParser(html).document
    text = " ".join(document.text().split())
    heads = document.find("head")
    robots = [meta for head in heads for meta in head.find("meta") if meta.attrs.get("name", "").lower() == "robots"]
    check(len(robots) == 1 and {"noindex", "nofollow"}.issubset(set(robots[0].attrs.get("content", "").lower().replace(" ", "").split(","))), "Review HTML head must contain one robots tag with noindex, nofollow")
    check(not any({"canonical", "alternate"} & set(link.attrs.get("rel", "").split()) for head in heads for link in head.find("link")), "Review page must have no canonical or language-alternate discovery links")
    check(len(document.find("h1")) == 1, "Review page must have one H1")
    check("REVIEW DRAFT" in text and "Not published" not in text, "Hosted review banner must be accurate")
    method = "Based on Rowan’s Four Lenses of Innovation. All four lenses remain fully applicable; their implementation is redesigned to leverage big data and AI, moving from an analogue approach to a digital, AI-enabled workflow."
    check(method in text, "Required Four Lenses method statement changed")
    check(not re.search(r"\b(?:EUR|USD|CHF|20[ ,]?000|70[ ,]?000)\b|€", text), "Public page must not contain internal prices")
    check(not document.find("form"), "Review enquiries must reuse the existing contact form")
    ctas = document.find("a", class_name="ie-button")
    check(bool(ctas) and all(link.attrs.get("href") == "https://alpinno-solutions.ch/#contact-form" for link in ctas), "Every enquiry button must use the existing contact form")

    def portrait_order(class_name):
        groups = document.find(class_name=class_name)
        return [Path(image.attrs.get("src", "")).name for image in groups[0].find("img")] if groups else []

    check(portrait_order("ie-portrait-pair") == ["rowan-gibson.jpg", "pier-paolo-monticone.jpg"], "Hero portrait order must be Rowan, Pier")
    check(portrait_order("ie-expert-grid") == ["pier-paolo-monticone.jpg", "rowan-gibson.jpg"], "Lower profile order must be Pier, Rowan")
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
        check(asset.is_file() and hashlib.sha256(asset.read_bytes()).hexdigest() == expected_hash, f"Asset must match supplied V3 bytes: {relative_name}")
    png = root / "images" / "innovation-excellence" / "innovation-ai-agile-metaphor.png"
    if png.is_file():
        header = png.read_bytes()[:26]
        check(header[:8] == b"\x89PNG\r\n\x1a\n" and header[16:20] == header[20:24] and header[25] == 6, "Metaphor must remain a square RGBA PNG")

    public_html = [name for name in PUBLIC_FILES if name.endswith(".html")]
    public_html += ["sharewise/" + name for name in PUBLIC_SHAREWISE_FILES if name.endswith(".html")]
    for relative_name in public_html:
        path = root / relative_name
        if path == review_path or not path.is_file():
            continue
        for _, reference in parse_html(path).references:
            check(Path(unquote(urlsplit(reference).path)).name != review_name, f"Public inbound review link in {relative_name}")
    for name in PUBLIC_FILES:
        if Path(name).suffix in {".txt", ".xml", ".json", ".rss", ".atom"} and (root / name).is_file():
            check(review_name not in (root / name).read_text(encoding="utf-8"), f"Review route exposed in public discovery file: {name}")
    robots_path = root / "robots.txt"
    if robots_path.is_file():
        for line in robots_path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            value = value.split("#", 1)[0].strip()
            if key.strip().lower() == "disallow" and value:
                check(not ("/" + review_name).startswith(value), "robots.txt must allow crawling the review robots directive")
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
        print(f"Review validation failed with {len(errors)} error(s).")
        return 1
    print("Review content, agenda, assets, noindex and discovery checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
