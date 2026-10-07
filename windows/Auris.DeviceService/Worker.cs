namespace Auris.DeviceService;

public sealed class Worker(
    ILogger<Worker> logger,
    ServiceRuntimeState runtimeState,
    TimeProvider timeProvider) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        await runtimeState.WriteAsync(
            "online",
            cloudConfigured: CloudConfigured(),
            stoppingToken);
        logger.LogInformation(
            "AURIS Device Service online. Remote channel configured: {Configured}",
            CloudConfigured());
        while (!stoppingToken.IsCancellationRequested)
        {
            await runtimeState.WriteAsync(
                "online",
                cloudConfigured: CloudConfigured(),
                stoppingToken);
            await Task.Delay(TimeSpan.FromSeconds(10), timeProvider, stoppingToken);
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        await runtimeState.WriteAsync(
            "stopping",
            cloudConfigured: CloudConfigured(),
            cancellationToken);
        await base.StopAsync(cancellationToken);
    }

    private static bool CloudConfigured() =>
        Uri.TryCreate(
            Environment.GetEnvironmentVariable("AURIS_CLOUD_ENDPOINT"),
            UriKind.Absolute,
            out var endpoint)
        && endpoint.Scheme == Uri.UriSchemeHttps
        && !string.IsNullOrWhiteSpace(
            Environment.GetEnvironmentVariable("AURIS_CLOUD_SIGNING_PUBLIC_KEY"));
}
