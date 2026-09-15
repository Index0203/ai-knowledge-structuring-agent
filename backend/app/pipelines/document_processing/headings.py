"""Heading detection shared by the parsers.

The knowledge map mirrors the document outline, so a parser must report the
real section hierarchy instead of a flat page list whenever it can.
"""

import re
from dataclasses import dataclass

MAX_HEADING_CHARACTERS = 80
SENTENCE_END_PUNCTUATION = ("。", "！", "？", "!", "?")
CLAUSE_PUNCTUATION = ("，", ",", "；", ";")

CHINESE_NUMBER = "一二三四五六七八九十百千万零〇两"
# OCR regularly reads 二 as "=" and 一 as "I"/"l"/"|", so those count as numerals too.
NUMBER = rf"[0-9{CHINESE_NUMBER}=Il|≡]"
BRACKETED_NUMBER = rf"[0-9{CHINESE_NUMBER}=Il|≡]{{1,3}}"

HEADING_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    # (1) / （12） list items inside a labelled block are the fourth level.
    (re.compile(r"^[（(]\s*\d{1,2}\s*[)）]\s*\S"), 4),
    # 第一章 / 第 2 篇 / 第一部分
    (re.compile(rf"^第\s*{NUMBER}+\s*[章篇部]\b"), 1),
    # 第二章第一节
    (re.compile(rf"^第\s*{NUMBER}+\s*节\b"), 2),
    # 一、xxx
    (re.compile(rf"^[（(]?[{CHINESE_NUMBER}]{{1,3}}[)）]?[、.．]\s*\S"), 2),
    # （一）xxx / （=）xxx / (三 ) xxx (OCR reads 二 as "=" and adds stray spaces)
    (re.compile(rf"^[（(]\s*{BRACKETED_NUMBER}\s*[)）]\s*\S"), 3),
    # 1.1 / 1.1.2 numbered sections
    (re.compile(r"^\d+(?:\.\d+){1,3}\s*\S{1,24}$"), 3),
    # 1. / 1、 / 1． items; a following digit means it is a decimal like `1.5 亿元`, not a heading
    (re.compile(r"^\d{1,2}\s*[.．、]\s*(?![0-9])\S"), 4),
    # Chapter 1 / Section 2
    (re.compile(r"^(?:chapter|section|part)\s+\d+\b", re.IGNORECASE), 1),
)


@dataclass(frozen=True)
class TextLine:
    """One visual line with the layout hints heading detection can use."""

    text: str
    size: float | None = None


def detect_heading_level(text: str) -> int | None:
    """Return the outline depth implied by numbering, or None."""
    candidate = text.strip()
    if not candidate or len(candidate) > MAX_HEADING_CHARACTERS:
        return None
    for pattern, level in HEADING_PATTERNS:
        if pattern.search(candidate) and not _rejected_punctuation(candidate, level):
            return level
    return None


def _rejected_punctuation(candidate: str, level: int) -> bool:
    """A sentence ending never looks like a heading; list items may end with `;`."""
    if candidate.endswith(SENTENCE_END_PUNCTUATION):
        return True
    return level < 4 and candidate.endswith(CLAUSE_PUNCTUATION)


def detect_visual_heading_level(line: TextLine, body_size: float | None) -> int | None:
    """Return a depth for lines that stand out by font size."""
    if body_size is None or line.size is None or body_size <= 0:
        return None
    candidate = line.text.strip()
    if not candidate or len(candidate) > MAX_HEADING_CHARACTERS or candidate.endswith(("。", ".", "；", ";")):
        return None
    ratio = line.size / body_size
    if ratio >= 1.6:
        return 1
    if ratio >= 1.3:
        return 2
    if ratio >= 1.15:
        return 3
    return None


def detect_level(line: TextLine, body_size: float | None) -> int | None:
    """Combine numbering and typography hints, preferring explicit numbering."""
    return detect_heading_level(line.text) or detect_visual_heading_level(line, body_size)


