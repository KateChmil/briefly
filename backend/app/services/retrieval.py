"""Tiny keyword retrieval so the tutor sees the parts of the sources that matter.

No embeddings: chunks are scored by how often the question's words appear in them.
That is plenty for course notes and keeps the app free of extra services.
"""

import math
import re
from collections import Counter

CHUNK_CHARS = 1000
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = {
    "the", "and", "for", "with", "that", "this", "what", "how", "why", "are",
    "was", "were", "you", "your", "can", "could", "would", "should", "does",
    "did", "not", "but", "from", "have", "has", "had", "about", "into", "than",
    "then", "them", "they", "there", "their", "which", "when", "where", "who",
    "explain", "tell", "give", "please", "let", "know", "want", "need",
}


def _tokens(text: str) -> list[str]:
    return [w for w in (m.lower() for m in _WORD.findall(text)) if w not in _STOP]


def split_chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split on paragraph boundaries into chunks of roughly `size` characters."""
    chunks: list[str] = []
    current = ""
    for para in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        para = para.strip()
        if not para:
            continue
        while len(para) > size:  # a single huge paragraph
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:size])
            para = para[size:]
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def select_excerpts(sources, query: str, budget: int) -> list[tuple[str, str]]:
    """Pick the most relevant chunks across `sources` within `budget` characters.

    `sources` need `.filename` and `.extracted_text`. Returns (filename, chunk)
    pairs in reading order. Every source contributes its opening chunk when there
    is room, so the tutor always knows what each file is about.
    """
    q = Counter(_tokens(query))
    candidates = []  # (score, source_idx, chunk_idx, filename, chunk)
    for si, src in enumerate(sources):
        for ci, chunk in enumerate(split_chunks(src.extracted_text or "")):
            counts = Counter(_tokens(chunk))
            score = sum(
                math.log1p(counts[w]) * (1 + math.log1p(q[w])) for w in q if w in counts
            )
            candidates.append((score, si, ci, src.filename, chunk))

    chosen: list[tuple[int, int, str, str]] = []
    used = 0

    def take(item) -> None:
        nonlocal used
        _, si, ci, name, chunk = item
        if any(c[0] == si and c[1] == ci for c in chosen):
            return
        if used + len(chunk) > budget:
            return
        chosen.append((si, ci, name, chunk))
        used += len(chunk)

    # Best-scoring chunks first, then the opening chunk of every source.
    for item in sorted(candidates, key=lambda c: (-c[0], c[1], c[2])):
        if item[0] <= 0:
            break
        take(item)
    for item in candidates:
        if item[2] == 0:
            take(item)

    chosen.sort(key=lambda c: (c[0], c[1]))
    return [(name, chunk) for _, _, name, chunk in chosen]
