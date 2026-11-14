import numpy as np
import pytest
from uncertainty import uncertainty_from_probabilities,run,NODATA

def test_high_confidence_low_entropy():
    p=np.array([[[.99]],[[.01]]]); result=uncertainty_from_probabilities(p,np.array([[True]]))
    assert result['normalized_entropy'][0,0]<.09
    assert result['top_two_margin'][0,0]>.97
    assert result['review_required'][0,0]==0

def test_ambiguous_binary():
    r=uncertainty_from_probabilities(np.array([[[.5]],[[.5]]]),np.array([[True]]))
    assert np.isclose(r['normalized_entropy'][0,0],1)
    assert r['top_two_margin'][0,0]==0
    assert r['review_required'][0,0]==1

def test_invalid_not_assigned_confidence():
    r=uncertainty_from_probabilities(np.array([[[-9999]], [[-9999]]]),np.array([[False]]))
    assert r['normalized_entropy'][0,0]==NODATA
    assert r['review_required'][0,0]==255

def test_reject_invalid_sum():
    with pytest.raises(ValueError,match='sum to 1'):
        uncertainty_from_probabilities(np.array([[[.8]],[[.8]]]),np.array([[True]]))

def test_reject_negative_and_nan():
    for p in ([[-.1],[1.1]],[[np.nan],[1]]):
        with pytest.raises(ValueError):uncertainty_from_probabilities(np.asarray(p).reshape(2,1,1),np.array([[True]]))

def test_three_classes_normalization():
    r=uncertainty_from_probabilities(np.ones((3,2,2))/3,np.ones((2,2),bool))
    assert np.allclose(r['normalized_entropy'],1)

def test_shapes():
    with pytest.raises(ValueError):uncertainty_from_probabilities(np.ones((2,3,3)),np.ones((2,2),bool))

def test_threshold_restricted():
    with pytest.raises(ValueError):uncertainty_from_probabilities(np.ones((2,1,1))*.5,np.ones((1,1),bool),low_confidence_threshold=1.0)

def test_scientific_signoff_requires_registration():
    with pytest.raises(ValueError,match='subpixel'):run('/missing','/missing','/missing')