def extract_lines(page: object) -> list[TextLine]:
    """Read visual lines from a PyMuPDF page, including their font size."""
    raw = page.get_text("dict")  # type: ignore[attr-defined]
    lines: list[TextLine] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            size = max((float(span.get("size", 0.0)) for span in spans), default=0.0) or None
            lines.append(TextLine(text=text, size=size))
    return lines


def estimate_body_size(lines: list[TextLine]) -> float | None:
    """Most common font size, used as the baseline for visual heading detection."""
    sizes = [round(line.size, 1) for line in lines if line.size]
    if not sizes:
        return None
    counts: dict[float, int] = {}
    for size in sizes:
        counts[size] = counts.get(size, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def normalize_heading_text(text: str) -> str:
    return _repair_ocr_numbering(" ".join(text.split()))[:160]


BRACKET_NUMBERING = re.compile(rf"^([（(])({BRACKETED_NUMBER})([)）])")
OCR_NUMERAL_REPAIRS = {
    "=": "二",
    "≡": "三",
    "I": "一",
    "l": "一",
    "|": "一",
}


def _repair_ocr_numbering(text: str) -> str:
    """Turn `(=)` back into `(二)` so exported numbering matches the document."""
    match = BRACKET_NUMBERING.match(text)
    if match is None:
        return text
    number = match.group(2)
    repaired = "".join(OCR_NUMERAL_REPAIRS.get(character, character) for character in number)
    if repaired == number:
        return text
    return f"{match.group(1)}{repaired}{match.group(3)}{text[match.end():]}"


DOT_LEADER = re.compile(r"[.·…]{2,}")
PAGE_REFERENCE = re.compile(r"[-–—\s]*\d{1,4}\s*[-–—]?\s*$")
PAGE_NUMBER_LINE = re.compile(r"^[-–—\s]*\d{1,4}[-–—\s]*$")


def is_noise_line(text: str) -> bool:
    """Page numbers and dot rulers are layout, not content."""
    candidate = text.strip()
    if not candidate:
        return True
    if PAGE_NUMBER_LINE.match(candidate):
        return True
    return DOT_LEADER.sub("", candidate).strip() == ""


def looks_like_toc_entry(text: str) -> bool:
    """A heading line that also points at a page, e.g. `第二章 方法 …… 12`."""
    candidate = text.strip()
    if len(candidate) < 3:
        return False
    if DOT_LEADER.search(candidate):
        return True
    return bool(PAGE_REFERENCE.search(candidate) and detect_heading_level(candidate))


def is_table_of_contents(lines: list[TextLine]) -> bool:
    """Detect contents pages so their entries never become chapters."""
    candidates = [line for line in lines if len(line.text.strip()) >= 3]
    if len(candidates) < 3:
        return False
    toc_entries = sum(1 for line in candidates if looks_like_toc_entry(line.text))
    return toc_entries / len(candidates) >= 0.5


def dedupe_key(title: str) -> str:
    """Normalised title used to collapse repeated chapter headings."""
    cleaned = DOT_LEADER.sub("", title)
    cleaned = PAGE_REFERENCE.sub("", cleaned)
    return re.sub(r"[\s\-–—_]+", "", cleaned).lower()


# Labels the documents use as inline sub-headings, e.g. 传统发展痛点: / 赋能路径：
LABEL_HEADING = re.compile(r"^(?P<label>[\u4e00-\u9fffA-Za-z]{2,12})\s*[:：;；]\s*(?P<rest>.*)$")
KNOWN_LABELS = (
    "传统发展痛点",
    "发展痛点",
    "数字化赋能路径",
    "数智化赋能路径",
    "赋能路径",
    "数字化赋能成效",
    "数智化赋能成效",
    "赋能成效",
    "典型案例",
)
# The order these labels follow inside one section, used to repair OCR-mangled labels.
LABEL_SEQUENCE = ("传统发展痛点", "数智化赋能路径", "数智化赋能成效")
LABEL_HEADING_LEVEL = 3
NOISE_LABEL_HEADING = re.compile(
    r"^(?P<label>[A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff \t]{0,13})\s*[:：;；]\s*(?P<rest>.*)$"
)


def split_label_heading(text: str) -> tuple[str, str] | None:
    """Split `传统发展痛点: (1) ...` into its heading label and remaining body text."""
    candidate = text.strip()
    if len(candidate) > 120:
        return None
    match = LABEL_HEADING.match(candidate)
    if match is None:
        return None
    label = match.group("label").strip()
    if label not in KNOWN_LABELS:
        return None
    return label, match.group("rest").strip()


def looks_like_noise_label(text: str) -> bool:
    """True when a line is a labelled block whose label OCR mangled into noise."""
    return split_noise_label(text) is not None


def split_noise_label(text: str) -> tuple[str, str] | None:
    """Split a garbled label line, e.g. `RRR RB: (1) 知识传承: ...`."""
    candidate = text.strip()
    if len(candidate) > 120 or split_label_heading(candidate) is not None:
        return None
    match = NOISE_LABEL_HEADING.match(candidate)
    if match is None:
        return None
    label = match.group("label").strip()
    compact = label.replace(" ", "")
    if not compact:
        return None
    ascii_letters = sum(1 for character in compact if character.isascii() and character.isalpha())
    numbered_body = re.match(r"^[（(]?\d", match.group("rest")) is not None
    if ascii_letters / len(compact) >= 0.6 or numbered_body:
        return label, match.group("rest").strip()
    return None


def next_expected_label(seen_labels: set[str]) -> str | None:
    """The label this section should still contain, in document order."""
    for label in LABEL_SEQUENCE:
        if label not in seen_labels:
            return label
    return None


OUTCOME_LABEL = "数智化赋能成效"
OUTCOME_MARKERS = ("形成", "构建了", "打造", "实现", "有效")


def repair_label(seen_labels: set[str], body: str) -> str | None:
    """Choose which label a garbled label line actually is.

    Position narrows it down; the wording decides between an outline of pain points
    or paths (lists such as `(1) …`) and a description of results (`形成 …`).
    """
    expected = next_expected_label(seen_labels)
    stripped = body.lstrip()
    looks_like_outcome = stripped.startswith(OUTCOME_MARKERS) and not re.match(r"^[（(]?\d", stripped)
    if looks_like_outcome and OUTCOME_LABEL not in seen_labels:
        return OUTCOME_LABEL
    if expected in {"数智化赋能路径", "数字化赋能路径"} and looks_like_outcome:
        return OUTCOME_LABEL
    return expected


CASE_LABEL = "典型案例"
MAX_CASE_TITLE_CHARACTERS = 26


def label_title(label: str, body: str) -> str:
    """Name a repeated case-study node after its own first clause."""
    if label != CASE_LABEL:
        return label
    headline = re.split(r"[，。；;]", body.strip(), maxsplit=1)[0].strip()
    if not headline:
        return label
    return f"{label}：{headline[:MAX_CASE_TITLE_CHARACTERS]}"


# OCR adds stray spaces such as "(3 ) 长效运营层面", so the marker match is loose.
INLINE_ITEM_SPLIT = re.compile(r"(?<=[。；;：:])\s*(?=[（(]\s*\d{1,2}\s*[)）]\s*\S)")


def split_inline_items(text: str) -> list[str]:
    """Split `…痛点: (1) 甲; (2) 乙` into separate lines so each item can become a node."""
    parts = INLINE_ITEM_SPLIT.split(text)
    return [part.strip() for part in parts if part.strip()]


NUMBERED_ITEM = re.compile(r"^(?P<marker>[（(]\s*\d{1,2}\s*[)）])\s*(?P<rest>.*)$")
MAX_ITEM_TITLE_CHARACTERS = 24


def split_numbered_item(text: str) -> tuple[str, str]:
    """Turn `(3) 系统匹配: 适配不足` into the node title `(3) 系统匹配` plus its body."""
    candidate = text.strip()
    match = NUMBERED_ITEM.match(candidate)
    if match is None:
        return candidate[:MAX_ITEM_TITLE_CHARACTERS], candidate
    marker = match.group("marker")
    headline, separator, remainder = match.group("rest").strip().partition(":")
    if separator and 0 < len(headline.strip()) <= MAX_ITEM_TITLE_CHARACTERS:
        return f"{marker} {headline.strip()}", remainder.strip()
    # Without an inner label the whole line is both the title and the content.
    return candidate[:MAX_ITEM_TITLE_CHARACTERS], candidate


TRAILING_MARKER = re.compile(r"[（(]\s*\d{1,2}\s*[)）]\s*$")


def reattach_trailing_markers(lines: list[TextLine]) -> list[TextLine]:
    """Move a marker that OCR left at the end of a line onto the next line.

    `…促进技术沉淀; (2)` followed by `固化为算法模型…` becomes
    `…促进技术沉淀;` and `(2) 固化为算法模型…`, so the second point becomes a node.
    """
    result: list[TextLine] = []
    pending: str | None = None
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        if pending is not None:
            text = f"{pending} {text}"
            pending = None
        match = TRAILING_MARKER.search(text)
        if match is not None:
            pending = re.sub(r"\s+", "", match.group(0))
            text = text[: match.start()].rstrip()
        if text:
            result.append(TextLine(text=text, size=line.size))
    return result


NUMBERED_SECTION = re.compile(rf"^[{CHINESE_NUMBER}]{{1,3}}[、.．]\s*\S")


def looks_like_unlabelled_chapter_opener(lines: list[str]) -> str | None:
    """Detect a stylised chapter opener: a short first line followed by numbered sections."""
    candidates = [line.strip() for line in lines if line.strip()]
    if len(candidates) < 3:
        return None
    # The opener may sit below a few trailing body lines of the previous page.
    for index, opener in enumerate(candidates[:8]):
        if index + 1 >= len(candidates):
            break
        if len(opener) > 40 or opener.endswith(("。", "；", "，", ";", ",", ":", "：")):
            continue
        if detect_heading_level(opener) is not None:
            continue
        if not NUMBERED_SECTION.match(candidates[index + 1]):
            continue
        numbered = sum(1 for line in candidates[index + 1 : index + 7] if NUMBERED_SECTION.match(line))
        if numbered >= 2:
            return opener
    return None


CHAPTER_TITLE = re.compile(r"^第\s*([一二三四五六七八九十百零〇两]+)\s*章")


def next_chapter_prefix(previous_chapter_title: str | None) -> str:
    """`第六章 ` for an unlabelled opener that follows 第五章, else an empty string."""
    if not previous_chapter_title:
        return ""
    match = CHAPTER_TITLE.match(previous_chapter_title.strip())
    if match is None:
        return ""
    number = _chinese_to_int(match.group(1))
    if number is None or number >= 99:
        return ""
    return f"第{_int_to_chinese(number + 1)}章"


OPENER_NOISE = re.compile(r"^(?:[A-Za-z]{1,4}|\d{1,3})\s+(?=[\u4e00-\u9fff])")


def strip_opener_noise(text: str) -> str:
    """Drop the latin/digit noise OCR leaves in front of a stylised chapter title."""
    return OPENER_NOISE.sub("", text.strip(), count=1).strip() or text.strip()


CHINESE_DIGITS = "零一二三四五六七八九"


def _chinese_to_int(text: str) -> int | None:
    if not text:
        return None
    if text == "十":
        return 10
    if "百" in text:
        return None
    if "十" in text:
        tens, _, ones = text.partition("十")
        tens_value = CHINESE_DIGITS.index(tens) if tens in CHINESE_DIGITS else 1
        ones_value = CHINESE_DIGITS.index(ones) if ones in CHINESE_DIGITS else 0
        return tens_value * 10 + ones_value
    return CHINESE_DIGITS.index(text) if text in CHINESE_DIGITS else None


def _int_to_chinese(value: int) -> str:
    if value < 10:
        return CHINESE_DIGITS[value]
    if value < 20:
        return "十" + (CHINESE_DIGITS[value - 10] if value > 10 else "")
    tens, ones = divmod(value, 10)
    return f"{CHINESE_DIGITS[tens]}十" + (CHINESE_DIGITS[ones] if ones else "")
