import time
from bot import generate_reply
from db import insert_reply
from announcer import active_notice

def run_worker():

    while True:

        notice = active_notice()
        if notice:
            print("NOTICE:", notice)
        print("Checking new comments...")

        # here you would:
        # - fetch all connected users
        # - fetch their YouTube comments
        # - generate replies
        # - store in DB

        time.sleep(60)
