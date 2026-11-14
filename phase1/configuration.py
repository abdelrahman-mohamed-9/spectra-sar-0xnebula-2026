from copy import deepcopy
from pathlib import Path
from phase1.common import ROOT

def resolve_config(config):
    cfg=deepcopy(config)
    for key in ('before','after','pair_dir','model_dir','reference','provenance'):
        if cfg.get(key) and not Path(cfg[key]).is_absolute(): cfg[key]=str(ROOT/cfg[key])
    for key in ('aoi','osm','population','source_manifest'):
        if cfg.get('impact',{}).get(key) and not Path(cfg['impact'][key]).is_absolute():
            cfg['impact'][key]=str(ROOT/cfg['impact'][key])
    return cfg
