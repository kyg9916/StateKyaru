import os, re, yt_dlp, subprocess, zipfile, datetime, requests, html, base64, random, shutil
from flask import Blueprint, render_template, request, send_file, jsonify
from google import genai
from googleapiclient.discovery import build # 추가
from soynlp.noun import LRNounExtractor_v2 # 추가
from collections import Counter
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud
from datetime import datetime
from moviepy import AudioFileClip, concatenate_audioclips
import matplotlib.font_manager as fm

# 블루프린트 설정
services_bp = Blueprint('services', __name__)

# --- [공통 설정 및 키] ---
# 1. 환경변수에서 값들을 먼저 다 가져옵니다.
MY_KEY = os.environ.get("MY_YOUTUBE_KEY")
GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY")
STEAM_API_KEY = os.environ.get("MY_STEAM_KEY")

# 2. [매우 중요] 가져온 값이 진짜 있는지 확인해봅니다.
# 만약 파이참 설정이 안 먹혔다면 여기서 에러가 나서 우리가 알 수 있어요.
if not GEMINI_API_KEY:
    # 파이참 설정이 안 되었을 때를 대비한 임시 방편 (테스트용)
    GEMINI_API_KEY = "AIzaSyD0vu4fiYirJ3FVkm-rOkfiXksET06N1Hc"
    print("⚠️ 경고: 환경변수를 못 찾아서 코드에 적힌 키를 사용합니다.")

# 3. 이제 클라이언트를 만듭니다.
client_gemini = genai.Client(api_key=GEMINI_API_KEY)


TEMP_AUDIO_DIR = 'temp_audio'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(BASE_DIR, 'malgun.ttf')

# 폰트 파일이 있는지 확인하고 로드
if os.path.exists(font_path):
    # 1. 폰트 매니저에게 이 파일을 직접 등록 (이게 빠지면 시스템 폰트만 찾아요)
    fm.fontManager.addfont(font_path)

    font_prop = fm.FontProperties(fname=font_path)
    font_name = font_prop.get_name()

    # 2. 등록된 폰트 이름을 기본 패밀리로 설정
    plt.rcParams['font.family'] = font_name
else:
    # 폰트 파일이 없을 때 서버가 죽지 않도록 기본 폰트 설정
    plt.rcParams['font.family'] = 'sans-serif'
    print(f"⚠️ 경고: {font_path} 파일을 찾을 수 없어 기본 폰트를 사용합니다.")

plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# 1. 유튜브 댓글 여론 분석 기능 (기존 app.py에서 이동)
# ==========================================

# (이곳에 아까 주신 모든 분석 함수들을 넣으세요)
def is_korean(text):
    # 한글 자음, 모음, 글자가 포함되어 있는지 확인하는 정규식
    ko_py = re.compile('[ㄱ-ㅎㅏ-ㅣ가-힣]+')
    return bool(ko_py.search(text))


def get_wordcloud_image(all_top_words):
    if not all_top_words: return None

    word_dict = dict(all_top_words)

    # 이 부분을 깔끔하게 수정했습니다!
    wc = WordCloud(
        font_path=font_path,  # 위에서 잡은 변수 경로 사용
        background_color='white',
        width=1000, height=500,
        max_words=100,
        colormap='viridis',
        prefer_horizontal=0.7
    ).generate_from_frequencies(word_dict)

    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')

    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', pad_inches=0)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return f"data:image/png;base64,{plot_url}"


