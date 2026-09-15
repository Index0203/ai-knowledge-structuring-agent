"""Extractive digesting for the structure fallback.

Without a chat model the tree cannot paraphrase, so summaries are the single most
informative sentence of a section (a real summarisation technique, not a raw
truncation) and keywords are the section's most characteristic terms.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable

LATIN_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9\-]{1,}")
CJK_SEGMENT_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
SENTENCE_PATTERN = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
DIGITS_ONLY = re.compile(r"^\d+$")
# OCR glues the tail of the previous line onto the start of a paragraph.
LEADING_FRAGMENT = re.compile(r"^[\u4e00-\u9fff]{1,3}\s+(?=[\u4e00-\u9fff])")
DEFINITION_MARKERS = ("是指", "指的是", "即为", "定义为")

MAX_SUMMARY_CHARACTERS = 80
MAX_SENTENCES_CONSIDERED = 12
MAX_KEYWORD_CHARACTERS = 8
STRONG_CANDIDATE_WEIGHT = 3
MAX_NGRAM_LENGTH = 5
MAX_NGRAM_SPAN_CHARACTERS = 40

# Characters that usually sit between words, so they mark word boundaries.
CJK_BOUNDARY_CHARACTERS = set(
    "的了和与及或在是为对把被从到就都也而其之等将并且以于由这那有着随需应可很更最使所者我你他们一个等"
)

STOPWORDS = {
    "的", "了", "和", "与", "及", "或", "在", "是", "为", "对", "把", "被", "从", "到", "就",
    "都", "也", "而", "其", "之", "等", "将", "并", "且", "以", "于", "由", "这", "那", "有",
    "一个", "我们", "他们", "可以", "以及", "通过", "进行", "随着", "不断", "进一步", "目前",
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have",
    "will", "can", "not", "but", "its", "into", "than", "then", "they", "them", "their", "our",
}

MIN_CONTENT_CJK_CHARACTERS = 4
MIN_CONTENT_LATIN_WORDS = 3


def has_content(text: str) -> bool:
    """False for page-number-only or empty fragments produced by OCR."""
    if len(CJK_SEGMENT_PATTERN.findall(text)) and sum(len(part) for part in CJK_SEGMENT_PATTERN.findall(text)) >= MIN_CONTENT_CJK_CHARACTERS:
        return True
    return len(LATIN_WORD_PATTERN.findall(text)) >= MIN_CONTENT_LATIN_WORDS


def split_sentences(text: str) -> list[str]:
    sentences = []
    for match in SENTENCE_PATTERN.finditer(text.replace("\n", " ")):
        sentence = " ".join(match.group(0).split())
        if len(sentence) >= 6:
            sentences.append(sentence)
        if len(sentences) >= MAX_SENTENCES_CONSIDERED:
            break
    return sentences


def summarize(text: str, max_characters: int = MAX_SUMMARY_CHARACTERS) -> str:
    """Return the most representative single sentence of a section."""
    sentences = split_sentences(LEADING_FRAGMENT.sub("", text, count=1))
    if not sentences:
        return _shorten(" ".join(text.split()), max_characters)
    if len(sentences) == 1:
        return _shorten(sentences[0], max_characters)

    counts = Counter(_terms(" ".join(sentences)))
    best_sentence = sentences[0]
    best_score = -math.inf
    for position, sentence in enumerate(sentences):
        terms = _terms(sentence)
        if not terms:
            continue
        weight = sum(counts[term] for term in terms) / math.sqrt(len(terms))
        # Earlier sentences carry the topic of a section, so give them a small bonus.
        score = weight * (1.0 - 0.05 * position)
        # Definitions answer "what is this node about?" better than any other sentence.
        if any(marker in sentence for marker in DEFINITION_MARKERS):
            score *= 1.35
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return _shorten(best_sentence, max_characters)


def extract_keywords(
    text: str,
    *,
    document_counts: Counter[str] | None = None,
    limit: int = 5,
) -> list[str]:
    """Pick the most characteristic terms of a section."""
    terms = _terms(text)
    if not terms:
        return []
    counts = Counter(terms)
    document_counts = document_counts or Counter()
    first_position: dict[str, int] = {}
    for position, term in enumerate(terms):
        first_position.setdefault(term, position)

    ranked = sorted(
        counts.items(),
        key=lambda item: (
            -item[1],
            -document_counts.get(item[0], 0),
            _length_penalty(item[0]),
            -len(item[0]),
            first_position[item[0]],
        ),
    )

    selected: list[str] = []
    for term, _count in ranked:
        if any(term in chosen or chosen in term for chosen in selected):
            continue
        selected.append(term)
        if len(selected) >= limit:
            break
    return selected


def _length_penalty(term: str) -> int:
    """Prefer 2-4 character words and latin terms over long spans."""
    if LATIN_WORD_PATTERN.fullmatch(term):
        return 0
    return max(0, len(term) - 4)


def document_term_counts(texts: Iterable[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(set(_terms(text)))
    return counts


def _terms(text: str) -> list[str]:
    """Latin words plus CJK spans and bigrams that can stand in for Chinese words.

    Spans bounded by function characters score higher than raw bigrams, which
    keeps phrases like 「数据协同」 ahead of cross-boundary noise like 「据协」.
    """
    terms: list[str] = []
    for word in LATIN_WORD_PATTERN.findall(text.lower()):
        if len(word) >= 3 and word not in STOPWORDS:
            terms.extend([word] * STRONG_CANDIDATE_WEIGHT)
    strong_spans: list[str] = []
    long_spans: list[str] = []
    for segment in CJK_SEGMENT_PATTERN.findall(text):
        for span in _split_on_boundaries(segment):
            if 2 <= len(span) <= MAX_KEYWORD_CHARACTERS:
                strong_spans.append(span)
            else:
                long_spans.append(span)
    terms.extend(strong_spans * STRONG_CANDIDATE_WEIGHT)

    # A long run has no clear word boundaries, so fall back to bigrams - but never
    # to fragments of a phrase that the document itself states as a whole.
    for span in long_spans:
        for candidate in _span_candidates(span):
            if candidate in STOPWORDS or any(character in STOPWORDS for character in candidate):
                continue
            if any(character in CJK_BOUNDARY_CHARACTERS for character in candidate):
                continue
            if any(candidate in strong for strong in strong_spans):
                continue
            terms.append(candidate)
    return [term for term in terms if term and not DIGITS_ONLY.match(term)]


def _span_candidates(span: str) -> list[str]:
    """Every plausible word inside a run of characters without boundaries."""
    longest = MAX_NGRAM_LENGTH if len(span) <= MAX_NGRAM_SPAN_CHARACTERS else 2
    candidates: list[str] = []
    for length in range(2, longest + 1):
        candidates.extend(span[index : index + length] for index in range(len(span) - length + 1))
    return candidates


def _split_on_boundaries(segment: str) -> list[str]:
    spans: list[str] = []
    current: list[str] = []
    for character in segment:
        if character in CJK_BOUNDARY_CHARACTERS:
            if current:
                spans.append("".join(current))
                current = []
            continue
        current.append(character)
    if current:
        spans.append("".join(current))
    return spans


def _shorten(sentence: str, max_characters: int) -> str:
    cleaned = " ".join(sentence.split())
    if len(cleaned) <= max_characters:
        return cleaned
    window = cleaned[:max_characters]
    for separator in ("，", "、", ",", "；", ";", " "):
        index = window.rfind(separator)
        if index >= max_characters // 2:
            return window[:index].strip()
    return window.strip()
