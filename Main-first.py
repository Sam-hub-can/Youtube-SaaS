import os
import json
import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from groq import Groq

# ----------------------------
# Load environment
# ----------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

client = Groq(api_key=GROQ_API_KEY)

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

REPLIED_FILE = "replied.json"

# ----------------------------
# Load replied comments
# ----------------------------
def load_replied():
    try:
        with open(REPLIED_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_replied(data):
    with open(REPLIED_FILE, "w") as f:
        json.dump(data, f)

# ----------------------------
# Get latest videos
# ----------------------------
def get_videos():
    request = youtube.search().list(
        part="id",
        channelId=CHANNEL_ID,
        maxResults=10,
        order="date",
        type="video"
    )
    response = request.execute()

    return [item["id"]["videoId"] for item in response["items"]]

# ----------------------------
# Get comments
# ----------------------------
def get_comments(video_id):
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=20,
        textFormat="plainText"
    )
    response = request.execute()

    comments = []

    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]

        comments.append({
            "id": item["id"],
            "text": snippet["textDisplay"],
            "author": snippet["authorDisplayName"],
            "video": video_id
        })

    return comments

# ----------------------------
# Groq AI reply generator
# ----------------------------
def generate_reply(comment_text):
    prompt = f"""
You are replying to YouTube comments.

Rules:
- natural human tone
- short (1–3 sentences)
- no emojis overload
- slightly analytical if needed
- not robotic

Comment:
{comment_text}

Reply:
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    return response.choices[0].message.content.strip()

# ----------------------------
# Main logic
# ----------------------------
def run():
    replied = load_replied()
    videos = get_videos()

    results = []

    for video in videos:
        comments = get_comments(video)

        for c in comments:
            if c["id"] in replied:
                continue

            reply = generate_reply(c["text"])

            print("\nCOMMENT:", c["text"])
            print("REPLY:", reply)

            results.append({
                "video": video,
                "author": c["author"],
                "comment": c["text"],
                "reply": reply
            })

            replied.append(c["id"])

    save_replied(replied)

    pd.DataFrame(results).to_csv("replies.csv", index=False)
    print("\nSaved to replies.csv")

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    run()
