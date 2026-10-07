package ai.auris.companion

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Bundle
import android.speech.RecognizerIntent
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.FactCheck
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import java.util.Locale

private val Background = Color(0xFF05090D)
private val Panel = Color(0xFF081117)
private val Border = Color(0xFF1A3945)
private val Cyan = Color(0xFF35D9FF)
private val Mint = Color(0xFF65E5CF)
private val Critical = Color(0xFFFF5268)
private val Muted = Color(0xFF77909B)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AurisMobileApp() }
    }
}

@Composable
fun AurisMobileApp(model: AurisViewModel = viewModel()) {
    val state = model.state
    val colors = darkColorScheme(
        primary = Cyan,
        secondary = Mint,
        background = Background,
        surface = Panel,
        error = Critical,
        onPrimary = Background,
        onBackground = Color(0xFFE9F8FF),
        onSurface = Color(0xFFE9F8FF),
    )
    MaterialTheme(colorScheme = colors) {
        Scaffold(
            containerColor = Background,
            topBar = { AurisHeader(state, model::emergencyStop, model::resume) },
            bottomBar = { NavigationBar(state.selectedView, model::select) },
        ) { padding ->
            Box(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 14.dp),
            ) {
                when (state.selectedView) {
                    CompanionView.COMMAND -> CommandView(state, model)
                    CompanionView.MISSIONS -> MissionsView()
                    CompanionView.APPROVALS -> ApprovalsView()
                    CompanionView.DEVICE -> DeviceView(state, model)
                }
            }
        }
    }
}

@Composable
private fun AurisHeader(
    state: CompanionUiState,
    stop: () -> Unit,
    resume: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(Background)
            .border(1.dp, Border)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(36.dp)
                .border(1.dp, Cyan),
            contentAlignment = Alignment.Center,
        ) {
            Text("A", color = Cyan, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text("AURIS", fontWeight = FontWeight.Bold, letterSpacing = 0.sp)
            Text(
                if (state.remoteConnected) "MOBILE CHANNEL ONLINE" else "MOBILE CHANNEL OFFLINE",
                color = if (state.remoteConnected) Mint else Muted,
                fontFamily = FontFamily.Monospace,
                fontSize = 9.sp,
            )
        }
        TextButton(
            onClick = if (state.emergencyStopped) resume else stop,
            colors = ButtonDefaults.textButtonColors(
                contentColor = if (state.emergencyStopped) Mint else Critical,
            ),
        ) {
            Icon(
                if (state.emergencyStopped) Icons.Default.PlayArrow else Icons.Default.Stop,
                contentDescription = null,
            )
            Spacer(Modifier.width(4.dp))
            Text(if (state.emergencyStopped) "RESUME" else "STOP", fontSize = 11.sp)
        }
    }
}

