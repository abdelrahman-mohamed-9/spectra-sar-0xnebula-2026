import numpy as np
from scipy.ndimage import shift as ndshift
from registration import estimate_shift, inspect_registration
from test_t03 import _create_pair


def textured(n=128):
    rng=np.random.default_rng(321)
    a=rng.normal(size=(n,n))
    from scipy.ndimage import gaussian_filter
    x=gaussian_filter(a,3)
    x=(x-x.min())/(x.max()-x.min())
    return np.exp(x*2).astype('float32')


def test_zero_shift():
    x=textured(); r=estimate_shift(x,x,np.ones_like(x,dtype=bool))
    assert r is not None and r[:2]==(0,0)


def test_integer_translation():
    x=textured(); y=ndshift(x,shift=(3,-2),order=0,mode='nearest')
    r=estimate_shift(x,y,np.ones_like(x,dtype=bool))
    assert r is not None and r[:2]==(3,-2)


def test_untextured_inconclusive():
    x=np.ones((128,128),dtype='float32')
    assert estimate_shift(x,x,np.ones_like(x,dtype=bool)) is None


def test_sparse_valid_inconclusive():
    x=textured(); m=np.zeros_like(x,dtype=bool); m[:10,:10]=True
    assert estimate_shift(x,x,m) is None


def test_small_patch_inconclusive():
    x=textured(16)
    assert estimate_shift(x,x,np.ones_like(x,dtype=bool)) is None


def test_end_to_end_inconclusive_small_pair(tmp_path):
    root=_create_pair(tmp_path/'pair')
    result=inspect_registration(root,patch=32,allow_warning=True)
    assert result['status']=='WARNING'
    assert result['valid_patch_count']<3


def test_bad_patch_parameter():
    import pytest
    with pytest.raises(ValueError):inspect_registration('/tmp/none',patch=8)
