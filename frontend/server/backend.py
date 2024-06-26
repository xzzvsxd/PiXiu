import json
import re
import sys

import requests
from flask import request, Response, stream_with_context
from requests import get

from frontend.server.config import special_instructions

sys.path.insert(0, '../g4f')
from frontend.g4f import ChatCompletion
from frontend.g4f.Provider import __providers__


def find_provider(name):
    new_variable = None
    for provider in __providers__:
        if provider.__name__ == name and provider.working:
            new_variable = provider
            break
        #else:
        #    print("name " + provider.__name__)
    return new_variable


class Backend_Api:
    def __init__(self, bp, config: dict) -> None:
        """
        Initialize the Backend_Api class.
        :param app: Flask application instance
        :param config: Configuration dictionary
        """
        self.bp = bp
        self.routes = {
            '/backend-api/v2/conversation': {
                'function': self._conversation,
                'methods': ['POST']
            }
        }

    def _conversation(self):
        """  
        Handles the conversation route.  

        :return: Response object containing the generated conversation stream  
        """
        if request.headers.get('content-type').startswith('application/json'):
            conversation_json = request.json
            conversation_id = conversation_json['conversation_id']
            model = conversation_json['model']
        else:
        # elif request.headers.get('content-type').startswith('multipart/form-data'):
            conversation_json = request.form
            model = conversation_json.get('model')

        try:
            if model == "Pixiu":
                """
                Handles the conversation route to generate new conversation responses in a streaming fashion.

                :return: Response object containing the generated conversation stream
                """

                if request.headers.get('content-type', '').startswith('multipart/form-data'):
                    conversation_json = request.form
                    conversation_id = conversation_json.get('conversation_id')
                    meta = json.loads(conversation_json.get('meta'))
                    prompt = meta['content']['message']

                    # 准备要发送到 generate_async 服务的数据
                    data = {
                        'conversation_id': conversation_id,
                        'prompt': prompt,
                    }

                    if 'file' in request.files:
                        uploaded_file = request.files['file']
                        # print(f"Received file: {uploaded_file.filename}")

                        # 使用 Multipart-Encoded 请求发送数据和文件
                        request_kwargs = {
                            'data': data,
                            'files': {
                                'file': (uploaded_file.filename, uploaded_file.stream, uploaded_file.content_type)}
                        }
                    else:
                        # 没有文件，仅发送数据
                        request_kwargs = {
                            'data': data,
                        }
                else:
                    # 处理不带文件的情况
                    conversation_id = request.json['conversation_id']
                    prompt = request.json['meta']['content']['message']

                    # 准备要发送到 generate_async 服务的数据
                    data = {
                        "conversation_id": conversation_id,
                        "prompt": prompt
                    }
                    request_kwargs = {
                        'data': data
                    }

                def generate():
                    with requests.post('http://localhost:8000/generate_async', stream=True, **request_kwargs) as r:
                        if r.status_code == 200:
                            # 每接收到一块数据，就 yield 出去，实现流式传输
                            for chunk in r.iter_content(chunk_size=None):  # chunk_size=None 表示服务器决定分块的大小
                                if chunk:  # 过滤掉保持连接的空白 chunk
                                    yield chunk
                        else:
                            yield f"Error: {r.status_code}"

                return Response(stream_with_context(generate()), mimetype='text/event-stream')

            else:
                jailbreak = conversation_json['jailbreak']
                messages = build_messages(jailbreak)
                # noinspection PyTestUnpassedFixture
                provider = conversation_json.get('provider', '').replace('g4f.Provider.', '')
                print("provider " + provider)
                provider = provider if provider and provider != "Auto" else None
                provider_class = find_provider(provider)

                response = ChatCompletion.create(
                    model=model,
                    provider=provider_class,
                    chatId=conversation_id,
                    messages=messages,
                    stream=True,
                    proxy='http://127.0.0.1:7890'
                )

                return Response(stream_with_context(generate_stream(response, jailbreak)), mimetype='text/event-stream')

        except Exception as e:
            print(e)
            print(e.__traceback__.tb_next)

            return {
                '_action': '_ask',
                'success': False,
                "error": f"an error occurred {str(e)}"
            }, 400


def build_messages(jailbreak):
    """  
    Build the messages for the conversation.  

    :param jailbreak: Jailbreak instruction string  
    :return: List of messages for the conversation  
    """
    print(request.json['meta'])
    _conversation = request.json['meta']['content']['conversation']
    prompt = request.json['meta']['content']['parts'][0]

    # Add the existing conversation
    conversation = _conversation
    # print(f"prompt is {prompt}, conversation is {conversation}")

    # Add jailbreak instructions if enabled
    if jailbreak_instructions := getJailbreak(jailbreak):
        conversation.extend(jailbreak_instructions)

    # Add the prompt
    conversation.append(prompt)

    # Reduce conversation size to avoid API Token quantity error
    if len(conversation) > 3:
        conversation = conversation[-4:]

    # print(conversation)

    return conversation


def fetch_search_results(query):
    """  
    Fetch search results for a given query.  

    :param query: Search query string  
    :return: List of search results  
    """
    search = get('https://ddg-api.herokuapp.com/search',
                 params={
                     'query': query,
                     'limit': 3,
                 })

    snippets = ""
    for index, result in enumerate(search.json()):
        snippet = f'[{index + 1}] "{result["snippet"]}" URL:{result["link"]}.'
        snippets += snippet

    response = "Here are some updated web searches. Use this to improve user response:"
    response += snippets

    return [{'role': 'system', 'content': response}]


def generate_stream(response, jailbreak):
    """
    Generate the conversation stream.

    :param response: Response object from ChatCompletion.create
    :param jailbreak: Jailbreak instruction string
    :return: Generator object yielding messages in the conversation
    """
    if getJailbreak(jailbreak):
        response_jailbreak = ''
        jailbroken_checked = False
        for message in response:
            response_jailbreak += message
            if jailbroken_checked:
                yield message
            else:
                if response_jailbroken_success(response_jailbreak):
                    jailbroken_checked = True
                if response_jailbroken_failed(response_jailbreak):
                    yield response_jailbreak
                    jailbroken_checked = True
    else:
        yield from response


def response_jailbroken_success(response: str) -> bool:
    """Check if the response has been jailbroken.

    :param response: Response string
    :return: Boolean indicating if the response has been jailbroken
    """
    act_match = re.search(r'ACT:', response, flags=re.DOTALL)
    return bool(act_match)


def response_jailbroken_failed(response):
    """
    Check if the response has not been jailbroken.

    :param response: Response string
    :return: Boolean indicating if the response has not been jailbroken
    """
    return False if len(response) < 4 else not (response.startswith("GPT:") or response.startswith("ACT:"))


def getJailbreak(jailbreak):
    """  
    Check if jailbreak instructions are provided.  

    :param jailbreak: Jailbreak instruction string  
    :return: Jailbreak instructions if provided, otherwise None  
    """
    if jailbreak != "default":
        special_instructions[jailbreak][0]['content'] += special_instructions['two_responses_instruction']
        if jailbreak in special_instructions:
            special_instructions[jailbreak]
            return special_instructions[jailbreak]
        else:
            return None
    else:
        return None
