from fastapi import FastAPI, HTTPException
import yt_dlp

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
        
    target_query = f"ytsearch{limit}:{q}"
    
    ydl_opts = {
        'extract_flat': False,
        'skip_download': True,
        'format': '140/bestaudio[protocol^=http]/bestaudio',
    }
    
    detailed_song_list = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(target_query, download=False)
            entries = search_results.get('entries', [])
            
            for entry in entries:
                title = entry.get('title', 'Unknown Title')
                artist = entry.get('uploader', entry.get('channel', 'Unknown Artist'))
                duration = entry.get('duration_string', 'N/A')
                video_id = entry.get('id', '')
                
                stream_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get('url', '')
                
                thumbnails = entry.get('thumbnails', [])
                cover_url = thumbnails[-1].get('url', '') if thumbnails else entry.get('thumbnail', '')
                
                # Cari direct audio link googlevideo
                direct_audio_url = ""
                formats = entry.get('formats', [])
                for f in formats:
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                        protocol = f.get('protocol', '')
                        url = f.get('url', '')
                        if 'http' in protocol and 'googlevideo.com' in url and 'm3u8' not in url:
                            direct_audio_url = url
                            break
                
                if not direct_audio_url and formats:
                    for f in formats:
                        if f.get('url') and 'googlevideo.com' in f.get('url') and 'm3u8' not in f.get('url'):
                            direct_audio_url = f.get('url')
                            break

                song_info = {
                    "judul": title,
                    "artis": artist,
                    "durasi": duration,
                    "video_id": video_id,
                    "link_streaming": stream_url,
                    "link_cover": cover_url,
                    "direct_audio_link": direct_audio_url if direct_audio_url else stream_url
                }
                
                detailed_song_list.append(song_info)
                
        return {
            "query": q,
            "total_ditemukan": len(detailed_song_list),
            "result": detailed_song_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
def get_stream(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="Parameter 'url' wajib diisi!")
        
    ydl_opts = {
        'extract_flat': False,
        'skip_download': True,
        'format': '140/bestaudio[protocol^=http]/bestaudio',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            direct_audio_url = ""
            formats = info.get('formats', [])
            
            for f in formats:
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    protocol = f.get('protocol', '')
                    stream_link = f.get('url', '')
                    if 'http' in protocol and 'googlevideo.com' in stream_link and 'm3u8' not in stream_link:
                        direct_audio_url = stream_link
                        break
                        
            if not direct_audio_url and formats:
                for f in formats:
                    if f.get('url') and 'googlevideo.com' in f.get('url') and 'm3u8' not in f.get('url'):
                        direct_audio_url = f.get('url')
                        break
                        
            return {
                "original_url": url,
                "direct_audio_link": direct_audio_url if direct_audio_url else url
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
