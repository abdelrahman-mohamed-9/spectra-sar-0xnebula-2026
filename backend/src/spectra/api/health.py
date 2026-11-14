import asyncio
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from spectra.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: str
    components: dict[str, str] | None = None


async def tcp_probe(url: str | None, default_port: int) -> str:
    """T02 connectivity-only probe; not a database query or object-store auth check."""
    if not url:
        return "not_configured"
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or default_port
    if not host:
        return "invalid_configuration"
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
        writer.close()
        await writer.wait_closed()
        return "reachable_tcp_only"
    except (OSError, asyncio.TimeoutError, ValueError):
        return "unreachable"


@router.get("/live", response_model=HealthStatus)
async def live() -> HealthStatus:
    return HealthStatus(status="alive")


def dependency_probe(name, settings):
    """Authenticated protocol checks, never TCP-only readiness."""
    try:
        if name == 'database':
            if not settings.database_url:return 'not_configured'
            from spectra.persistence.database import get_engine, database_status
            database_status(get_engine())
        elif name == 'queue':
            if not settings.redis_url:return 'not_configured'
            from redis import Redis
            client=Redis.from_url(settings.redis_url,socket_connect_timeout=3,socket_timeout=3)
            try:
                if client.ping() is not True: return 'unavailable'
            finally: client.close()
        elif name == 'object_storage':
            if not all([settings.s3_endpoint_url,settings.s3_access_key,settings.s3_secret_key]):return 'not_configured'
            import boto3
            from botocore.config import Config
            client=boto3.client('s3',endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,config=Config(connect_timeout=3,read_timeout=3,retries={'max_attempts':0}))
            try:client.head_bucket(Bucket=settings.s3_bucket)
            finally:client.close()
        return 'ready'
    except Exception:
        return 'unavailable'  # Never return connection URLs or credential-bearing errors.


@router.get("/ready", response_model=HealthStatus)
async def ready(response: Response, settings: Settings = Depends(get_settings)) -> HealthStatus:
    names=['database','queue','object_storage']
    values=await asyncio.gather(*(asyncio.to_thread(dependency_probe,n,settings) for n in names))
    components=dict(zip(names,values))
    ok=all(v=='ready' for v in values)
    response.status_code=200 if ok else 503
    return HealthStatus(status='ready' if ok else 'integration_not_verified',components=components)
