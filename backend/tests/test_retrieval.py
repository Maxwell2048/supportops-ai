from hashlib import sha256
from uuid import uuid4

import httpx
import pytest

from supportops.config import Settings
from supportops.embeddings import MINILM, OllamaEmbedding, normalize_vectors
from supportops.errors import ApiError
from supportops.retrieval import chunks


@pytest.mark.parametrize('body', ['a', 'a'*400, 'a'*401, 'a'*50000, 'Unicode cafe\u0301 and \U0001f642 '*100], ids=['one','boundary','overlap','maximum','unicode'])
def test_chunks_are_deterministic_contiguous_source_slices_with_bounded_overlap(body):
    version=uuid4()
    first=chunks(version,body)
    assert first==chunks(version,body) and len(first)<=139
    assert first[0]['start_offset']==0 and first[-1]['end_offset']==len(body)
    for number,row in enumerate(first):
        assert row['ordinal']==number and row['content']==body[row['start_offset']:row['end_offset']]
        assert row['content_hash']==sha256(row['content'].encode()).hexdigest()
        if number:assert row['start_offset']==first[number-1]['end_offset']-40
    assert first[0]['id']!=chunks(uuid4(),body)[0]['id']


@pytest.mark.parametrize('vectors', [[], [[0,0]], [[1]], [[True,1]], [[float('nan'),1]], [[float('inf'),1]], [[1e308,1e308]], 'bad'])
def test_invalid_embeddings_are_rejected(vectors):
    with pytest.raises(ApiError) as failure:normalize_vectors(vectors,1,2)
    assert failure.value.status_code==503


def test_local_model_digest_dimension_and_normalization_are_validated_without_truncation():
    calls=[]
    def server(request):
        calls.append(request)
        return httpx.Response(200,json={'models':[{'name':MINILM.model,'digest':MINILM.model_digest}]} if request.url.path=='/api/tags' else {'embeddings':[[3]+[0]*383]})
    result=OllamaEmbedding(transport=httpx.MockTransport(server)).embed(['Synthetic query'])
    assert result==[[1]+[0]*383]
    assert b'"truncate":false' in calls[1].content and len(calls)==3


def test_model_drift_and_provider_errors_do_not_reflect_sensitive_payloads():
    provider=OllamaEmbedding(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'models':[]})))
    with pytest.raises(ApiError) as failure:provider.embed(['PRIVATE-SYNTHETIC-DIAGNOSTIC'])
    assert failure.value.code=='embedding_model_changed'
    provider=OllamaEmbedding(transport=httpx.MockTransport(lambda request:httpx.Response(500,text='PRIVATE-SYNTHETIC-DIAGNOSTIC')))
    with pytest.raises(ApiError) as failure:provider.embed(['PRIVATE-SYNTHETIC-DIAGNOSTIC'])
    assert 'PRIVATE' not in str(failure.value)


@pytest.mark.parametrize('url',['https://remote.example.invalid','http://127.0.0.1:11434/path','http://user:secret@localhost:11434','http://localhost:11434?token=x'])
def test_embedding_endpoint_cannot_exfiltrate_to_a_remote_or_credential_url(url):
    with pytest.raises(ValueError):Settings(embedding_url=url)
