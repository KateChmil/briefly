from types import SimpleNamespace

from app.services.retrieval import select_excerpts, split_chunks


def src(name, text):
    return SimpleNamespace(filename=name, extracted_text=text)


def test_split_chunks_respects_size_and_keeps_all_text():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(30))
    chunks = split_chunks(text, size=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "Paragraph 29" in chunks[-1]
    assert split_chunks("x" * 2500, size=1000) == ["x" * 1000, "x" * 1000, "x" * 500]


def test_selects_relevant_chunk_from_deep_in_a_long_source():
    filler = "\n\n".join(f"Filler paragraph {i} about the weather." for i in range(300))
    text = filler + "\n\nThe Krebs cycle oxidises acetyl-CoA to carbon dioxide."
    out = select_excerpts([src("bio.txt", text)], "explain the krebs cycle", budget=3000)
    joined = " ".join(chunk for _, chunk in out)
    assert "Krebs cycle oxidises" in joined
    assert sum(len(c) for _, c in out) <= 3000


def test_every_source_contributes_its_opening_chunk():
    sources = [
        src("a.txt", "Alpha intro paragraph.\n\nmore alpha"),
        src("b.txt", "Beta intro paragraph.\n\nmore beta"),
    ]
    out = select_excerpts(sources, "unrelated question about zebras", budget=5000)
    assert {name for name, _ in out} == {"a.txt", "b.txt"}


def test_empty_sources_and_query():
    assert select_excerpts([], "anything", 1000) == []
    assert select_excerpts([src("a.txt", "")], "", 1000) == []
