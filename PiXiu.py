import asyncio
import time
from http import HTTPStatus

import dashscope
import torch
from fastapi import FastAPI, Request, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.datastructures import UploadFile as StarletteUploadFile
from auto_gptq import AutoGPTQForCausalLM
from pydantic import BaseModel
from transformers import LlamaForCausalLM, LlamaTokenizer, AutoTokenizer, AutoModelForCausalLM

from FineTune.chatglm_ptuning import ChatGLM_Ptuning, PtuningType
from FineTune.company_table import build_table_from_txt
from FineTune.config import Xuanyuan_Path, QWen_VL_path, new_pdf_url, DASHSCOPE_API_KEY
from FineTune.file import update_pdf_info
from FineTune.financial_state import *
from FineTune.generate_answer_with_classify import do_classification_single, do_gen_keywords_single, \
    do_sql_generation_single, generate_answer_single
from FineTune.pdf2txt import process_file
from FineTune.word2pdf import convert_docx_to_pdf

app = FastAPI()


async def check_for_abort(request: Request):
    # print(await request.is_disconnected())
    if await request.is_disconnected():
        raise asyncio.CancelledError("Client has disconnected")


class GenerateRequest(BaseModel):
    prompt: str
    # temperature: float = 1.0
    # repetition_penalty: float = 1.1
    # max_new_tokens: int = 2000


