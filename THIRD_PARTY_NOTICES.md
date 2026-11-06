# Third-party notices

AeroGrab itself is MIT-licensed (see `LICENSE`). The release downloads (installer and portable exe) also contain or ship the following
third-party software, each under its own licence. This file is a good-faith summary - check the upstream projects for the authoritative text.

| Component | Used for | Licence | Source |
|---|---|---|---|
| **FFmpeg** (`ffmpeg.exe`, gyan.dev "essentials" build, built with `--enable-gpl --enable-version3`) | merging video + audio, DASH, remuxing. Shipped as a **separate program** next to AeroGrab, not linked into it | **GPL v3** | https://ffmpeg.org (source) - https://www.gyan.dev/ffmpeg/builds/ (this build) |
| **yt-dlp** and yt-dlp-ejs | sites such as YouTube, Vimeo, Instagram | Unlicense / (MIT, ISC for parts of ejs) | https://github.com/yt-dlp/yt-dlp |
| **pystray** (system tray icon) | tray icon and menu | **LGPL v3** | https://github.com/moses-palmer/pystray |
| **python-xlib** (Linux only, via pystray) | tray on Linux | LGPL v2+ | https://github.com/python-xlib/python-xlib |
| **Pillow** | tray icon image | MIT-CMU (HPND) | https://python-pillow.org |
| **cryptography** | AES-encrypted HLS streams | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| **certifi** | CA certificate bundle | MPL 2.0 | https://github.com/certifi/python-certifi |
| **websockets** | native messaging / local connections | BSD-3-Clause | https://github.com/python-websockets/websockets |
| **Python** and **Tcl/Tk** | the runtime and the window toolkit | PSF License / Tcl-Tk licence | https://www.python.org |
| **Lucide** icons (`aerograb_icons.py`) | toolbar, menu and tree icons | ISC (`assets/LUCIDE_LICENSE.txt`) | https://lucide.dev |

## What the GPL / LGPL items mean for you as the publisher
* **FFmpeg (GPL v3):** if you distribute `ffmpeg.exe` (it is inside the installer and the `dist/aerograb` folder), you must be able to hand the recipient
  the corresponding source on request. Linking to the exact build's source (the gyan.dev page above lists it) and keeping this notice in the release
  satisfies the usual practice. FFmpeg runs as its own process, so AeroGrab's MIT licence is unaffected.
* **pystray (LGPL v3):** shipped unmodified as a library; the PyInstaller folder build keeps it replaceable. Keep this notice with the release.
* Do **not** commit `ffmpeg.exe` to the repository (it is over GitHub's 100 MB limit); attach releases on the *Releases* page instead.

*This is a practical summary, not legal advice.*
