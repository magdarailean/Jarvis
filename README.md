# Jarvis

A Windows desktop assistant and tutor for Romanian-speaking users, primarily in Moldova.

**Current state: Milestone 0 — initialization.** This version opens a Romanian welcome window, displays `Gata`, and exits cleanly. It does not yet provide AI answers, voice, screenshots, annotations, global shortcuts, or tray operation. Closing the window stops the application.

## Prerequisites

- Windows 10/11, x64. This milestone was tested on Windows 11 (build 26200); Windows 10 validation is pending.
- [.NET 8 SDK](https://dotnet.microsoft.com/en-us/download/dotnet/8.0), **8.0.424 or a newer 8.0.4xx patch**, including the Windows desktop targeting pack. `global.json` pins that feature band. The SDK includes the runtime; a runtime-only installation cannot build the project.
- PowerShell and a local checkout. Rider/Visual Studio are optional; open `Jarvis.sln` if using an IDE.

.NET 8 is the already-installed bootstrap toolchain. Its support ends November 10, 2026; upgrading to .NET 10 is a required release gate. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Build and launch

Open PowerShell at the repository root (the folder containing `Jarvis.sln`):

```powershell
dotnet --version
dotnet restore Jarvis.sln
dotnet build Jarvis.sln --configuration Debug --no-restore
dotnet run --project src/Jarvis.Desktop/Jarvis.Desktop.csproj --configuration Debug --no-build
```

No installer, administrator rights, third-party NuGet packages, AI server, models, API keys, or environment variables are required. There are no application-specific environment variables in this milestone. The first SDK invocation may initialize the normal .NET caches.

For a Release build:

```powershell
dotnet build Jarvis.sln --configuration Release
dotnet run --project src/Jarvis.Desktop/Jarvis.Desktop.csproj --configuration Release --no-build
```

After building, you may also launch `src\Jarvis.Desktop\bin\Release\net8.0-windows\Jarvis.exe` from File Explorer. This is a framework-dependent development build, not a portable installer.

## Test the current version

1. Run the Debug commands above. Check that a window titled **Jarvis — Asistent și tutore** appears without a console error.
2. Verify **Gata**, **Bine ai venit!**, and the Romanian initial-version/privacy notices are visible and readable.
3. Resize or maximize the window. Content should wrap; a scrollbar appears when needed. The close button remains accessible.
4. Press Tab to navigate to **Închide**, then Enter, or click **Închide**. The application should exit and return control to PowerShell.
5. Run it again and close with the window's **X**. Confirm it also exits.
6. Optionally inspect diagnostic events:

```powershell
Get-Content "$env:LOCALAPPDATA\Jarvis\logs\application.log" -Tail 20
Get-Process -Name Jarvis -ErrorAction SilentlyContinue
```

The log should include `Application starting`, `Main window loaded`, and `Application stopped; exitCode=0`. With all Jarvis windows closed, the process command should return no Jarvis processes. Logs are best-effort: denied disk access does not prevent launch or exit. The log is reset after reaching about 1 MiB. It contains lifecycle events only, no screen/audio/conversation content.

There is no unit-test suite yet because the bootstrap has no domain logic. Milestone 0 verification consists of Debug/Release builds and real Windows UI smoke testing; `dotnet test` is not claimed as validation.

## Repository

- `src/Jarvis.Desktop` — WPF application, Romanian presentation, minimal diagnostic adapter.
- [ARCHITECTURE.md](ARCHITECTURE.md) — selected stack, planned boundaries, privacy/data flow.
- [STATUS.md](STATUS.md) — verification evidence, known limits, next milestone, and 12-milestone roadmap.

Development stops after each tested milestone for manual review and commit. No automatic Git commits.
