using System.Globalization;
using System.Text.RegularExpressions;
using Auris.DeviceService.Contracts;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

namespace Auris.DeviceService.Security;

public sealed record CommandValidationResult(
    bool Ok,
    string Error,
    bool SignatureVerified,
    bool NonceClaimed);

public sealed partial class CommandValidator(
    Guid expectedDeviceId,
    byte[] cloudPublicKey,
    IReadOnlySet<string> allowedPermissions,
    INonceStore nonceStore)
{
    public CommandValidationResult ValidateAndClaim(
        DeviceCommandEnvelope envelope,
        DateTimeOffset now)
    {
        if (!Guid.TryParse(envelope.CommandId, out _)
            || !Guid.TryParse(envelope.DeviceId, out var targetDevice)
            || targetDevice != expectedDeviceId)
        {
            return Reject("The command targets the wrong device identity.");
        }
        if (envelope.Tool != "windows.device_action")
        {
            return Reject("The requested device tool is not allowlisted.");
        }
        if (envelope.PermissionScope != envelope.Parameters.Kind
            || !allowedPermissions.Contains(envelope.PermissionScope))
        {
            return Reject("The device permission scope is missing or denied.");
        }
        if (!ActionIdPattern().IsMatch(envelope.Parameters.ActionId)
            || string.IsNullOrWhiteSpace(envelope.Parameters.Target)
            || envelope.Parameters.Target.Length > 200)
        {
            return Reject("The typed device parameters are invalid.");
        }
        if (!TryTimestamp(envelope.IssuedAt, out var issuedAt)
            || !TryTimestamp(envelope.ExpiresAt, out var expiresAt)
            || issuedAt > now.AddSeconds(30)
            || expiresAt <= now
            || expiresAt - issuedAt > TimeSpan.FromSeconds(120))
        {
            return Reject("The signed command is expired or not yet valid.");
        }
        if (!NoncePattern().IsMatch(envelope.Nonce))
        {
            return Reject("The command nonce is invalid.");
        }
        if (!TryBase64Url(envelope.Signature, out var signature)
            || signature.Length != 64
            || cloudPublicKey.Length != Ed25519PublicKeyParameters.KeySize
            || !VerifySignature(signature, CanonicalJson.WithoutSignature(envelope)))
        {
            return Reject("The cloud command signature is invalid.");
        }
        if (!nonceStore.TryClaim(envelope.Nonce, expiresAt, now))
        {
            return new(false, "The command nonce was already consumed.", true, false);
        }
        return new(true, string.Empty, true, true);
    }

    private static bool TryTimestamp(string value, out DateTimeOffset result) =>
        DateTimeOffset.TryParse(
            value,
            CultureInfo.InvariantCulture,
            DateTimeStyles.RoundtripKind,
            out result);

    private static bool TryBase64Url(string value, out byte[] result)
    {
        try
        {
            result = Convert.FromBase64String(
                value.Replace('-', '+').Replace('_', '/') + new string('=', (4 - value.Length % 4) % 4));
            return true;
        }
        catch (FormatException)
        {
            result = [];
            return false;
        }
    }

    private bool VerifySignature(byte[] signature, byte[] payload)
    {
        var verifier = new Ed25519Signer();
        verifier.Init(false, new Ed25519PublicKeyParameters(cloudPublicKey));
        verifier.BlockUpdate(payload, 0, payload.Length);
        return verifier.VerifySignature(signature);
    }

    private static CommandValidationResult Reject(string error) =>
        new(false, error, false, false);

    [GeneratedRegex("^[a-z0-9_]{2,120}$", RegexOptions.CultureInvariant)]
    private static partial Regex ActionIdPattern();

    [GeneratedRegex("^[A-Za-z0-9_-]{32,160}$", RegexOptions.CultureInvariant)]
    private static partial Regex NoncePattern();
}
