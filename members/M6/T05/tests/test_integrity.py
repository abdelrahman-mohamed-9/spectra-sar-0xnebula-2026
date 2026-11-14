import hashlib
import pytest
from src.qa_validators import verify_file,validate_lineage,QualityError

@pytest.mark.integrity
def test_file_checksum_and_bytes(tmp_path):
    p=tmp_path/'artifact.bin';p.write_bytes(b'local test only')
    assert verify_file(p,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size)

@pytest.mark.integrity
def test_file_tampering_detected(tmp_path):
    p=tmp_path/'artifact.bin';p.write_bytes(b'abc')
    digest=hashlib.sha256(b'abc').hexdigest()
    p.write_bytes(b'abd')
    with pytest.raises(QualityError,match='checksum'):verify_file(p,digest,3)

@pytest.mark.integrity
def test_file_size_detected(tmp_path):
    p=tmp_path/'artifact.bin';p.write_bytes(b'abc')
    with pytest.raises(QualityError,match='size'):verify_file(p,hashlib.sha256(b'abc').hexdigest(),4)

@pytest.mark.integrity
def test_valid_lineage():
    assert validate_lineage([{'asset_id':'input','input_asset_ids':[]},
        {'asset_id':'output','input_asset_ids':['input']}])

@pytest.mark.integrity
@pytest.mark.parametrize('records',[
    [{'asset_id':'a','input_asset_ids':['missing']}],
    [{'asset_id':'a','input_asset_ids':['b']},{'asset_id':'b','input_asset_ids':['a']}],
    [{'asset_id':'a','input_asset_ids':[]},{'asset_id':'a','input_asset_ids':[]}],
    [{'asset_id':'a','input_asset_ids':['a']}],
])
def test_bad_lineage_rejected(records):
    with pytest.raises(QualityError):validate_lineage(records)
