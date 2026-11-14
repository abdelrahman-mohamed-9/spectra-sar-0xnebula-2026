"""Visual comparison of ORIGINAL vs FILTERED for one REAL input acquisition."""
import argparse
from pathlib import Path
import numpy as np
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data_loader import load_manifest, safe_pair_file


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('pair_dir',type=Path); ap.add_argument('filter_dir',type=Path)
    ap.add_argument('--side',choices=['before','after'],default='before')
    ap.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    ap.add_argument('--max-dimension',type=int,default=1200)
    args=ap.parse_args()
    if args.max_dimension<1: ap.error('max-dimension must be positive')
    manifest=load_manifest(args.pair_dir)
    original=safe_pair_file(args.pair_dir.resolve(),manifest[args.side]['raster_files'][args.polarization])
    filtered=args.filter_dir/f'{args.side}_{args.polarization}_lee.tif'
    with rasterio.open(original) as a,rasterio.open(filtered) as b:
        if (a.width,a.height,a.crs,a.transform)!=(b.width,b.height,b.crs,b.transform):
            raise ValueError('Filtered and original raster grids differ')
        scale=min(1,args.max_dimension/max(a.width,a.height))
        shape=(max(1,round(a.height*scale)),max(1,round(a.width*scale)))
        raw=a.read(1,out_shape=shape,masked=True).filled(np.nan)
        den=b.read(1,out_shape=shape,masked=True).filled(np.nan)
    positive=np.isfinite(raw)&(raw>0)&np.isfinite(den)&(den>0)
    if not positive.any(): raise ValueError('No valid samples for comparison')
    rdb=np.where(positive,10*np.log10(np.maximum(raw,1e-12)),np.nan)
    ddb=np.where(positive,10*np.log10(np.maximum(den,1e-12)),np.nan)
    lo,hi=np.nanpercentile(rdb[positive],[2,98])
    fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
    for ax,x,title in zip(axs,[rdb,ddb],['Original RTC (unfiltered)','After Lee filtering']):
        ax.imshow(x,cmap='gray',vmin=lo,vmax=hi,interpolation='nearest')
        ax.set_title(title);ax.set_axis_off()
    fig.suptitle(f'{args.side} {args.polarization}: SAME acquisition, gamma0 display in dB')
    output=args.filter_dir/f'{args.side}_{args.polarization}_before_after.png'
    fig.savefig(output,dpi=160);plt.close(fig)
    print(output)
if __name__=='__main__':main()