# --- [추가] 초간단 감정 분석 함수 (맛보기용) ---
def analyze_sentiment(comments_data):
    # 실제로는 딥러닝 모델(KcBERT 등)을 올리는 게 좋지만,
    # 일단은 긍정/부정 단어 사전을 이용한 기초 로직으로 시작해볼게요.
    pos_words = [
        # 기본 감정
        '좋다', '최고', '대박', '응원', '감사', '예쁘다', '재밌', '훈훈', '사랑', '감동',
        '멋지', '유익', '최강', '갓', '꿀잼', '웃겨', '레전드', '힐링', '깔끔', '완벽',
        '좋아요', '구독', '팬', '천사', '대단', '인정', '따뜻', '천재', '역시', '품격',
        '기다렸', '기대', '행복', '최고예요', '존맛', '맛있', '멋있', '잘보고', '도움',

        # 유튜브/커뮤니티 유행어 및 감탄사
        '폼 미쳤', '폼미쳤', '귀여워', '커엽', '킹갓', '빛', '혜자', '지렸다', '오졌다',
        '미쳤다', '역대급', '지리네', '오지네', '지존', '압권', '믿고보는', '믿보',
        '기깔', '찰떡', '찰지', '취향저격', '취저', '갓벽', '대만족', '눈물난', '광광',

        # 칭찬 및 동의
        '정답', '공감', '동감', '옳다', '맞는말', '팩트', '천재', '능력자', '금손',
        '갓생', '성지순례', '명작', '꿀팁', '알짜', '대성공', '소중한', '최애', '강추'
    ]

    # --- [업데이트] 부정 단어 리스트 ---
    neg_words = [
        # 기본 감정 및 비판
        '나쁘다', '불편', '최악', '지루', '실망', '어이', '지적', '논란', '나락', '별로',
        '싫다', '노잼', '짜증', '극혐', '가식', '피곤', '그만', '작작', '한심', '충격',
        '안봐', '비호감', '역겹', '혐오', '쓰레기', '망해라', '노답', '답답', '주작',
        '억지', '비매너', '무례', '실수', '변명', '거짓말', '짜치', '싸구려', '저질',

        # 유튜브 특유의 부정 표현
        '노잼', '핵노잼', '갑분싸', '뇌절', '선넘', '비추', '극혐', '편집왜이래', '노이해',
        '극혐', '탈퇴', '구독취소', '구취', '망했', '폭망', '한남', '한녀', '틀딱', '급식',
        '광고질', '돈독', '변했네', '초심', '실망이야', '작위적', '오글', '오글거려',

        # 논란 및 거부감
        '허언', '구라', '날조', '선동', '징그럽', '드럽', '더럽', '수준', '실력미달',
        '시간낭비', '시낭', '돈아깝', '보여주기식', '꼴보기싫', '꼴사납', '적당히'
    ]

    pos_count = 0
    neg_count = 0
    neutral_count = 0

    for comm in comments_data:
        text = comm['text']
        # 긍정/부정 단어 리스트 (위에 보강한 리스트 사용)
        p_score = sum(1 for w in pos_words if w in text)
        n_score = sum(1 for w in neg_words if w in text)

        if p_score > n_score:
            pos_count += 1
        elif n_score > p_score:
            neg_count += 1
        else:
            # 단어가 아예 없거나 긍정/부정이 똑같을 때만 중립!
            neutral_count += 1

    total = len(comments_data)
    # 중립 95% 방지: 단순히 개수로 비율 계산
    pos_p = round((pos_count / total) * 100)
    neg_p = round((neg_count / total) * 100)
    neu_p = 100 - (pos_p + neg_p)

    return pos_p, neg_p, neu_p


# --- 기존 함수들 (extract_video_id, get_comments 등은 유지) ---
def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    search = re.search(regex, url)
    return search.group(1) if search else None


def clean_html(text):
    clean_text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(clean_text)


