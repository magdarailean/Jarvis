# Jarvis

Python-only Romanian Windows assistant. Two independent applications currently exist: Jarvis's PySide6 tray app prepares screen/voice context but does not call AI; the owner's PyQt6 companion uses OpenRouter for voice, screenshot guidance, pointing, captions and Romanian TTS. Run one at a time; shortcuts overlap. The owner's package is named CursorMain in this checkout (no Ion folder exists). It is read-only.

## Installation on Windows 10/11 x64

Use Python 3.12 **64-bit**, with pip/venv. Install it first if `py -3.12` is unavailable. PowerShell:

```powershell
cd C:\Users\Magda\Documents\GitHub\Jarvis
# Create only if .venv does not exist:
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e ".[voice,openrouter]"
.\.venv\Scripts\python.exe -m pip check
```

If activation is blocked by execution policy, skip activation: these commands explicitly use the environment's Python. Base shell alone: `python -m pip install -e .`. The combined install above includes all Ion/STT and companion requirements; **no additional install inside CursorMain is needed**. Editable checkout installation is required; owner sources are not packaged in the Jarvis wheel.

STT dependencies: sounddevice, NumPy, faster-whisper (CTranslate2, PyAV, Hugging Face dependencies). Jarvis's owner module also imports google-genai and mss, although the adapter never calls Gemini/capture; no Google key is needed. Companion dependencies additionally include PyQt6 and edge-tts. PySide6 and PyQt6 stay in separate processes.

CPU/int8 is used. No CUDA, cuDNN, NVIDIA GPU, PyTorch or PyAudio is required. No separate FFmpeg executable is required: [PyAV bundles FFmpeg libraries](https://github.com/SYSTRAN/faster-whisper). sounddevice's Windows pip wheel bundles PortAudio. [CTranslate2 requires the Visual C++ runtime](https://opennmt.net/CTranslate2/installation.html). If missing or DLL imports fail, install Microsoft's x64 redistributable:

```powershell
Invoke-WebRequest https://aka.ms/vc14/vc_redist.x64.exe -OutFile "$env:TEMP\jarvis-vc-redist.x64.exe"
Start-Process -FilePath "$env:TEMP\jarvis-vc-redist.x64.exe" -ArgumentList '/install','/passive','/norestart' -Wait
```

The installer may request administrator approval. [Microsoft runtime downloads](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Current-machine CTranslate2 imports succeed, but do not assume the runtime exists on another machine. Windows Settings → Privacy / Privacy & security → Microphone: enable microphone access and desktop application access. Select the intended default input in Windows Sound settings.

## Local OpenRouter key

File created: **C:\Users\Magda\Documents\GitHub\Jarvis\.env**.

```powershell
notepad .env
```

Paste the key immediately after the equals sign on the existing line:

```dotenv
OPENROUTER_API_KEY=your-key-here
```

Save and restart the companion. To change it, replace the value; to remove it, leave `OPENROUTER_API_KEY=` empty. No source changes. On a fresh clone copy `.env.example` to `.env`; the template must stay empty. Existing process environment variables override the file; clear a shell override with `Remove-Item Env:OPENROUTER_API_KEY -ErrorAction SilentlyContinue`.

```powershell
git check-ignore -v -- .env
# Must print nothing:
git ls-files -- .env
```

Verified: `.gitignore` ignores `.env` and the file is not tracked. Ordinary Git add excludes it; do not force-add secrets. Optional allowed settings: OPENROUTER_MODEL, JARVIS_ION_MODEL, JARVIS_SPEECH_MODEL. Model overrides can point to existing faster-whisper/CTranslate2 directories, not PyTorch .pt files.

## Explicit model installation

Internet, disk space and sufficient RAM are required; large-v3 occupies several GB and may be slow on CPU. Downloads go into ignored repository `models\stt`, **outside CursorMain**:

```powershell
# Original Jarvis/Ion default:
.\.venv\Scripts\python.exe -m jarvis.stt_setup download --model large-v3
# OpenRouter companion default:
.\.venv\Scripts\python.exe -m jarvis.stt_setup download --model small
```

Download whichever model you need, or both. Jarvis uses local-files-only loading: **no first-use download**. The original companion's lazy SpeechEngine downloads on first transcription into CursorMain/models; our launcher requires a local model directory instead, preserving the read-only package. Downloaded defaults are discovered automatically; model environment/.env overrides take precedence.

## Verify microphone and Romanian recognition

```powershell
# Lists devices, checks 16 kHz mono support, loads local model; no recording:
.\.venv\Scripts\python.exe -m jarvis.stt_setup check --model small
# Explicit five-second recording; speak Romanian, read printed transcription:
.\.venv\Scripts\python.exe -m jarvis.stt_setup test --model small
```

Use `--model large-v3` to check Jarvis's default. Append `--device N` using the printed device index for diagnostics; application input uses Windows's default device. A missing model/device/dependency returns failure. Empty text is not successful recognition: check input level, device and permissions. Audio remains in memory; no files, screenshots or AI calls in this diagnostic.

## Launch and manual tests

```powershell
.\.venv\Scripts\python.exe -m jarvis
# Optional diagnostics:
.\.venv\Scripts\python.exe -m jarvis --window
```

After warmup, hold Ctrl+Shift+Space, speak Romanian, release. Expect Ascult…, Procesez…, then **Context pregătit · AI neconectat**. This app stops at the AI boundary. Recording has a ten-second maximum. Tray End Session clears context, Ieșire exits. Typed input cannot produce AI responses yet; overlay demo and manual capture are diagnostic options.

Exit Jarvis first, then:

```powershell
# Demo: no key/model/microphone/network:
.\.venv\Scripts\python.exe -m jarvis.openrouter --demo --mute
# Real companion after key/model setup:
.\.venv\Scripts\python.exe -m jarvis.openrouter
```

Ctrl+Space toggles voice activation/recording (this companion is **not hold-to-talk**). Ctrl+Shift+Space refreshes context; Escape cancels; Ctrl+Shift+Q exits. Ask a Romanian question about the visible interface and verify pointer, caption and speech. `--mute` disables TTS. Real requests send screenshots and transcribed questions to OpenRouter; TTS also needs network. Default AI model: google/gemini-2.5-flash-lite. Account billing/availability apply. Missing key/model is reported before startup. This setup does not merge the companion into Jarvis's tutoring/session pipeline.

## Regression checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m unittest discover -s CursorMain -p 'test_workingVersion*.py' -v
```

-B prevents bytecode writes into the read-only package. Tests use synthetic audio/models and mocked responses; live recognition/API replies remain manual checks. No .NET implementation, database or server is required.
