"""Download control tests use fake file bytes; never invoke NASA or credentials."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import fetch_harmony as fetch

def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(fetch,'OUTPUT',tmp_path/'data')
    monkeypatch.setattr(fetch,'REPORTS',tmp_path/'reports')
    monkeypatch.setattr(fetch,'build_request',lambda *args:object())
    (tmp_path/'reports').mkdir()
    row={'date':'20261002','source':{'cmr_concept_id':'G-TEST','granule_id':'TEST_GRANULE','acquisition_start_utc':'2026-10-02T00:00:00Z'}}
    doc={'job_id':'TEST-JOB','cmr_granule_concept_id':'G-TEST','granule_id':'TEST_GRANULE',
         'variable_requested':fetch.VARIABLE,'bbox_lonlat':list(fetch.BBOX),'request_url':'https://example.test/TEST_ONLY'}
    (tmp_path/'reports/after-harmony-job.json').write_text(json.dumps(doc))
    class Client:
        submitted=False
        def submit(self,request):self.submitted=True;return 'NEW-TEST-JOB'
        def request_as_url(self,request):return 'https://example.test/TEST_ONLY'
        def download_all(self,job_id,directory,overwrite):
            self.downloaded_job=job_id
            path=Path(directory)/'SYNTHETIC_TEST_HHHH.tif'
            path.write_bytes(b'TEST_ONLY_NOT_TIFF'*100)
            return [SimpleNamespace(result=lambda:path)]
    return row,doc,Client()

def test_resume_existing_job_without_duplicate_submission(tmp_path,monkeypatch):
    row,doc,client=setup(tmp_path,monkeypatch)
    target=fetch.handle_role(client,'after',row,'COLLECTION_TEST')
    assert target.exists() and client.downloaded_job=='TEST-JOB' and not client.submitted

def test_job_source_mismatch_fails(tmp_path,monkeypatch):
    row,doc,client=setup(tmp_path,monkeypatch)
    row['source']['cmr_concept_id']='WRONG'
    with pytest.raises(ValueError,match='source mismatch'):fetch.handle_role(client,'after',row,'COLLECTION_TEST')
    assert not client.submitted

def test_explicit_new_job_preserves_prior_receipt(tmp_path,monkeypatch):
    row,doc,client=setup(tmp_path,monkeypatch)
    fetch.handle_role(client,'after',row,'COLLECTION_TEST',new_job=True)
    assert client.submitted and client.downloaded_job=='NEW-TEST-JOB'
    assert len(list((tmp_path/'reports').glob('after-previous-*.json')))==1
