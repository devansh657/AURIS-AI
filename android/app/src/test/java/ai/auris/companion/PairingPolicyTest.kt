package ai.auris.companion

import java.util.Base64
import java.util.UUID
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PairingPolicyTest {
    private val valid = PairingConfig(
        endpoint = "https://auris.example.com",
        enrolmentCode = "A".repeat(48),
        deviceId = UUID.randomUUID().toString(),
        cloudSigningKey = Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(32) { 7 }),
    )

    @Test
    fun validPinnedConfigurationIsAccepted() {
        assertTrue(PairingPolicy.validate(valid).accepted)
    }

    @Test
    fun insecureEndpointAndEmbeddedCredentialsAreRejected() {
        assertFalse(PairingPolicy.validate(valid.copy(endpoint = "http://auris.example.com")).accepted)
        assertFalse(PairingPolicy.validate(valid.copy(endpoint = "https://user:pass@auris.example.com")).accepted)
    }

    @Test
    fun malformedIdentityCodeAndCloudKeyAreRejected() {
        assertFalse(PairingPolicy.validate(valid.copy(deviceId = "mobile")).accepted)
        assertFalse(PairingPolicy.validate(valid.copy(enrolmentCode = "short")).accepted)
        assertFalse(PairingPolicy.validate(valid.copy(cloudSigningKey = "invalid")).accepted)
    }
}
