import math
import re
from collections import Counter
from dataclasses import dataclass

from app.schemas import Evidence, EvidenceDocument, EvidenceMap, JobRequirement
from app.services.parser import normalize_skills

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#./-]*|[\u4e00-\u9fff]{2,}")


@dataclass(frozen=True)
class IndexedChunk:
    document: EvidenceDocument
    chunk_index: int
    content: str


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def chunk_document(document: EvidenceDocument, size: int = 500) -> list[IndexedChunk]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document.content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > size:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return [
        IndexedChunk(document=document, chunk_index=index, content=content)
        for index, content in enumerate(chunks, start=1)
    ]


def build_evidence_map(
    requirements: list[JobRequirement],
    documents: list[EvidenceDocument],
    limit: int = 5,
) -> list[EvidenceMap]:
    corpus = [chunk for document in documents for chunk in chunk_document(document)]
    document_frequency = Counter(
        token for chunk in corpus for token in set(tokenize(chunk.content))
    )
    corpus_size = max(len(corpus), 1)

    mappings: list[EvidenceMap] = []
    for requirement in requirements:
        query = set(tokenize(requirement.text) + requirement.skills)
        scored: list[tuple[float, IndexedChunk]] = []
        for chunk in corpus:
            counts = Counter(tokenize(chunk.content))
            lexical_score = sum(
                (1 + math.log(counts[token]))
                * math.log((corpus_size + 1) / (document_frequency[token] + 0.5))
                for token in query
                if counts[token]
            )
            skill_overlap = len(set(requirement.skills) & set(normalize_skills(chunk.content)))
            score = lexical_score + (skill_overlap * 2.0)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        maximum = scored[0][0] if scored else 1
        evidence = [
            Evidence(
                source_id=f"{chunk.document.source_id}#chunk-{chunk.chunk_index}",
                source_path=chunk.document.source_path,
                excerpt=chunk.content,
                skills=normalize_skills(chunk.content),
                confidence=round(min(score / maximum, 1.0), 3),
            )
            for score, chunk in scored[:limit]
        ]
        mappings.append(EvidenceMap(requirement=requirement, evidence=evidence))
    return mappings
