from flask import Flask, request, jsonify, Response, stream_with_context, render_template
from flask_cors import CORS
import requests
import re

# Tambahkan template_folder='.' agar Flask mencari index.html di folder root (luar folder templates)
app = Flask(__name__, template_folder='.')
CORS(app)

BASE_HEADERS = {
    'authority': 'spotdown.org',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
    'referer': 'https://spotdown.org/search',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- BAGIAN INI YANG DIUBAH ---
@app.route('/')
def index():
    # Flask sekarang yang akan merender HTML, bukan Vercel
    return render_template('index.html')
# ------------------------------

@app.route('/api/search', methods=['GET'])
def search_music():
    query = request.args.get('q')
    
    if not query:
        return jsonify({"error": "Parameter 'q' diperlukan."}), 400

    try:
        session = requests.Session()
        params = {'url': query}
        
        response = session.get(
            'https://spotdown.org/api/song-details', 
            params=params, 
            headers=BASE_HEADERS
        )
        response.raise_for_status()
        
        data = response.json()
        
        if 'songs' not in data:
            return jsonify({"message": "Lagu tidak ditemukan", "data": []}), 404

        results = []
        for item in data['songs']:
            raw_url = item.get('url')
            raw_title = item.get('title')
            raw_artist = item.get('artist')
            
            dl_link = (
                f"{request.host_url}api/download"
                f"?url={raw_url}"
                f"&title={raw_title}"
                f"&artist={raw_artist}"
            )

            results.append({
                "title": raw_title,
                "artist": raw_artist,
                "duration": item.get('duration'),
                "thumbnail": item.get('thumbnail'),
                "download_api": dl_link
            })

        return jsonify({"status": "success", "results": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_music():
    target_url = request.args.get('url')
    raw_title = request.args.get('title', 'Unknown Title')
    raw_artist = request.args.get('artist', 'Unknown Artist')
    
    if not target_url:
        return jsonify({"error": "Parameter 'url' diperlukan."}), 400

    try:
        session = requests.Session()
        
        check_params = {'url': target_url}
        session.get(
            'https://spotdown.org/api/check-direct-download', 
            params=check_params, 
            headers=BASE_HEADERS
        )

        json_data = {'url': target_url}
        req_file = session.post(
            'https://spotdown.org/api/download', 
            headers=BASE_HEADERS, 
            json=json_data,
            stream=True
        )

        clean_title = sanitize_filename(raw_title)
        clean_artist = sanitize_filename(raw_artist)
        filename = f"{clean_title} - {clean_artist}.mp3"

        response_headers = {
            'Content-Type': 'audio/mpeg',
            'Content-Disposition': f'attachment; filename="{filename}"',
        }

        def generate():
            for chunk in req_file.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk

        return Response(stream_with_context(generate()), headers=response_headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
