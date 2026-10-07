using Auris.DeviceService.Security;

namespace Auris.DeviceService.Tests;

public sealed class DurableNonceStoreTests : IDisposable
{
    private readonly string root = Path.Combine(Path.GetTempPath(), "auris-nonce-" + Guid.NewGuid());

    [Fact]
    public void ClaimedNonceRemainsRejectedAfterStoreRestart()
    {
        var path = Path.Combine(root, "nonces.json");
        var now = DateTimeOffset.Parse("2026-08-12T12:00:00Z");
        var firstProcess = new DurableNonceStore(path);

        var claimed = firstProcess.TryClaim("nonce-restart-test", now.AddMinutes(1), now);
        var restartedProcess = new DurableNonceStore(path);
        var replayed = restartedProcess.TryClaim("nonce-restart-test", now.AddMinutes(1), now);

        Assert.True(claimed);
        Assert.False(replayed);
        Assert.DoesNotContain("nonce-restart-test", File.ReadAllText(path));
    }

    [Fact]
    public void CorruptLedgerFailsClosed()
    {
        Directory.CreateDirectory(root);
        var path = Path.Combine(root, "nonces.json");
        File.WriteAllText(path, "not-json");

        var store = new DurableNonceStore(path);

        Assert.False(store.TryClaim(
            "nonce-corrupt-ledger",
            DateTimeOffset.UtcNow.AddMinutes(1),
            DateTimeOffset.UtcNow));
    }

    public void Dispose()
    {
        if (Directory.Exists(root))
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
