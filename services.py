# -*- coding: utf-8 -*-
import os, re, yt_dlp, subprocess, zipfile, datetime, requests
from flask import Blueprint, render_template, request, send_file, jsonify
from google import genai

# [중요] 블루프린트 설정 (메인 앱에 등록될 이름: services)
services_bp = Blueprint('services', __name__)

# --- [설정 및 클라이언트] ---
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY") or "AIzaSyD0vu4fiYirJ3FVkm-rOkfiXksET06N1Hc"
STEAM_API_KEY = "C7FACE44079582DF54BB9AB26641E50B"
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

KYARU_SYSTEM_PROMPT = """너는 게임 '프린세스 커넥트'의 '캬루'야.
말투는 항상 반말로 하고, 상대방을 '너'라고 불러.
엄청 까칠하고 배신자라고 불리면 화를 내지만, 사실은 외로움을 많이 타는 츤데레야.
문장 끝에 '...거든!', '...란 말이야!', '흥!' 같은 걸 자주 붙여줘"""

# --- [유튜브/스팀 로직 함수들] ---
def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def extract_audio_logic(url, ext_choice, sub_folder):
    format_settings = {
        "mp3": ["-ab", "192k", "-acodec", "libmp3lame"],
        "m4a": ["-vcodec", "copy", "-acodec", "aac"],
        "wav": ["-acodec", "pcm_s16le"]
    }

    current_dir = os.path.dirname(os.path.abspath(__file__))
    actual_cookie_path = os.path.join(current_dir, "youtube_cookies.txt")

    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "cookiefile": actual_cookie_path,
        "outtmpl": os.path.join(sub_folder, "%(title)s.%(ext)s"),
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "extractor_args": {"youtube": {"player_client": ["android", "web"], "include_dash_manifest": False}},
        "retries": 10,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info: raise Exception("음원 정보를 찾을 수 없습니다.")
        original_file = ydl.prepare_filename(info)
        title = info.get('title', 'audio')

    safe_title = sanitize_filename(title)
    final_filename = f"{safe_title}.{ext_choice}"
    final_path = os.path.join(sub_folder, final_filename)

    ffmpeg_cmd = ["ffmpeg", "-y", "-i", original_file, "-vn"] + format_settings[ext_choice] + [final_path]
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(original_file): os.remove(original_file)
    return final_path, final_filename

def resolve_steam_id(input_id):
    if input_id.isdigit() and len(input_id) == 17: return input_id
    url = "http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
    params = {'key': STEAM_API_KEY, 'vanityurl': input_id}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data['response'].get('steamid') if data['response'].get('success') == 1 else None
    except:
        return None

def get_steam_data(steam_id):
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        'key': STEAM_API_KEY,
        'steamid': steam_id,
        'format': 'json',
        'include_appinfo': True,
        'include_played_free_games': True
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()

        # 응답 데이터 유효성 검사
        if 'response' not in data or 'games' not in data['response']:
            return None

        games = data['response']['games']
        total_count = len(games)
        if total_count == 0: return None

        # 1. 기본 데이터 가공 및 시간 계산
        for game in games:
            # playtime_forever는 분(minute) 단위이므로 시간으로 변환
            game['playtime_hours'] = round(game.get('playtime_forever', 0) / 60, 1)
            last_time = game.get('rtime_last_played', 0)
            game['last_played_date'] = datetime.datetime.fromtimestamp(last_time).strftime(
                '%Y-%m-%d') if last_time > 0 else "기록 없음"
            game['img_url'] = f"https://cdn.akamai.steamstatic.com/steam/apps/{game['appid']}/header.jpg"

        # 2. 정렬 및 필터링
        most_played = sorted(games, key=lambda x: x.get('playtime_forever', 0), reverse=True)
        last_played = sorted(games, key=lambda x: x.get('rtime_last_played', 0), reverse=True)[:10]
        never_played = [g for g in games if g.get('playtime_forever', 0) == 0]
        played_games = [g for g in games if g.get('playtime_forever', 0) > 0]

        # 3. 주요 통계 수치 계산
        played_count = len(played_games)
        total_playtime_mins = sum(g.get('playtime_forever', 0) for g in games)
        total_hours = round(total_playtime_mins / 60, 1)

        avg_hours = round(total_hours / played_count, 1) if played_count > 0 else 0
        completion_rate = round((played_count / total_count) * 100, 1) if total_count > 0 else 0

        # 4. 신규 통계: 플레이 시간대별 분포 (차트용)
        dist_data = {
            "100h+ (갓겜)": 0,
            "50h~100h": 0,
            "10h~50h": 0,
            "1h~10h": 0,
            "1h 미만": 0
        }
        for g in played_games:
            h = g['playtime_hours']
            if h >= 100:
                dist_data["100h+ (갓겜)"] += 1
            elif h >= 50:
                dist_data["50h~100h"] += 1
            elif h >= 10:
                dist_data["10h~50h"] += 1
            elif h >= 1:
                dist_data["1h~10h"] += 1
            else:
                dist_data["1h 미만"] += 1

        # 5. 최종 결과 반환
        return {
            'most_played': most_played,
            'last_played': last_played,
            'never_played': never_played,
            'summary': {
                'total_count': total_count,
                'played_count': played_count,
                'never_played_count': len(never_played),
                'total_hours': total_hours,
                'avg_hours': avg_hours,
                'completion_rate': completion_rate  # HTML 52번 줄 에러 해결
            },
            'chart_most_played_labels': [g['name'] for g in most_played[:10]],
            'chart_most_played_data': [g['playtime_hours'] for g in most_played[:10]],
            # 시간대별 분포 차트 데이터
            'chart_dist_labels': list(dist_data.keys()),
            'chart_dist_data': list(dist_data.values())
        }
    except Exception as e:
        print(f"Error fetching steam data: {e}")
        return None

