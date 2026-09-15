"""Pure text windowing used by the chunking stage."""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int
    end: int


def iter_block_spans(text: str) -> Iterator[tuple[int, int]]:
    """Yield character spans of consecutive non-blank lines."""
    offset = 0
    block_start: int | None = None
    block_end = 0
    for line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(line)
        if not line.strip():
            if block_start is not None:
                yield (block_start, block_end)
                block_start = None
            continue
        if block_start is None:
            block_start = line_start
        block_end = line_start + len(line.rstrip("\r\n"))
    if block_start is not None:
        yield (block_start, block_end)


def split_text(text: str, max_characters: int, overlap_characters: int) -> list[TextSpan]:
    """Split text into overlapping windows aligned with paragraph boundaries."""
    if max_characters <= 0:
        raise ValueError("max_characters must be positive.")
    overlap = max(0, min(overlap_characters, max_characters - 1))
    spans: list[TextSpan] = []
    window_start: int | None = None
    window_end = 0

    for start, end in iter_block_spans(text):
        while end - start > max_characters:
            if window_start is not None:
                spans.append(_make_span(text, window_start, window_end))
                window_start = None
            hard_end = start + max_characters
            spans.append(_make_span(text, start, hard_end))
            start = max(hard_end - overlap, start + 1)

        if window_start is None:
            window_start, window_end = start, end
        elif end - window_start <= max_characters:
            window_end = end
        else:
            spans.append(_make_span(text, window_start, window_end))
            window_start = max(window_end - overlap, start)
            window_end = end

    if window_start is not None:
        spans.append(_make_span(text, window_start, window_end))
    return [span for span in spans if span.text.strip()]


def _make_span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(text=text[start:end].strip(), start=start, end=end)
