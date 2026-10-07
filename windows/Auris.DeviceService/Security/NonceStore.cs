using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Auris.DeviceService.Security;

public interface INonceStore
{
    bool TryClaim(string nonce, DateTimeOffset expiresAt, DateTimeOffset now);
}

public sealed class DurableNonceStore : INonceStore
{
    private readonly object sync = new();
    private readonly string path;
    private Dictionary<string, DateTimeOffset> claims;
    private bool healthy = true;

    public DurableNonceStore(string path)
    {
        this.path = Path.GetFullPath(path);
        claims = Load();
    }

    public bool TryClaim(string nonce, DateTimeOffset expiresAt, DateTimeOffset now)
    {
        lock (sync)
        {
            if (!healthy)
            {
                return false;
            }
            claims = claims
                .Where(item => item.Value > now)
                .ToDictionary(item => item.Key, item => item.Value, StringComparer.Ordinal);
            var digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(nonce)));
            if (!claims.TryAdd(digest, expiresAt))
            {
                return false;
            }
            try
            {
                Persist();
                return true;
            }
            catch (IOException)
            {
                claims.Remove(digest);
                healthy = false;
                return false;
            }
            catch (UnauthorizedAccessException)
            {
                claims.Remove(digest);
                healthy = false;
                return false;
            }
        }
    }

    private Dictionary<string, DateTimeOffset> Load()
    {
        if (!File.Exists(path))
        {
            return new Dictionary<string, DateTimeOffset>(StringComparer.Ordinal);
        }
        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, DateTimeOffset>>(
                    File.ReadAllText(path))
                ?? new Dictionary<string, DateTimeOffset>(StringComparer.Ordinal);
        }
        catch (JsonException)
        {
            healthy = false;
            return new Dictionary<string, DateTimeOffset>(StringComparer.Ordinal);
        }
    }

    private void Persist()
    {
        var directory = Path.GetDirectoryName(path)
            ?? throw new IOException("The nonce ledger directory is invalid.");
        Directory.CreateDirectory(directory);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(claims));
        File.Move(temporary, path, overwrite: true);
    }
}

public sealed class InMemoryNonceStore : INonceStore
{
    private readonly object sync = new();
    private readonly Dictionary<string, DateTimeOffset> claims = new(StringComparer.Ordinal);

    public bool TryClaim(string nonce, DateTimeOffset expiresAt, DateTimeOffset now)
    {
        lock (sync)
        {
            foreach (var expired in claims.Where(item => item.Value <= now).Select(item => item.Key).ToArray())
            {
                claims.Remove(expired);
            }
            return claims.TryAdd(nonce, expiresAt);
        }
    }
}