@Composable
private fun CommandView(state: CompanionUiState, model: AurisViewModel) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var cameraPreview by remember { mutableStateOf<Bitmap?>(null) }
    val voiceLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                ?.let(model::acceptVoiceTranscript)
        }
    }
    val microphonePermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            voiceLauncher.launch(voiceIntent())
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicturePreview(),
    ) { bitmap ->
        cameraPreview = bitmap
        if (bitmap != null) model.cameraCaptured()
    }
    val cameraPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> if (granted) cameraLauncher.launch(null) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionTitle("LIVE COMMAND", "Speak or type a directive")
        StatusBand(state)
        Card(
            colors = CardDefaults.cardColors(containerColor = Panel),
            shape = RoundedCornerShape(4.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, Border),
        ) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                state.transcript.takeLast(8).forEach { entry ->
                    Column {
                        Text(entry.source, color = Cyan, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
                        Text(entry.message, fontSize = 13.sp, lineHeight = 18.sp)
                    }
                }
            }
        }
        cameraPreview?.let {
            Image(
                bitmap = it.asImageBitmap(),
                contentDescription = "Temporary camera preview",
                modifier = Modifier
                    .fillMaxWidth()
                    .height(180.dp)
                    .border(1.dp, Border),
            )
        }
        OutlinedTextField(
            value = state.command,
            onValueChange = model::updateCommand,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Directive") },
            enabled = !state.emergencyStopped,
            trailingIcon = {
                IconButton(onClick = model::submitCommand, enabled = state.command.isNotBlank()) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send directive")
                }
            },
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TechnicalButton(
                "VOICE",
                Icons.Default.Mic,
                Modifier.weight(1f),
            ) {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    voiceLauncher.launch(voiceIntent())
                } else {
                    microphonePermission.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
            TechnicalButton(
                "CAMERA",
                Icons.Default.CameraAlt,
                Modifier.weight(1f),
            ) {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                    cameraLauncher.launch(null)
                } else {
                    cameraPermission.launch(Manifest.permission.CAMERA)
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun StatusBand(state: CompanionUiState) {
    Row(
        Modifier
            .fillMaxWidth()
            .border(1.dp, if (state.emergencyStopped) Critical else Border)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (state.emergencyStopped) Icons.Default.ErrorOutline else Icons.Default.CheckCircle,
            contentDescription = null,
            tint = if (state.emergencyStopped) Critical else Muted,
        )
        Spacer(Modifier.width(9.dp))
        Column {
            Text(if (state.emergencyStopped) "AUTOMATION STOPPED" else "SUPERVISED MODE", fontWeight = FontWeight.Bold)
            Text(
                if (state.remoteConnected) "Certificate channel connected" else "No remote endpoint connected",
                color = Muted,
                fontFamily = FontFamily.Monospace,
                fontSize = 9.sp,
            )
        }
    }
}

@Composable
private fun MissionsView() {
    Column(Modifier.fillMaxSize().padding(vertical = 14.dp)) {
        SectionTitle("MISSIONS", "Remote task monitoring")
        EmptyState(Icons.Default.Terminal, "NO REMOTE MISSIONS", "Pair this device before task state can be loaded.")
    }
}

@Composable
private fun ApprovalsView() {
    Column(Modifier.fillMaxSize().padding(vertical = 14.dp)) {
        SectionTitle("APPROVALS", "Human authority")
        EmptyState(Icons.AutoMirrored.Filled.FactCheck, "NO CONNECTED APPROVAL QUEUE", "Approvals cannot be accepted while device identity is unpaired.")
    }
}

@Composable
private fun DeviceView(state: CompanionUiState, model: AurisViewModel) {
    var endpoint by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var cloudKey by remember { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        SectionTitle("SECURE PAIRING", "Register this mobile device")
        TelemetryRow("DEVICE ID", state.deviceId)
        TelemetryRow("CERTIFICATE", "NOT ENROLLED")
        TelemetryRow("CHANNEL", "NOT CONNECTED")
        TelemetryRow("REMOTE APPROVALS", "DISABLED")
        OutlinedTextField(endpoint, { endpoint = it }, Modifier.fillMaxWidth(), label = { Text("HTTPS cloud endpoint") })
        OutlinedTextField(code, { code = it }, Modifier.fillMaxWidth(), label = { Text("One-time enrolment code") })
        OutlinedTextField(cloudKey, { cloudKey = it }, Modifier.fillMaxWidth(), label = { Text("Pinned cloud signing key") })
        Button(
            onClick = { model.validatePairing(endpoint, code, cloudKey) },
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(4.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Cyan, contentColor = Background),
        ) {
            Icon(Icons.Default.Devices, contentDescription = null)
            Spacer(Modifier.width(7.dp))
            Text("VALIDATE PAIRING")
        }
        if (state.pairingValidated) {
            Text("Configuration validated // enrolment transport not activated", color = Mint, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
        } else if (state.pairingError.isNotBlank()) {
            Text(state.pairingError, color = Critical, fontSize = 11.sp)
        }
    }
}

@Composable
private fun NavigationBar(selected: CompanionView, select: (CompanionView) -> Unit) {
    Row(Modifier.fillMaxWidth().background(Background).border(1.dp, Border)) {
        NavItem("COMMAND", Icons.Default.Mic, CompanionView.COMMAND, selected, select)
        NavItem("MISSIONS", Icons.Default.Terminal, CompanionView.MISSIONS, selected, select)
        NavItem("APPROVALS", Icons.AutoMirrored.Filled.FactCheck, CompanionView.APPROVALS, selected, select)
        NavItem("DEVICE", Icons.Default.Devices, CompanionView.DEVICE, selected, select)
    }
}

@Composable
private fun RowScope.NavItem(
    label: String,
    icon: ImageVector,
    view: CompanionView,
    selected: CompanionView,
    select: (CompanionView) -> Unit,
) {
    TextButton(
        onClick = { select(view) },
        modifier = Modifier.weight(1f).height(58.dp),
        shape = RoundedCornerShape(0.dp),
        colors = ButtonDefaults.textButtonColors(contentColor = if (view == selected) Cyan else Muted),
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(icon, contentDescription = label, Modifier.size(18.dp))
            Text(label, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
private fun SectionTitle(eyebrow: String, title: String) {
    Column {
        Text(eyebrow, color = Cyan, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
        Text(title, fontSize = 22.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun EmptyState(icon: ImageVector, title: String, detail: String) {
    Column(
        Modifier.fillMaxWidth().border(1.dp, Border).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(icon, contentDescription = null, tint = Muted, modifier = Modifier.size(28.dp))
        Text(title, color = Cyan, fontFamily = FontFamily.Monospace, fontSize = 11.sp)
        Text(detail, color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun TelemetryRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().border(1.dp, Border).padding(10.dp)) {
        Text(label, Modifier.width(118.dp), color = Muted, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
        Text(value, color = Color(0xFFD2EBF5), fontSize = 10.sp)
    }
}

@Composable
private fun TechnicalButton(label: String, icon: ImageVector, modifier: Modifier, action: () -> Unit) {
    Button(
        onClick = action,
        modifier = modifier.height(44.dp),
        shape = RoundedCornerShape(4.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Panel, contentColor = Cyan),
        border = androidx.compose.foundation.BorderStroke(1.dp, Cyan),
    ) {
        Icon(icon, contentDescription = null, Modifier.size(18.dp))
        Spacer(Modifier.width(6.dp))
        Text(label, fontSize = 10.sp)
    }
}

private fun voiceIntent(): Intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
    putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to AURIS")
}
