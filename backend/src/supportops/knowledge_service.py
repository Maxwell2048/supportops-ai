"""Immutable snapshots; mutable publication pointer and audit share one transaction."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from supportops.errors import ApiError
from supportops.idempotency import COLLECTION_ID, canonical_hash, claim, finish
from supportops.knowledge_schemas import KnowledgeArticleResponse, KnowledgeEventPage, KnowledgeEventResponse, KnowledgePage, KnowledgeSummary, KnowledgeVersionResponse
from supportops.models import KnowledgeArticle, KnowledgeEvent, KnowledgeVersion, User
from supportops.security import invalid_session, require_auth_config


def require_knowledge(user, *, manager=False):
    if user.role != "manager" and (manager or user.role != "agent"):
        raise ApiError(403, "forbidden", "Your current role cannot access this knowledge feature")


def _manager(session, user_id):
    actor = session.scalar(select(User).where(User.id == user_id).with_for_update(read=True).execution_options(populate_existing=True))
    if actor is None or not actor.active:
        raise invalid_session()
    require_knowledge(actor, manager=True)
    return actor


def _article(session, article_id, *, lock=False):
    statement = select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    article = session.scalar(statement)
    if article is None:
        raise ApiError(404, "not_found", "This knowledge article is unavailable")
    return article


def _published(version_id):
    return exists(select(KnowledgeEvent.id).where(KnowledgeEvent.version_id == version_id, KnowledgeEvent.action == "published"))


def _status(article, version, was_published):
    if article.published_version_id == version.id and not article.archived:
        return "published"
    return "archived" if was_published else "draft"


def version_response(session, article, version):
    fields = {name: getattr(version, name) for name in KnowledgeVersionResponse.model_fields if name != "status"}
    return KnowledgeVersionResponse(**fields, status=_status(article, version, session.scalar(select(_published(version.id)))))


def _response(session, article, version, *, manager=True):
    return KnowledgeArticleResponse(id=article.id, revision=article.revision if manager else None,
        published_version_id=article.published_version_id, archived=article.archived, version=version_response(session, article, version))


def _revision(article, expected):
    if article.revision != expected:
        raise ApiError(409, "version_conflict", "The article has changed; reload and review before continuing")
    if article.revision >= 2147483647:
        raise ApiError(409, "version_exhausted", "The article revision limit has been reached")


def _audit(session, actor, article, version, action, before=None):
    session.add(KnowledgeEvent(article_id=article.id, version_id=version.id, article_revision=article.revision,
        actor_id=actor.id, action=action, request_id=session.info.get("request_id") or uuid4(),
        changes={"version_id": str(version.id), "content_hash": version.content_hash, "scope": version.scope,
                 "published_version_id": str(article.published_version_id) if article.published_version_id else None,
                 "previous_published_version_id": str(before) if before else None, "archived": article.archived}))


def create_draft(session, user_id, payload, key):
    actor = _manager(session, user_id)
    article = _article(session, payload.article_id, lock=True) if payload.article_id else None
    record, replay = claim(session, actor.id, article.id if article else COLLECTION_ID, "knowledge_draft", key, payload)
    if replay:
        return replay
    if article:
        _revision(article, payload.expected_revision)
        article.revision += 1
        article.latest_version_number += 1
        article.updated_at = datetime.now(timezone.utc)
    else:
        article = KnowledgeArticle(id=uuid4(), created_by=actor.id, revision=1, latest_version_number=1, archived=False)
        session.add(article)
        session.flush()
    content = payload.model_dump(exclude={"article_id", "expected_revision"})
    version = KnowledgeVersion(id=uuid4(), article_id=article.id, number=article.latest_version_number,
        created_by=actor.id, content_hash=canonical_hash(content), **content)
    session.add(version)
    session.flush()
    _audit(session, actor, article, version, "draft_created", article.published_version_id)
    return finish(session, record, 201, _response(session, article, version))


def change_publication(session, user_id, article_id, payload, key, *, archive=False):
    actor = _manager(session, user_id)
    article = _article(session, article_id, lock=True)
    record, replay = claim(session, actor.id, article.id, "knowledge_archive" if archive else "knowledge_publish", key, payload)
    if replay:
        return replay
    _revision(article, payload.expected_revision)
    version = session.scalar(select(KnowledgeVersion).where(KnowledgeVersion.article_id == article.id, KnowledgeVersion.id == payload.version_id))
    if version is None:
        raise ApiError(404, "not_found", "This knowledge version is unavailable")
    if archive and (article.published_version_id != version.id or article.archived):
        raise ApiError(409, "invalid_archive", "Only the current active publication can be archived")
    if not archive and article.published_version_id == version.id and not article.archived:
        raise ApiError(422, "no_changes", "This version is already the active publication")
    before = article.published_version_id
    article.published_version_id = version.id
    article.archived = archive
    article.revision += 1
    article.updated_at = datetime.now(timezone.utc)
    session.flush()
    _audit(session, actor, article, version, "archived" if archive else "published", before)
    return finish(session, record, 200, _response(session, article, version))


def active_versions(user):
    """Current retrieval eligibility only; historical reads must use read_version."""
    require_knowledge(user)
    statement = select(KnowledgeArticle, KnowledgeVersion).join(KnowledgeVersion, KnowledgeVersion.id == KnowledgeArticle.published_version_id).where(KnowledgeArticle.archived.is_(False))
    if user.role == "agent":
        statement = statement.where(KnowledgeVersion.scope == "support")
    return statement


def read_article(session, user, article_id):
    require_knowledge(user)
    if user.role == "manager":
        article = _article(session, article_id)
        version = session.scalar(select(KnowledgeVersion).where(KnowledgeVersion.article_id == article.id, KnowledgeVersion.number == article.latest_version_number))
    else:
        row = session.execute(active_versions(user).where(KnowledgeArticle.id == article_id)).first()
        if row is None:
            raise ApiError(404, "not_found", "This knowledge article is unavailable")
        article, version = row
    return _response(session, article, version, manager=user.role == "manager")


def read_version(session, user, version_id):
    require_knowledge(user)
    statement = select(KnowledgeArticle, KnowledgeVersion).join(KnowledgeVersion, KnowledgeVersion.article_id == KnowledgeArticle.id).where(KnowledgeVersion.id == version_id)
    if user.role == "agent":
        current = aliased(KnowledgeVersion)
        statement = statement.join(current, current.id == KnowledgeArticle.published_version_id).where(
            KnowledgeArticle.archived.is_(False), current.scope == "support", KnowledgeVersion.scope == "support", _published(KnowledgeVersion.id))
    row = session.execute(statement).first()
    if row is None:
        raise ApiError(404, "not_found", "This knowledge version is unavailable")
    return version_response(session, *row)


def _position(query, user, settings, purpose, *, integer=False):
    secret = require_auth_config(settings)
    scope = canonical_hash({"limit": query.limit, "role": user.role})
    if not query.cursor:
        return None, secret, scope
    try:
        claims = jwt.decode(query.cursor, secret, algorithms=["HS256"], issuer=settings.jwt_issuer,
            audience=settings.jwt_audience + ":" + purpose, options={"require": ["sub", "scope", "position", "purpose", "iat", "exp", "iss", "aud"], "strict_aud": True})
        if claims["sub"] != str(user.id) or claims["scope"] != scope or claims["purpose"] != purpose:
            raise ValueError("Cursor mismatch")
        value = claims["position"]
        if integer:
            if type(value) is not int or value < 1:
                raise ValueError("Invalid revision")
        else:
            value = UUID(value)
        return value, secret, scope
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError, AttributeError):
        raise ApiError(422, "invalid_cursor", "This knowledge cursor does not match the current identity or query") from None


def _cursor(position, query, user, settings, purpose, secret, scope):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "scope": scope, "position": position, "purpose": purpose,
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience + ":" + purpose, "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes)}, secret, algorithm="HS256")


def list_knowledge(session, user, query, settings, article_id=None):
    require_knowledge(user, manager=article_id is not None)
    if article_id is not None:
        _article(session, article_id)
        statement = select(KnowledgeArticle, KnowledgeVersion).join(KnowledgeVersion, KnowledgeVersion.article_id == KnowledgeArticle.id).where(KnowledgeArticle.id == article_id)
        column = KnowledgeVersion.id
    elif user.role == "manager":
        statement = select(KnowledgeArticle, KnowledgeVersion).join(KnowledgeVersion, (KnowledgeVersion.article_id == KnowledgeArticle.id) & (KnowledgeVersion.number == KnowledgeArticle.latest_version_number))
        column = KnowledgeArticle.id
    else:
        statement, column = active_versions(user), KnowledgeArticle.id
    purpose = "knowledge-versions-" + str(article_id) if article_id else "knowledge-articles"
    position, secret, scope = _position(query, user, settings, purpose)
    if position is not None:
        statement = statement.where(column > position)
    rows = session.execute(statement.add_columns(_published(KnowledgeVersion.id)).order_by(column).limit(query.limit + 1)).all()
    page = rows[:query.limit]
    items = [KnowledgeSummary(article_id=article.id, version_id=version.id, number=version.number, title=version.title,
        scope=version.scope, status=_status(article, version, was_published)) for article, version, was_published in page]
    cursor = _cursor(str(page[-1][1].id if article_id else page[-1][0].id), query, user, settings, purpose, secret, scope) if len(rows) > query.limit else None
    return KnowledgePage(items=items, next_cursor=cursor)


def list_events(session, user, article_id, query, settings):
    require_knowledge(user, manager=True)
    _article(session, article_id)
    purpose = "knowledge-events-" + str(article_id)
    position, secret, scope = _position(query, user, settings, purpose, integer=True)
    statement = select(KnowledgeEvent).where(KnowledgeEvent.article_id == article_id)
    if position is not None:
        statement = statement.where(KnowledgeEvent.article_revision > position)
    rows = list(session.scalars(statement.order_by(KnowledgeEvent.article_revision).limit(query.limit + 1)))
    page = rows[:query.limit]
    cursor = _cursor(page[-1].article_revision, query, user, settings, purpose, secret, scope) if len(rows) > query.limit else None
    return KnowledgeEventPage(items=[KnowledgeEventResponse.model_validate(row) for row in page], next_cursor=cursor)
