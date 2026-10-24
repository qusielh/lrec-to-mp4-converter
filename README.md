# L2M

**L2M converts Linktivity `.lrec` recordings into normal MP4 files.**

It is a small Windows desktop app built for SVU students who need to keep, review, and share recorded lectures without depending on the original Linktivity player. The app is free, offline, and has no account, activation, or usage limit.

![L2M screenshot](assets/screenshot.png)

## Why this exists

SVU recordings often arrive as `.lrec` files. They play inside an old Linktivity/Collaboration Player, which is not convenient when you want to study on a phone, skip around in a video player, or keep an archive that will still open years from now.

The obvious solution is to record the screen while the player runs. That works, but it is slow, it captures notifications and window chrome, and it makes the video quality depend on the recording setup.

L2M reads the archive directly. It rebuilds the screen frames and the voice track from the original data, then muxes them into an MP4 with ffmpeg. The result is a clean file with the original timing, not a screen capture.

## What it does

- Converts one or many `.lrec` files in a single run.
- Preserves the original screen frames and timing.
- Decodes the TrueSpeech voice packets into a normal audio track.
- Mixes simultaneous speakers instead of dropping one of them.
- Keeps the recorder's own silence behavior so the audio stays aligned with the video.
- Works completely offline after installation.
- Remembers the last folders and language.
- Has a bilingual Arabic/English interface.

## The hard parts

The `.lrec` format is not documented. The first version was built by inspecting real recordings: record headers, compressed and encrypted buffers, viewport frames, chat records, and voice packets. Some of the fields still do not have official names; they were identified by how the original player reacts to them.

Audio was the second problem. Linktivity stores voice as 240 ms TrueSpeech packets, but it does not place every packet at its raw timestamp. Short waits are suppressed so continuous speech does not click, while longer waits are preserved. The player uses a 400 ms threshold for that decision. L2M reproduces the same rule, including the exact `>=` comparison, so the exported audio matches the player's timeline. This is documented in [AUDIO.md](AUDIO.md).

The third problem was packaging. The app needs WebView2, ffmpeg, and a small TrueSpeech decoder, but it should still install like a normal Windows program. The current build bundles everything into one executable and adds WebView2 only when it is missing.

There is one known limitation: some gaps of 400 ms or more sit inside a single continuous talk spurt. Preserving them is faithful to the player, but it can leave a short pause in the middle of a sentence. A packet-type-aware experiment is written down in [PLAN.md](PLAN.md); it is deliberately not enabled until it has been validated by listening tests.

## Free for students

L2M is free for SVU students and for personal, noncommercial use. There is no trial timer, no device activation, no account, and no feature lock. If the app saves you time, you can support its development or star the repository. That is optional.

Institutions that need deployment help, custom work, or a support agreement can use the contact link on the [L2M website](https://l2m-platform.qusielh.workers.dev).

## Install

1. Download the latest `L2M_Setup.exe` from the Releases page of this repository.
2. Run the installer. Windows may ask for permission to install the Microsoft WebView2 Runtime if it is not already present.
3. Open **L2M** from the Start menu or desktop shortcut.

The app does not require Python or any other runtime after installation.

## Use

1. Click **Add files** and choose one or more `.lrec` recordings.
2. Rename the output files if you want; the `.mp4` extension is added automatically.
3. Click **Convert to MP4**.
4. The finished files are written next to the source recordings, or in the last output folder you used. Use **Open folder** to find them.

The log at the bottom shows what the engine is doing and reports any file that could not be converted.

## Build from source

Requirements:

- Windows 10 or later
- Python 3.13
- [Inno Setup](https://jrsoftware.org/isinfo.php) for the installer
- `ffmpeg.exe` and `tsdecode.exe` in `bin/`

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --clean --noconfirm L2M.spec
iscc installer\L2M.iss
```

The application is written in `l2m_ui.py`; the conversion engine is `l2m_engine.py`; the UI lives in `ui/`. The installer output is `dist\installer\L2M_Setup.exe`.

For a quick command-line conversion:

```powershell
python l2m_cli.py recording.lrec recording.mp4
```

## Project layout

```text
l2m_ui.py          desktop shell and Python/JS bridge
l2m_cli.py         command-line converter
l2m_engine.py      .lrec parser, frame reconstruction, audio decode, MP4 mux
ui/                HTML/CSS/JS interface
installer/         Inno Setup script
assets/            icon and screenshot
bin/               ffmpeg and TrueSpeech decoder (not committed)
AUDIO.md           audio pipeline and recorder parity notes
PLAN.md            deferred audio experiment
```

## Roadmap

- Validate the packet-type-aware gap handling described in `PLAN.md` with a listening test before changing the engine.
- Improve installer diagnostics for missing WebView2 and antivirus false positives.
- Add more real-world recordings to the regression set.
- Keep the free student build free.

## License

L2M is source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE). You may use, study, modify, and share it for noncommercial purposes. Commercial redistribution, resale, or bundling into a paid product requires a separate license. Institutional deployment and support are available separately through the website.

The bundled ffmpeg and TrueSpeech decoder remain under their own licenses; see the files in `bin/` and their upstream projects for details.