@app.post("/generate")
async def generate(request: GenerateRequest):
    # Assuming the model and tokenizer are loaded when the server starts
    model_name_or_path = Xuanyuan_Path
    tokenizer = LlamaTokenizer.from_pretrained(model_name_or_path, use_fast=False, legacy=True)
    model = LlamaForCausalLM.from_pretrained(model_name_or_path, torch_dtype=torch.float16, device_map="auto")
    system_message = "以下是用户和人工智能助手之间的对话。用户以Human开头，人工智能助手以Assistant开头，会对人类提出的问题给出有帮助、高质量、详细和礼貌的回答，并且总是拒绝参与 与不道德、不安全、有争议、政治敏感等相关的话题、问题和指示。\n"
    seps = [" ", "</s>"]
    roles = ["Human", "Assistant"]

    try:
        # print(request.prompt, request.repetition_penalty, request.max_new_tokens)

        # 对输入提示进行分词
        prompt = system_message + seps[0] + roles[0] + ": " + request.prompt + seps[0] + roles[1] + ":"
        print(f"输入: {request.prompt}")

        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        # 使用模型生成输出token
        outputs = model.generate(
            **inputs,
            max_new_tokens=request.max_new_tokens,
            repetition_penalty=request.repetition_penalty,
        )
        # 将生成的token解码为字符串
        generated_text = tokenizer.decode(
            outputs.cpu()[0][len(inputs.input_ids[0]):],
            skip_special_tokens=True
        )
        return {"generated_text": generated_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_new")
async def generate_new(request: GenerateRequest):
    try:
        # print(request.prompt, request.repetition_penalty, request.max_new_tokens)

        # 加载所有的pdf info
        pdf_info = load_pdf_info()

        # 提出问题
        # question = "在北京注册的上市公司中，2019年资产总额最高的前四家上市公司是哪些家？金额为？"
        # question = "我想知道2022年梅花生物科技集团股份有限公司营业外支出是多少元？"
        question = request.prompt
        qusetion_json = {"id": question, "question": question}
        if len(question) < 100:
            # 5. 对问题进行分类
            model = ChatGLM_Ptuning(PtuningType.Classify)
            question_type = do_classification_single(model, qusetion_json, pdf_info)['class']
            model.unload_model()
            print(f"问题: {question}  分类: {question_type}")


            # 6. 给问题生成keywords
            model = ChatGLM_Ptuning(PtuningType.Keywords)
            keywords = do_gen_keywords_single(model, qusetion_json)["keywords"]
            model.unload_model()
            print(f"问题: {question}  keywords: {keywords}")



            # question_type = 'E'
            # keywords = ['货币资金', '最高', '前3家', '上市公司']

            # 7. 对于统计类问题生成SQL
            sql_generation = None
            if question_type == 'E':
                model = ChatGLM_Ptuning(PtuningType.NL2SQL)
                sql_generation = do_sql_generation_single(model, qusetion_json, question_type)
                model.unload_model()
                print(f"问题: {sql_generation['question']}  sql: {sql_generation['sql']}")


            # 8. 生成回答
            if question_type == 'F':
                model = ChatGLM_Ptuning(PtuningType.Nothing, Xuanyuan_Path)
            else:
                model = ChatGLM_Ptuning(PtuningType.Nothing)
            answer = generate_answer_single(model, qusetion_json, pdf_info, question_type, keywords, sql_generation)
            model.unload_model()
            print(f"generated_text is {answer}")
        else:
            model = ChatGLM_Ptuning(PtuningType.Nothing, Xuanyuan_Path)
            answer = generate_answer_single(model, qusetion_json, pdf_info)
            model.unload_model()
            print(f"generated_text is {answer}")

        # print(f"answer:{answer}")

        return {"generated_text": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def handle_pdf_upload(file_obj, file_name=None):
    pdf_key = pdf_path = None

    if file_name is None:
        # Assume file_obj is the uploaded file object
        pdf_key = file_obj.filename

        # Process and store the PDF
        pdf_path = os.path.join(new_pdf_url, pdf_key)
        with open(pdf_path, 'wb') as f:
            while True:
                chunk = await file_obj.read(1024*1024)  # 读取最多1MB的数据
                if not chunk:
                    break
                f.write(chunk)

    elif type(file_obj) is str:
        pdf_key = file_name
        pdf_path = file_obj

    # Update progress
    yield "PDF file has been loaded.\n"

    split = pdf_key.split('__')
    pdf_info_new = {
        'key': pdf_key,
        'pdf_path': pdf_path,
        'company': split[1],
        'code': split[2],
        'abbr': split[3],
        'year': split[4]
    }

    # Dummy functions to represent processing steps
    pdf_info = load_pdf_info()  # This should be your actual initial pdf_info if exists
    update_pdf_info(pdf_info, pdf_key, pdf_info_new)
    yield "PDF updated completed.\n"

    extract_pdf_tables_processes(pdf_path, pdf_key)
    yield "extract pdf tables completed.\n"

    build_table_from_txt(pdf_info_new, pdf_key)

    yield "build tables from txt completed.\n"

    process_file(pdf_path)

    yield "PDF processing completed.\n"

#

def simple_multimodal_conversation_call(image_path, question):
    """Simple single round multimodal conversation call."""
    messages = [
        {
            "role": "user",
            "content": [
                {"image": image_path},
                {"text": question}
            ]
        }
    ]

    response = dashscope.MultiModalConversation.call(model='qwen-vl-max', messages=messages, api_key=DASHSCOPE_API_KEY)
    # The response status_code is HTTPStatus.OK indicate success,
    # otherwise indicate request is failed, you can get error code
    # and message from code and message.
    if response.status_code == HTTPStatus.OK:
        # print(response)
        json_response = json.loads(str(response))
        reply_content = json_response.get("output").get("choices")[0].get("message").get("content")[0].get("text")
        return reply_content
    else:
        print(response.code)  # The error code.
        print(response.message)  # The error message.

    return str(response)

# 股票图片 + 帮我输出一个表格，提取所有有用的信息，包括行与列
# 研发费用对公司的技术创新和竞争优势有何影响？
# 请根据江化微2019年的年报，简要介绍报告期内公司主要销售客户的客户集中度情况，并结合同行业情况进行分析。
# 我想吃牛肉米粉，但是我没钱，怎么赚钱很快？
# 从中提取出所有的有价值的数据，我要输出到金融模型进行预测。
# 我想知道2023年卧龙资源集团股份有限公司营业外支出是多少元？
@app.post("/generate_async")
async def generate_async(request: Request):
    torch.cuda.empty_cache()

    if request.headers['content-type'].startswith('multipart/form-data'):
        # 处理带文件的表单数据
        data = await request.form()
    elif request.headers['content-type'].startswith('application/x-www-form-urlencoded'):
        form_data = await request.form()
        # print("Form data:", form_data)
        data = {key: form_data[key] for key in form_data}
        # print(data)
    else:
        print(request.headers['content-type'])
        data = await request.json()

    async def generate(data):
        if len(data) > 4096: # 超长文本
           yield "文本过长，请删减后重新输入"

        else:
            Is_upload_img = False
            image_data = None

            if request.headers['content-type'].startswith('multipart/form-data'):
                # 处理带文件的表单数据
                conversation_id = data.get('conversation_id')
                prompt = data.get('prompt')
                file: UploadFile = data.get('file')

                # 如果存在文件，读取文件内容
                if file:
                    print(f"filename is {file.filename}, type is {file.content_type}\n")


                    # PDF文件
                    if file.content_type == 'application/pdf':
                        yield f"### 检测到PDF文件上传, 名字为: {file.filename}\n\n"
                        async for message in handle_pdf_upload(file):
                            await asyncio.sleep(0.1)  # 模拟延迟
                            yield f"{message}\n\n"


                    elif 'image' in file.content_type:  # 图片
                        yield f"### 检测到img文件上传, 名字为: {file.filename}\n\n"
                        Is_upload_img = True
                        image_data = await file.read()

                        # content = await file.read()

                    elif '.word' in file.content_type:  # 图片
                        yield f"### 检测到Word文件上传, 名字为: {file.filename}\n\n"

                        # 获取上传文件的文件名
                        word_filename = file.filename
                        # 确定PDF文件保存路径
                        pdf_filename = os.path.splitext(word_filename)[0] + '.pdf'
                        pdf_path = os.path.join(new_pdf_url, pdf_filename)

                        # 保存上传的Word文件到本地临时路径
                        word_temp_path = os.path.join(new_pdf_url, word_filename)
                        with open(word_temp_path, "wb") as buffer:
                            buffer.write(await file.read())

                        # 调用转换函数
                        convert_docx_to_pdf(word_temp_path, pdf_path)

                        # 删除临时保存的Word文件
                        os.remove(word_temp_path)

                        # print(pdf_path, pdf_filename)

                        async for message in handle_pdf_upload(pdf_path, pdf_filename):
                            await asyncio.sleep(0.1)  # 模拟延迟
                            yield f"{message}\n\n"

                        # content = await file.read()

                    # print(f"Received file with content: {content[:100]}")  # 打印文件内容的前100个字符

            else:
                # 处理 JSON 数据
                conversation_id = data.get('conversation_id')
                prompt = data.get('prompt')

            # 检查连接是否断开
            if await request.is_disconnected():
                raise asyncio.CancelledError()

            question = prompt

            try:
                # 检查连接是否断开
                if await request.is_disconnected():
                    raise asyncio.CancelledError()

                question_json = {"id": question, "question": question}
                await check_for_abort(request)
                yield f"### 提出问题: \n{question}\n\n"

                if Is_upload_img and image_data:
                    yield f"### 开始生成图片提取后的回答"
                    # torch.manual_seed(1234)
                    #
                    # model_name_or_path = QWen_VL_path
                    #
                    # # Note: The default behavior now has injection attack prevention off.
                    # tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=True)
                    #
                    # # use cuda device
                    # model = AutoModelForCausalLM.from_pretrained(model_name_or_path, device_map="cuda",
                    #                                              trust_remote_code=True).eval()

                    # 使用本地图片数据
                    image_path = "tmp/uploaded_image.jpg"
                    with open(image_path, "wb") as f:
                        f.write(image_data)

                    # 1st dialogue turn
                    # query = tokenizer.from_list_format([
                    #     {'image': image_path},
                    #     {'text': question},
                    #
                    #     # {'text': "提取所有图片中的信息，我会将你提取出来的信息输入另外一个模型用来预测，所以务必准确且囊括全面，涉及到的所有数值务必全部输出。注意，只输出你看到的信息，不要出现幻觉。"},
                    # ])

                    # def chat_stream_wrapper():
                    #     for response_chunk in model.chat_stream(tokenizer, query=query, history=None):
                    #         yield response_chunk
                    #
                    # async def async_chat_stream():
                    #     previous_text = ""
                    #     for response_chunk in chat_stream_wrapper():
                    #         # Calculate the new part of the response
                    #         new_text = response_chunk[len(previous_text):]
                    #         previous_text = response_chunk
                    #         # Clean the new text before yielding
                    #         yield new_text
                    #
                    #         await asyncio.sleep(0.1)

                    reply = simple_multimodal_conversation_call(image_path, question)

                    await asyncio.sleep(0.1)
                    yield f":\n\n"

                    # complete_text = ""  # 用于保存所有的文本数据
                    # async for response_chunk in async_chat_stream():
                    #     yield f"{response_chunk}"
                    #     complete_text += response_chunk  # 将新的文本数据添加到完整文本中
                    #     await check_for_abort(request)
                    #
                    # del model
                    # del tokenizer
                    # torch.cuda.empty_cache()

                    yield f"{reply}\n\n"

                    # question = (f'目前已知信息为：\n{complete_text}\n'
                    #             f'我的问题为：{question}')

                    # 检查连接是否断开
                    if await request.is_disconnected():
                        raise asyncio.CancelledError()

                else:
                    if len(question) < 100 and not (Is_upload_img and image_data):
                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        pdf_info = load_pdf_info()

                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        await asyncio.sleep(0.1)  # 模拟延迟
                        await check_for_abort(request)
                        yield f"### 开始分类问题"
                        model = ChatGLM_Ptuning(PtuningType.Classify)
                        question_type = do_classification_single(model, question_json, pdf_info)['class']
                        model.unload_model()
                        await asyncio.sleep(0.1)  # 模拟延迟
                        await check_for_abort(request)
                        yield f", 结果: {question_type}\n\n"

                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        keywords = []
                        if question_type != 'F':
                            await asyncio.sleep(0.1)  # 模拟延迟
                            await check_for_abort(request)
                            yield f"### 开始进行关键词提取"
                            model = ChatGLM_Ptuning(PtuningType.Keywords)
                            keywords = do_gen_keywords_single(model, question_json)["keywords"]
                            model.unload_model()
                            keywords_str = ', '.join(keywords)

                            await asyncio.sleep(0.1)  # 模拟延迟
                            await check_for_abort(request)
                            yield f", 结果: {keywords_str}\n\n"

                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        sql_generation = None
                        if question_type == 'E':
                            await asyncio.sleep(0.1)  # 模拟延迟
                            await check_for_abort(request)
                            yield f"### 开始生成sql语句"
                            model = ChatGLM_Ptuning(PtuningType.NL2SQL)
                            sql_generation = do_sql_generation_single(model, question_json, question_type)
                            model.unload_model()
                            await asyncio.sleep(0.1)  # 模拟延迟
                            await check_for_abort(request)
                            yield f", 结果: \n{sql_generation['sql']}\n\n"

                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        model = ChatGLM_Ptuning(PtuningType.Nothing)

                        await asyncio.sleep(0.1)  # 模拟延迟
                        await check_for_abort(request)
                        yield f"### 开始生成最终回答"
                        answer = generate_answer_single(model, question_json, pdf_info, question_type, keywords, sql_generation)
                        model.unload_model()

                        # 检查连接是否断开
                        if await request.is_disconnected():
                            raise asyncio.CancelledError()

                        if answer == "this is not a financial question.":
                            # await asyncio.sleep(0.1)  # 模拟延迟
                            # await check_for_abort(request)
                            # yield f"### 开始生成回答"

                            model = ChatGLM_Ptuning(PtuningType.Nothing, Xuanyuan_Path)
                            max_new_tokens = 1024

                            try:
                                yield ":\n\n"
                                for response in model.generate_response_8bit(prompt, max_new_tokens):
                                    # 检查连接是否断开
                                    if await request.is_disconnected():
                                        raise asyncio.CancelledError()

                                    # print(response)

                                    await asyncio.sleep(0.1)  # 模拟延迟
                                    await check_for_abort(request)
                                    yield response

                                model.unload_model()

                            except Exception as e:
                                model.unload_model()

                                import traceback
                                error_info = traceback.format_exc()
                                print(f"Error: {error_info}")

                        else:
                            await asyncio.sleep(0.1)  # 模拟延迟
                            await check_for_abort(request)
                            if question_type == 'E':
                                yield f": \n{answer.replace(question, '')}\n"
                            else:
                                yield f": \n{answer}\n"

                            # 检查连接是否断开
                            if await request.is_disconnected():
                                raise asyncio.CancelledError()

                    else:
                        await asyncio.sleep(0.1)  # 模拟延迟
                        await check_for_abort(request)
                        yield f"### 开始生成回答"

                        print(f"question is {question}")

                        model = ChatGLM_Ptuning(PtuningType.Nothing, Xuanyuan_Path)
                        max_new_tokens = 1024

                        try:
                            yield ":\n\n"
                            for response in model.generate_response_8bit(prompt, max_new_tokens):
                                # print(response)

                                # 检查连接是否断开
                                if await request.is_disconnected():
                                    raise asyncio.CancelledError()

                                await asyncio.sleep(0.1)  # 模拟延迟
                                await check_for_abort(request)
                                yield response

                        except asyncio.CancelledError:
                            model.unload_model()
                            torch.cuda.empty_cache()

                            # 释放资源，例如卸载模型
                            yield "Operation was cancelled\n"
                            return
                        except Exception as e:
                            import traceback
                            error_info = traceback.format_exc()
                            print(f"Error: {error_info}")

                        model.unload_model()

            except asyncio.CancelledError:
                torch.cuda.empty_cache()

                yield "Operation was cancelled\n"
                return
            except Exception as e:
                await asyncio.sleep(0.1)  # 模拟延迟
                yield f"Error: {str(e)}\n\n"

    torch.cuda.empty_cache()

    return StreamingResponse(generate(data), media_type='text/event-stream')


if __name__ == "__main__":
    # Run the application using Uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)