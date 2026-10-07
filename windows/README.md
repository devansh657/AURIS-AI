# AURIS Windows Device Service

The .NET 10 worker is the production service boundary for device identity, remote command validation, replay protection, emergency state, and the future outbound cloud poller. Interactive desktop automation must remain in the signed-in user's visible broker because Windows services run outside the interactive desktop session.

Current implementation:

- `net10.0-windows`, self-contained `win-x64`, single-file publish.
- Windows Service hosting integration.
- Exact JSON envelope and typed parameter parsing.
- Pinned Ed25519 cloud-signature verification compatible with the Python cloud core.
- Device targeting, permission, expiry, action identifier, target, and nonce validation.
- Durable hashed nonce ledger that rejects replay after restart and fails closed if corrupted.
- Health state that keeps remote execution disabled until signed installation and a visible user-session broker are connected.
- Installer that refuses any executable without a valid trusted Authenticode signature.

Build and test:

```powershell
.\.dotnet\dotnet.exe test .\windows\AURIS.Windows.slnx --configuration Release
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_windows_service.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_windows_service.ps1
```

Production installation is intentionally blocked until a trusted code-signing certificate signs `AURIS.DeviceService.exe`. Administrator elevation is required only for the explicit service-registration step.
