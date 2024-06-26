import copy
import json
import os
import re
import sqlite3
from collections import Counter

import numpy as np
import pandas as pd

from . import config as cfg
from .file import load_pdf_info, load_tables_of_years


def count_table_keys(pdf_info, all_tables):
    all_keys = []

    for pdf_key, pdf_item in list(pdf_info.items()):
        # print(pdf_key)
        company = pdf_item['company']
        year = pdf_item['year'].replace('年', '')
        table = load_tables_of_years(company, [year], all_tables, pdf_info)

        row_names = list(set([t[2] for t in table]))

        all_keys.extend(row_names)
    all_keys = Counter(all_keys)
    with open(os.path.join(cfg.DATA_PATH, 'key_count.json'), 'w', encoding='utf-8') as f:
        json.dump(all_keys, f, ensure_ascii=False, indent=4)

    return all_keys

def append_key_counts(pdf_info, all_tables):
    """
    This function takes a single pdf_info and all_tables, counts the keys, and appends the counts to key_count.json.
    Args:
        pdf_info (dict): Information about the single PDF.
        all_tables (dict): All tables with data from different information categories.
    """
    # Extract company and year from pdf_info
    company = pdf_info['company']
    year = pdf_info['year'].replace('年', '')

    # Assuming `load_tables_of_years` is a function that you have defined elsewhere
    table = load_tables_of_years(company, [year], all_tables, pdf_info)

    # Extract row names and count them
    row_names = list(set([t[2] for t in table]))
    new_keys = Counter(row_names)

    # Path to key_count.json file
    key_count_path = os.path.join(cfg.DATA_PATH, 'key_count.json')

    # Load existing counts from key_count.json and update with new counts
    if os.path.exists(key_count_path):
        with open(key_count_path, 'r', encoding='utf-8') as f:
            existing_counts = json.load(f)
        existing_counts = Counter(existing_counts)
        existing_counts.update(new_keys)
    else:
        existing_counts = new_keys

    # Write updated counts back to key_count.json
    with open(key_count_path, 'w', encoding='utf-8') as f:
        json.dump(existing_counts, f, ensure_ascii=False, indent=4)

    return existing_counts


