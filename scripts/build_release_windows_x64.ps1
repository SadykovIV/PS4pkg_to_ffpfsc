param(
    [string]$VcpkgRoot = $env:VCPKG_INSTALLATION_ROOT,
    [string]$DlcTemplatePath = $env:PS4FFPSC_DLC_TEMPLATE
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $ProjectRoot "build-release-windows"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$AppPath = Join-Path $BuildRoot "dist\PS4 FFPFSC"
$Version = "0.2.8"

if (-not $IsWindows) {
    throw "This release script must run on Windows."
}
if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne
    [System.Runtime.InteropServices.Architecture]::X64) {
    throw "Native Windows x64 is required."
}
if (-not $VcpkgRoot) {
    throw "VcpkgRoot or VCPKG_INSTALLATION_ROOT is required."
}
if (-not $DlcTemplatePath -or
    -not (Test-Path $DlcTemplatePath -PathType Leaf)) {
    throw "PS4FFPSC_DLC_TEMPLATE must identify the build-time DLC module template."
}
$DlcTemplatePath = (Resolve-Path $DlcTemplatePath).Path

python -c "import platform, sys; raise SystemExit(0 if sys.version_info[:3] == (3, 13, 14) and platform.machine().lower() in ('amd64', 'x86_64') else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The release environment must use native Python 3.13.14 x64."
}
python -c "from importlib.metadata import version; expected = {'PySide6-Essentials': '6.9.3', 'shiboken6': '6.9.3', 'pyinstaller': '6.21.0'}; raise SystemExit(0 if all(version(name) == value for name, value in expected.items()) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Pinned Python release dependencies are missing or have wrong versions."
}

$VcpkgToolchain = Join-Path $VcpkgRoot "scripts\buildsystems\vcpkg.cmake"
if (-not (Test-Path $VcpkgToolchain -PathType Leaf)) {
    throw "vcpkg toolchain was not found: $VcpkgToolchain"
}

if (Test-Path $BuildRoot) {
    Remove-Item $BuildRoot -Recurse -Force
}
New-Item $BuildRoot -ItemType Directory | Out-Null
New-Item $ReleaseRoot -ItemType Directory -Force | Out-Null
$PlatformReleaseFiles = @(
    "PS4-FFPFSC-v$Version-windows-x64.zip",
    "PS4-FFPFSC-v$Version-windows-x64.zip.sha256",
    "RELEASE_NOTES-v$Version-windows-x64.md"
)
foreach ($Name in $PlatformReleaseFiles) {
    $ExistingReleaseFile = Join-Path $ReleaseRoot $Name
    if (Test-Path $ExistingReleaseFile -PathType Leaf) {
        Remove-Item $ExistingReleaseFile -Force
    }
}

cmake -S $ProjectRoot -B (Join-Path $BuildRoot "helper") -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_TOOLCHAIN_FILE=$VcpkgToolchain" `
    -DVCPKG_TARGET_TRIPLET=x64-windows-static `
    -DPS4FFPSC_STATIC_CRYPTOPP=ON
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed." }

cmake --build (Join-Path $BuildRoot "helper") --parallel 2
if ($LASTEXITCODE -ne 0) { throw "C++ helper build failed." }

ctest --test-dir (Join-Path $BuildRoot "helper") --output-on-failure
if ($LASTEXITCODE -ne 0) { throw "C++ helper tests failed." }

$env:DOTNET_CLI_HOME = Join-Path $BuildRoot "dotnet-home"
$env:NUGET_PACKAGES = Join-Path $BuildRoot "nuget-packages"
$DlcHelperOutput = Join-Path $BuildRoot "dlc-helper"
$DlcManagedOutput = Join-Path $BuildRoot "dlc-helper-managed"
$DlcIntermediate = Join-Path $BuildRoot "dlc-helper-intermediate"
dotnet publish (Join-Path $ProjectRoot "third_party\ps4_dlc_patch\ps4-dlc-patch.csproj") `
    --configuration Release `
    --runtime win-x64 `
    --self-contained true `
    --output $DlcHelperOutput `
    -p:PublishAot=true `
    "-p:DlcPrxTemplatePath=$DlcTemplatePath" `
    "-p:BaseOutputPath=$DlcManagedOutput\" `
    "-p:BaseIntermediateOutputPath=$DlcIntermediate\" `
    "-p:MSBuildProjectExtensionsPath=$DlcIntermediate\obj\"
if ($LASTEXITCODE -ne 0) { throw "Experimental DLC helper build failed." }
$DlcHelper = Join-Path $DlcHelperOutput "ps4-dlc-patch.exe"
if (-not (Test-Path $DlcHelper -PathType Leaf)) {
    throw "Experimental DLC helper executable was not created."
}

