"""Derived immutable chunks/vectors. Current SQL authorization always gates ranking/limits."""
from dataclasses import asdict
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert

from supportops.embeddings import normalize_vectors
from supportops.errors import ApiError
from supportops.idempotency import canonical_hash, claim, finish
from supportops.knowledge_service import _article, _manager, _revision, active_versions, require_knowledge
from supportops.models import EmbeddingProfile, KnowledgeArticle, KnowledgeChunk, KnowledgeEmbedding, KnowledgeIndex, KnowledgeVersion
from supportops.retrieval_schemas import IndexResponse, SearchHit, SearchResponse

CHUNKER = "unicode-chars-v1:400:40"


def chunks(version_id, body):
    result, start = [], 0
    while start < len(body):
        end = min(start + 400, len(body))
        content = body[start:end]
        digest = sha256(content.encode("utf-8")).hexdigest()
        ordinal = len(result)
        result.append(dict(id=uuid5(version_id, f"{CHUNKER}:{ordinal}:{digest}"), version_id=version_id, chunker=CHUNKER,
            ordinal=ordinal, start_offset=start, end_offset=end, content=content, content_hash=digest))
        if end == len(body):
            break
        start = end - 40
    return result


def representation(profile=None):
    return canonical_hash({"chunker": CHUNKER, "profile": str(profile.id) if profile else None})


def build_index(session, user_id, article_id, payload, key, provider):
    actor = _manager(session, user_id)
    article = _article(session, article_id, lock=True)
    record, replay = claim(session, actor.id, article.id, "knowledge_index", key, payload)
    if replay:
        return replay
    _revision(article, payload.expected_revision)
    version = session.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == payload.version_id, KnowledgeVersion.article_id == article.id))
    if version is None:
        raise ApiError(404, "not_found", "This knowledge version is unavailable")
    spec = provider.spec if payload.mode == "vector" else None
    identity = representation(spec)
    existing = session.scalar(select(KnowledgeIndex).where(KnowledgeIndex.version_id == version.id, KnowledgeIndex.representation == identity))
    values = chunks(version.id, version.body)
    if existing is None:
        vectors = normalize_vectors(provider.embed([row["content"] for row in values]), len(values), spec.dimensions) if spec else None
        if spec:
            session.execute(insert(EmbeddingProfile).values(id=spec.id, **asdict(spec)).on_conflict_do_nothing())
        for row in values:
            session.execute(insert(KnowledgeChunk).values(**row).on_conflict_do_nothing(constraint="uq_chunk_ordinal"))
        if spec:
            for row, vector in zip(values, vectors, strict=True):
                session.execute(insert(KnowledgeEmbedding).values(chunk_id=row["id"], profile_id=spec.id, dimensions=spec.dimensions, embedding=vector).on_conflict_do_nothing())
        for profile in ([None, spec] if spec else [None]):
            session.execute(insert(KnowledgeIndex).values(id=uuid4(), version_id=version.id, representation=representation(profile),
                chunker=CHUNKER, mode="vector" if profile else "keyword", profile_id=profile.id if profile else None,
                chunk_count=len(values), actor_id=actor.id, request_id=session.info.get("request_id") or uuid4()).on_conflict_do_nothing(constraint="uq_knowledge_representation"))
    return finish(session, record, 200, IndexResponse(version_id=version.id, representation=identity, chunk_count=len(values),
        mode=payload.mode, profile_id=spec.id if spec else None, provider=spec.provider if spec else None))


def search(session, user, query, provider):
    require_knowledge(user)
    spec = provider.spec if query.mode == "vector" else None
    eligible = active_versions(user).with_only_columns(KnowledgeVersion.id).subquery()
    available = session.scalar(select(func.count()).select_from(eligible))
    ready = select(KnowledgeIndex.version_id).where(KnowledgeIndex.representation == representation(spec), KnowledgeIndex.version_id.in_(select(eligible.c.id))).subquery()
    indexed = session.scalar(select(func.count()).select_from(ready))
    fields = dict(mode=query.mode, score_kind="cosine_similarity" if spec else "ts_rank_cd", chunker=CHUNKER,
        profile_id=spec.id if spec else None, provider=spec.provider if spec else None, available_versions=available, indexed_versions=indexed)
    if not indexed:
        return SearchResponse(**fields, items=[])
    statement = select(KnowledgeChunk, KnowledgeVersion).join(KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id).where(
        KnowledgeChunk.version_id.in_(select(ready.c.version_id)), KnowledgeChunk.chunker == CHUNKER)
    if spec:
        vector = normalize_vectors(provider.embed([query.q]), 1, spec.dimensions)[0]
        statement = statement.join(KnowledgeEmbedding, KnowledgeEmbedding.chunk_id == KnowledgeChunk.id).where(KnowledgeEmbedding.profile_id == spec.id)
        score = 1 - KnowledgeEmbedding.embedding.cosine_distance(vector)
    else:
        config = literal_column("'english'::regconfig")
        document = func.to_tsvector(config, KnowledgeVersion.title + " " + KnowledgeChunk.content)
        terms = func.websearch_to_tsquery(config, query.q)
        statement = statement.where(document.op("@@")(terms))
        score = func.ts_rank_cd(document, terms)
    rows = session.execute(statement.add_columns(score).order_by(score.desc(), KnowledgeChunk.id).limit(query.limit)).all()
    hits = [SearchHit(article_id=version.article_id, version_id=version.id, chunk_id=chunk.id, ordinal=chunk.ordinal,
        start_offset=chunk.start_offset, end_offset=chunk.end_offset, text=chunk.content, title=version.title,
        content_hash=chunk.content_hash, version_hash=version.content_hash, source_kind=version.source_kind,
        source_reference=version.source_reference, license_note=version.license_note, score=float(value)) for chunk, version, value in rows]
    return SearchResponse(**fields, items=hits)
