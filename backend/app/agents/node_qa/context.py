"""Node Context: the single, bounded snapshot every node answer is built from.

The assistant never sees the whole document. It receives this deterministic context,
which always carries evidence ids, so every sentence can be traced back to a chunk.
"""

from dataclasses import dataclass, field

from app.agents.node_qa.contracts import EvidenceItem

DEFAULT_MAX_CHARACTERS = 6000
MAX_SUMMARY_CHARACTERS = 600
MAX_CHILDREN = 8
MAX_SIBLINGS = 6
MAX_EVIDENCE_ITEMS = 6


@dataclass(frozen=True)
class NodeContext:
    """Everything the model may use when answering about one node."""

    document_title: str
    breadcrumb: tuple[str, ...]
    node_title: str
    node_summary: str
    keywords: tuple[str, ...]
    children: tuple[tuple[str, str], ...]
    siblings: tuple[str, ...]
    evidence: tuple[EvidenceItem, ...]
    truncated: bool = False
    dropped_evidence: int = 0
    dropped_children: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def is_empty(self) -> bool:
        """True when there is nothing grounded to answer from."""
        return not self.evidence and not self.node_summary.strip()

    def render(self) -> str:
        """Prompt block. Evidence labels stay stable so citations can be validated."""
        lines: list[str] = [f"Document: {self.document_title}"]
        if self.breadcrumb:
            lines.append(f"Outline path: {' > '.join(self.breadcrumb)}")
        lines.append(f"Node: {self.node_title}")
        if self.keywords:
            lines.append(f"Node keywords: {', '.join(self.keywords)}")
        if self.node_summary:
            lines.append(f"Node summary: {self.node_summary[:MAX_SUMMARY_CHARACTERS]}")
        if self.children:
            lines.append("Child nodes:")
            lines.extend(f"- {title}: {summary[:120]}" for title, summary in self.children)
        if self.siblings:
            lines.append(f"Sibling nodes (for contrast): {', '.join(self.siblings)}")
        lines.append("Evidence blocks (cite them by label):")
        lines.extend(
            f'[Evidence {item.label} | {item.location} | section="{item.section_title}"]\n{item.text}'
            for item in self.evidence
        )
        if self.truncated:
            note = f"Context truncated: dropped {self.dropped_evidence} evidence blocks"
            if self.dropped_children:
                note += f" and {self.dropped_children} child summaries"
            lines.append(note + ". Say so if the answer may be incomplete.")
        lines.extend(self.notes)
        return "\n".join(lines)


def build_node_context(
    *,
    document_title: str,
    node_title: str,
    node_summary: str,
    keywords: list[str] | tuple[str, ...] = (),
    breadcrumb: list[str] | tuple[str, ...] = (),
    children: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
    siblings: list[str] | tuple[str, ...] = (),
    evidence: list[EvidenceItem] | tuple[EvidenceItem, ...] = (),
    max_characters: int = DEFAULT_MAX_CHARACTERS,
) -> NodeContext:
    """Assemble a bounded context: node identity first, then evidence, then surroundings."""
    selected_evidence: list[EvidenceItem] = []
    dropped_evidence = 0
    used = len(document_title) + len(node_title) + len(node_summary)
    for item in evidence[:MAX_EVIDENCE_ITEMS]:
        cost = len(item.text) + 40
        if used + cost > max_characters:
            dropped_evidence += 1
            continue
        selected_evidence.append(item)
        used += cost

    selected_children = list(children[:MAX_CHILDREN])
    dropped_children = max(0, len(children) - len(selected_children))
    truncated = dropped_evidence > 0 or dropped_children > 0

    return NodeContext(
        document_title=document_title,
        breadcrumb=tuple(breadcrumb),
        node_title=node_title,
        node_summary=node_summary,
        keywords=tuple(keywords),
        children=tuple(selected_children),
        siblings=tuple(siblings[:MAX_SIBLINGS]),
        evidence=tuple(selected_evidence),
        truncated=truncated,
        dropped_evidence=dropped_evidence,
        dropped_children=dropped_children,
    )
