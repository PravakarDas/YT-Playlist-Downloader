# YT Playlist Downloader

A modern, minimalist, dark-themed YouTube playlist downloader built with Flask, yt-dlp, and a responsive UI. Supports selective video download, MP4/MP3 formats, quality presets, real-time progress, ZIP packaging, and automatic cleanup.

## Features
- Load any YouTube playlist with thumbnails and metadata
- Select specific videos for download
- Download in MP4 (video) or MP3 (audio only)
- High / Medium / Low quality options
- Live progress tracking for each video
- All selected items are packaged into a single ZIP file
- Fully server-side processing
- Automatic cleanup on:
  - Page refresh (client-specific data)
  - 3 hours idle time
- Scalable for 100+ concurrent users
- Clean modular structure with `templates/` and `static/` assets
- Dark modern UI with responsive design

## Screenshots
| Playlist Loaded | Download Progress |
| --- | --- |
| ![Playlist Loaded](static/screenshots/image%201.png) | ![Download Progress](static/screenshots/image%202.png) |

## Project Structure
```
yt-downloader/
│
├── app.py
├── download.py
├── requirements.txt
├── .gitignore
│
├── downloads/               # auto-created at runtime (ignored in git)
│
├── templates/
│   └── index.html
│
└── static/
    ├── css/
    │   └── style.css
    ├── js/
    │   └── main.js
    └── screenshots/
        ├── image 1.png
        └── image 2.png
```

## Installation
1. Clone the repository
   ```bash
   git clone https://github.com/YOUR_USERNAME/yt-playlist-downloader.git
   cd yt-playlist-downloader
   ```
2. Create and activate a virtual environment
   ```bash
   python -m venv venv
   # Linux / macOS
   source venv/bin/activate
   # Windows
   venv\Scripts\activate
   ```
3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the server:
```bash
python app.py
```

Then open `http://127.0.0.1:5000` and:
- Paste a YouTube playlist URL
- Select videos to download
- Choose MP4/MP3 and quality
- Click Download selected
- Receive a ZIP file automatically

## Technologies Used
- Flask - backend web framework
- yt-dlp - high-performance YouTube downloader
- JavaScript - UI logic, live progress polling
- HTML5 + CSS3 - modern dark-theme UI

## Author
Built by Pravakar Das  
GitHub: https://github.com/PravakarDas  
LinkedIn: https://www.linkedin.com/in/pravakarda
