"""SPECTRA-SAR M3/T08: auditable analyst-facing suggestions, not emergency decisions."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import yaml

SCHEMA = '1.0.0'
DISCLAIMER = ('Research-only analytical screening. No evacuation, rescue, closure, '
              'resource-dispatch, casualty, or confirmed-damage decision is authorized.')

class DecisionInputError(ValueError):
    pass

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_json(path, module):
    try:
        doc=json.loads(Path(path).read_text(encoding='utf-8'),
                       parse_constant=lambda x: (_ for _ in ()).throw(DecisionInputError('Invalid JSON number '+x)))
    except json.JSONDecodeError as exc:
        raise DecisionInputError('Malformed JSON') from exc
    if not isinstance(doc,dict) or doc.get('schema_version')!=SCHEMA or doc.get('module')!=module:
        raise DecisionInputError('Expected '+module+' schema '+SCHEMA)
    return doc

def validate_rules(rules):
    if not isinstance(rules,dict) or rules.get('schema_version')!=SCHEMA or not rules.get('rule_set_id'):
        raise DecisionInputError('Invalid rules schema')
    classes={'LOW','MODERATE','HIGH','VERY_HIGH'}
    if set(rules.get('allowed_classes',[]))!=classes or set(rules.get('priority_rules',{}))!=classes:
        raise DecisionInputError('Unexpected priority classes')
    for spec in [*rules['priority_rules'].values(),rules.get('review_required')]:
        if not isinstance(spec,dict) or not isinstance(spec.get('urgency'),str):
            raise DecisionInputError('Invalid recommendation branch')
        recs=spec.get('recommendations')
        if not isinstance(recs,list) or not recs:
            raise DecisionInputError('Each branch needs recommendations')
        for rec in recs:
            if not isinstance(rec,dict) or not all(isinstance(rec.get(k),str) and rec[k].strip() for k in ('code','text')):
                raise DecisionInputError('Invalid recommendation entry')
    q=rules.get('quality')
    if not isinstance(q,dict) or any(type(q.get(k)) is not bool for k in ('require_full_population_coverage','require_source_provenance')):
        raise DecisionInputError('Invalid quality switches')

def develop_recommendations(t07, t06, rules, *, t07_hash=None, t06_hash=None, rules_hash=None):
    """Fail closed on file mismatch; degrade to review on incomplete evidence."""
    validate_rules(rules)
    if t07.get('module')!='SPECTRA-SAR/M3/T07' or t07.get('schema_version')!=SCHEMA:
        raise DecisionInputError('Invalid T07 report')
    if t06.get('module')!='SPECTRA-SAR/M3/T06' or t06.get('schema_version')!=SCHEMA:
        raise DecisionInputError('Invalid T06 report')
    if t06_hash is not None and t07.get('inputs',{}).get('t06_sha256')!=t06_hash:
        raise DecisionInputError('T07 and T06 hash mismatch: possible mixed event')
    summary=t07.get('summary')
    quality=t07.get('data_quality')
    dec=t06.get('decision')
    if not isinstance(summary,dict) or not isinstance(quality,dict) or not isinstance(dec,dict):
        raise DecisionInputError('Missing metrics or decision')
    status=dec.get('status')
    if status not in ('SCREENED','REVIEW_REQUIRED') or summary.get('exposure_priority_status')!=status:
        raise DecisionInputError('Inconsistent T06/T07 statuses')
    warnings=[]
    complete=summary.get('population_estimate_is_complete')
    if type(complete) is not bool: raise DecisionInputError('Invalid completeness indicator')
    if rules['quality']['require_full_population_coverage'] and not complete:
        warnings.append('Population data incomplete; do not rank the area.')
    if rules['quality']['require_source_provenance']:
        provenance=t07.get('inputs',{})
        if not provenance.get('population_provenance') or not provenance.get('hazard_provenance'):
            warnings.append('Missing population or change-footprint provenance.')
    score=summary.get('exposure_priority_index')
    cls=summary.get('exposure_priority_class')
    if status=='SCREENED':
        if (isinstance(score,bool) or not isinstance(score,(int,float))
                or not math.isfinite(score) or not 0<=score<=100
                or cls not in rules['allowed_classes']
                or dec.get('priority_class')!=cls or dec.get('priority_score')!=score):
            raise DecisionInputError('Invalid or inconsistent screened index/class')
    else:
        if score is not None or cls is not None or dec.get('priority_score') is not None or dec.get('priority_class') is not None:
            raise DecisionInputError('REVIEW_REQUIRED cannot have a priority score/class')
        warnings.extend(dec.get('reasons',[]))
    if not isinstance(t07.get('warnings'),list) or any(not isinstance(x,str) for x in t07['warnings']):
        raise DecisionInputError('Invalid T07 warnings')
    warnings.extend(t07['warnings'])
    publish_priority=status=='SCREENED' and not any(x.startswith(('Population data incomplete','Missing population')) for x in warnings)
    branch=rules['priority_rules'][cls] if publish_priority else rules['review_required']
    result={
        'schema_version':SCHEMA,'module':'SPECTRA-SAR/M3/T08',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'inputs':{'t07_sha256':t07_hash,'t06_sha256':t06_hash,'rules_sha256':rules_hash,
                  'rule_set_id':rules['rule_set_id']},
        'decision':{'status':'ANALYST_REVIEW_SUGGESTED' if publish_priority else 'REVIEW_REQUIRED',
                    'urgency':branch['urgency'],
                    'relative_priority_class':cls if publish_priority else None,
                    'relative_priority_index':score if publish_priority else None,
                    'recommendations':[{**item,'type':'ANALYST_ACTION','requires_human_review':True}
                                       for item in branch['recommendations']],
                    'rationale':('Validated T06 screening class: '+cls if publish_priority else
                                 'Incomplete or unverified evidence; no ranking is provided.')},
        'quality_warnings':list(dict.fromkeys(warnings)),
        'limitations':[DISCLAIMER,'SAR spatial change is not proof of a flood or fire.',
                       'OSM and WorldPop coverage varies by geography and vintage.',
                       'Priority thresholds are uncalibrated and must not be interpreted as physical risk.']}
    return result

def analyze(t07_path, t06_path, rules_path):
    t07=load_json(t07_path,'SPECTRA-SAR/M3/T07')
    t06=load_json(t06_path,'SPECTRA-SAR/M3/T06')
    cfg=yaml.safe_load(Path(rules_path).read_text(encoding='utf-8'))
    return develop_recommendations(t07,t06,cfg,t07_hash=sha256(t07_path),
                                   t06_hash=sha256(t06_path),rules_hash=sha256(rules_path))

def main():
    p=argparse.ArgumentParser(description='M3/T08 analyst-facing recommendations, NOT emergency response')
    p.add_argument('--t07',required=True)
    p.add_argument('--t06',required=True)
    p.add_argument('--rules',default='recommendation_rules.yaml')
    p.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        result=analyze(args.t07,args.t06,args.rules)
        out=Path(args.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({'status':result['decision']['status'],'out':str(out)},indent=2))
    except (DecisionInputError,OSError,ValueError,KeyError,yaml.YAMLError) as exc:
        p.exit(2,'REJECT: '+str(exc)+'\n')

if __name__=='__main__': main()
