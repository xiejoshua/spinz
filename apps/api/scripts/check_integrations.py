#!/usr/bin/env python3
"""Smoke-test every auxd-api external integration against the local ``.env``.

Run from ``apps/api/`` (so pydantic-settings picks up ``./.env``)::

    uv run python scripts/check_integrations.py

Each check is **non-destructive**: a sandbox event, a TTL'd Redis key,
a temporary R2 object that gets deleted, etc. The Sentry + PostHog
checks leave one harmless test event in each dashboard — clearly tagged
``smoke_test=true`` so they're easy to filter or delete.

Exit code 0 if every check passes; exit 1 if any fail.

Not part of the production code surface — lives outside ``src/`` so mypy
doesn't enforce strict typing on third-party SDKs that lack stubs.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time
import uuid
from dataclasses import dataclass

# Make Python's HTTPS stack use the OS-native cert store BEFORE any HTTPS-
# using library imports. This is the canonical fix for two macOS pain points:
#   (1) python.org Python ships with an empty cert.pem (Install Certificates
#       command never run), and
#   (2) corporate TLS-inspecting proxies (Zscaler, Netskope, etc.) install
#       their own root CA in the system keychain — certifi's static bundle
#       can't see it, but the OS keychain can.
# truststore is maintained by the urllib3 author; it patches the stdlib `ssl`
# module to use the macOS Security framework / Windows schannel / Linux
# openssl-system-CAs depending on platform.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover — truststore is a hard dep in pyproject
    # Fallback: at least point requests/urllib3 at certifi's bundle.
    try:
        import certifi

        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass

from auxd_api.settings import Settings, get_settings  # noqa: E402 — env tweak above must come first

# --- Result type ----------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    duration_ms: float


def _ok(name: str, message: str, t0: float) -> CheckResult:
    return CheckResult(name, True, message, (time.perf_counter() - t0) * 1000)


def _fail(name: str, message: str, t0: float) -> CheckResult:
    return CheckResult(name, False, message, (time.perf_counter() - t0) * 1000)


# --- Individual checks ---------------------------------------------


async def check_settings(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    enabled = []
    if s.SENTRY_DSN:
        enabled.append("Sentry")
    if s.POSTHOG_API_KEY:
        enabled.append("PostHog")
    if s.RESEND_API_KEY:
        enabled.append("Resend")
    if s.R2_ACCESS_KEY_ID and s.R2_SECRET_ACCESS_KEY and s.R2_ENDPOINT_URL:
        enabled.append("R2")
    if s.SPOTIFY_INTEGRATION_ENABLED:
        enabled.append("Spotify")
    summary = ", ".join(enabled) if enabled else "none"
    return _ok(
        "Settings",
        f"env={s.ENVIRONMENT.value} · integrations enabled: {summary}",
        t0,
    )


async def check_mongodb(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(s.MONGODB_URI, serverSelectionTimeoutMS=8000)
        try:
            await client.admin.command("ping")
            db = client.get_default_database()
            db_name = db.name if db is not None else "<no default db>"
            collections = await db.list_collection_names() if db is not None else []
            return _ok(
                "MongoDB",
                f"ping ok · db={db_name} · collections={len(collections)}",
                t0,
            )
        finally:
            client.close()
    except Exception as exc:
        return _fail("MongoDB", f"{type(exc).__name__}: {exc}", t0)


async def check_redis(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    try:
        from redis.asyncio import from_url

        client = from_url(s.REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        try:
            pong = await client.ping()
            key = f"_auxd_smoke_test:{uuid.uuid4().hex[:8]}"
            await client.set(key, "ok", ex=5)
            value = await client.get(key)
            await client.delete(key)
            value_str = value.decode() if isinstance(value, bytes) else value
            result = _ok(
                "Redis",
                f"PING={pong} · SET/GET/DEL roundtrip ok · value={value_str}",
                t0,
            )
        finally:
            # Upstash + Python 3.14 + corporate proxies sometimes drag the
            # TLS-close handshake past 5s. The smoke test cares that the
            # commands succeeded — not that the socket closes cleanly. So
            # bound the close and swallow timeout/exception.
            with contextlib.suppress(TimeoutError, Exception):
                await asyncio.wait_for(client.aclose(), timeout=2)
        return result
    except Exception as exc:
        return _fail("Redis", f"{type(exc).__name__}: {exc}", t0)


async def check_sentry(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    if not s.SENTRY_DSN:
        return _fail("Sentry", "SENTRY_DSN not set", t0)
    try:
        import sentry_sdk

        from auxd_api.lib.observability import init_sentry

        initialized = init_sentry(
            dsn=s.SENTRY_DSN,
            environment=s.ENVIRONMENT.value,
            release="auxd-smoke-test",
        )
        if not initialized:
            return _fail("Sentry", "init_sentry returned False", t0)
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("smoke_test", "true")
            scope.set_tag("source", "check_integrations.py")
            event_id = sentry_sdk.capture_message(
                "auxd integration smoke test — safe to delete",
                level="info",
            )
        # sentry_sdk.flush() in 2.x returns None (not a bool) — it blocks
        # until the transport queue drains or the timeout elapses. If the
        # SDK itself raises, we catch it in the outer `except` below. 15s
        # timeout gives Zscaler-mediated HTTPS handshakes room to complete.
        sentry_sdk.flush(timeout=15)
        return _ok(
            "Sentry",
            f"event captured · id={event_id} · check sentry.io for tag smoke_test=true",
            t0,
        )
    except Exception as exc:
        return _fail("Sentry", f"{type(exc).__name__}: {exc}", t0)


async def check_posthog(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    if not s.POSTHOG_API_KEY:
        return _fail("PostHog", "POSTHOG_API_KEY not set", t0)
    try:
        # Use a dedicated Posthog() instance for the smoke test so we control
        # init + shutdown deterministically. (lib/observability.emit_event uses
        # a different lazy-init pattern; mixing the two leaks the module-level
        # `posthog` API which requires its own api_key setup.)
        from posthog import Posthog

        client = Posthog(
            project_api_key=s.POSTHOG_API_KEY,
            host=s.POSTHOG_HOST,
            sync_mode=True,  # block on send so SSL errors surface here, not at exit
        )
        client.capture(
            distinct_id="smoke-test",
            event="smoke_test.run",
            properties={
                "smoke_test": True,
                "source": "check_integrations.py",
                "environment": s.ENVIRONMENT.value,
                "timestamp": int(time.time()),
            },
        )
        client.shutdown()
        return _ok(
            "PostHog",
            f"event smoke_test.run captured + flushed · check {s.POSTHOG_HOST}",
            t0,
        )
    except Exception as exc:
        return _fail("PostHog", f"{type(exc).__name__}: {exc}", t0)


async def check_resend(s: Settings) -> CheckResult:
    t0 = time.perf_counter()
    if not s.RESEND_API_KEY:
        return _fail("Resend", "RESEND_API_KEY not set", t0)
    try:
        import resend

        resend.api_key = s.RESEND_API_KEY
        # Resend's universal sandbox: `onboarding@resend.dev` from + `delivered@resend.dev` to
        # both work BEFORE the sender domain is verified. Once xiejoshua.com DKIM is in,
        # swap `from` to `noreply@xiejoshua.com`.
        params = {
            "from": "onboarding@resend.dev",
            "to": ["delivered@resend.dev"],
            "subject": "auxd integration smoke test",
            "text": (
                "This is a sandbox test from check_integrations.py.\n"
                "Safe to ignore — Resend's delivered@resend.dev address swallows it."
            ),
        }
        result = resend.Emails.send(params)
        email_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        return _ok(
            "Resend",
            f"sandbox send ok · email_id={email_id or 'unknown'}",
            t0,
        )
    except Exception as exc:
        return _fail("Resend", f"{type(exc).__name__}: {exc}", t0)


def check_r2(s: Settings) -> CheckResult:
    """boto3 is sync — we wrap in a thread elsewhere if needed."""
    t0 = time.perf_counter()
    if not (s.R2_ACCESS_KEY_ID and s.R2_SECRET_ACCESS_KEY and s.R2_ENDPOINT_URL):
        return _fail("R2", "one or more R2_* env vars missing", t0)
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=s.R2_ENDPOINT_URL,
            aws_access_key_id=s.R2_ACCESS_KEY_ID,
            aws_secret_access_key=s.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 2}),
        )
        # 1. head_bucket — confirms bucket exists + credentials authorize it.
        client.head_bucket(Bucket=s.R2_BUCKET_NAME)
        # 2. Round-trip a tiny smoke object.
        key = f"_auxd_smoke_test/{uuid.uuid4().hex[:8]}.txt"
        body = b"auxd smoke test payload"
        client.put_object(
            Bucket=s.R2_BUCKET_NAME,
            Key=key,
            Body=body,
            ContentType="text/plain",
        )
        retrieved = client.get_object(Bucket=s.R2_BUCKET_NAME, Key=key)["Body"].read()
        if retrieved != body:
            return _fail("R2", f"roundtrip mismatch on {key}", t0)
        client.delete_object(Bucket=s.R2_BUCKET_NAME, Key=key)
        return _ok(
            "R2",
            f"head_bucket + PUT/GET/DELETE ok on bucket={s.R2_BUCKET_NAME}",
            t0,
        )
    except Exception as exc:
        return _fail("R2", f"{type(exc).__name__}: {exc}", t0)


# --- Runner --------------------------------------------------------


async def run_all() -> int:
    print("\n🔌 auxd integration smoke test\n")
    # Load settings first — any validation error fails loud here.
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"  ✗ Settings validation failed: {type(exc).__name__}: {exc}\n")
        print("  Fix apps/api/.env (compare against apps/api/.env.example) and re-run.\n")
        return 1

    results: list[CheckResult] = [
        await check_settings(settings),
        await check_mongodb(settings),
        await check_redis(settings),
        await check_sentry(settings),
        await check_posthog(settings),
        await check_resend(settings),
        check_r2(settings),  # sync
    ]

    # Pretty table.
    name_w = max(len(r.name) for r in results)
    print(f"  {'CHECK':<{name_w}}  STATUS  TIME      MESSAGE")
    print(f"  {'-' * name_w}  ------  --------  {'-' * 60}")
    for r in results:
        icon = "✓" if r.passed else "✗"
        print(f"  {r.name:<{name_w}}  {icon}       {r.duration_ms:>5.0f}ms   {r.message}")

    failed = [r for r in results if not r.passed]
    print()
    if failed:
        print(f"❌ {len(failed)} of {len(results)} integrations failed.\n")
        for r in failed:
            print(f"   • {r.name}: {r.message}")
        print()
        return 1
    print(f"✅ All {len(results)} checks green — env is ready for Fly deploy.\n")
    return 0


def main() -> None:
    sys.exit(asyncio.run(run_all()))


if __name__ == "__main__":
    main()
