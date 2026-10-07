using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Auris.DeviceService.Contracts;

namespace Auris.DeviceService.Security;

public static class CanonicalJson
{
    public static byte[] WithoutSignature(DeviceCommandEnvelope envelope)
    {
        var unsigned = new Dictionary<string, object?>
        {
            ["command_id"] = envelope.CommandId,
            ["device_id"] = envelope.DeviceId,
            ["tool"] = envelope.Tool,
            ["parameters"] = new Dictionary<string, object?>
            {
                ["action_id"] = envelope.Parameters.ActionId,
                ["kind"] = envelope.Parameters.Kind,
                ["target"] = envelope.Parameters.Target,
            },
            ["permission_scope"] = envelope.PermissionScope,
            ["issued_at"] = envelope.IssuedAt,
            ["expires_at"] = envelope.ExpiresAt,
            ["nonce"] = envelope.Nonce,
        };
        var element = JsonSerializer.SerializeToElement(unsigned);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(
            stream,
            new JsonWriterOptions
            {
                Indented = false,
                Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            }))
        {
            WriteElement(writer, element);
        }
        return stream.ToArray();
    }

    private static void WriteElement(Utf8JsonWriter writer, JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in element.EnumerateObject().OrderBy(
                    property => property.Name,
                    StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteElement(writer, property.Value);
                }
                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in element.EnumerateArray())
                {
                    WriteElement(writer, item);
                }
                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(element.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(element.GetRawText());
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new InvalidOperationException("Unsupported JSON value in signed command.");
        }
    }
}
