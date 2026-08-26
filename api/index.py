"""API pencarian musik berbasis YouTube dan yt-dlp untuk Vercel."""

import base64
import json
import os
from pathlib import Path
from typing import Any

import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Music Search API",
    version="1.0.0",
    description="Mencari video/musik berdasarkan artis atau judul menggunakan yt-dlp.",
)

# Untuk produksi, sebaiknya batasi allow_origins ke domain frontend Anda.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _to_netscape_cookiefile(source_path: Path) -> str:
    """Menerima cookies Netscape atau JSON hasil export ekstensi browser."""
    raw = source_path.read_text(encoding="utf-8-sig").strip()
    if raw.startswith("# Netscape HTTP Cookie File") or raw.startswith("# HTTP Cookie File"):
        return str(source_path)

    try:
        parsed = json.loads(raw)
        cookies = parsed.get("cookies", []) if isinstance(parsed, dict) else parsed
        if not isinstance(cookies, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            "api/cookies.txt harus berformat Netscape atau JSON cookies browser"
        ) from exc

    target_path = Path("/tmp/youtube-cookies-netscape.txt")
    lines = ["# Netscape HTTP Cookie File", ""]
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain", ""))
        name = str(cookie.get("name", ""))
        if not domain or not name:
            continue
        include_subdomains = "TRUE" if domain.startswith(".") or not cookie.get("hostOnly", False) else "FALSE"
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = int(cookie.get("expirationDate", cookie.get("expires", 0)) or 0)
        path = str(cookie.get("path", "/"))
        value = str(cookie.get("value", ""))
        lines.append("\\t".join([domain, include_subdomains, path, secure, str(expires), name, value]))

    if len(lines) == 2:
        raise RuntimeError("api/cookies.txt tidak berisi cookie yang valid")
    target_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    return str(target_path)


def _prepare_cookiefile() -> str | None:
    """Membuat cookiefile sementara dari env atau api/cookies.txt."""
    encoded_cookies = os.getenv("YOUTUBE_COOKIES_B64")
    if encoded_cookies:
        cookie_path = Path("/tmp/youtube-cookies.txt")
        try:
            cookie_path.write_bytes(base64.b64decode(encoded_cookies, validate=True))
        except Exception as exc:
            raise RuntimeError("YOUTUBE_COOKIES_B64 bukan Base64 yang valid") from exc
        return _to_netscape_cookiefile(cookie_path)

    # Fallback khusus testing lokal/deployment private. Jangan gunakan produksi.
    local_cookie_path = Path(__file__).parent / "cookies.txt"
    if local_cookie_path.exists():
        return _to_netscape_cookiefile(local_cookie_path)

    return None


def search_music(query: str, limit: int) -> list[dict[str, Any]]:
    """Menjalankan pencarian yt-dlp tanpa mengunduh file audio."""
    ydl_opts = {
        "extract_flat": False,
        "skip_download": True,
        "format": "140/bestaudio[protocol^=http]/bestaudio",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    cookiefile = _prepare_cookiefile()
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    results: list[dict[str, Any]] = []
    target_query = f"ytsearch{limit}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(target_query, download=False) or {}
            entries = search_results.get("entries", []) or []

            for entry in entries:
                if not entry:
                    continue

                video_id = entry.get("id", "")
                formats = entry.get("formats", []) or []
                direct_audio_url = ""

                # Pilih direct audio URL HTTP googlevideo, bukan HLS/m3u8.
                for media_format in formats:
                    if (
                        media_format.get("acodec") != "none"
                        and media_format.get("vcodec") == "none"
                    ):
                        protocol = media_format.get("protocol", "")
                        url = media_format.get("url", "")
                        if (
                            "http" in protocol
                            and "googlevideo.com" in url
                            and "m3u8" not in url
                        ):
                            direct_audio_url = url
                            break

                # Fallback jika format audio-only tidak tersedia.
                if not direct_audio_url:
                    for media_format in formats:
                        url = media_format.get("url", "")
                        if "googlevideo.com" in url and "m3u8" not in url:
                            direct_audio_url = url
                            break

                thumbnails = entry.get("thumbnails", []) or []
                cover_url = (
                    thumbnails[-1].get("url", "")
                    if thumbnails
                    else entry.get("thumbnail", "")
                )
                stream_url = (
                    f"https://www.youtube.com/watch?v={video_id}"
                    if video_id
                    else entry.get("webpage_url", "")
                )

                results.append(
                    {
                        "judul": entry.get("title", "Unknown Title"),
                        "artis": entry.get(
                            "uploader", entry.get("channel", "Unknown Artist")
                        ),
                        "durasi": entry.get("duration_string", "N/A"),
                        "video_id": video_id,
                        "link_streaming": stream_url,
                        "link_cover": cover_url,
                        "direct_audio_link": direct_audio_url or stream_url,
                    }
                )
    except Exception as exc:
        raise RuntimeError(f"Pencarian yt-dlp gagal: {exc}") from exc

    return results


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Music Search API aktif"}


@app.get("/api/search")
def search_endpoint(
    query: str = Query(..., min_length=1, max_length=100, description="Artis atau judul musik"),
    limit: int = Query(5, ge=1, le=10, description="Jumlah maksimum hasil"),
) -> dict[str, Any]:
    try:
        results = search_music(query.strip(), limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "query": query.strip(),
        "jumlah": len(results),
        "hasil": results,
    }
