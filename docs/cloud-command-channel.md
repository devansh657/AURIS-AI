# AURIS Cloud Command Channel

## Implemented Contract

The `auris_cloud` package is a FastAPI command-plane contract for an outbound-only Windows device channel. It provides:

- One-time, expiring device enrolment codes issued through bearer-authenticated admin routes.
- Pinned Ed25519 device certificates with a device UUID in the certificate SAN.
- Device-signed poll and acknowledgement requests with 30-second timestamps and durable nonce replay protection.
- Exact typed command envelopes signed by a pinned Ed25519 cloud key.
- Per-device permission scopes, revocation, bounded command expiry, durable leasing, acknowledgements, and audit records.
- An HTTPS-only edge client that independently validates the cloud signature, target device, tool, parameters, local permissions, expiry, and nonce before execution can be considered.

Remote Windows execution remains disabled until enrolment, a visible local-control indicator, and production transport are connected. Contract tests do not execute a Windows action.

## Isolated Runtime

Create the isolated cloud environment and install the pinned dependencies:

```powershell
C:\Users\dmodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m venv .cloud-venv
.\.cloud-venv\Scripts\python.exe -m pip install fastapi==0.139.2 uvicorn==0.51.0 cryptography==49.0.0 httpx2==2.7.0
```

Run the cloud contract suite:

```powershell
.\.cloud-venv\Scripts\python.exe -m unittest tests.test_cloud_command_api -v
```

## Required Configuration

The cloud API refuses to start without these values:

```text
AURIS_CLOUD_ADMIN_TOKEN       Random secret of at least 40 characters
AURIS_CLOUD_SIGNING_KEY_PATH Read-only mounted Ed25519 private PEM
AURIS_CLOUD_DATABASE_PATH    Durable database path for development
AURIS_CLOUD_REQUIRE_HTTPS    true in every remote environment
AURIS_CLOUD_TRUSTED_PROXIES  Explicit ingress proxy addresses
```

The edge channel additionally requires a deployed HTTPS endpoint, enrolled device certificate/private key, and pinned cloud public key. These are intentionally absent from the repository.

## Production Gates

- Replace the contract SQLite store with PostgreSQL and migration ownership.
- Store the admin and signing secrets in the cloud provider's secret vault or managed key service.
- Terminate TLS with a trusted server certificate and require mutual TLS at ingress.
- Add identity-aware portal authentication, rate limiting, monitoring, backup/restore, and disaster recovery.
- Package the edge poller inside the signed Windows service and expose a permanent visible operation indicator.
- Run independent penetration, replay, revocation, and recovery evaluations.

Until those gates pass, the local Device workspace must show the cloud router as `NOT CONNECTED`.
