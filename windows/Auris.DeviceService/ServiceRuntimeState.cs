using System.Text.Json;

namespace Auris.DeviceService;

public sealed class ServiceRuntimeState
{
    private readonly string statusPath;

    public ServiceRuntimeState()
    {
        var configured = Environment.GetEnvironmentVariable("AURIS_SERVICE_STATUS_PATH");
        statusPath = string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "AURIS",
                "device-service-status.json")
            : Path.GetFullPath(configured);
    }

    public async Task WriteAsync(
        string state,
        bool cloudConfigured,
        CancellationToken cancellationToken)
    {
        var directory = Path.GetDirectoryName(statusPath)
            ?? throw new InvalidOperationException("The service status directory is invalid.");
        Directory.CreateDirectory(directory);
        var payload = new
        {
            service = "AURIS Device Service",
            state,
            cloud_configured = cloudConfigured,
            remote_execution = "disabled_until_signed_install_and_visible_broker",
            process_id = Environment.ProcessId,
            updated_at = DateTimeOffset.UtcNow,
        };
        var temporary = statusPath + ".tmp";
        await File.WriteAllTextAsync(
            temporary,
            JsonSerializer.Serialize(payload),
            cancellationToken);
        File.Move(temporary, statusPath, overwrite: true);
    }
}
