import numpy as np
import pytest
from ai_classifier import features_from_arrays,_label_metadata,train,infer

def test_no_fake_semantic_labels():
    with pytest.raises(ValueError): _label_metadata({'1':'flood'})

def test_label_validation():
    assert _label_metadata({'1':'water','2':'other'})=={1:'water',2:'other'}
    with pytest.raises(ValueError): _label_metadata({'255':'water','1':'other'})

def test_score_sign():
    b=np.ones((15,15),dtype='float32');a=b*2
    f,v=features_from_arrays(b,a,np.ones_like(b,dtype=bool))
    assert v.all() and np.allclose(f[:,:,2],10*np.log10(2))

def test_invalid_excluded():
    b=np.ones((10,10));a=b.copy();a[4,4]=0
    f,v=features_from_arrays(b,a,np.ones_like(b,dtype=bool))
    assert not v[4,4] and np.isnan(f[4,4]).all()

def test_local_feature_ignores_invalid():
    b=np.ones((17,17));a=b.copy();a[8,8]=1e15
    v=np.ones_like(b,dtype=bool);v[8,8]=False
    f,_=features_from_arrays(b,a,v)
    assert abs(f[8,9,5])<1e-5

def test_mismatched_shape():
    with pytest.raises(ValueError):features_from_arrays(np.ones((3,3)),np.ones((2,2)),np.ones((3,3),bool))

def test_training_needs_real_labels():
    with pytest.raises(Exception): train('/no/such/pair','/missing.tif','/missing.json','/tmp/unused')

def test_inference_requires_registration_bypass():
    with pytest.raises(ValueError,match='subpixel'): infer('/missing','/missing','/tmp/unused')
