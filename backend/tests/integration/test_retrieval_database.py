from dataclasses import replace
from hashlib import sha256
from uuid import UUID,uuid4

import pytest
from sqlalchemy import event,func,select,text,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supportops.embeddings import EmbeddingSpec
from supportops.errors import ApiError
from supportops.models import EmbeddingProfile,KnowledgeChunk,KnowledgeEmbedding,KnowledgeIndex,KnowledgeVersion
from supportops.retrieval_schemas import SearchQuery
from supportops import retrieval
from supportops.seed import synthetic_id
from test_knowledge import ROOT,create,change
from test_tickets import env,call

pytestmark=pytest.mark.integration


class FakeEmbedding:
    # Explicit synthetic vectors exercise storage/authorization, not model quality.
    spec=EmbeddingSpec('mock','synthetic-three-axis',sha256(b'synthetic-v1').hexdigest(),3,'Synthetic test vectors; not a language model')
    def __init__(self):self.calls=0
    def embed(self,texts):
        self.calls+=1
        return [[1,0,0] if 'restricted' in value.lower() else [0,1,0] for value in texts]


def index(env,article,mode='keyword',key=None):
    return call(env,'POST',f"{ROOT}/articles/{article['id']}/index",payload={'version_id':article['version']['id'],'expected_revision':article['revision'],'mode':mode},key=key)


def query(env,q='synthetic',mode='keyword',who='agent-a',limit=5):
    return call(env,'GET',ROOT+'/search',who=who,params={'q':q,'mode':mode,'limit':limit})


def test_keyword_baseline_requires_complete_index_and_current_publication(env):
    article=create(env,body='Synthetic account access instructions.')
    assert index(env,article).status_code==200
    assert query(env).json()['items']==[]
    article=change(env,article).json()
    found=query(env,'access').json()
    assert found['provider'] is None and found['available_versions']==found['indexed_versions']==1
    assert found['items'][0]['text']=='Synthetic account access instructions.'
    assert query(env,'unmatched-xyz').json()['items']==[]
    assert query(env,'the and').json()['items']==[]
    assert change(env,article,'archive').status_code==200
    assert query(env,'access').json()['items']==[]


def test_vector_storage_is_real_pgvector_and_cannot_broaden_scope_before_limit(env):
    provider=FakeEmbedding();env[0].state.embedding_provider=provider
    support=create(env,body='Ordinary support instructions.')
    private=create(env,scope='management',body='Restricted management source.')
    for article in (support,private):
        assert index(env,article,'vector').status_code==200
        assert change(env,article).status_code==200
    assert provider.calls==2
    result=query(env,'restricted',mode='vector',limit=1).json()
    assert result['provider']=='mock' and result['available_versions']==result['indexed_versions']==1
    assert [item['version_id'] for item in result['items']]==[support['version']['id']]
    assert query(env,'restricted',mode='vector',who='manager',limit=1).json()['items'][0]['version_id']==private['version']['id']
    assert env[1].scalar(text('SELECT pg_typeof(embedding)::text FROM knowledge_embeddings LIMIT 1'))=='vector'
    assert env[1].scalar(text('SELECT min(vector_dims(embedding)) FROM knowledge_embeddings'))==3


def test_index_retries_reuse_immutable_rows_and_profile_namespace(env):
    provider=FakeEmbedding();env[0].state.embedding_provider=provider
    article=create(env,body='Synthetic body '*60)
    first=index(env,article,'vector',key='same-index')
    assert first.status_code==200
    for key in ('same-index','different-index'):
        assert index(env,article,'vector',key=key).json()==first.json()
    assert provider.calls==1
    assert env[1].scalar(select(func.count()).select_from(KnowledgeIndex))==2
    count=first.json()['chunk_count']
    assert env[1].scalar(select(func.count()).select_from(KnowledgeEmbedding))==count
    provider.spec=replace(provider.spec,model_digest=sha256(b'synthetic-v2').hexdigest())
    second=index(env,article,'vector').json()
    assert second['profile_id']!=first.json()['profile_id']
    assert provider.calls==2
    assert env[1].scalar(select(func.count()).select_from(KnowledgeChunk))==count
    assert env[1].scalar(select(func.count()).select_from(KnowledgeEmbedding))==count*2


def test_new_publication_is_not_replaced_by_stale_historical_indexes(env):
    env[0].state.embedding_provider=FakeEmbedding()
    first=create(env,body='Old synthetic source.')
    assert index(env,first,'vector').status_code==200
    first=change(env,first).json()
    second=create(env,article_id=first['id'],expected_revision=2,body='Restricted new management source.',scope='management')
    assert index(env,second,'vector').status_code==200
    second=change(env,second).json()
    assert query(env,'old',mode='vector').json()['items']==[]
    assert query(env,'synthetic').json()['items']==[]
    third=create(env,article_id=first['id'],expected_revision=4,body='New unindexed support source.')
    third=change(env,third).json()
    empty=query(env,'source',mode='vector').json()
    assert empty['available_versions']==1 and empty['indexed_versions']==0 and empty['items']==[]


