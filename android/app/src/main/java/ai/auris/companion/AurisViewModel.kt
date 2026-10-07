package ai.auris.companion

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import java.util.UUID

enum class CompanionView { COMMAND, MISSIONS, APPROVALS, DEVICE }

data class TranscriptEntry(val source: String, val message: String)

data class CompanionUiState(
    val selectedView: CompanionView = CompanionView.COMMAND,
    val command: String = "",
    val emergencyStopped: Boolean = false,
    val pairingValidated: Boolean = false,
    val remoteConnected: Boolean = false,
    val deviceId: String = UUID.randomUUID().toString(),
    val pairingError: String = "",
    val transcript: List<TranscriptEntry> = listOf(
        TranscriptEntry("AURIS", "Mobile command channel is offline. Pair this device to a deployed AURIS core."),
    ),
)

class AurisViewModel : ViewModel() {
    var state by mutableStateOf(CompanionUiState())
        private set

    fun select(view: CompanionView) {
        state = state.copy(selectedView = view)
    }

    fun updateCommand(value: String) {
        state = state.copy(command = value.take(4_000))
    }

    fun acceptVoiceTranscript(value: String) {
        updateCommand(value)
        append("VOICE", value)
    }

    fun submitCommand() {
        val command = state.command.trim()
        if (command.isEmpty()) return
        append("DEVANSH", command)
        state = state.copy(command = "")
        when {
            state.emergencyStopped -> append("AURIS", "Automation is stopped locally. Resume before issuing a command.")
            !state.remoteConnected -> append("AURIS", "No remote action ran. Secure cloud pairing is not connected.")
            else -> append("AURIS", "Command queued for supervised execution.")
        }
    }

    fun emergencyStop() {
        state = state.copy(emergencyStopped = true)
        append("SECURITY", "Local emergency state active. Remote acknowledgement is unavailable while offline.")
    }

    fun resume() {
        state = state.copy(emergencyStopped = false)
        append("SECURITY", "Local emergency state cleared. Remote channel remains offline.")
    }

    fun validatePairing(endpoint: String, code: String, cloudKey: String) {
        val decision = PairingPolicy.validate(
            PairingConfig(endpoint, code, state.deviceId, cloudKey),
        )
        state = state.copy(
            pairingValidated = decision.accepted,
            pairingError = decision.error,
        )
        append(
            "PAIRING",
            if (decision.accepted) {
                "Configuration validated. Certificate enrolment is not activated in this build."
            } else {
                decision.error
            },
        )
    }

    fun cameraCaptured() {
        append("CAMERA", "Local preview captured. No image was uploaded or persisted.")
    }

    private fun append(source: String, message: String) {
        state = state.copy(
            transcript = (state.transcript + TranscriptEntry(source, message)).takeLast(30),
        )
    }
}
