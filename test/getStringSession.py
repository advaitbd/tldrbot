from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 2954792
API_HASH = "c3efacabe4b91251c8d50e8e98c9a573"

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print(client.session.save())