$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
python (Join-Path $ProjectRoot "packaging\windows\make_icon.py") `
    (Join-Path $BuildRoot "AppIcon.ico")
if ($LASTEXITCODE -ne 0) { throw "Windows icon generation failed." }

python -m PyInstaller --clean --noconfirm `
    --distpath (Join-Path $BuildRoot "dist") `
    --workpath (Join-Path $BuildRoot "pyinstaller") `
    (Join-Path $ProjectRoot "packaging\windows\PS4FFPFSC.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

python (Join-Path $ProjectRoot "scripts\audit_windows_x64.py") $AppPath
if ($LASTEXITCODE -ne 0) { throw "Windows x64 audit failed." }
$BundledDlcHelper = Join-Path $AppPath "_internal\bin\ps4-dlc-patch.exe"
& $BundledDlcHelper --help |
    Set-Content (Join-Path $BuildRoot "dlc-helper-help.txt") -Encoding utf8NoBOM
if ($LASTEXITCODE -ne 0) { throw "Bundled experimental DLC helper smoke test failed." }
$DlcTemplateCheck = Join-Path $BuildRoot "dlc-helper-template.json"
& $BundledDlcHelper --check-template |
    Set-Content $DlcTemplateCheck -Encoding utf8NoBOM
if ($LASTEXITCODE -ne 0) {
    throw "Bundled experimental DLC template validation failed."
}
$DlcTemplateStatus = Get-Content $DlcTemplateCheck -Raw | ConvertFrom-Json
if ($DlcTemplateStatus.status -ne "ok" -or
    $DlcTemplateStatus.template_compatible -ne $true) {
    throw "Bundled experimental DLC template returned an invalid status."
}

$TemporaryParent = if ($env:RUNNER_TEMP) {
    $env:RUNNER_TEMP
} else {
    [System.IO.Path]::GetTempPath()
}
$SmokeRoot = Join-Path $TemporaryParent "ps4ffpsc-release-smoke-$PID"
New-Item $SmokeRoot -ItemType Directory -Force | Out-Null
$env:PS4FFPSC_DATA_ROOT = $SmokeRoot
$Worker = Join-Path $AppPath "ps4ffpsc-worker.exe"
$Gui = Join-Path $AppPath "PS4 FFPFSC.exe"

$InputRoot = Join-Path $SmokeRoot "Входные PKG"
$TempWorkspace = Join-Path $SmokeRoot "selected-temp\PS4 FFPFSC"
New-Item $InputRoot -ItemType Directory -Force | Out-Null
& $Worker --worker doctor `
    --pkg-dir $InputRoot `
    --unpacked-dir (Join-Path $TempWorkspace "unpacked") `
    --work-dir (Join-Path $TempWorkspace "work") `
    --temp-dir (Join-Path $TempWorkspace "tmp") `
    --output-dir (Join-Path $SmokeRoot "output") `
    --json |
    Set-Content (Join-Path $BuildRoot "doctor.json") -Encoding utf8NoBOM
if ($LASTEXITCODE -ne 0) { throw "Frozen doctor smoke test failed." }

& $Worker --worker scan `
    --pkg-dir $InputRoot `
    --unpacked-dir (Join-Path $TempWorkspace "unpacked") `
    --work-dir (Join-Path $TempWorkspace "work") `
    --temp-dir (Join-Path $TempWorkspace "tmp") `
    --output-dir (Join-Path $SmokeRoot "output") `
    --json |
    Set-Content (Join-Path $BuildRoot "temp-routing.json") -Encoding utf8NoBOM
if ($LASTEXITCODE -ne 0) { throw "Frozen temporary routing smoke test failed." }
if (-not (Test-Path (Join-Path $TempWorkspace "unpacked\package_inventory.json"))) {
    throw "Temporary inventory was not written below the selected temp directory."
}
if ((Test-Path (Join-Path $SmokeRoot "unpacked")) -or
    (Test-Path (Join-Path $SmokeRoot "work"))) {
    throw "Heavy temporary directories leaked into application data."
}

& $Worker --mkpfs -V |
    Set-Content (Join-Path $BuildRoot "mkpfs-version.txt") -Encoding utf8NoBOM
if ($LASTEXITCODE -ne 0) { throw "Frozen MkPFS smoke test failed." }

$GuiProcess = Start-Process -FilePath $Gui -ArgumentList "--gui-smoke-test" `
    -Wait -PassThru
if ($GuiProcess.ExitCode -ne 0) { throw "Frozen GUI smoke test failed." }
"gui_smoke_ok" |
    Set-Content (Join-Path $BuildRoot "gui-smoke.txt") -Encoding utf8NoBOM

$Archive = Join-Path $ReleaseRoot "PS4-FFPFSC-v$Version-windows-x64.zip"
Compress-Archive -LiteralPath $AppPath -DestinationPath $Archive -CompressionLevel Optimal
$Digest = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
$ChecksumLine = "$Digest  $([System.IO.Path]::GetFileName($Archive))`n"
[System.IO.File]::WriteAllText(
    "$Archive.sha256",
    $ChecksumLine,
    [System.Text.Encoding]::ASCII
)
Copy-Item (Join-Path $ProjectRoot "packaging\releases\v$Version.md") `
    (Join-Path $ReleaseRoot "RELEASE_NOTES-v$Version-windows-x64.md")

Write-Host "Release created: $Archive"