def test_provider_failure_rolls_back_new_index_and_is_not_an_empty_result(env):
    provider=FakeEmbedding();env[0].state.embedding_provider=provider
    article=create(env)
    original=provider.embed
    def fail(texts):raise ApiError(503,'embedding_unavailable','Local embeddings unavailable')
    provider.embed=fail
    assert index(env,article,'vector',key='retry-after-failure').status_code==503
    assert env[1].scalar(select(func.count()).select_from(KnowledgeChunk))==0
    assert env[1].scalar(select(func.count()).select_from(KnowledgeIndex))==0
    provider.embed=original
    assert index(env,article,'vector',key='retry-after-failure').status_code==200
    assert change(env,article).status_code==200
    provider.embed=fail
    assert query(env,mode='vector').status_code==503


@pytest.mark.parametrize('who',['agent-a','requester-a'])
def test_index_is_manager_only_and_requesters_cannot_search(env,who):
    article=create(env)
    assert call(env,'POST',f"{ROOT}/articles/{article['id']}/index",who=who,payload={'version_id':article['version']['id'],'expected_revision':1}).status_code==403
    if who=='requester-a':assert query(env,who=who).status_code==403


@pytest.mark.parametrize('changes',[{'q':''},{'q':'x'*501},{'q':'bad\x00text'},{'mode':'hybrid'},{'limit':21},{'profile_id':str(uuid4())}])
def test_search_input_and_client_profile_override_are_rejected(env,changes):
    assert call(env,'GET',ROOT+'/search',params={'q':'synthetic',**changes}).status_code==422


def test_snapshot_offsets_and_embedding_constraints_survive_direct_sql(env):
    env[0].state.embedding_provider=FakeEmbedding()
    article=create(env)
    assert index(env,article,'vector').status_code==200
    for table in ('knowledge_chunks','knowledge_embeddings','embedding_profiles','knowledge_indexes'):
        with pytest.raises(IntegrityError),env[1].begin_nested():env[1].execute(text(f'UPDATE {table} SET '+('chunk_id=chunk_id' if table=='knowledge_embeddings' else 'id=id')))
    existing=dict(env[1].execute(select(KnowledgeChunk.__table__)).mappings().first())
    existing.update(id=uuid4(),chunker='constraint-test-only')
    env[1].execute(KnowledgeChunk.__table__.insert().values(**existing))
    profile=FakeEmbedding.spec.id
    with pytest.raises(IntegrityError) as failure,env[1].begin_nested():
        env[1].execute(KnowledgeEmbedding.__table__.insert().values(chunk_id=existing['id'],profile_id=profile,dimensions=2,embedding=[1,0]))
    assert failure.value.orig.diag.constraint_name=='fk_embedding_profile_dimension'
    with pytest.raises(IntegrityError) as failure,env[1].begin_nested():
        env[1].execute(KnowledgeEmbedding.__table__.insert().values(chunk_id=existing['id'],profile_id=profile,dimensions=3,embedding=[0,0,0]))
    assert failure.value.orig.diag.constraint_name=='ck_embedding_vector'


def test_different_dimensions_share_chunks_but_never_vector_spaces(env):
    provider=FakeEmbedding();env[0].state.embedding_provider=provider
    article=create(env)
    assert index(env,article,'vector').status_code==200
    provider.spec=replace(provider.spec,dimensions=4)
    provider.embed=lambda texts:[[0,1,0,0] for _ in texts]
    assert index(env,article,'vector').status_code==200
    assert env[1].scalar(select(func.count()).select_from(KnowledgeChunk))==1
    assert env[1].scalar(select(func.count()).select_from(KnowledgeEmbedding))==2
    assert change(env,article).status_code==200
    result=query(env,'synthetic',mode='vector').json()
    assert result['profile_id']==str(provider.spec.id) and len(result['items'])==1


def test_manifest_failure_rolls_back_chunks_vectors_and_allows_same_key_retry(env):
    env[0].state.embedding_provider=FakeEmbedding()
    article=create(env)
    def fail(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO knowledge_indexes'):raise RuntimeError('Synthetic manifest insertion failure')
    event.listen(env[1],'before_cursor_execute',fail)
    try:assert index(env,article,'vector',key='manifest-fault').status_code==500
    finally:event.remove(env[1],'before_cursor_execute',fail)
    for model in (KnowledgeChunk,KnowledgeEmbedding,KnowledgeIndex,EmbeddingProfile):
        assert env[1].scalar(select(func.count()).select_from(model))==0
    assert index(env,article,'vector',key='manifest-fault').status_code==200
