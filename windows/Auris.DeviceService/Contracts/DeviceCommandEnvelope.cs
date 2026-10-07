using System.Text.Json;
using System.Text.Json.Serialization;

namespace Auris.DeviceService.Contracts;

public sealed record DeviceActionParameters(
    [property: JsonPropertyName("action_id")] string ActionId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("target")] string Target);

public sealed record DeviceCommandEnvelope(
    [property: JsonPropertyName("command_id")] string CommandId,
    [property: JsonPropertyName("device_id")] string DeviceId,
    [property: JsonPropertyName("tool")] string Tool,
    [property: JsonPropertyName("parameters")] DeviceActionParameters Parameters,
    [property: JsonPropertyName("permission_scope")] string PermissionScope,
    [property: JsonPropertyName("issued_at")] string IssuedAt,
    [property: JsonPropertyName("expires_at")] string ExpiresAt,
    [property: JsonPropertyName("nonce")] string Nonce,
    [property: JsonPropertyName("signature")] string Signature)
{
    private static readonly HashSet<string> EnvelopeKeys =
    [
        "command_id", "device_id", "tool", "parameters", "permission_scope",
        "issued_at", "expires_at", "nonce", "signature",
    ];

    private static readonly HashSet<string> ParameterKeys =
        ["action_id", "kind", "target"];

    public static DeviceCommandEnvelope Parse(string json)
    {
        using var document = JsonDocument.Parse(
            json,
            new JsonDocumentOptions { MaxDepth = 8, CommentHandling = JsonCommentHandling.Disallow });
        if (document.RootElement.ValueKind != JsonValueKind.Object
            || !HasExactKeys(document.RootElement, EnvelopeKeys))
        {
            throw new CommandFormatException("The signed command schema is invalid.");
        }

        var parameters = document.RootElement.GetProperty("parameters");
        if (parameters.ValueKind != JsonValueKind.Object || !HasExactKeys(parameters, ParameterKeys))
        {
            throw new CommandFormatException("The typed command parameters are invalid.");
        }

        try
        {
            return JsonSerializer.Deserialize<DeviceCommandEnvelope>(document.RootElement.GetRawText())
                ?? throw new CommandFormatException("The signed command could not be parsed.");
        }
        catch (JsonException error)
        {
            throw new CommandFormatException("The signed command contains invalid values.", error);
        }
    }

    private static bool HasExactKeys(JsonElement element, HashSet<string> expected)
    {
        var names = element.EnumerateObject().Select(property => property.Name).ToArray();
        return names.Length == expected.Count && names.All(expected.Contains);
    }
}

public sealed class CommandFormatException(string message, Exception? inner = null)
    : Exception(message, inner);