def get_comments(api_key, video_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    comments_data = []
    next_page_token = None

    while len(comments_data) < 2000:
        request = youtube.commentThreads().list(
            part="snippet", videoId=video_id, maxResults=100,
            pageToken=next_page_token, order="relevance"
        )
        response = request.execute()
        for item in response['items']:
            snippet = item['snippet']['topLevelComment']['snippet']
            text = clean_html(snippet['textDisplay'])

            # [로직 보강] 한국어가 포함된 댓글인지 확인
            has_korean = is_korean(text)

            # 외국어 댓글이라도 통계(좋아요 수 등)를 위해 일단 수집은 하되,
            # 텍스트 분석용 데이터인지 표시만 해둡니다.
            comment_dict = {
                'author': snippet.get('authorDisplayName', '익명'),
                'text': text,
                'like_count': snippet['likeCount'],
                'reply_count': item['snippet']['totalReplyCount'],
                'published_at': datetime.strptime(snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'),
                'is_korean': has_korean  # 한국어 여부 저장
            }
            comments_data.append(comment_dict)

        next_page_token = response.get('nextPageToken')
        if not next_page_token: break

    return comments_data


def get_pin_candidates(scored_comments):
    # 조건: 점수가 높고(긍정), 길이는 20자 이상
    candidates = [c for c in scored_comments if c['score'] > 1 and len(c['text']) > 20]
    return sorted(candidates, key=lambda x: (x['like_count'], x['score']), reverse=True)[:3]


# --- [신규] 관리 필요 댓글 감지 (Toxic Detection) ---
def get_toxic_comments(comments_data):
    # 초록자두님의 리스트에 몇 가지 더 추가했어요!
    toxic_words = [
        # 1. 직접적인 욕설 및 비속어 (자음 포함)
        'ㅅㅂ', '씨발', '시발', '존나', '좆', 'ㄲㅈ', '꺼져', '쳐먹', '빡치', 'ㅆㅂ',

        # 2. 인격 모독 및 비하 (병명, 지능 관련)
        '병신', 'ㅂㅅ', '장애', '저능', '꼴통', '빡대가리', '무식', '한남', '한녀', '틀딱',

        # 3. 공격적인 표현 및 저주
        '미친', '개같', '죽어', '자살', '살인', '망해라', '나락', '꼴좋다', '극혐', '혐오',

        # 4. 강한 비판 및 부정적 단어
        '쓰레기', '노답', '답답', '주작', '가식', '역겹', '더럽', '수준', '싸구려', '저질',

        # 5. 채널 공격성 멘트
        '차단', '신고', '구독취소', '안본다', '삭제해', '편집왜이래', '노잼', '실망'
    ]

    toxic_list = []
    for comm in comments_data:
        if any(t in comm['text'] for t in toxic_words):
            toxic_list.append(comm)

    # 좋아요를 많이 받은 욕설 댓글부터 확인해야 하므로 정렬
    return sorted(toxic_list, key=lambda x: x['like_count'], reverse=True)[:5]


def get_clean_score(all_data, toxic_comments):
    if not all_data:
        return 100

    # 영향력 있는 악플 반영: 좋아요 수 + 1(최소값)을 가중치로 사용
    # 좋아요가 100개인 악플은 일반 악플보다 100배 더 위험하다고 판단합니다.
    weighted_toxic = sum(c.get('like_count', 0) + 1 for c in toxic_comments)
    weighted_total = sum(c.get('like_count', 0) + 1 for c in all_data)

    if weighted_total == 0: return 100

    score = 100 - (weighted_toxic / weighted_total * 100)
    return round(score, 1)


# --- [신규] 2. 콘텐츠 아이디어 요약 ---
def get_content_ideas(request_list):
    if not request_list:
        return ["데이터가 부족합니다", "소통을 시작해보세요!", "질문을 유도해보세요"]

    # 그물을 훨씬 크게 넓혔어요!
    category_map = {
        '🎮 게임 공략/플레이': ['게임', '플레', '공략', '롤', '배그', '옵치', '스팀', '모바일', '전투', '보스', '엔딩'],
        '🌸 애니·만화 리뷰': ['애니', '만화', '웹툰', '캐릭터', '주인공', '에피', '극장판', '덕질', '최애', '성우'],
        '🤣 병맛더빙/개그': ['더빙', '목소리', '웃겨', '개웃', '병맛', '드립', '개그', '꿀잼', '개드립'],
        '🐱 동물/펫 영상': ['강아지', '고양이', '동물', '커엽', '집사', '댕댕', '냥이', '귀여', '간식'],
        '🎵 음악·노래 커버': ['음악', '노래', '커버', '플리', '노래방', '띵곡', '멜로디', '가수', '라이브'],
        '🃏 인터넷밈/챌린지': ['밈', '챌린지', '유행', '쇼츠', '짤', '틱톡', '요즘', '대세'],
        '🌎 해외반응 분석': ['해외', '외국', '자막', '번역', '글로벌', '반응', '일본인', '미국인'],
        '💻 기술·IT 정보': ['기술', '컴퓨터', 'IT', 'AI', '코딩', '폰', '갤럭시', '아이폰', '앱', '꿀팁'],
        '📚 교육/자기계발': ['일본어', '공부', '방법', '강의', '팁', '노하우', '학습', '시험', 'jlpt', '단어'],
        '📦 언박싱/하울': ['언박싱', '하울', '택배', '쇼핑', '구매', '지름', '리뷰', '후기']
    }

    ideas_raw = []
    for r in request_list:
        text = r['text'].replace(" ", "").lower() # 공백 제거로 '게 임'도 '게임'으로 인식!
        matched = False

        for category, keywords in category_map.items():
            if any(kw in text for kw in keywords):
                ideas_raw.append(category)
                matched = True
                break

        if not matched:
            ideas_raw.append('📂 시청자 궁금증/Q&A') # 명칭을 좀 더 매력적으로 변경

    # 빈도수 계산
    most_common = Counter(ideas_raw).most_common(3)
    result = [item[0] for item in most_common]

    # 중복 제거 및 결과 보장
    while len(result) < 3:
        result.append("📂 새로운 주제 도전")

    return result


def get_sentiment_lists(comments_data):
    # 1. 단어 리스트 정교화 (중립적이거나 오해의 소지가 있는 '협상', '결렬' 등 제외)
    pos_words = [
        '좋다', '최고', '대박', '응원', '감사', '예쁘다', '재밌다', '훈훈', '사랑', '감동',
        '멋지다', '유익', '최강', '갓', '꿀잼', '응원해요', '감사해요', '잘보고', '기대', '행복',
        '최고예요', '웃겨', '레전드', '힐링', '깔끔', '완벽', '좋아요', '구독', '알람', '팬이에요',
        '천사', '대단', '최고다', '정답', '공감', '인정', '따뜻', '명언', '천재', '기부',
        '나눔', '멋짐', '귀엽', '매력', '정석', '믿고보는', '역시', '품격', '클라스', '훌륭'
    ]

    neg_words = [
        '나쁘다', '불편', '최악', '지루', '실망', '어이', '지적', '논란', '나락', '별로',
        '싫다', '노잼', '짜증', '극혐', '편집왜이래', '작위적', '가식', '피곤', '그만', '작작',
        '한심', '충격', '선넘', '문제', '실망이야', '안봐', '비호감', '역겹', '혐오',
        '쓰레기', '망해라', '노답', '답답', '작작해', '그만해', '보기싫', '삭제해', '신고', '주작',
        '억지', '비매너', '무례', '실수', '변명', '거짓말', '실망스럽', '짜치네', '싸구려', '저질'
    ]

    scored_comments = []
    for comm in comments_data:
        if not comm.get('is_korean', True): continue
        text = comm['text']
        p_count = sum(text.count(w) for w in pos_words)
        n_count = sum(text.count(w) for w in neg_words)

        import math
        weight = 1 + (math.log10(comm['like_count'] + 1) * 0.5)
        final_score = (p_count - n_count) * weight

        scored_comments.append({
            'author': comm['author'],
            'text': text,
            'like_count': comm['like_count'],
            'score': final_score
        })

    pos_top = sorted([c for c in scored_comments if c['score'] > 0], key=lambda x: x['score'], reverse=True)[:10]
    neg_top = sorted([c for c in scored_comments if c['score'] < 0], key=lambda x: x['score'])[:10]

    return pos_top, neg_top, scored_comments


def get_request_list(comments_data):
    # 구독자들이 주로 사용하는 요청 키워드 (동사/종결어미 중심)
    request_keywords = [
        '해주세요', '해주세여', '해줘요', '만들어주세요', '보여주세요', '찍어주세요',
        '알려주세요', '부탁드려요', '리뷰해주세요', '실험해주세요', '소개해주세요',
        '보고싶어요', '보고싶네', '원해요', '바랍니다', '기다릴게요', '올려주세요',
        '제작해주세요', '비교해주세요', '다뤄주세요', '궁금해요'
    ]

    request_comments = []

    for comm in comments_data:
        # 한국어인 경우만 요청사항 분석
        if not comm.get('is_korean', True):
            continue

        text = comm['text']
        if any(keyword in text for keyword in request_keywords):
            request_comments.append({
                'author': comm['author'],  # 작성자 추가
                'text': text,
                'like_count': comm['like_count'],
                'is_korean': comm['is_korean']
            })

    return sorted(request_comments, key=lambda x: x['like_count'], reverse=True)[:10]


def analyze_words_extended(comments_data, limit=100):
    """워드클라우드와 차트를 위해 단어(명사)를 추출합니다."""
    # 한국어인 댓글만 모으기
    ko_texts = [c['text'] for c in comments_data if c.get('is_korean', False)]

    if not ko_texts:
        return []

    # 분석에서 제외할 무의미한 단어들 (불용어)
    stopwords = {'정말', '진짜', '너무', '많이', '보고', '하고', '좋다', '항상', '오늘', '그냥', '유튜브', '영상'}

    # soynlp를 이용한 명사 추출
    noun_extractor = LRNounExtractor_v2(verbose=False)
    try:
        nouns = noun_extractor.train_extract(ko_texts)
        all_nouns = []
        for word, score in nouns.items():
            # 2글자 이상이고 불용어에 포함되지 않는 단어만 선택
            if len(word) > 1 and word not in stopwords:
                # 빈도수만큼 리스트에 추가
                for _ in range(int(score.frequency)):
                    all_nouns.append(word)

        # 가장 많이 나온 순서대로 limit 개수만큼 반환
        return Counter(all_nouns).most_common(limit)
    except Exception as e:
        print(f"명사 추출 중 에러 발생: {e}")
        return []


def get_chart_image(top_words):
    if not top_words: return None
    df = pd.DataFrame(top_words, columns=['단어', '빈도수'])

    plt.figure(figsize=(8, 4))

    # 폰트 속성을 직접 불러옵니다.
    font_p = fm.FontProperties(fname=font_path)

    # 차트를 그릴 때 x축 단어들에 폰트를 직접 입힙니다.
    plt.bar(df['단어'], df['빈도수'], color='skyblue')

    # [핵심] X축의 글자들(단어)에 폰트 적용
    plt.xticks(fontproperties=font_p)

    # 제목이나 라벨도 깨진다면 똑같이 적용해줍니다.
    plt.title("📈 키워드 빈도 TOP 10", fontproperties=font_p)
    plt.xlabel("단어", fontproperties=font_p)
    plt.ylabel("빈도수", fontproperties=font_p)

    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return f"data:image/png;base64,{plot_url}"




# --- [추가] 통계 요약 정보 계산 함수 ---
def get_stat_summary(comments_data):
    likes = [c['like_count'] for c in comments_data]
    df = pd.Series(likes)

    # 찐팬 지수: 좋아요 10개 이상 댓글 비율
    super_fan_count = len([l for l in likes if l >= 10])
    super_fan_score = round((super_fan_count / len(likes)) * 100, 1) if likes else 0

    summary = {
        'mean': round(df.mean(), 2),
        'median': int(df.median()),
        'max': int(df.max()),
        'std': round(df.std(), 2),
        'super_fan_score': super_fan_score  # 찐팬 지수 추가
    }
    return summary


# --- [신규] 좋아요 분포 히스토그램 생성 ---
def get_distribution_chart(comments_data):
    likes = [c['like_count'] for c in comments_data]

    # 구간 설정 (0, 1~10, 11~50, 51~100, 100+)
    bins = [-1, 0, 10, 50, 100, float('inf')]
    labels = ['0개', '1-10개', '11-50개', '51-100개', '100개+']
    cats = pd.cut(likes, bins=bins, labels=labels)
    dist = cats.value_counts().reindex(labels)

    plt.figure(figsize=(7, 4))
    plt.bar(dist.index, dist.values, color='#ff9999')
    plt.title("좋아요 구간별 댓글 분포")

    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}"


# --- [신규] 시간대별 댓글 추이 생성 ---
def get_timeseries_chart(comments_data):
    df = pd.DataFrame(comments_data)
    # 시간별로 그룹화
    df['hour'] = df['published_at'].dt.hour
    time_dist = df.groupby('hour').size().reindex(range(24), fill_value=0)

    plt.figure(figsize=(7, 4))
    plt.plot(time_dist.index, time_dist.values, marker='o', linestyle='-', color='#4285F4')
    plt.fill_between(time_dist.index, time_dist.values, color='#4285F4', alpha=0.2)
    plt.title("시간대별 댓글 작성 현황 (24시간)")
    plt.xticks(range(0, 24, 2))
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return f"data:image/png;base64,{base64.b64encode(img.getvalue()).decode()}"


def get_video_info(api_key, video_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.videos().list(
        part="snippet,statistics",
        id=video_id
    )
    response = request.execute()

    if not response['items']:
        return None

    snippet = response['items'][0]['snippet']
    stats = response['items'][0]['statistics']

    # [수정] 유튜버가 쓴 설명글 가져오기
    raw_desc = snippet.get('description', '')

    # 설명이 아예 없거나 공백만 있을 때
    if not raw_desc.strip():
        description = "유튜버가 작성한 영상 설명이 존재하지 않습니다. (신비주의 채널인가 봐요! 🧐)"
    else:
        # 가독성을 위해 줄바꿈을 공백으로 바꾸고 200자까지만 깔끔하게 보여주기
        description = raw_desc.replace("\n", " ").strip()
        if len(description) > 200:
            description = description[:200] + "..."

    return {
        'title': snippet['title'],
        'channel': snippet['channelTitle'],
        'view_count': stats.get('viewCount', '0'),
        'description': description,
        'thumbnail': snippet['thumbnails']['high']['url']
    }


def get_ai_style_advice(stats, pos_p, view_count):
    # 1. 조회수 대비 댓글 확률 계산
    total_comments = 500  # 현재 수집 제한량 기준 (실제 전체 댓글수로 하면 더 정확함)
    comment_rate = round((total_comments / int(view_count)) * 100, 2) if int(view_count) > 0 else 0

    # 2. 찐팬 지수 진단
    if stats['super_fan_score'] >= 15:
        fan_status = "강력한 팬덤이 형성된 '청정 구역'입니다. 팬들의 충성도가 매우 높아요!"
    elif stats['super_fan_score'] >= 7:
        fan_status = "안정적인 소통이 이루어지고 있습니다. 꾸준한 답글이 성장의 열쇠입니다."
    else:
        fan_status = "시청자들이 눈팅 위주로 활동 중입니다. 참여를 유도하는 질문이 필요해요."

    # 3. 감성 분석 연동 진단
    if pos_p >= 80:
        sentiment_status = "민심이 매우 좋습니다! 현재의 콘텐츠 방향을 유지하세요. 😊"
    elif pos_p <= 40:
        sentiment_status = "여론이 다소 날카롭습니다. 비판적인 피드백을 수용하거나 해명이 필요할 수 있어요. 🧐"
    else:
        sentiment_status = "건전한 토론이 오가는 중입니다. 다양한 의견이 채널의 활력이 됩니다."

    # 4. 조회수 대비 댓글율 진단
    if comment_rate >= 1.0:
        rate_status = "조회수 대비 댓글이 아주 많습니다! 영상의 몰입도가 매우 높다는 뜻이에요."
    else:
        rate_status = "조회수 대비 댓글이 적은 편입니다. 영상 마지막에 질문을 던져보세요!"

    return {
        'fan_status': fan_status,
        'sentiment_status': sentiment_status,
        'rate_status': rate_status,
        'comment_rate': comment_rate
    }

@services_bp.route("/youtube_comment", methods=["GET", "POST"])
def youtube_comment_service():
    # POST 방식일 때 (사용자가 URL을 넣고 분석 버튼을 눌렀을 때)
    if request.method == "POST":
        url = request.form.get("url")
        video_id = extract_video_id(url) # URL에서 ID 추출

        if video_id:
            # 1. 데이터 수집
            video_info = get_video_info(MY_KEY, video_id)
            all_data = get_comments(MY_KEY, video_id)

            # 2. 한국어 존재 여부 검사
            has_ko_comments = any(c.get('is_korean', False) for c in all_data)
            if not has_ko_comments:
                error_msg = f"'{video_info['title']}' 영상에는 분석 가능한 한국어 댓글이 없습니다. 🌎"
                return render_template("youtube_comment.html", error=error_msg, video=video_info)

            # 3. 핵심 통계 및 감정 분석
            stat_summary = get_stat_summary(all_data)
            pos_p, neg_p, neu_p = analyze_sentiment(all_data)

            toxic_comments = get_toxic_comments(all_data)
            clean_score = get_clean_score(all_data, toxic_comments)
            clean_status = "매우 클린함 ✨" if clean_score >= 95 else "보통 ✅" if clean_score >= 85 else "주의 필요 ⚠️"

            # AI 진단
            ai_advice = get_ai_style_advice(stat_summary, pos_p, video_info['view_count'])

            # 4. 리스트 및 키워드 분석
            likes_top = sorted(all_data, key=lambda x: x['like_count'], reverse=True)[:10]
            top_words_for_chart = analyze_words_extended(all_data, limit=10)
            top_words_for_cloud = analyze_words_extended(all_data, limit=100)

            # 5. 시각화 이미지 생성
            chart_img = get_chart_image(top_words_for_chart)
            wordcloud_img = get_wordcloud_image(top_words_for_cloud)
            dist_chart = get_distribution_chart(all_data)
            time_chart = get_timeseries_chart(all_data)

            # 6. 상세 댓글 분류
            pos_comments, neg_comments, scored_comments = get_sentiment_lists(all_data)
            request_list = get_request_list(all_data)
            content_ideas = get_content_ideas(request_list)
            pin_candidates = get_pin_candidates(scored_comments)

            # 7. AI 요약 멘트
            top_keyword = top_words_for_chart[0][0] if top_words_for_chart else "콘텐츠"
            summary_text = f"이번 영상은 긍정 반응이 {pos_p}%이며, 시청자들은 특히 '{top_keyword}' 키워드에 큰 관심을 보이고 있습니다."

            # 8. 최종 결과물 전달
            return render_template(
                "youtube_comment.html",
                likes=likes_top,
                words=top_words_for_chart,
                chart=chart_img,
                wordcloud=wordcloud_img,
                dist_chart=dist_chart,
                time_chart=time_chart,
                pos_percent=pos_p,
                neg_percent=neg_p,
                neu_percent=neu_p,
                stats=stat_summary,
                pos_comments=pos_comments,
                neg_comments=neg_comments,
                requests=request_list,
                video=video_info,
                advice=ai_advice,
                video_id=video_id,
                pin_candidates=pin_candidates,
                toxic_comments=toxic_comments,
                summary=summary_text,
                clean_score=clean_score,
                clean_status=clean_status,
                content_ideas=content_ideas
            )

    # GET 방식일 때 (처음 페이지에 접속했을 때)
    return render_template("youtube_comment.html")

# --- [설정 및 클라이언트] ---
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

GEMINI_API_KEY = os.environ.get("MY_GEMINI_KEY") or "AIzaSyD0vu4fiYirJ3FVkm-rOkfiXksET06N1Hc"
STEAM_API_KEY = os.environ.get("MY_STEAM_KEY")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

KYARU_SYSTEM_PROMPT = """너는 게임 '프린세스 커넥트'의 '캬루'야.
말투는 항상 반말로 하고, 상대방을 '너'라고 불러.
엄청 까칠하고 배신자라고 불리면 화를 내지만, 사실은 외로움을 많이 타는 츤데레야.
문장 끝에 '...거든!', '...란 말이야!', '흥!' 같은 걸 자주 붙여줘"""

# --- [유튜브/스팀 로직 함수들] ---
def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def get_playlist_videos(api_key, playlist_id):
    youtube = build('youtube', 'v3', developerKey=api_key)
    video_list = []
    # 최대 50개까지만 가져오도록 설정
    request_api = youtube.playlistItems().list(
        part='snippet', playlistId=playlist_id, maxResults=50
    )
    response = request_api.execute()
    for item in response['items']:
        video_id = item['snippet']['resourceId']['videoId']
        title = item['snippet']['title']
        video_list.append({
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'title': title,
            'id': video_id
        })
    return video_list

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

            # 수정된 부분: datetime.datetime 대신 datetime만 사용
            if last_time > 0:
                game['last_played_date'] = datetime.fromtimestamp(last_time).strftime('%Y-%m-%d')
            else:
                game['last_played_date'] = "기록 없음"

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


@services_bp.route("/youtube_music_shuffle")
def youtube_music_shuffle_page():
    return render_template('youtube_music_suffle.html')


# --- 실제 처리 프로세스 ---
@services_bp.route('/process_shuffle', methods=['POST'])
def process_shuffle():
    api_key = request.form.get('api_key') or MY_KEY  # 입력 없으면 기본 키 사용
    playlist_id = request.form.get('playlist_id')
    mode = request.form.get('mode')

    if not playlist_id:
        return "재생목록 ID를 입력해주세요.", 400

    videos = get_playlist_videos(api_key, playlist_id)

    # 임시 폴더 초기화
    if os.path.exists(TEMP_AUDIO_DIR):
        shutil.rmtree(TEMP_AUDIO_DIR)
    os.makedirs(TEMP_AUDIO_DIR)

    downloaded_paths = []

    # yt-dlp 설정
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True
    }

    for index, v in enumerate(videos, start=1):
        # 파일명 안전하게 만들기
        safe_title = "".join([c for c in v['title'] if c.isalnum() or c in (' ', '_', '-')]).strip()

        # 3번 모드(개별다운)일 때만 번호 붙이기
        out_name = f"{index:02d}_{safe_title}" if mode == '3' else v['id']

        current_opts = ydl_opts.copy()
        current_opts['outtmpl'] = f'{TEMP_AUDIO_DIR}/{out_name}.%(ext)s'

        with yt_dlp.YoutubeDL(current_opts) as ydl:
            ydl.download([v['url']])
            downloaded_paths.append(f"{TEMP_AUDIO_DIR}/{out_name}.mp3")

    # 결과물 처리 로직
    if mode in ['1', '2']:
        if mode == '2':
            random.shuffle(downloaded_paths)

        # 오디오 합치기 작업
        clips = [AudioFileClip(f) for f in downloaded_paths]
        final_audio = concatenate_audioclips(clips)
        output_filename = "merged_playlist.mp3"
        final_audio.write_audiofile(output_filename)

        for clip in clips:
            clip.close()

        return send_file(output_filename, as_attachment=True)

    else:
        # ZIP 압축 다운로드
        zip_name = "my_music_collection.zip"
        with zipfile.ZipFile(zip_name, 'w') as music_zip:
            for file in downloaded_paths:
                music_zip.write(file, os.path.basename(file))

        return send_file(zip_name, as_attachment=True)

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

@services_bp.route('/youtube_music_suffle_test')
def shuffle_test_page():
    # 안내 문구가 담긴 html 파일을 보여줍니다.
    # 파일명이 'youtube_music_suffle_test.html' 인지 꼭 확인하세요!
    return render_template('youtube_music_suffle_test.html')


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