import time
from bot import generate_reply
from db import insert_reply

def run_worker():

    while True:

        print("Checking new comments...")

        # here you would:
        # - fetch all connected users
        # - fetch their YouTube comments
        # - generate replies
        # - store in DB

        time.sleep(60)
