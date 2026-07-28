import math
import re
from collections import Counter

from app.schemas import Evidence, EvidenceDocument, EvidenceMap, JobRequirement
from app.services.parser import normalize_skills

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]*|[\u4e00-\u9fff]{2,}")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def _chunks(document: EvidenceDocument, size: int = 500) -> list[str]:
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
    return chunks


def build_evidence_map(
    requirements: list[JobRequirement],
    documents: list[EvidenceDocument],
    limit: int = 5,
) -> list[EvidenceMap]:
    corpus = [
        (document, index, chunk)
        for document in documents
        for index, chunk in enumerate(_chunks(document), start=1)
    ]
    document_frequency = Counter(token for _, _, chunk in corpus for token in set(tokenize(chunk)))
    corpus_size = max(len(corpus), 1)

    mappings: list[EvidenceMap] = []
    for requirement in requirements:
        query = set(tokenize(requirement.text) + requirement.skills)
        scored: list[tuple[float, EvidenceDocument, int, str]] = []
        for document, index, chunk in corpus:
            counts = Counter(tokenize(chunk))
            lexical_score = sum(
                (1 + math.log(counts[token]))
                * math.log((corpus_size + 1) / (document_frequency[token] + 0.5))
                for token in query
                if counts[token]
            )
            skill_overlap = len(set(requirement.skills) & set(normalize_skills(chunk)))
            score = lexical_score + (skill_overlap * 2.0)
            if score > 0:
                scored.append((score, document, index, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        maximum = scored[0][0] if scored else 1
        evidence = [
            Evidence(
                source_id=f"{document.source_id}#chunk-{index}",
                source_path=document.source_path,
                excerpt=chunk,
                skills=normalize_skills(chunk),
                confidence=round(min(score / maximum, 1.0), 3),
            )
            for score, document, index, chunk in scored[:limit]
        ]
        mappings.append(EvidenceMap(requirement=requirement, evidence=evidence))
    return mappings
