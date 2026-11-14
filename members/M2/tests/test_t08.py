import json
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from evaluation import binary_metrics,multiclass_metrics,reliability_bins,split_check,evaluate

def test_binary_exact():
    m=binary_metrics([1,1,0,0],[1,0,1,0])
    assert (m['TP'],m['FP'],m['FN'],m['TN'])==(1,1,1,1)
    assert m['f1']==.5 and m['iou']==1/3

def test_binary_no_positive():
    m=binary_metrics([0,0],[0,0]); assert m['precision'] is None and m['f1'] is None

def test_multiclass():
    m=multiclass_metrics([1,1,2,2],[1,2,2,2],[1,2])
    assert m['accuracy']==.75 and m['confusion_matrix']==[[1,1],[0,2]]

def test_reject_unknown_class():
    with pytest.raises(ValueError,match='outside'):multiclass_metrics([1,9],[1,2],[1,2])

def test_reliability():
    r=reliability_bins([True,False],[.9,.1]);assert np.isclose(r['ece_diagnostic'],.1)

def test_invalid_score():
    with pytest.raises(ValueError):reliability_bins([True],[1.1])

def test_provenance_disjoint():
    p={'train_region_ids':['a'],'validation_region_ids':['b'],'test_region_ids':['c'],'reference_source':'field survey','model_identifier':'model-1'}
    assert split_check(p)['declared_spatial_separation']

def test_provenance_overlap_rejected():
    p={'train_region_ids':['a'],'validation_region_ids':['b'],'test_region_ids':['a'],'reference_source':'survey','model_identifier':'m'}
    with pytest.raises(ValueError,match='overlap'):split_check(p)

def _make(path,array,transform=None):
    with rasterio.open(path,'w',driver='GTiff',width=array.shape[1],height=array.shape[0],count=1,dtype='uint8',crs='EPSG:32632',transform=transform or from_origin(0,20,10,10),nodata=255) as ds:ds.write(array.astype('uint8'),1)

def test_raster_e2e_exploratory(tmp_path):
    a=np.array([[1,1],[0,0]],dtype='uint8');b=np.array([[1,0],[1,0]],dtype='uint8')
    for name,arr in [('reference',a),('prediction',b),('mask',np.ones_like(a))]:_make(tmp_path/(name+'.tif'),arr)
    output=tmp_path/'report.json'
    r=evaluate(tmp_path/'reference.tif',tmp_path/'prediction.tif',tmp_path/'mask.tif',output,mode='binary',allow_exploratory=True)
    assert r['metrics']['f1']==.5 and r['status']=='UNVERIFIED_EXPLORATORY'
    assert json.loads(output.read_text())['evaluated_pixels']==4

def test_reject_missing_provenance(tmp_path):
    with pytest.raises(ValueError,match='Independent evaluation'):evaluate('x','y','z','o',mode='binary')

def test_grid_mismatch(tmp_path):
    a=np.ones((2,2),dtype='uint8'); _make(tmp_path/'ref.tif',a)
    _make(tmp_path/'pred.tif',a,from_origin(100,20,10,10));_make(tmp_path/'mask.tif',a)
    with pytest.raises(ValueError,match='grid mismatch'):evaluate(tmp_path/'ref.tif',tmp_path/'pred.tif',tmp_path/'mask.tif',tmp_path/'out.json',mode='binary',allow_exploratory=True)

def test_mask_excludes_pixels(tmp_path):
    a=np.array([[1,0],[1,0]],dtype='uint8');b=np.array([[1,1],[0,0]],dtype='uint8');v=np.array([[1,0],[0,1]],dtype='uint8')
    for n,x in [('ref',a),('pred',b),('mask',v)]:_make(tmp_path/(n+'.tif'),x)
    r=evaluate(tmp_path/'ref.tif',tmp_path/'pred.tif',tmp_path/'mask.tif',tmp_path/'out.json',mode='binary',allow_exploratory=True)
    assert r['evaluated_pixels']==2 and r['metrics']['f1']==1
