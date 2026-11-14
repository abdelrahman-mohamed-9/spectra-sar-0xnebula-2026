from pathlib import Path
import os,secrets
root=Path(__file__).resolve().parents[1]
p=root/'.local.env'
if not p.exists():
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:
        for key in ('INTERNAL_API_KEY','JWT_SECRET','POSTGRES_PASSWORD','MINIO_ROOT_PASSWORD'):
            f.write(key+'='+secrets.token_hex(32)+'\n')
        f.write('MINIO_ROOT_USER=spectra-local\n')
print('Local credentials ready in .local.env (not printed).')
