# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-08-12

### Added
- **Initial Release of USB Music Shuffler**: A modern desktop application designed to randomize audio playback on car stereos, Bluetooth speakers, TVs, soundbars, and hardware USB audio players.
- **Filename Prefix Shuffling Engine**: Pre-pends randomized numerical index tags (e.g. `[001]`, `[042]`) to audio filenames, forcing devices that sort alphabetically to play music in a random sequence.
- **Physical FAT Directory Re-ordering**: Re-writes physical FAT directory index entries to force hardware players that read strictly by creation or sector order to shuffle tracks.
- **Automatic Rollback Recovery System**: Safe FAT re-ordering engine that catches disk interruptions and automatically restores files back to their original state. Guaranteed zero data loss!
- **⚡ Scandir Speed Acceleration**: Multi-threaded directory scanning powered by `os.scandir` for instant file discovery on large USB drives.
- **🔎 Real-Time Track Search Bar**: Search bar to instantly filter tracks by filename or subfolder path.
- **Modern Slate High-Contrast Desktop GUI**: Clean, high-contrast Tkinter interface built with a light slate palette (`#F8FAFC`), crisp white cards, vibrant blue accents, and readable file tables.
- **Windows Taskbar & Titlebar Icon Integration**: Integration via `AppUserModelID` (`usbshuffler.app.v1`) to display custom logo graphics on both the titlebar and Windows Taskbar.
- **One-Click Un-shuffle**: Restores original filenames by stripping generated prefix tags with a single click.
- **Automatic USB Drive Detection**: Auto-detects removable USB drives across Windows, macOS, and Linux.
- **Audio Format Support**: Full support for `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.wma`, `.ogg`, and `.opus`.
