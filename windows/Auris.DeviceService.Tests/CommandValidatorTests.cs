using System.Text.Json;
using System.Text;
using Auris.DeviceService.Contracts;
using Auris.DeviceService.Security;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

namespace Auris.DeviceService.Tests;

public sealed class CommandValidatorTests
{
    private static readonly DateTimeOffset Now = DateTimeOffset.Parse("2026-08-12T12:00:00Z");
    private readonly Guid deviceId = Guid.Parse("88f6ca2b-24e6-4f2d-91ba-f057974f36d2");
    private readonly Ed25519PrivateKeyParameters privateKey = new(
        Enumerable.Range(1, 32).Select(value => (byte)value).ToArray());

    [Fact]
    public void ValidCommandIsAcceptedOnceAndReplayIsRejected()
    {
        var validator = Validator(new InMemoryNonceStore());
        var envelope = SignedEnvelope();

        var accepted = validator.ValidateAndClaim(envelope, Now);
        var replayed = validator.ValidateAndClaim(envelope, Now);

        Assert.True(accepted.Ok);
        Assert.True(accepted.SignatureVerified);
        Assert.True(accepted.NonceClaimed);
        Assert.False(replayed.Ok);
        Assert.True(replayed.SignatureVerified);
        Assert.Contains("already consumed", replayed.Error);
    }

    [Fact]
    public void TamperExpiryWrongDeviceAndMissingPermissionAreRejected()
    {
        var validator = Validator(new InMemoryNonceStore());
        var valid = SignedEnvelope();
        var tampered = valid with
        {
            Parameters = valid.Parameters with { Target = "Changed target" },
        };
        var expired = SignedEnvelope(
            issuedAt: Now.AddMinutes(-3),
            expiresAt: Now.AddMinutes(-2));
        var wrongDevice = SignedEnvelope(device: Guid.NewGuid());
        var denied = SignedEnvelope(kind: "media_key");

        Assert.Contains("signature", validator.ValidateAndClaim(tampered, Now).Error);
        Assert.Contains("expired", validator.ValidateAndClaim(expired, Now).Error);
        Assert.Contains("wrong device", validator.ValidateAndClaim(wrongDevice, Now).Error);
        Assert.Contains("denied", validator.ValidateAndClaim(denied, Now).Error);
    }

    [Fact]
    public void ParserRequiresExactEnvelopeAndParameterSchemas()
    {
        var validJson = JsonSerializer.Serialize(SignedEnvelope());
        var extraEnvelope = validJson[..^1] + ",\"unexpected\":true}";
        var extraParameter = validJson.Replace(
            "\"target\":\"AURIS Workspace\"",
            "\"target\":\"AURIS Workspace\",\"path\":\"C:\\\\secret\"");

        var parsed = DeviceCommandEnvelope.Parse(validJson);

        Assert.Equal(deviceId.ToString(), parsed.DeviceId);
        Assert.Throws<CommandFormatException>(() => DeviceCommandEnvelope.Parse(extraEnvelope));
        Assert.Throws<CommandFormatException>(() => DeviceCommandEnvelope.Parse(extraParameter));
    }

    [Fact]
    public void PythonCompatibleCanonicalFixtureVerifies()
    {
        const string json = """
            {"command_id":"60d9e0b1-1f5b-4c50-9914-3dc479154957","device_id":"88f6ca2b-24e6-4f2d-91ba-f057974f36d2","tool":"windows.device_action","parameters":{"action_id":"list_auris_workspace","kind":"list_folder","target":"AURIS Workspace"},"permission_scope":"list_folder","issued_at":"2026-08-12T12:00:00+00:00","expires_at":"2026-08-12T12:00:30+00:00","nonce":"abcdefghijklmnopqrstuvwxyzABCDEFGH","signature":"wMT1j8cSfOy49oJYQNpMkgFGq7bADSw8DvO7zgo-0HWvVwputDOIOVfIujckg_CMXCxU1K6PuZcIRN7XIWFcDg"}
            """;
        var envelope = DeviceCommandEnvelope.Parse(json);
        const string expectedCanonical = "{\"command_id\":\"60d9e0b1-1f5b-4c50-9914-3dc479154957\",\"device_id\":\"88f6ca2b-24e6-4f2d-91ba-f057974f36d2\",\"expires_at\":\"2026-08-12T12:00:30+00:00\",\"issued_at\":\"2026-08-12T12:00:00+00:00\",\"nonce\":\"abcdefghijklmnopqrstuvwxyzABCDEFGH\",\"parameters\":{\"action_id\":\"list_auris_workspace\",\"kind\":\"list_folder\",\"target\":\"AURIS Workspace\"},\"permission_scope\":\"list_folder\",\"tool\":\"windows.device_action\"}";

        Assert.Equal(expectedCanonical, Encoding.UTF8.GetString(CanonicalJson.WithoutSignature(envelope)));
        var result = Validator(new InMemoryNonceStore()).ValidateAndClaim(envelope, Now);

        Assert.True(result.Ok, result.Error);
    }

    [Fact]
    public void UiAutomationPermissionIsAcceptedOnlyWhenExplicitlyConfigured()
    {
        var envelope = SignedEnvelope(kind: "invoke_control");
        var allowed = new CommandValidator(
            deviceId,
            privateKey.GeneratePublicKey().GetEncoded(),
            new HashSet<string>(["invoke_control"], StringComparer.Ordinal),
            new InMemoryNonceStore());
        var denied = Validator(new InMemoryNonceStore());

        Assert.True(allowed.ValidateAndClaim(envelope, Now).Ok);
        Assert.Contains("denied", denied.ValidateAndClaim(envelope, Now).Error);
    }

    private CommandValidator Validator(INonceStore nonceStore) =>
        new(
            deviceId,
            privateKey.GeneratePublicKey().GetEncoded(),
            new HashSet<string>(["list_folder", "launch_app"], StringComparer.Ordinal),
            nonceStore);

    private DeviceCommandEnvelope SignedEnvelope(
        DateTimeOffset? issuedAt = null,
        DateTimeOffset? expiresAt = null,
        Guid? device = null,
        string kind = "list_folder")
    {
        var envelope = new DeviceCommandEnvelope(
            Guid.NewGuid().ToString(),
            (device ?? deviceId).ToString(),
            "windows.device_action",
            new DeviceActionParameters("list_auris_workspace", kind, "AURIS Workspace"),
            kind,
            (issuedAt ?? Now).ToString("O"),
            (expiresAt ?? Now.AddSeconds(30)).ToString("O"),
            "abcdefghijklmnopqrstuvwxyzABCDEFGH",
            string.Empty);
        var signer = new Ed25519Signer();
        signer.Init(true, privateKey);
        var payload = CanonicalJson.WithoutSignature(envelope);
        signer.BlockUpdate(payload, 0, payload.Length);
        return envelope with { Signature = Base64Url(signer.GenerateSignature()) };
    }

    private static string Base64Url(byte[] value) =>
        Convert.ToBase64String(value).TrimEnd('=').Replace('+', '-').Replace('/', '_');
}
