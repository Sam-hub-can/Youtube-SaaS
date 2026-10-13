import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from db import init_db, insert_reply
from bot import generate, score, strategy, get_transcript
from announcer import active_notice

load_dotenv()

youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))
CHANNEL_ID = os.getenv("CHANNEL_ID")


# ----------------------------
# GET VIDEOS
# ----------------------------
def get_videos():
    res = youtube.search().list(
        part="id",
        channelId=CHANNEL_ID,
        order="date",
        maxResults=5,
        type="video"
    ).execute()

    return [x["id"]["videoId"] for x in res["items"]]


# ----------------------------
# GET COMMENTS
# ----------------------------
def get_comments(video_id):
    res = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=10,
        textFormat="plainText"
    ).execute()

    comments = []

    for i in res.get("items", []):
        s = i["snippet"]["topLevelComment"]["snippet"]

        comments.append({
            "id": i["id"],
            "text": s["textDisplay"],
            "author": s["authorDisplayName"]
        })

    return comments


# ----------------------------
# RUN
# ----------------------------
def run():

    notice = active_notice()
    if notice:
        print("NOTICE:", notice)

    init_db()

    videos = get_videos()
    print("VIDEOS:", len(videos))

    for v in videos:

        transcript = get_transcript(v)
        comments = get_comments(v)

        print("\nVIDEO:", v)
        print("COMMENTS:", len(comments))

        for c in comments:

            s = score(c["text"])
            st = strategy(s)

            reply = generate(c["text"], v, transcript, st)

            print("\nCOMMENT:", c["text"])
            print("REPLY:", reply)

            insert_reply({
                "id": c["id"],
                "video": v,
                "author": c["author"],
                "comment": c["text"],
                "reply": reply,
                "score": s,
                "strategy": st
            })


if __name__ == "__main__":
    run()
