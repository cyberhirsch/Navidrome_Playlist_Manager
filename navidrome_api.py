import os
import json
import re
import requests
import random
import string
import unicodedata
from hashlib import md5

try:
    from thefuzz import fuzz
except ImportError:
    pass

CONFIG_FILE = "config.json"

# --- All other functions are unchanged and correct ---

def load_config():
    default_local_path = os.path.abspath("local_playlists")
    default_navi_path = os.path.abspath("navidrome_playlists")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        except json.JSONDecodeError: config = {}
    else: config = {}
    if 'navidrome_url' not in config: config['navidrome_url'] = ""
    if 'navidrome_user' not in config: config['navidrome_user'] = ""
    if 'navidrome_password' not in config: config['navidrome_password'] = ""
    if 'local_playlists_path' not in config: config['local_playlists_path'] = default_local_path
    if 'navidrome_playlists_path' not in config: config['navidrome_playlists_path'] = default_navi_path
    os.makedirs(config['local_playlists_path'], exist_ok=True)
    os.makedirs(config['navidrome_playlists_path'], exist_ok=True)
    return config

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

def verify_connection(config):
    if not all([config.get('navidrome_url'), config.get('navidrome_user'), config.get('navidrome_password')]):
        return False, "URL, Username, and Password must be filled."
    ping_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'ping')
    if ping_res: return True, "Connection successful!"
    else: return False, "Connection failed. Check URL, credentials, and network."

def normalize_for_search(text):
    if not isinstance(text, str): return ""
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def send_api_request(base_url, username, password, endpoint, **kwargs):
    if not all([base_url, username, password]): return None
    url = base_url.strip()
    if not url.endswith('/'): url += '/'
    if not url.endswith('/rest/'): url += 'rest/'
    api_args = {'f': 'json', 'u': username, 'v': '1.16.1', 'c': 'PlaylistToolGUI'}
    query = kwargs.pop('query', None)
    api_args.update(kwargs)
    salt = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(7))
    token = md5((password + salt).encode('utf-8')).hexdigest()
    api_args.update({'t': token, 's': salt})
    full_url = url + endpoint + ".view"
    params = api_args.copy()
    if query: params['query'] = query
    try:
        res = requests.get(full_url, params=params, timeout=30)
        res.raise_for_status()
        res_json = res.json()
        if 'subsonic-response' in res_json and res_json['subsonic-response'].get('status') == 'ok':
            return res_json['subsonic-response']
    except (requests.exceptions.RequestException, json.JSONDecodeError): return None
    return None

def get_all_songs_cache(config):
    song_cache = {}
    offset = 0
    PAGE_SIZE = 500
    while True:
        album_list_res = send_api_request(
            config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 
            'getAlbumList2', type='alphabeticalByName', size=PAGE_SIZE, offset=offset
        )
        if not album_list_res or 'albumList2' not in album_list_res or 'album' not in album_list_res['albumList2']:
            if offset == 0: return None 
            break
        albums = album_list_res['albumList2']['album']
        if isinstance(albums, dict): albums = [albums]
        for album in albums:
            album_detail_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'getAlbum', id=album['id'])
            if album_detail_res and 'album' in album_detail_res and 'song' in album_detail_res['album']:
                songs = album_detail_res['album']['song']
                if isinstance(songs, dict): songs = [songs]
                for song in songs:
                    if 'path' in song and 'id' in song:
                        normalized_path = song['path'].replace('\\', '/')
                        song_cache[normalized_path] = song
        if len(albums) < PAGE_SIZE: break
        offset += PAGE_SIZE
    return song_cache

def download_all_playlists(config):
    output_dir = config.get('navidrome_playlists_path')
    if not output_dir: return 0, 0, "Navidrome playlists path not set in config."
    playlists_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'getPlaylists')
    if not playlists_res or 'playlists' not in playlists_res or 'playlist' not in playlists_res['playlists']:
        return 0, 0, "Could not fetch playlist list from Navidrome."
    playlists = playlists_res['playlists']['playlist']
    total_count, success_count = len(playlists), 0
    for playlist in playlists:
        tracks_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'getPlaylist', id=playlist['id'])
        if tracks_res and 'playlist' in tracks_res and 'entry' in tracks_res['playlist']:
            filepath = os.path.join(output_dir, sanitize_filename(playlist['name']) + ".m3u")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("#EXTM3U\n")
                    for track in tracks_res['playlist']['entry']:
                        if track.get('path'): f.write(track['path'] + "\n")
                success_count += 1
            except IOError: continue
    return success_count, total_count, ""

def parse_m3u(file_path):
    tracks = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f: lines = f.readlines()
    except Exception: return []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#EXTM3U'): continue
        normalized_line = line.replace('\\', '/')
        parts = normalized_line.split('/')
        if len(parts) >= 3:
            try:
                artist, filename = parts[0], parts[-1]
                album = '/'.join(parts[1:-1])
                raw_title = os.path.splitext(filename)[0]
                cleaned_title = re.sub(r'^\s*\d+\s*[-._]?\s*', '', raw_title)
                tracks.append({'artist': artist.strip(), 'album': album.strip(), 'title': cleaned_title.strip(), 'path': line})
            except IndexError: continue
    return tracks

