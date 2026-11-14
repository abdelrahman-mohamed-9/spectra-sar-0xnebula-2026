"""CLI: evaluate real, pre-aligned numpy raster masks with documented reference."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from verification import verify_result

def main():
    a=argparse.ArgumentParser(description='Evaluate aligned SAR change masks against independent reference')
    a.add_argument('--prediction',required=True,help='npy file with 0/1 predicted changes')
    a.add_argument('--reference',required=True,help='npy file with 0/1 reference changes')
    a.add_argument('--prediction-meta',required=True,help='metadata JSON')
    a.add_argument('--reference-meta',required=True,help='metadata JSON')
    a.add_argument('--valid-mask',help='optional boolean .npy; exclude unknown/cloud/layover pixels')
    a.add_argument('--probabilities',help='optional probability .npy')
    a.add_argument('--output',required=True,help='result json path')
    args=a.parse_args()
    data=lambda path: np.load(path,allow_pickle=False)
    meta=lambda path: json.loads(Path(path).read_text(encoding='utf8'))
    result=verify_result(data(args.prediction),data(args.reference),meta(args.prediction_meta),meta(args.reference_meta),
             data(args.valid_mask) if args.valid_mask else None,data(args.probabilities) if args.probabilities else None)
    Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps({'status':result['status'],'metrics':result['metrics']},indent=2))
if __name__=='__main__': main()
