# AURIS Android Companion

The Android companion provides the mobile command, mission, approval, and device-pairing surfaces from the AURIS master directives. It intentionally reports remote functions as disconnected until a production HTTPS command plane, enrolment code, and pinned cloud signing key are supplied.

## Verified Build

```powershell
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21"
$env:ANDROID_HOME = (Resolve-Path "..\.android-sdk").Path
& "..\.gradle-dist\gradle-9.4.1\bin\gradle.bat" testDebugUnitTest lintDebug assembleDebug --no-daemon
```

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. It is suitable for local device testing only. Production release requires a Devansh-controlled release signing key, an attached Android device or approved distribution channel, and configured cloud enrolment.
