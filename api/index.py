from fastapi import FastAPI, HTTPException
import yt_dlp
import requests

app = FastAPI(title="API Musik Pribadi Fajar (Vercel)", version="1.0")

@app.get("/")
def home():
    return {
        "status": "API Musik Pribadi Aktif di Vercel!",
        "endpoints": {
            "search": "/search?q=nama_artis&limit=5",
            "stream": "/stream?url=https://www.youtube.com/watch?v=VIDEO_ID"
        }
    }

@app.get("/search")
def search_music(q: str, limit: int = 5):
    if not q:
        raise HTTPException(status_code=400, detail="Parameter query 'q' wajib diisi!")
        
    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://piped-api.garudalinux.org",
        "https://api.piped.privacy.com.de"
    ]
    
    search_results = []
    
    for instance in piped_instances:
        try:
            res = requests.get(f"{instance}/search?q={q}&filter=videos", timeout=4)
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])
                if items:
                    search_results = items[:limit]
                    break
        except Exception:
            continue
            
    if not search_results:
        target_query = f"ytsearch{limit}:{q}"
        ydl_opts = {'extract_flat': True, 'skip_download': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_query, download=False)
                search_results = info.get('entries', [])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal mencari musik: {str(e)}")

    detailed_song_list = []
    
    for item in search_results:
        if 'url' in item and '/watch?v=' in item['url']:
            video_id = item['url'].split('v=')[-1].split('&')[0]
            title = item.get('title', 'Unknown Title')
            artist = item.get('uploaderName', 'Tulus / Artis')
            duration_sec = item.get('duration', 0)
            if duration_sec > 0:
                m, s = divmod(duration_sec, 60)
                duration = f"{m}:{s:02d}"
            else:
                duration = "N/A"
        else:
            video_id = item.get('id', '')
            title = item.get('title', 'Unknown Title')
            artist = item.get('uploader', item.get('channel', 'Tulus / Artis'))
            duration = item.get('duration_string', 'N/A')
            
        stream_url = f"https://www.youtube.com/watch?v={video_id}"
        cover_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        
        song_info = {
            "judul": title,
            "artis": artist,
            "durasi": duration,
            "video_id": video_id,
            "link_streaming": stream_url,
            "link_cover": cover_url,
            "direct_audio_link": f"/stream?url={stream_url}"
        }
        detailed_song_list.append(song_info)
        
    return {
        "query": q,
        "total_ditemukan": len(detailed_song_list),
        "result": detailed_song_list
    }

@app.get("/stream")
def get_stream(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="Parameter 'url' wajib diisi!")
        
    if "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    else:
        raise HTTPException(status_code=400, detail="URL YouTube tidak valid!")
        
    audio_link = ""
    
    # METODE 1: Menggunakan Cobalt API (Sangat stabil untuk direct download/streaming link)
    try:
        cobalt_res = requests.post(
            "https://api.cobalt.tools/api/json",
            json={"url": url, "downloadMode": "audio", "audioFormat": "mp3"},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=5
        )
        if cobalt_res.status_code == 200:
            cobalt_data = cobalt_res.json()
            if cobalt_data.get("url"):
                audio_link = cobalt_data["url"]
    except Exception:
        pass
        
    # METODE 2: Fallback ke Piped API jika Cobalt sedang sibuk
    if not audio_link:
        piped_instances = [
            "https://pipedapi.kavin.rocks",
            "https://piped-api.garudalinux.org",
            "https://api.piped.privacy.com.de"
        ]
        for instance in piped_instances:
            try:
                res = requests.get(f"{instance}/streams/{video_id}", timeout=4)
                if res.status_code == 200:
                    data = res.json()
                    audio_streams = data.get("audioStreams", [])
                    best_audio = next((s for s in audio_streams if s.get("url")), None)
                    if best_audio and best_audio.get("url"):
                        audio_link = best_audio["url"]
                        break
            except Exception:
                continue
                
    if not audio_link:
        raise HTTPException(status_code=500, detail="Gagal mendapatkan direct audio link. Silakan coba beberapa saat lagi.")
        
    return {
        "original_url": url,
        "direct_audio_link": audio_link
    }
