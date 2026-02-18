from flask import Blueprint, jsonify, request, render_template
from googleapiclient.discovery import build
from datetime import datetime
import os

youtube_bp = Blueprint('youtube_subs', __name__)

# 환경변수에서 키를 가져오도록 설정 (보안 강화)
API_KEY = os.environ.get('MY_YOUTUBE_KEY')
youtube = build('youtube', 'v3', developerKey=API_KEY)


@youtube_bp.route('/subscribers')
def get_subscribers():
    target_channel_id = request.args.get('channel_id')

    # 1. 아이디가 없으면 그냥 빈 화면 보여주기
    if not target_channel_id:
        return render_template('youtube_sub.html')

    try:
        results = []
        # 구독자 목록 가져오기 (테스트를 위해 우선 1페이지 50명만!)
        sub_request = youtube.subscriptions().list(
            part="snippet",
            channelId=target_channel_id,
            maxResults=50
        )
        sub_response = sub_request.execute()

        # 만약 구독자가 한 명도 없으면 (비공개 채널 등)
        if not sub_response.get('items'):
            return render_template('youtube_sub.html', total_count=0, searched_id=target_channel_id)

        for item in sub_response.get('items', []):
            sub_channel_id = item['snippet']['resourceId']['channelId']
            sub_channel_name = item['snippet']['title']

            # 활동 내역 가져오기
            try:
                act_request = youtube.activities().list(
                    part="snippet,contentDetails",
                    channelId=sub_channel_id,
                    maxResults=1
                )
                act_response = act_request.execute()

                last_upload_date = None
                for act in act_response.get('items', []):
                    if act['snippet']['type'] == 'upload':
                        pub_at = act['snippet']['publishedAt']
                        # 시간 파싱 (안전한 방식)
                        last_upload_date = datetime.strptime(pub_at[:10], '%Y-%m-%d')
                        break

                now = datetime.utcnow()
                days_inactive = (now - last_upload_date).days if last_upload_date else 999

                results.append({
                    "name": sub_channel_name,
                    "last_upload_date": last_upload_date,
                    "days_inactive": days_inactive
                })
            except:
                continue

        # 데이터 가공
        active_top5 = sorted([r for r in results if r['last_upload_date']],
                             key=lambda x: x['last_upload_date'], reverse=True)[:5]
        inactive_list = sorted([r for r in results if r['days_inactive'] >= 30],
                               key=lambda x: x['days_inactive'], reverse=True)
        all_subscribers = sorted(results, key=lambda x: x['name'])

        # [중요] 데이터가 비어있어도 변수는 넘겨줘야 HTML이 렌더링됩니다.
        return render_template('youtube_sub.html',
                               active_top5=active_top5,
                               inactive_list=inactive_list,
                               all_subscribers=all_subscribers,
                               total_count=len(results),
                               searched_id=target_channel_id)

    except Exception as e:
        # 에러가 나면 화면에 에러 내용을 던져줌
        print(f"API 에러 발생: {e}")
        return render_template('youtube_sub.html', error_msg=str(e), searched_id=target_channel_id)