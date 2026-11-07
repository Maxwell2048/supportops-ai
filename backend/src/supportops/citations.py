"""Validate untrusted citations against the exact retrieved source chunks."""
from sqlalchemy import select

from supportops.knowledge_service import active_versions
from supportops.models import KnowledgeArticle, KnowledgeChunk, KnowledgeVersion


class InvalidCitation(Exception):
    pass


def validate_citations(suggestion, hits):
    sources = {(hit.chunk_id, hit.version_id): hit for hit in hits}
    if not suggestion.citations:
        raise InvalidCitation()
    for citation in suggestion.citations:
        hit = sources.get((citation.chunk_id, citation.version_id))
        if hit is None or not citation.quote.strip() or citation.quote not in hit.text:
            raise InvalidCitation()


def lock_current_sources(session, actor, hits):
    article_ids = sorted({hit.article_id for hit in hits})
    if not article_ids:
        return True
    session.scalars(select(KnowledgeArticle).where(KnowledgeArticle.id.in_(article_ids)).order_by(KnowledgeArticle.id).with_for_update(read=True)).all()
    eligible = active_versions(actor).with_only_columns(KnowledgeVersion.id).subquery()
    rows = session.execute(select(KnowledgeChunk, KnowledgeVersion).join(
        KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id).where(
        KnowledgeChunk.id.in_([hit.chunk_id for hit in hits]),
        KnowledgeChunk.version_id.in_(select(eligible.c.id)),
    )).all()
    actual = {(chunk.id, version.id): (chunk, version) for chunk, version in rows}
    for hit in hits:
        source = actual.get((hit.chunk_id, hit.version_id))
        if source is None:
            return False
        chunk, version = source
        if hit.text != chunk.content or chunk.content != version.body[chunk.start_offset:chunk.end_offset]:
            return False
    return True
