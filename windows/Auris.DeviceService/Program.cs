using Auris.DeviceService;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddWindowsService(options => options.ServiceName = "AURIS Device Service");
builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<ServiceRuntimeState>();
builder.Services.AddHostedService<Worker>();

var host = builder.Build();
host.Run();
