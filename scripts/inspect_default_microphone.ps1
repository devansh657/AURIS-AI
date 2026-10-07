param(
    [int]$SampleMilliseconds = 1800,
    [switch]$Unmute,
    [ValidateRange(-1,100)][int]$VolumePercent = -1
)

$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;

namespace Auris.Audio
{
    public enum DataFlow { Render = 0, Capture = 1, All = 2 }
    public enum Role { Console = 0, Multimedia = 1, Communications = 2 }

    [ComImport]
    [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    internal class MMDeviceEnumeratorComObject { }

    [ComImport]
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(DataFlow dataFlow, int stateMask, out object devices);
        int GetDefaultAudioEndpoint(DataFlow dataFlow, Role role, out IMMDevice device);
        int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice device);
        int RegisterEndpointNotificationCallback(IntPtr client);
        int UnregisterEndpointNotificationCallback(IntPtr client);
    }

    [ComImport]
    [Guid("D666063F-1587-4E43-81F1-B948E807363F")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IMMDevice
    {
        int Activate(ref Guid interfaceId, int classContext, IntPtr activationParameters,
            [MarshalAs(UnmanagedType.IUnknown)] out object instance);
        int OpenPropertyStore(int storageMode, out IntPtr properties);
        int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
        int GetState(out int state);
    }

    [ComImport]
    [Guid("C02216F6-8C67-4B5B-9D00-D008E73E0064")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IAudioMeterInformation
    {
        int GetPeakValue(out float peak);
        int GetMeteringChannelCount(out int channelCount);
        int GetChannelsPeakValues(int channelCount, IntPtr peakValues);
        int QueryHardwareSupport(out int hardwareSupportMask);
    }

    [ComImport]
    [Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IAudioEndpointVolume
    {
        int RegisterControlChangeNotify(IntPtr notify);
        int UnregisterControlChangeNotify(IntPtr notify);
        int GetChannelCount(out int channelCount);
        int SetMasterVolumeLevel(float levelDb, Guid eventContext);
        int SetMasterVolumeLevelScalar(float level, Guid eventContext);
        int GetMasterVolumeLevel(out float levelDb);
        int GetMasterVolumeLevelScalar(out float level);
        int SetChannelVolumeLevel(int channel, float levelDb, Guid eventContext);
        int SetChannelVolumeLevelScalar(int channel, float level, Guid eventContext);
        int GetChannelVolumeLevel(int channel, out float levelDb);
        int GetChannelVolumeLevelScalar(int channel, out float level);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, Guid eventContext);
        int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
    }

    public sealed class CaptureSnapshot
    {
        public string Role { get; set; }
        public string EndpointId { get; set; }
        public int DeviceState { get; set; }
        public bool Muted { get; set; }
        public int VolumePercent { get; set; }
        public int PreviousVolumePercent { get; set; }
        public int PeakPercent { get; set; }
    }

    public static class DefaultCaptureProbe
    {
        private const int InProcess = 0x1;
        private const int LocalServer = 0x4;

        public static CaptureSnapshot Inspect(Role role, int sampleMilliseconds, bool unmute, int volumePercent)
        {
            var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            IMMDevice device;
            Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(DataFlow.Capture, role, out device));

            string id;
            int state;
            Marshal.ThrowExceptionForHR(device.GetId(out id));
            Marshal.ThrowExceptionForHR(device.GetState(out state));

            object volumeObject;
            var volumeId = typeof(IAudioEndpointVolume).GUID;
            Marshal.ThrowExceptionForHR(device.Activate(ref volumeId, InProcess | LocalServer, IntPtr.Zero, out volumeObject));
            var volume = (IAudioEndpointVolume)volumeObject;
            float scalar;
            bool muted;
            Marshal.ThrowExceptionForHR(volume.GetMasterVolumeLevelScalar(out scalar));
            var previousVolume = scalar;
            Marshal.ThrowExceptionForHR(volume.GetMute(out muted));
            if (volumePercent >= 0 && volumePercent <= 100)
            {
                Marshal.ThrowExceptionForHR(volume.SetMasterVolumeLevelScalar(volumePercent / 100.0f, Guid.Empty));
                Marshal.ThrowExceptionForHR(volume.GetMasterVolumeLevelScalar(out scalar));
            }
            if (unmute && muted)
            {
                Marshal.ThrowExceptionForHR(volume.SetMute(false, Guid.Empty));
                Marshal.ThrowExceptionForHR(volume.GetMute(out muted));
            }

            object meterObject;
            var meterId = typeof(IAudioMeterInformation).GUID;
            Marshal.ThrowExceptionForHR(device.Activate(ref meterId, InProcess | LocalServer, IntPtr.Zero, out meterObject));
            var meter = (IAudioMeterInformation)meterObject;
            var peak = 0.0f;
            var deadline = DateTime.UtcNow.AddMilliseconds(Math.Max(100, Math.Min(sampleMilliseconds, 10000)));
            while (DateTime.UtcNow < deadline)
            {
                float current;
                Marshal.ThrowExceptionForHR(meter.GetPeakValue(out current));
                peak = Math.Max(peak, current);
                Thread.Sleep(35);
            }

            return new CaptureSnapshot {
                Role = role.ToString(),
                EndpointId = id,
                DeviceState = state,
                Muted = muted,
                VolumePercent = (int)Math.Round(scalar * 100),
                PreviousVolumePercent = (int)Math.Round(previousVolume * 100),
                PeakPercent = (int)Math.Round(peak * 100)
            };
        }
    }
}
'@

$snapshots = foreach ($role in @(
    [Auris.Audio.Role]::Console,
    [Auris.Audio.Role]::Multimedia,
    [Auris.Audio.Role]::Communications
)) {
    $snapshot = [Auris.Audio.DefaultCaptureProbe]::Inspect($role, $SampleMilliseconds, [bool]$Unmute, $VolumePercent)
    $endpointKey = [regex]::Match($snapshot.EndpointId, '\{[0-9a-f-]{36}\}$', 'IgnoreCase').Value
    $propertiesPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture\$endpointKey\Properties"
    $properties = Get-ItemProperty -LiteralPath $propertiesPath -ErrorAction SilentlyContinue
    [PSCustomObject]@{
        role = $snapshot.Role
        endpoint_id = $snapshot.EndpointId
        name = $properties.'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
        state = $snapshot.DeviceState
        muted = $snapshot.Muted
        volume_percent = $snapshot.VolumePercent
        previous_volume_percent = $snapshot.PreviousVolumePercent
        peak_percent = $snapshot.PeakPercent
    }
}

$snapshots | ConvertTo-Json -Depth 4
