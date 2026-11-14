from phase1.population_gap import is_only_population_nodata

def qa(pop_errors=('ALL_NODATA',),other_errors=()):
    def rep(status, issues=None):return {'status':status,'issues':issues or []}
    return {'overall_status':'REJECT','reports':{'aoi':rep('PASS'),
        'osm':rep('WARNING',[{'severity':'WARNING','code':'EMPTY_VECTOR'}]),
        'population':rep('REJECT',[{'severity':'ERROR','code':e} for e in pop_errors]),
        'manifest':rep('PASS',[{'severity':'ERROR','code':e} for e in other_errors])}}

def test_only_all_nodata_accepted_as_gap():
    assert is_only_population_nodata(qa()) is True

def test_no_data_with_other_science_error_stays_rejected():
    assert is_only_population_nodata(qa(('ALL_NODATA','NEGATIVE_POPULATION'))) is False
    assert is_only_population_nodata(qa(other_errors=('HASH_MISMATCH',))) is False

def test_no_population_gap_if_missing_qa():
    x=qa(); x['reports'].pop('manifest')
    assert is_only_population_nodata(x) is False

def test_gap_documents_but_other_five_members_continue(tmp_path):
    import json
    from phase1.pipeline import run
    from phase1.common import write
    from test_unified import pair_fixture
    pair = pair_fixture(tmp_path/'pair')
    report=tmp_path/'verified_source_gap.json'
    write(report, {'status':'PARTIAL_DATA_GAP','estimated_people_exposed_to_radar_change':None,
                   'population_spatial_status':'UNAVAILABLE','science_approved':False})
    result=run({'pair_dir':str(pair),'min_pixels':1,'exploratory':True,
                'impact_gap':{'report':str(report),'status':'PARTIAL_DATA_GAP'}},tmp_path/'new_run')
    assert result['status']=='PARTIAL'
    assert result['stages']['M3']['status']=='PARTIAL_DATA_GAP'
    assert all(result['stages'][m]['status']=='PASS' for m in ('M1','M2','M4','M5','M6'))
    assert (tmp_path/'new_run/M3/population-data-gap.json').exists()
    assert (tmp_path/'new_run/M2/m3-delivery.json').exists()
