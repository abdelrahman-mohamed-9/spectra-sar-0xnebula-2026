"""Opt-in external service probes; no synthetic satellite data or data modifications.

Usage: python scripts/integration_smoke.py --api http://127.0.0.1:8000
Checks API health, PostGIS, Redis, S3 bucket access and worker inspection.
Requires service dependencies to be installed and services reachable.
"""
import argparse
import json
import os
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

def check_api(base):
    with urlopen(base.rstrip('/')+'/health/live',timeout=5) as response:
        doc=json.load(response)
        if response.status != 200 or doc.get('status')!='alive':
            raise RuntimeError('unexpected liveness response')

def check_postgis():
    from sqlalchemy import create_engine,text
    url=os.environ.get('DATABASE_URL')
    if not url: raise RuntimeError('DATABASE_URL not configured')
    engine=create_engine(url,pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            version=conn.execute(text('SELECT PostGIS_Version()')).scalar()
            migration=conn.execute(text('SELECT version_num FROM alembic_version')).scalar()
            if not version or not migration: raise RuntimeError('missing PostGIS extension or migration')
    finally: engine.dispose()

def check_redis():
    import redis
    url=os.environ.get('REDIS_URL')
    if not url: raise RuntimeError('REDIS_URL not configured')
    r=redis.Redis.from_url(url,socket_connect_timeout=4,socket_timeout=4)
    if not r.ping(): raise RuntimeError('Redis ping returned false')

def check_storage():
    import boto3
    endpoint=os.environ.get('S3_ENDPOINT_URL')
    bucket=os.environ.get('S3_BUCKET','spectra-sar')
    if not endpoint: raise RuntimeError('S3_ENDPOINT_URL not configured')
    client=boto3.client('s3',endpoint_url=endpoint,
        aws_access_key_id=os.environ.get('S3_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('S3_SECRET_KEY'),
        region_name=os.environ.get('S3_REGION','us-east-1'))
    client.head_bucket(Bucket=bucket)

def check_worker():
    from spectra.workers.task_queue import celery_app
    if celery_app is None: raise RuntimeError('Celery app unavailable')
    result=celery_app.control.ping(timeout=4)
    if not result: raise RuntimeError('no responding Celery workers')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://127.0.0.1:8000')
    args=parser.parse_args()
    checks={'api_liveness':lambda:check_api(args.api),'postgis_migration':check_postgis,
            'redis':check_redis,'s3_bucket':check_storage,'celery_worker':check_worker}
    results={}
    for name,fn in checks.items():
        try:
            fn()
            results[name]={'status':'PASS'}
        except Exception as exc:
            results[name]={'status':'FAIL','detail':str(exc)[:300]}
    print(json.dumps(results,indent=2))
    return 0 if all(item['status']=='PASS' for item in results.values()) else 1

if __name__=='__main__':sys.exit(main())
