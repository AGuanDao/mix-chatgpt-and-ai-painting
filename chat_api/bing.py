import asyncio
from typing import Generator
from requests.exceptions import SSLError, ProxyError, RequestException
from urllib3.exceptions import MaxRetryError
from httpx import HTTPStatusError, ConnectTimeout, ConnectError

from EdgeGPT import Chatbot as EdgeChatbot, ConversationStyle, NotAllowedToAccess

import re
import config
from utils import *

class BingAdapter:
    cookieData = None
    count: int = 0
    # reconnect_try_count: int = 0

    conversation_style: ConversationStyle = None

    bot: EdgeChatbot

    preset_context: str = ""
    """实例"""

    def __init__(self, session_id: str = "unknown", conversation_style: ConversationStyle = ConversationStyle.creative):
        self.session_id = session_id
        self.conversation_style = conversation_style
        self.cookieData = []
        for line in config.bing_cookie.split("; "):
            name, value = line.split("=", 1)
            self.cookieData.append({"name": name, "value": value})
        self.init_bot()

    def init_bot(self):
        self.count = 0
        while True:
            try:
                if config.need_loc_proxy:
                    self.bot = EdgeChatbot(cookies=self.cookieData, proxy= "http://" + config.loc_proxy)
                else:
                    self.bot = EdgeChatbot(cookies=self.cookieData)
                break;
            # except ConnectError as e:
            #     continue
            except Exception as e:
                raise e

    async def rollback(self):
        raise "BotOperationNotSupportedException"

    async def on_reset(self):
        self.count = 0
        await self.bot.reset()
        await self.preset_ask(self.preset_context)

    async def ask(self, prompt: str) -> Generator[str, None, None]:
        self.count = self.count + 1
        parsed_content = ''
        try:
            async for final, response in self.bot.ask_stream(prompt=prompt,
                                                             conversation_style=self.conversation_style,
                                                             wss_link=config.bing_wss_link):
                if not final:
                    response = re.sub(r"\[\^\d+\^\]", "", response)
                    if config.bing_show_references:
                        response = re.sub(r"\[(\d+)\]: ", r"\1: ", response)
                    else:
                        response = re.sub(r"(\[\d+\]\: .+)+\n", "", response)
                        response = re.sub(r"\[\d+\]", "", response)
                    parsed_content = response

                else:
                    try:
                        max_messages = response["item"]["throttling"]["maxNumUserMessagesInConversation"]
                    except:
                        max_messages = config.context_length
                    remaining_conversations = f'\n本次回复数：{self.count} / {max_messages} '
                    if len(response["item"].get('messages', [])) > 1 and config.bing_show_suggestions:
                        suggestions = response["item"]["messages"][-1].get("suggestedResponses", [])
                        if len(suggestions) > 0:
                            parsed_content = parsed_content + '\n猜你想问：  \n'
                            for suggestion in suggestions:
                                parsed_content = parsed_content + f"* {suggestion.get('text')}  \n"
                        yield parsed_content
                    parsed_content = parsed_content + remaining_conversations
                    # not final的parsed_content已经yield走了，只能在末尾加剩余回复数，或者改用EdgeGPT自己封装的ask之后再正则替换
                    if parsed_content == remaining_conversations:  # No content
                        # 执行 asyncio.run() 时，当前函数会被阻塞，直到协程运行完毕
                        self.init_bot()
                        await self.preset_ask(self.preset_context)
                        yield "Bing 已结束本次会话。将重新开启一个新会话。"
                        return

                yield parsed_content
            # print("[Bing AI 响应] " + parsed_content)
            # self.reconnect_try_count = 0 # 成功连接到服务器，重置重连次数
        except NotAllowedToAccess as e:
            yield "Bing 服务需要重新认证。"
            await self.on_reset()
            return 
        # except ConnectError as e: # 说明第三方库在reset的时候发生了异常，需要重新创建实例
        #     self.init_bot()
        #     if self.reconnect_try_count < 5:
        #         self.reconnect_try_count += 1
        #         async for res in self.ask(prompt):
        #             yield res
        #     else:
        #         raise e
        #     return
        # except (RequestException, SSLError, ProxyError, MaxRetryError, HTTPStatusError, ConnectTimeout, ConnectError) as e:  # 网络异常
        #     if self.reconnect_try_count < 5:
        #         self.reconnect_try_count += 1
        #         async for res in self.ask(prompt):
        #             yield res
        #     else:
        #         raise e
        #     return
        except Exception as e:
            self.init_bot()
            await self.preset_ask(self.preset_context)
            yield "Bing 已结束本次会话。将重新开启一个新会话。"
            return
    async def preset_ask(self, text: str):
        assert(self.count==0)
        self.preset_context = text
        if self.preset_context == "":
            return
        async for res in self.ask(text):
            pass
        print (f"preset result:\n{res}")
        return