import concurrent
from queue import Queue

from chatglm_ptuning import ChatGLM_Ptuning, PtuningType
from company_table import count_table_keys, build_table, append_key_counts, build_table_from_txt
from file import download_data_online, update_pdf_info, load_total_tables
from financial_state import *
from generate_answer_with_classify import do_classification_single, do_gen_keywords_single, do_sql_generation_single, \
    generate_answer_single

import json
import os
from threading import Lock, Thread


if __name__ == '__main__':
    pdf_url = r"E:\chatglm_llm_fintech_raw_dataset\allpdf\\"

    ### 第一次需要解开注释运行 ###
    '''
        # 第一次要生成一下pdf_info
        download_data_online(pdf_url)
        # 遍历 pdf_url 文件夹, 释放tables
        pdf_path = os.path.join(cfg.DATA_PATH, 'pdf_docs')
        if not os.path.exists(pdf_path):
            os.mkdir(pdf_path)
    
        ### 方法一：一个个循环，太慢了 ###
        # for filename in os.listdir(pdf_url):
        #     if filename.lower().endswith('.pdf'):  # 确保是 PDF 文件
        #         pdf_key = filename
        #         pdf_file_path = os.path.join(pdf_url, pdf_key)  # 完整的文件路径
        #         extract_pdf_tables(pdf_file_path, pdf_key)  # 调用函数处理 PDF
    
    
        # Use ProcessPoolExecutor to process files in parallel
        url = os.listdir(pdf_url)
        with concurrent.futures.ProcessPoolExecutor() as executor:
            # Submit tasks to the executor
            futures = [executor.submit(process_pdf_file, pdf_url, filename) for filename in url]
    
            # Wait for all the futures to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Get the result of the future
                except Exception as e:
                    print(f"A process caused an exception: {e}")
                    
        # 使用队列来存储每个线程处理的结果
        results_queue = Queue()
        merge_all_info(results_queue)
        
        all_tables = load_total_tables()
        key_count = count_table_keys(pdf_info, all_tables)
        build_table(pdf_info, all_tables, key_count=key_count)
    '''

    # 加载所有的pdf info
    pdf_info = load_pdf_info()
    # pdf_keys = list(pdf_info.keys())
    # print(pdf_keys)


    # # 新的文件上传进来
    # pdf_key = '2023-03-06__梅花生物科技集团股份有限公司__600873__梅花生物__2022年__年度报告.pdf'
    # new_pdf_url = r'E:\XuanYuan\pdf_info\\'
    # # 生成pdf info new
    # pdf_path = os.path.join(new_pdf_url, pdf_key)
    # split = pdf_key.split('__')
    # pdf_info_new = {
    #     'key': pdf_key,
    #     'pdf_path': pdf_path,
    #     'company': split[1],
    #     'code': split[2],
    #     'abbr': split[3],
    #     'year': split[4]
    # }
    # pdf_info = update_pdf_info(pdf_info, pdf_key, pdf_info_new)
    #
    # # 解析新文件的各个字段info(basic_info、employee_info、cbs_info、cscf_info、cis_info、dev_info)
    # extract_pdf_tables(pdf_path, pdf_key)
    #
    # # 生成添加进去的CompanyTable.csv
    # build_table_from_txt(pdf_info_new, pdf_key)



    # 提出问题
    # question = "在北京注册的上市公司中，2019年资产总额最高的前四家上市公司是哪些家？金额为？"
    question = "我想知道2022年梅花生物科技集团股份有限公司营业外支出是多少元？"
    qusetion_json = {"id": question, "question": question}

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
    model = ChatGLM_Ptuning(PtuningType.Nothing)
    answer = generate_answer_single(model, qusetion_json, pdf_info, question_type, keywords, sql_generation)['answer']