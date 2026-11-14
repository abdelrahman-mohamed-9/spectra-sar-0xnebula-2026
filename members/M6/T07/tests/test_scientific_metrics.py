import numpy as np
import pytest
from scientific_metrics import evaluate_binary,evaluate_probabilities
from verification import verify_result,verify_alignment

def meta(**kw):
    d={'crs':'EPSG:32636','transform':[10,0,500000,0,-10,3300000],
       'width':2,'height':2,'reference_source':'independent-mapped-survey',
       'reference_date':'2026-01-01','reference_method':'manual delineation'}
    d.update(kw);return d

def test_confusion_and_metrics():
    s=evaluate_binary([[1,1],[0,0]],[[1,0],[1,0]])
    assert [s[k] for k in ('tp','fp','fn','tn')]==[1,1,1,1]
    assert s['precision']==s['recall']==s['f1']==s['iou']*1.5==0.5

def test_perfect():
    s=evaluate_binary([[1,0],[0,1]],[[1,0],[0,1]])
    assert s['iou']==s['f1']==1

def test_all_negative_is_not_perfect_change_detection():
    s=evaluate_binary([[0,0],[0,0]],[[0,0],[0,0]])
    assert s['accuracy']==1 and s['precision'] is None and s['f1'] is None and s['iou'] is None

def test_valid_mask_excludes_pixels():
    s=evaluate_binary([[1,1],[1,1]],[[1,0],[0,0]],np.array([[True,False],[False,False]]))
    assert s['valid_pixels']==1 and s['precision']==1

def test_empty_valid_mask_rejected():
    with pytest.raises(ValueError): evaluate_binary([[1]],[[1]],np.array([[False]]))

def test_unmatched_shape_rejected():
    with pytest.raises(ValueError): evaluate_binary([[1]],[[1,0]])

def test_nonbinary_rejected():
    with pytest.raises(ValueError): evaluate_binary([[2]],[[1]])

def test_brier_perfect():
    p=evaluate_probabilities([[0,1],[1,0]],[[0,1],[1,0]])
    assert p['brier_score']==0 and p['ece_change_probability']==0

def test_invalid_probabilities_rejected():
    with pytest.raises(ValueError): evaluate_probabilities([[float('nan')]],[[1]])

def test_bad_reference_labels_rejected():
    with pytest.raises(ValueError): evaluate_probabilities([[0.2]],[[3]])

def test_crs_mismatch():
    with pytest.raises(ValueError,match='CRS'):verify_alignment(meta(),meta(crs='EPSG:4326'))

def test_transform_mismatch():
    with pytest.raises(ValueError,match='CRS'):verify_alignment(meta(),meta(transform=[11,0,500000,0,-10,3300000]))

def test_grid_dimensions_mismatch():
    with pytest.raises(ValueError,match='dimensions'):verify_alignment(meta(),meta(width=3))

def test_missing_reference_provenance_rejected():
    with pytest.raises(ValueError): verify_alignment(meta(),meta(reference_source=''))

def test_full_report():
    result=verify_result([[1,0],[0,1]],[[1,0],[1,0]],meta(),meta(),probabilities=[[0.9,0.1],[0.2,0.6]])
    assert result['status']=='EVALUATED_AGAINST_REFERENCE'
    assert result['metrics']['tp']==1 and result['probability_metrics']['brier_score']>0

def test_no_reference_yields_no_metrics():
    with pytest.raises(ValueError):verify_result([[1]],None,meta(width=1,height=1),meta(width=1,height=1))
