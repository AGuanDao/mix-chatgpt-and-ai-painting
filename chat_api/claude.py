import asyncio

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from config import CLAUDE_BOT_ID,SLACK_USER_TOKEN


class SlackClient(AsyncWebClient):

    CHANNEL_ID = None
    LAST_TS = None

    async def chat(self, text):
        if not self.CHANNEL_ID:
            raise Exception("Channel not found.")

        resp = await self.chat_postMessage(channel=self.CHANNEL_ID, text=text)
        # print("c: ", resp)
        self.LAST_TS = resp["ts"]

    async def open_channel(self):
        if not self.CHANNEL_ID:
            # print("open successful")
            response = await self.conversations_open(users=CLAUDE_BOT_ID)
            self.CHANNEL_ID = response["channel"]["id"]

    async def get_reply(self):
        for _ in range(150):
            try:
                resp = await self.conversations_history(channel=self.CHANNEL_ID, oldest=self.LAST_TS, limit=2)
                # print("r: ", resp)
                msg = [msg["text"] for msg in resp["messages"] if msg["user"] == CLAUDE_BOT_ID]
                if msg and not msg[-1].endswith("Typing…_"):
                    return msg[-1]
            except (SlackApiError, KeyError) as e:
                # print(f"Get reply error: {e}")
                pass

            await asyncio.sleep(1)

        raise Exception("Get replay timeout")

def create_claude():
    return SlackClient(token=SLACK_USER_TOKEN)
