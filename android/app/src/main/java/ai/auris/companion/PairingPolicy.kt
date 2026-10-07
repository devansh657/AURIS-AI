package ai.auris.companion

import java.net.URI
import java.util.Base64
import java.util.UUID

data class PairingConfig(
    val endpoint: String,
    val enrolmentCode: String,
    val deviceId: String,
    val cloudSigningKey: String,
)

data class PairingDecision(val accepted: Boolean, val error: String = "")

object PairingPolicy {
    private val codePattern = Regex("^[A-Za-z0-9_-]{40,256}$")

    fun validate(config: PairingConfig): PairingDecision {
        val endpoint = try {
            URI(config.endpoint.trim())
        } catch (_: IllegalArgumentException) {
            return PairingDecision(false, "Enter a valid AURIS cloud endpoint.")
        }
        if (endpoint.scheme != "https" || endpoint.host.isNullOrBlank() || endpoint.userInfo != null) {
            return PairingDecision(false, "AURIS pairing requires an HTTPS endpoint without embedded credentials.")
        }
        if (!codePattern.matches(config.enrolmentCode.trim())) {
            return PairingDecision(false, "The one-time enrolment code is invalid.")
        }
        try {
            UUID.fromString(config.deviceId.trim())
        } catch (_: IllegalArgumentException) {
            return PairingDecision(false, "The mobile device identity is invalid.")
        }
        val key = try {
            Base64.getUrlDecoder().decode(padded(config.cloudSigningKey.trim()))
        } catch (_: IllegalArgumentException) {
            return PairingDecision(false, "The pinned cloud signing key is invalid.")
        }
        if (key.size != 32) {
            return PairingDecision(false, "The pinned cloud signing key must be Ed25519.")
        }
        return PairingDecision(true)
    }

    private fun padded(value: String): String = value + "=".repeat((4 - value.length % 4) % 4)
}