def load_key_from_txt(pdf_info, pdf_key, key, txt_path):
    data = []
    key_data = {}
    pdf_info_new = copy.deepcopy(pdf_info)  # 使用deepcopy来创建pdf_info的一个完全独立的副本

    with open(txt_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            data.append(line.strip() + "\n")

    pdf_info_new[key] = data
    # print(pdf_info_new)

    key_data[pdf_key] = pdf_info_new
    # print(key_data)

    return key_data


def build_table_from_txt(pdf_info, pdf_key):
    # Assuming the keys match the filenames without extension
    key_and_filenames = [
        'basic_info',
        'employee_info',
        'cbs_info',
        'cscf_info',
        'cis_info',
        'dev_info',
    ]

    all_tables = {}
    for key in key_and_filenames:
        txt_path = os.path.join(cfg.DATA_PATH, cfg.PDF_TEXT_DIR, pdf_key.replace(".pdf", ""), f'{key}.txt')
        all_tables[key] = load_key_from_txt(pdf_info, pdf_key, key, txt_path)

    # print(all_tables)
    # return

    used_keys = cfg.COMPANY_TABLE_COLUMES
    columns = ['公司全称', '年份'] + used_keys

    df_dict = {}
    for col in columns:
        df_dict[col] = []

    company = pdf_info['company']
    year = pdf_info['year'].replace('年', '')
    df_dict['公司全称'].append(company)
    df_dict['年份'].append(year)


    table = load_tables_of_years(company, [year], all_tables, {pdf_key: pdf_info})
    # print(table)


    for key in used_keys:
        value = 'NULLVALUE'
        for table_name, year, row_name, row_value in table:
            if year != year:
                continue
            if row_name == key:
                value = row_value
                break
        value = value.replace('人', '').replace('元', '').replace(' ', '')
        df_dict[key].append(value)

    # print(df_dict)

    # pd.DataFrame(df_dict).to_csv(os.path.join(cfg.DATA_PATH, 'CompanyTable_gb18030.csv'), sep='\t', index=False, encoding='gb18030')

    # 加载CSV文件
    csv_path = os.path.join(cfg.DATA_PATH, 'CompanyTable.csv')
    df = pd.read_csv(csv_path, sep='\t', encoding='utf-8')

    # 检查并删除存在的公司名称
    if '公司全称' in df_dict:
        # 获取需要检查的公司列表
        company_names = df_dict['公司全称']
        # 确定哪些行需要被删除
        df = df[~df['公司全称'].isin(company_names)]

    # 构建新的DataFrame
    new_df = pd.DataFrame(df_dict)

    # 追加新数据
    updated_df = pd.concat([df, new_df], ignore_index=True)

    # 保存到CSV
    updated_df.to_csv(csv_path, sep='\t', index=False, encoding='utf-8')

def build_table(pdf_info, all_tables, key_count=None, min_ratio=0.1):
    if key_count is None:
        with open(os.path.join(cfg.DATA_PATH, 'key_count.json'), 'r', encoding='utf-8') as f:
            key_count = json.load(f)
    
    max_count = max(key_count.values())
    key_count = sorted(key_count.items(), key=lambda x: x[1], reverse=True)
    used_keys = [key for key, count in key_count if count > min_ratio * max_count]

    columns = ['公司全称', '年份'] + used_keys

    df_dict = {}
    for col in columns:
        df_dict[col] = []
    
    for pdf_key, pdf_item in list(pdf_info.items()):
        # if pdf_key != '2020-04-22__比亚迪股份有限公司__002594__比亚迪__2019年__年度报告.pdf':
        #     continue
        company = pdf_item['company']
        year = pdf_item['year'].replace('年', '')
        table = load_tables_of_years(company, [year], all_tables, pdf_info)
        print(table)
        return
        
        df_dict['公司全称'].append(company)
        df_dict['年份'].append(year)

        for key in used_keys:
            value = 'NULLVALUE'
            for table_name, year, row_name, row_value in table:
                if year != year:
                    continue
                if row_name == key:
                    value = row_value
                    break
            value = value.replace('人', '').replace('元', '').replace(' ', '')
            df_dict[key].append(value)

    pd.DataFrame(df_dict).to_csv(os.path.join(cfg.DATA_PATH, 'CompanyTable.csv'), sep='\t', index=False, encoding='utf-8')


def load_company_table():
    df_path = os.path.join(cfg.DATA_PATH, 'CompanyTable.csv')
    df = pd.read_csv(df_path, sep='\t', encoding='utf-8')

    df['key'] = df.apply(lambda t: t['公司全称'] + str(t['年份']), axis=1)

    pdf_info = load_pdf_info()
    company_keys = [v['company'] + v['year'].replace('年', '').replace(' ', '') for v in pdf_info.values()]
    df = df[df['key'].isin(company_keys)]

    del df['key']

    return df


def col_to_numeric(t):
    try:
        value = float(t)
        if value > 2**63 - 1:
            return np.nan
        elif int(value) == value:
            return int(value)
        else:
            return float(t)
    except:
        return np.nan


def get_sql_search_cursor():
    conn = sqlite3.connect(':memory:')
    # build_table()

    df = load_company_table()
    print(df)

    dtypes = {}
    for col in df.columns:
        num_count = 0
        tot_count = 0
        for v in df[col]:
            if v == 'NULLVALUE':
                continue
            tot_count += 1
            try:
                number = float(v)
            except ValueError:
                continue
            num_count += 1
        if tot_count > 0 and num_count / tot_count > 0.5:
            print('Find numeric column {}, number count {}, total count {}'.format(col, num_count, tot_count))
            df[col] = df[col].apply(lambda t: col_to_numeric(t)).replace([np.inf, -np.inf], np.nan)
            dtypes[col] = 'REAL'
        else:
            dtypes[col] = 'TEXT'
    
    dtypes['年份'] = 'TEXT'

    # print(df['公司注册地址历史变更情况'].dtype)
    # for value in df['公司注册地址历史变更情况'].head(20):
    #     print(value, value == 'nan')
    # print(pd.isna(df['公司注册地址历史变更情况']).head(20))
    # print(df.head(5))

    df.to_sql(name='company_table', con=conn, if_exists='replace', dtype=dtypes)

    cursor = conn.cursor()
    return cursor


def get_search_result(cursor, query):
    result = cursor.execute(query)
    return result



def get_cn_en_key_map(model, keys):
    def get_en_key(cn_key):
        prompt = '''
    你的任务是将中文翻译为英文短语。
    注意：
    1. 你只需要回答英文短语，不要进行解释或者回答其他内容。
    2. 尽可能简短的回答。
    3. 你输出的格式是:XXX对应的英文短语是XXXXX。
    -----------------------
    需要翻译的中文为：{}
    '''.format(cn_key)
        en_key = model(prompt)
        print(en_key)
        en_key = ' '.join(re.findall('[ a-zA-Z]+', en_key)).strip(' ').split(' ')
        en_key = [w[0].upper() + w[1:] for w in en_key if len(w)>1]
        en_key = '_'.join(en_key)
        return en_key
    en_keys = [get_en_key(key) for key in keys]
    key_map = dict(zip(keys, en_keys))
    with open(os.path.join(cfg.DATA_PATH, 'key_map.json'), 'w', encoding='utf-8') as f:
        json.dump(key_map, f, ensure_ascii=False, indent=4)


def load_cn_en_key_map():
    with open(os.path.join(cfg.DATA_PATH, 'key_map.json'), 'r', encoding='utf-8') as f:
        key_map = json.load(f)
    return key_map


def check_company_table():
    df = load_company_table()

    df['key'] = df.apply(lambda t: t['公司全称'] + str(t['年份']), axis=1)

    with open(os.path.join(cfg.DATA_PATH, 'B-pdf-name.txt'), 'r', encoding='utf-8') as f:
        pdf_names = [t.strip() for t in f.readlines()]
    pdf_info = load_pdf_info()
    B_pdf_keys = []
    for pdf_name, pdf_item in pdf_info.items():
        if pdf_name not in pdf_names:
            continue
        B_pdf_keys.append(pdf_item['company'] + pdf_item['year'].replace('年', ''))
    print(B_pdf_keys[:10])
    # df = df[df['key'].isin(B_pdf_keys)]

    cols = ['公司全称', '年份', '其他非流动资产', '利润总额', '负债合计', '营业成本',
        '注册地址', '流动资产合计', '营业收入', '货币资金', '资产总计']

    df.loc[:, cols].to_csv(os.path.join(cfg.DATA_PATH, 'B_CompanyTable.csv'), index=False, sep='\t', encoding='utf-8')