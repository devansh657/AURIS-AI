from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "auris_cloud.app:create_app",
        factory=True,
        host=os.environ.get("AURIS_CLOUD_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("AURIS_CLOUD_TRUSTED_PROXIES", "127.0.0.1"),
        server_header=False,
    )


if __name__ == "__main__":
    main()