# --- [라우트 설정] @app 대신 @services_bp를 사용합니다! ---

@services_bp.route("/youtube")
def youtube_page():
    return render_template("test.html")

@services_bp.route("/rollet")
def rollet_page():
    return render_template("rollet_game.html")

@services_bp.route("/lotto")
def lotto_page():
    return render_template("lotto.html")

@services_bp.route("/lucky")
def taro_page():
    return render_template("lucky.html")

@services_bp.route('/download', methods=['POST'])
def download():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        work_dir = os.path.join(DOWNLOAD_FOLDER, timestamp)
        os.makedirs(work_dir, exist_ok=True)
        try:
            urls = request.form.getlist('urls[]')
            ext_choice = request.form.get('format', 'mp3')
            downloaded_results = []
            for url in [u for u in urls if u.strip()]:
                try:
                    f_path, f_name = extract_audio_logic(url, ext_choice, work_dir)
                    downloaded_results.append((f_path, f_name))
                except:
                    continue

            if not downloaded_results:
                return jsonify({"success": False, "message": "다운로드에 실패했습니다."}), 500

            if len(downloaded_results) == 1:
                return send_file(downloaded_results[0][0], as_attachment=True, download_name=downloaded_results[0][1])
            else:
                zip_path = os.path.join(DOWNLOAD_FOLDER, f"music_{timestamp}.zip")
                with zipfile.ZipFile(zip_path, 'w') as z:
                    for p, n in downloaded_results: z.write(p, n)
                return send_file(zip_path, as_attachment=True)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500


@services_bp.route("/steam_stats", methods=["GET", "POST"])
def steam_stats():
    # 내부에 있던 def steam_stats(): 줄을 삭제했습니다.
    stats, error = None, None
    if request.method == "POST":
        user_input = request.form.get("steam_id", "").strip()
        if 'steamcommunity.com/' in user_input:
            user_input = user_input.split('/profiles/')[-1].split('/')[0] if '/profiles/' in user_input else \
                user_input.split('/id/')[-1].split('/')[0]
        actual_id = resolve_steam_id(user_input)
        if actual_id:
            stats = get_steam_data(actual_id)
            if not stats: error = "프로필이 비공개이거나 게임 정보가 없습니다."
        else:
            error = "스팀 ID를 찾을 수 없습니다."

    # GET 방식일 때나 에러가 났을 때도 반드시 이 return이 실행됩니다!
    return render_template("steam_statistics.html", stats=stats, error=error)

@services_bp.route("/ask_kyaru", methods=["POST"])
def ask_kyaru():
    data = request.get_json()
    msg, nick = data.get("message", "").strip(), data.get("nickname", "사용자")
    if not msg: return jsonify({"answer": "흥! 할 말 없으면 가만히 있어!"})
    try:
        resp = client_gemini.models.generate_content(model="gemini-2.5-flash",
                                                     contents=f"{KYARU_SYSTEM_PROMPT}\n\n{nick}: {msg}")
        return jsonify({"answer": resp.text})
    except:
        return jsonify({"answer": "지금은 바쁘니까 나중에 와!"})