def merge_playlists(tracks1, tracks2):
    merged = []
    seen_paths = set()
    for track in tracks1 + tracks2:
        if track['path'] not in seen_paths:
            merged.append(track)
            seen_paths.add(track['path'])
    return merged

def search_tracks(config, query, count=50):
    if not query or not all(config.values()): return []
    res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'search3', query=query, songCount=count, artistCount=0, albumCount=0)
    if res and res.get('searchResult3', {}).get('song'): 
        songs = res['searchResult3']['song']
        return songs if isinstance(songs, list) else [songs]
    return []

def upload_playlist(config, playlist_filepath, song_cache):
    if not os.path.exists(playlist_filepath): return False, "Playlist file not found."
    playlist_name = os.path.splitext(os.path.basename(playlist_filepath))[0]
    tracks_to_find = parse_m3u(playlist_filepath)
    if not tracks_to_find: return False, "Playlist is empty or could not be read."

    song_ids_to_upload, found_count, missing_count = [], 0, 0
    for track in tracks_to_find:
        # --- FIX: Use the reliable cache lookup first ---
        normalized_path = track['path'].replace('\\', '/')
        song_object = song_cache.get(normalized_path)
        
        if song_object:
            song_ids_to_upload.append(song_object['id'])
            found_count += 1
        else:
            missing_count += 1

    if not song_ids_to_upload: return False, f"Could not find any tracks on the server using the path cache."
    
    playlists_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'getPlaylists')
    existing_playlist_id = None
    if playlists_res and 'playlists' in playlists_res and 'playlist' in playlists_res['playlists']:
        server_playlists = playlists_res['playlists']['playlist']
        if isinstance(server_playlists, dict): server_playlists = [server_playlists]
        for playlist in server_playlists:
            if playlist['name'] == playlist_name:
                existing_playlist_id = playlist['id']
                break
    upload_params = {'name': playlist_name, 'songId': song_ids_to_upload}
    action_verb = "Created"
    if existing_playlist_id:
        upload_params['playlistId'] = existing_playlist_id
        action_verb = "Updated"
    upload_res = send_api_request(config['navidrome_url'], config['navidrome_user'], config['navidrome_password'], 'createPlaylist', **upload_params)
    if upload_res:
        summary = f"Successfully {action_verb} playlist '{playlist_name}'.\n\nTracks Uploaded: {found_count}\nTracks Not Found: {missing_count}"
        return True, summary
    else:
        return False, f"Failed to upload playlist '{playlist_name}' to Navidrome."

def run_playlist_check(config, local_tracks, song_cache):
    MATCH_THRESHOLD = 75
    SUGGESTION_THRESHOLD = 10
    results = []
    for m3u_track in local_tracks:
        final_match, final_score, status = None, 0, 'missing'
        normalized_path = m3u_track['path'].replace('\\', '/')
        cached_match = song_cache.get(normalized_path)
        if cached_match:
            final_match, status, final_score = cached_match, 'ok', 100
        else:
            search_query = f"{m3u_track['artist']} {m3u_track['title']}"
            standard_results = search_tracks(config, search_query)
            best_std_candidate, highest_std_score = None, 0
            if standard_results:
                norm_m3u_title = normalize_for_search(m3u_track['title'])
                norm_m3u_album = normalize_for_search(m3u_track['album'])
                norm_m3u_artist = normalize_for_search(m3u_track['artist'])
                for song in standard_results:
                    title_score = fuzz.ratio(norm_m3u_title, normalize_for_search(song.get('title', '')))
                    album_score = fuzz.ratio(norm_m3u_album, normalize_for_search(song.get('album', '')))
                    artist_score = fuzz.ratio(norm_m3u_artist, normalize_for_search(song.get('artist', '')))
                    current_score = (title_score * 0.6) + (album_score * 0.3) + (artist_score * 0.1)
                    if current_score > highest_std_score:
                        highest_std_score, best_std_candidate = current_score, song
            best_title_candidate, highest_title_score = None, 0
            if highest_std_score < MATCH_THRESHOLD:
                title_only_results = search_tracks(config, m3u_track['title'])
                if title_only_results:
                    norm_m3u_title = normalize_for_search(m3u_track['title'])
                    for song in title_only_results:
                        current_score = fuzz.ratio(norm_m3u_title, normalize_for_search(song.get('title', '')))
                        if current_score > highest_title_score:
                            highest_title_score, best_title_candidate = current_score, song
            if highest_std_score >= MATCH_THRESHOLD:
                final_match, final_score, status = best_std_candidate, highest_std_score, 'found'
            elif highest_title_score > highest_std_score and highest_title_score >= SUGGESTION_THRESHOLD:
                final_match, final_score, status = best_title_candidate, highest_title_score, 'suggestion'
            elif highest_std_score >= SUGGESTION_THRESHOLD:
                final_match, final_score, status = best_std_candidate, highest_std_score, 'suggestion'
            else:
                status = 'missing'
        results.append({'original_track': m3u_track, 'navidrome_song': final_match, 'status': status, 'score': final_score})
    return results