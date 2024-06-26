import copy
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Tuple

from loguru import logger

from . import config as cfg
from . import prompt_util
from . import question_util
from . import re_util
from . import sql_correct_util
from . import type1
from . import type2
from .chatglm_ptuning import ChatGLM_Ptuning
from .company_table import get_sql_search_cursor, load_company_table
from .file import add_growth_rate_in_table
from .file import load_pdf_info, load_test_questions
from .file import load_tables_of_years
from .file import load_total_tables
from .file import table_to_text, add_text_compare_in_table
from .re_util import recall_pdf_tables, recall_annual_report_texts


def do_classification(model: ChatGLM_Ptuning):
    logger.info('Do classfication...')
    test_questions = load_test_questions()
    
    pdf_info = load_pdf_info()

    classify_dir = os.path.join(cfg.DATA_PATH, 'classify')
    if not os.path.exists(classify_dir):
        os.mkdir(classify_dir)

    for question in test_questions:
        print(question)
        class_csv = os.path.join(classify_dir, '{}.csv'.format(question['id']))

        mactched_comp_names = question_util.get_match_company_names(question['question'], pdf_info)
        
        logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question']))
        result = model.classify(question['question'])

        if re.findall('(状况|简要介绍|简要分析|概述|具体描述|审计意见)', question['question']):
            result = 'F'
        
        if re.findall('(什么是|指什么|什么意思|定义|含义|为什么)', question['question']):
            result = 'F'

        if result in ['A', 'B', 'C', 'D'] and len(mactched_comp_names) == 0:
            logger.info('AAAA{}'.format(question['question']))
            result = 'F'

        if result in ['E'] and len(mactched_comp_names) > 0:
            logger.info('BBBBB{}'.format(question['question']))
            result = 'G'

        logger.info(result.replace('<', ''))

        with open(class_csv, 'w', encoding='utf-8') as f:
            save_result = copy.deepcopy(question)
            save_result['class'] = result

            json.dump(save_result, f, ensure_ascii=False)


def do_classification_single(model: ChatGLM_Ptuning, question: dict, pdf_info: dict):
    logger.info('Do classfication...')

    classify_dir = os.path.join(cfg.DATA_PATH, 'classify')
    if not os.path.exists(classify_dir):
        os.mkdir(classify_dir)

    class_csv = os.path.join(classify_dir, '{}.csv'.format(question['id']))

    mactched_comp_names = question_util.get_match_company_names(question['question'], pdf_info)

    logger.opt(colors=True).info(
        '<blue>Start process question {} {}</>'.format(question['id'], question['question']))
    result = model.classify(question['question'])

    if re.findall('(状况|简要介绍|简要分析|概述|具体描述|审计意见)', question['question']):
        result = 'F'

    if re.findall('(什么是|指什么|什么意思|定义|含义|为什么)', question['question']):
        result = 'F'

    if result in ['A', 'B', 'C', 'D'] and len(mactched_comp_names) == 0:
        logger.info('AAAA{}'.format(question['question']))
        result = 'F'

    if result in ['E'] and len(mactched_comp_names) > 0:
        logger.info('BBBBB{}'.format(question['question']))
        result = 'G'

    # logger.info(result.replace('<', ''))

    save_result = ""
    with open(class_csv, 'w', encoding='utf-8') as f:
        save_result = copy.deepcopy(question)
        save_result['class'] = result

        json.dump(save_result, f, ensure_ascii=False)

    return save_result


def do_gen_keywords(model: ChatGLM_Ptuning):
    logger.info('Do gen keywords...')
    test_questions = load_test_questions()

    # pdf_info = load_pdf_info()

    keywords_dir = os.path.join(cfg.DATA_PATH, 'keywords')
    if not os.path.exists(keywords_dir):
        os.mkdir(keywords_dir)

    for question in test_questions:
        keywords_csv = os.path.join(keywords_dir, '{}.csv'.format(question['id']))

        # mactched_pdf_names = question_util.get_match_pdf_names(question['question'], pdf_info)

        logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question']))
        result = model.keywords(question['question']).split(',')

        logger.info(result)

        with open(keywords_csv, 'w', encoding='utf-8') as f:
            save_result = copy.deepcopy(question)
            if len(result) == 0:
                logger.warning('问题{}的关键词为空'.format(question['question']))
                result = [question['question']]
            save_result['keywords'] = result

            json.dump(save_result, f, ensure_ascii=False)


def do_gen_keywords_single(model: ChatGLM_Ptuning, question: dict):
    logger.info('Do gen keywords...')

    keywords_dir = os.path.join(cfg.DATA_PATH, 'keywords')
    if not os.path.exists(keywords_dir):
        os.mkdir(keywords_dir)

    keywords_csv = os.path.join(keywords_dir, '{}.csv'.format(question['id']))

    logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question']))
    result = model.keywords(question['question']).split(',')

    # logger.info(result)

    save_result = ""
    with open(keywords_csv, 'w', encoding='utf-8') as f:
        save_result = copy.deepcopy(question)
        if len(result) == 0:
            logger.warning('问题{}的关键词为空'.format(question['question']))
            result = [question['question']]
        save_result['keywords'] = result

        json.dump(save_result, f, ensure_ascii=False)

    return save_result


def do_sql_generation(model: ChatGLM_Ptuning):
    logger.info('Do sql generation...')
    test_questions = load_test_questions()

    sql_dir = os.path.join(cfg.DATA_PATH, 'sql')
    if not os.path.exists(sql_dir):
        os.mkdir(sql_dir)

    for question in test_questions:

        sql_csv = os.path.join(sql_dir, '{}.csv'.format(question['id']))

        sql = None
        class_csv = os.path.join(cfg.DATA_PATH, 'classify', '{}.csv'.format(question['id']))
        if os.path.exists(class_csv):
            with open(class_csv, 'r', encoding='utf-8') as f:
                class_result = json.load(f)
                question_type = class_result['class']

            if question_type == 'E':
                logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question'].replace('<', '')))
                sql = model.nl2sql(question['question'])
                logger.info(sql.replace('<>', ''))

        with open(sql_csv, 'w', encoding='utf-8') as f:
            save_result = copy.deepcopy(question)
            save_result['sql'] = sql
            json.dump(save_result, f, ensure_ascii=False)


def do_sql_generation_single(model: ChatGLM_Ptuning, question: dict, question_type=None):
    logger.info('Do sql generation...')

    sql_dir = os.path.join(cfg.DATA_PATH, 'sql')
    if not os.path.exists(sql_dir):
        os.mkdir(sql_dir)

    sql_csv = os.path.join(sql_dir, '{}.csv'.format(question['id']))

    sql = None
    if question_type is None:
        class_csv = os.path.join(cfg.DATA_PATH, 'classify', '{}.csv'.format(question['id']))
        if os.path.exists(class_csv):
            with open(class_csv, 'r', encoding='utf-8') as f:
                class_result = json.load(f)
                question_type = class_result['class']

    if question_type == 'E':
        logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question'].replace('<', '')))
        sql = model.nl2sql(question['question'])
        logger.info(sql.replace('<>', ''))

    save_result = ""
    with open(sql_csv, 'w', encoding='utf-8') as f:
        save_result = copy.deepcopy(question)
        save_result['sql'] = sql
        json.dump(save_result, f, ensure_ascii=False)

    return save_result



def generate_answer(model):
    global company, abbr, code, real_comp, e
    logger.info('Load pdf info...')
    pdf_info = load_pdf_info()
    pdf_tables = load_total_tables()

    test_questions = load_test_questions()

    sql_cursor = get_sql_search_cursor()
    key_words = list(load_company_table().columns)
    logger.info('key_words:{}'.format(key_words))

    answer_dir = os.path.join(cfg.DATA_PATH, 'answers')
    if not os.path.exists(answer_dir):
        os.mkdir(answer_dir)

    for question in test_questions:

        class_csv = os.path.join(cfg.DATA_PATH, 'classify', '{}.csv'.format(question['id']))
        if os.path.exists(class_csv):
            with open(class_csv, 'r', encoding='utf-8') as f:
                class_result = json.load(f)
                question_type = class_result['class']
        else:
            logger.warning('分类文件不存在!')
            question_type = 'F'

        keyword_csv = os.path.join(cfg.DATA_PATH, 'keywords', '{}.csv'.format(question['id']))
        if os.path.exists(keyword_csv):
            with open(keyword_csv, 'r', encoding='utf-8') as f:
                keyword_result = json.load(f)
                question_keywords = keyword_result['keywords']
        else:
            logger.warning('关键词文件不存在!')
            question_keywords = []

        answer_csv = os.path.join(answer_dir, '{}.csv'.format(question['id']))
        ori_question = re.sub('[()（）]', '', question['question'])
        
        years = question_util.get_years_of_question(ori_question)
        mactched_pdf_names = question_util.get_match_pdf_names(ori_question, pdf_info)
        company_abbrs = question_util.get_company_name_and_abbr_code_of_question(mactched_pdf_names, pdf_info)

        answer = '经查询，无法回答{}'.format(ori_question)

        if len(company_abbrs) > 0:
            company = company_abbrs[0][0]
            abbr = company_abbrs[0][1]
            code = company_abbrs[0][2]
            real_comp = company if company in ori_question else abbr

        logger.opt(colors=True).info('<blue>Start process question {} {}</>'.format(question['id'], question['question'].replace('<', '')))
        logger.opt(colors=True).info('<cyan>问题类型{}</>'.format(question_type.replace('<', '')))

        try:
            if question_type in ['A', 'B', 'C']:
                table_dict = {
                    'A': ['basic_info'],
                    'B': ['employee_info', 'dev_info'],
                    'C': ['cbs_info', 'cscf_info', 'cis_info']
                }
                if len(company_abbrs) == 0:
                    logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
                else:
                    # _, question_keywords = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                    logger.info('问题关键词: {}'.format(question_keywords))

                    background = ''
                    tot_matched_rows = []
                    for year in years:
                        pdf_table = load_tables_of_years(company, [year], pdf_tables, pdf_info)

                        background += '已知{}(简称:{},证券代码:{}){}年的资料如下:\n    '.format(company, abbr, code, year)
                        matched_table_rows = []
                        for keyword in question_keywords:
                            matched_table_rows.extend(recall_pdf_tables(keyword, [year], pdf_table, 
                                min_match_number=3, valid_tables=table_dict[question_type]))

                        if len(matched_table_rows) == 0:
                            for table_row in pdf_table:
                                if table_row[0] in table_dict[question_type]:
                                    matched_table_rows.append(table_row)
                        
                        table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
                        background += table_text
                        background += '\n'

                        tot_matched_rows.extend(matched_table_rows)

                    tot_matched_rows = add_text_compare_in_table(tot_matched_rows)
                    tot_text = table_to_text(real_comp, ori_question, tot_matched_rows, with_year=True)

                    if '相同' in tot_text or '不相同且不同' in tot_text:
                        answer = tot_text
                    else:
                        question_for_model = type1.get_prompt(ori_question, company, abbr, years).format(background, ori_question)
                        logger.info('Prompt length {}'.format(len(question_for_model)))
                        if len(question_for_model) > 5120:
                            question_for_model = question_for_model[:5120]
                        logger.info(question_for_model.replace('<', ''))
                        answer = model(question_for_model)
                    logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))

            elif question_type == 'D':
                if len(company_abbrs) == 0:
                    logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
                else:
                    # _, question_keywords = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                    logger.info('问题关键词: {}'.format(question_keywords))

                    if type2.is_type2_growth_rate(ori_question):
                        years_of_table = []
                        for year in years:
                            years_of_table.extend([year, str(int(year)-1)])
                        pdf_table = load_tables_of_years(company, years_of_table, pdf_tables, pdf_info)
                        pdf_table = add_growth_rate_in_table(pdf_table)
                    elif type2.is_type2_formula(ori_question):
                        pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)
                    else:
                        logger.error('无法匹配, 该问题既不是增长率也不是公式计算')
                        pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

                    step_questions, step_keywords, variable_names, step_years, formula, question_formula = type2.get_step_questions(
                        ori_question, ''.join(question_keywords), real_comp, years[0])
                    step_answers = []
                    variable_values = []
                    if len(step_questions) > 0:
                        for step_question, step_keyword, step_year in zip(step_questions, step_keywords, step_years):
                            if len(step_keyword) == 0:
                                logger.error('关键词为空')

                            background = '已知{}{}年的资料如下:\n'.format(real_comp, step_year)
                            # background += '----------------------------------------\n'
                            
                            matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table, 
                                min_match_number=3, top_k=5)
                            # print(matched_table_rows)
                            if len(matched_table_rows) == 0:
                                logger.warning('无法匹配keyword {}, 尝试不设置限制'.format(step_keyword))
                                matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table, 
                                min_match_number=2, top_k=None)
                            if len(matched_table_rows) == 0:
                                logger.error('仍然无法匹配keyword {}'.format(step_keyword))
                                matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table, 
                                min_match_number=0, top_k=10)
                            
                            table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
                            if table_text != '':
                                background += table_text

                            question_for_model = prompt_util.get_prompt_single_question(ori_question, real_comp, step_year).format(background, step_question)
                            logger.opt(colors=True).info('<cyan>{}</>'.format(question_for_model.replace('<', '')))
                            step_answer = model(question_for_model)
                            variable_value = type2.get_variable_value_from_answer(step_answer)
                            if variable_value is not None:
                                step_answers.append(step_answer)
                                variable_values.append(variable_value)
                            logger.opt(colors=True).info('<green>{}</><red>{}</>'.format(step_answer.replace('<', ''), variable_value))
                    if len(step_questions) == len(variable_values):
                        for name, value in zip(variable_names, variable_values):
                            formula = formula.replace(name, value)
                        result = None
                        try:
                            result = eval(formula)
                        except:
                            logger.error('Eval formula {} failed'.format(formula))
                        if result is not None:
                            answer = ''.join(step_answers)
                            answer += question_formula
                            answer += '得出结果{:.2f}({:.2f}%)'.format(result, result*100)
                            logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))

            elif question_type == 'E':
                logger.info('这是个统计题')
                sql_csv = os.path.join(cfg.DATA_PATH, 'sql', '{}.csv'.format(question['id']))
                if os.path.exists(sql_csv):
                    with open(sql_csv, 'r', encoding='utf-8') as f:
                        sql_result = json.load(f)
                        sql = sql_result['sql']
                    if sql is not None:
                        
                        sql = sql.replace('总资产', '资产总计')
                        sql = sql.replace('总负债', '负债合计')
                        sql = sql.replace('资产总额', '资产总计')
                        sql = sql.replace('其余资产', '其他流动资产')
                        sql = sql.replace('公司注册地址', '注册地址')
                        sql = sql_correct_util.correct_sql_number(sql, ori_question)
                        answer, exec_log = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)

                        if answer is None:
                            # sql错误尝试修复一次
                            try:
                                if 'no such column' in exec_log:
                                    sql = sql_correct_util.correct_sql_field(sql, ori_question, model)
                                    answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                                else:
                                    logger.info('模型纠正前sql：{}'.format(sql.replace('<>', '')))
                                    correct_sql_answer = model(prompt_util.prompt_sql_correct.format(key_words, sql, str(e)))
                                    logger.info('模型纠正sql结果：{}'.format(correct_sql_answer.replace('<>', '')))
                                    sql_result = re.findall('```sql([\s\S]+)```', correct_sql_answer)
                                    if len(sql_result) > 0:
                                        sql = sql_result[0].replace('\n','').strip()
                                    logger.info('模型纠正后sql：{}'.format(sql.replace('<>', '')))
                                    answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                            except Exception as e:
                                logger.error('纠正SQL[{}]错误! {}'.format(sql.replace('<>', ''), e))

                        logger.opt(colors=True).info('<green>{}</>'.format(sql.replace('<>', '')))
                        logger.opt(colors=True).info('<magenta>{}</>'.format(str(answer).replace('<>', '')))

            elif question_type == 'F':
                if len(years) == 0:
                    logger.warning('匹配到Type3-2')
                    answer = model(ori_question)
                    logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
                elif len(company_abbrs) == 0:
                    logger.warning('问题存在年份, 但没有匹配的年报')
                else:
                    anoy_question, _ = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                    logger.info('问题关键词: {}'.format(question_keywords))
                    pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

                    background = '***************{}{}年年报***************\n'.format(
                        real_comp, years[0])
                    matched_text = recall_annual_report_texts(model, anoy_question, ''.join(question_keywords), 
                        mactched_pdf_names[0], None)
                    for block_idx, text_block in enumerate(matched_text):
                        background += '{}片段:{}{}\n'.format('-'*15, block_idx+1, '-'*15)
                        background += text_block
                        background += '\n'
                    question_for_model = prompt_util.prompt_question_tp31.format(
                        background, ori_question, ''.join(question_keywords),
                        ''.join(question_keywords), ''.join(question_keywords))

                    logger.info('Prompt length {}'.format(len(question_for_model)))
                    if len(question_for_model) > 5120:
                        question_for_model = question_for_model[:5120]
                    logger.info(question_for_model.replace('<', ''))
                    answer = model(question_for_model)
                    logger.info('Answer length {}'.format(len(answer)))
                    logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
        except Exception as e:
            print(e)

        result = copy.deepcopy(question)
        if answer is not None:
            result['answer'] = answer
        else:
            logger.error('问题无法找到类别, 无法回答')
            result['answer'] = ''
        
        with open(answer_csv, 'w', encoding='utf-8') as f:
            try:
                json.dump(result, f, ensure_ascii=False)
            except:
                result['answer'] = ''
                json.dump(result, f, ensure_ascii=False)


def generate_answer_single_backup(model, question, pdf_info=None, question_type=None, question_keywords=None, sql=None):
    global company, abbr, code, real_comp
    logger.info('Load pdf info...')

    pdf_tables = load_total_tables()
    key_words = list(load_company_table().columns)
    logger.info('key_words:{}'.format(key_words))

    answer_dir = os.path.join(cfg.DATA_PATH, 'answers')
    if not os.path.exists(answer_dir):
        os.mkdir(answer_dir)

    if question_type is None:
        class_csv = os.path.join(cfg.DATA_PATH, 'classify', '{}.csv'.format(question['id']))
        if os.path.exists(class_csv):
            with open(class_csv, 'r', encoding='utf-8') as f:
                class_result = json.load(f)
                question_type = class_result['class']
        else:
            logger.warning('分类文件不存在!')
            question_type = 'F'

    if question_keywords is None:
        keyword_csv = os.path.join(cfg.DATA_PATH, 'keywords', '{}.csv'.format(question['id']))
        if os.path.exists(keyword_csv):
            with open(keyword_csv, 'r', encoding='utf-8') as f:
                keyword_result = json.load(f)
                question_keywords = keyword_result['keywords']
        else:
            logger.warning('关键词文件不存在!')
            question_keywords = []

    answer_csv = os.path.join(answer_dir, '{}.csv'.format(question['id']))
    ori_question = re.sub('[()（）]', '', question['question'])

    years = question_util.get_years_of_question(ori_question)
    mactched_pdf_names = question_util.get_match_pdf_names(ori_question, pdf_info)
    company_abbrs = question_util.get_company_name_and_abbr_code_of_question(mactched_pdf_names, pdf_info)

    answer = '经查询，无法回答{}'.format(ori_question)

    if len(company_abbrs) > 0:
        company = company_abbrs[0][0]
        abbr = company_abbrs[0][1]
        code = company_abbrs[0][2]
        real_comp = company if company in ori_question else abbr

    logger.opt(colors=True).info(
        '<blue>Start process question {} {}</>'.format(question['id'], question['question'].replace('<', '')))
    logger.opt(colors=True).info('<cyan>问题类型{}</>'.format(question_type.replace('<', '')))

    try:
        if question_type in ['A', 'B', 'C']:
            table_dict = {
                'A': ['basic_info'],
                'B': ['employee_info', 'dev_info'],
                'C': ['cbs_info', 'cscf_info', 'cis_info']
            }
            if len(company_abbrs) == 0:
                logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
            else:
                # _, question_keywords = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                logger.info('问题关键词: {}'.format(question_keywords))

                background = ''
                tot_matched_rows = []
                for year in years:
                    pdf_table = load_tables_of_years(company, [year], pdf_tables, pdf_info)

                    background += '已知{}(简称:{},证券代码:{}){}年的资料如下:\n    '.format(company, abbr, code,
                                                                                            year)
                    matched_table_rows = []
                    for keyword in question_keywords:
                        matched_table_rows.extend(recall_pdf_tables(keyword, [year], pdf_table,
                                                                    min_match_number=3,
                                                                    valid_tables=table_dict[question_type]))

                    if len(matched_table_rows) == 0:
                        for table_row in pdf_table:
                            if table_row[0] in table_dict[question_type]:
                                matched_table_rows.append(table_row)

                    table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
                    background += table_text
                    background += '\n'

                    tot_matched_rows.extend(matched_table_rows)

                tot_matched_rows = add_text_compare_in_table(tot_matched_rows)
                tot_text = table_to_text(real_comp, ori_question, tot_matched_rows, with_year=True)

                if '相同' in tot_text or '不相同且不同' in tot_text:
                    answer = tot_text
                else:
                    question_for_model = type1.get_prompt(ori_question, company, abbr, years).format(background,
                                                                                                     ori_question)
                    logger.info('Prompt length {}'.format(len(question_for_model)))
                    if len(question_for_model) > 5120:
                        question_for_model = question_for_model[:5120]
                    logger.info(question_for_model.replace('<', ''))
                    answer = model(question_for_model)
                logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))

        elif question_type == 'D':
            if len(company_abbrs) == 0:
                logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
            else:
                # _, question_keywords = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                logger.info('问题关键词: {}'.format(question_keywords))

                if type2.is_type2_growth_rate(ori_question):
                    years_of_table = []
                    for year in years:
                        years_of_table.extend([year, str(int(year) - 1)])
                    pdf_table = load_tables_of_years(company, years_of_table, pdf_tables, pdf_info)
                    pdf_table = add_growth_rate_in_table(pdf_table)
                elif type2.is_type2_formula(ori_question):
                    pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)
                else:
                    logger.error('无法匹配, 该问题既不是增长率也不是公式计算')
                    pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

                step_questions, step_keywords, variable_names, step_years, formula, question_formula = type2.get_step_questions(
                    ori_question, ''.join(question_keywords), real_comp, years[0])
                step_answers = []
                variable_values = []
                if len(step_questions) > 0:
                    for step_question, step_keyword, step_year in zip(step_questions, step_keywords, step_years):
                        if len(step_keyword) == 0:
                            logger.error('关键词为空')

                        background = '已知{}{}年的资料如下:\n'.format(real_comp, step_year)
                        # background += '----------------------------------------\n'

                        matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                               min_match_number=3, top_k=5)
                        # print(matched_table_rows)
                        if len(matched_table_rows) == 0:
                            logger.warning('无法匹配keyword {}, 尝试不设置限制'.format(step_keyword))
                            matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                                   min_match_number=2, top_k=None)
                        if len(matched_table_rows) == 0:
                            logger.error('仍然无法匹配keyword {}'.format(step_keyword))
                            matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                                   min_match_number=0, top_k=10)

                        table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
                        if table_text != '':
                            background += table_text

                        question_for_model = prompt_util.get_prompt_single_question(ori_question, real_comp,
                                                                                    step_year).format(background,
                                                                                                      step_question)
                        logger.opt(colors=True).info('<cyan>{}</>'.format(question_for_model.replace('<', '')))
                        step_answer = model(question_for_model)
                        variable_value = type2.get_variable_value_from_answer(step_answer)
                        if variable_value is not None:
                            step_answers.append(step_answer)
                            variable_values.append(variable_value)
                        logger.opt(colors=True).info(
                            '<green>{}</><red>{}</>'.format(step_answer.replace('<', ''), variable_value))
                if len(step_questions) == len(variable_values):
                    for name, value in zip(variable_names, variable_values):
                        formula = formula.replace(name, value)
                    result = None
                    try:
                        result = eval(formula)
                    except:
                        logger.error('Eval formula {} failed'.format(formula))
                    if result is not None:
                        answer = ''.join(step_answers)
                        answer += question_formula
                        answer += '得出结果{:.2f}({:.2f}%)'.format(result, result * 100)
                        logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))

        elif question_type == 'E':
            logger.info('这是个统计题')
            if sql is None:
                sql_csv = os.path.join(cfg.DATA_PATH, 'sql', '{}.csv'.format(question['id']))
                if os.path.exists(sql_csv):
                    with open(sql_csv, 'r', encoding='utf-8') as f:
                        sql_result = json.load(f)
                        sql = sql_result['sql']

            if sql is not None:
                sql_cursor = get_sql_search_cursor()
                sql = sql["sql"]
                sql = sql.replace('总资产', '资产总计')
                sql = sql.replace('总负债', '负债合计')
                sql = sql.replace('资产总额', '资产总计')
                sql = sql.replace('其余资产', '其他流动资产')
                sql = sql.replace('公司注册地址', '注册地址')
                sql = sql_correct_util.correct_sql_number(sql, ori_question)
                print(f"sql is {sql}")
                answer, exec_log = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                print(f"answer: {answer} exec_log: {exec_log}")

                if answer == "" or answer is None:
                    # sql错误尝试修复一次
                    e = ""
                    try:
                        if 'no such column' in exec_log:
                            sql = sql_correct_util.correct_sql_field(sql, ori_question, model)
                            answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                        else:
                            logger.info('模型纠正前sql：{}'.format(sql.replace('<>', '')))
                            correct_sql_answer = model(
                                prompt_util.prompt_sql_correct.format(key_words, sql, str(e)))
                            logger.info('模型纠正sql结果：{}'.format(correct_sql_answer.replace('<>', '')))
                            sql_result = re.findall('```sql([\s\S]+)```', correct_sql_answer)
                            if len(sql_result) > 0:
                                sql = sql_result[0].replace('\n', '').strip()
                            logger.info('模型纠正后sql：{}'.format(sql.replace('<>', '')))
                            answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                    except Exception as e:
                        logger.error('纠正SQL[{}]错误! {}'.format(sql.replace('<>', ''), e))

                answer = ori_question + "\n" + answer

                logger.opt(colors=True).info('<green>{}</>'.format(sql.replace('<>', '')))
                logger.opt(colors=True).info('<magenta>{}</>'.format(str(answer).replace('<>', '')))

        elif question_type == 'F':
            if len(years) == 0:
                logger.warning('匹配到非金融题目')
                # answer = model(ori_question)
                answer = "this is not a financial question."
                logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
            elif len(company_abbrs) == 0:
                logger.warning('问题存在年份, 但没有匹配的年报')
            else:
                anoy_question, _ = question_util.parse_question_keywords(model, ori_question, real_comp, years)
                logger.info('问题关键词: {}'.format(question_keywords))
                pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

                background = '***************{}{}年年报***************\n'.format(
                    real_comp, years[0])
                matched_text = recall_annual_report_texts(model, anoy_question, ''.join(question_keywords),
                                                          mactched_pdf_names[0], None)
                for block_idx, text_block in enumerate(matched_text):
                    background += '{}片段:{}{}\n'.format('-' * 15, block_idx + 1, '-' * 15)
                    background += text_block
                    background += '\n'
                question_for_model = prompt_util.prompt_question_tp31.format(
                    background, ori_question, ''.join(question_keywords),
                    ''.join(question_keywords), ''.join(question_keywords))

                logger.info('Prompt length {}'.format(len(question_for_model)))
                if len(question_for_model) > 5120:
                    question_for_model = question_for_model[:5120]
                logger.info(question_for_model.replace('<', ''))
                answer = model(question_for_model)
                logger.info('Answer length {}'.format(len(answer)))
                logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
    except Exception as e:
        print(e)

    try:
        result = copy.deepcopy(question)
        if answer is not None:
            result['answer'] = answer
        else:
            logger.error('问题无法找到类别, 无法回答')
            result['answer'] = ''

        with open(answer_csv, 'w', encoding='utf-8') as f:
            try:
                json.dump(result, f, ensure_ascii=False)
            except:
                result['answer'] = ''
                json.dump(result, f, ensure_ascii=False)
    except Exception as e:
        print(e)

    # print(f"answer: {answer}")

    return answer


def generate_answer_single(model, question: Dict, pdf_info: Dict = None, question_type: str = None,
                          question_keywords: List[str] = None, sql: Dict = None) -> str:
    """
    根据问题生成答案

    Args:
        model: 用于生成答案的模型
        question: 问题信息，包含 id 和 question 两个字段
        pdf_info: PDF 文件信息
        question_type: 问题类型
        question_keywords: 问题关键词
        sql: SQL 查询语句

    Returns:
        答案
    """

    global company, abbr, code, real_comp

    logger.info('Load pdf info...')
    pdf_tables = load_total_tables()
    key_words = list(load_company_table().columns)
    logger.info('key_words:{}'.format(key_words))

    # 创建答案存储目录
    answer_dir = os.path.join(cfg.DATA_PATH, 'answers')
    os.makedirs(answer_dir, exist_ok=True)

    # 获取问题类型
    if question_type is None:
        class_csv = os.path.join(cfg.DATA_PATH, 'classify', '{}.csv'.format(question['id']))
        try:
            with open(class_csv, 'r', encoding='utf-8') as f:
                class_result = json.load(f)
                question_type = class_result['class']
        except FileNotFoundError:
            logger.warning('分类文件不存在!')
            question_type = 'F'

    # 获取问题关键词
    if question_keywords is None:
        keyword_csv = os.path.join(cfg.DATA_PATH, 'keywords', '{}.csv'.format(question['id']))
        try:
            with open(keyword_csv, 'r', encoding='utf-8') as f:
                keyword_result = json.load(f)
                question_keywords = keyword_result['keywords']
        except FileNotFoundError:
            logger.warning('关键词文件不存在!')
            question_keywords = []

    answer_csv = os.path.join(answer_dir, '{}.csv'.format(question['id']))
    ori_question = re.sub('[()（）]', '', question['question'])

    # 获取问题中的年份和公司信息
    years = question_util.get_years_of_question(ori_question)
    mactched_pdf_names = question_util.get_match_pdf_names(ori_question, pdf_info)
    company_abbrs = question_util.get_company_name_and_abbr_code_of_question(mactched_pdf_names, pdf_info)

    answer = '经查询，无法回答{}'.format(ori_question)

    if company_abbrs:
        company, abbr, code = company_abbrs[0]
        real_comp = company if company in ori_question else abbr

    logger.opt(colors=True).info(
        '<blue>Start process question {} {}</>'.format(question['id'], question['question'].replace('<', '')))
    logger.opt(colors=True).info('<cyan>问题类型{}</>'.format(question_type.replace('<', '')))

    try:
        # 根据问题类型调用不同的处理逻辑
        if question_type in ['A', 'B', 'C']:
            answer = handle_type_abc(model, question_type, ori_question, real_comp, years, company_abbrs, question_keywords, pdf_tables, pdf_info)
        elif question_type == 'D':
            answer = handle_type_d(model, question_type, ori_question, real_comp, years, company_abbrs, question_keywords, pdf_tables, pdf_info)
        elif question_type == 'E':
            answer = handle_type_e(model, ori_question, key_words, question, sql)
        elif question_type == 'F':
            answer = handle_type_f(model, pdf_info, ori_question, real_comp, years, company_abbrs, question_keywords, pdf_tables, mactched_pdf_names)
        else:
            logger.error('未知问题类型: {}'.format(question_type))
    except Exception as e:
        logger.exception('处理问题时发生错误: {}'.format(e))

    # 保存答案
    save_answer(question, answer, answer_csv)

    return answer


def handle_type_abc(model, question_type: str, ori_question: str, real_comp: str, years: List[str], company_abbrs: List[Tuple[str, str, str]],
                   question_keywords: List[str], pdf_tables: Dict, pdf_info: Dict) -> str:
    """处理 A、B、C 类问题"""
    table_dict = {
        'A': ['basic_info'],
        'B': ['employee_info', 'dev_info'],
        'C': ['cbs_info', 'cscf_info', 'cis_info']
    }
    if not company_abbrs:
        logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
        return '经查询，无法回答{}'.format(ori_question)

    logger.info('问题关键词: {}'.format(question_keywords))

    background = ''
    tot_matched_rows = []
    for year in years:
        pdf_table = load_tables_of_years(company, [year], pdf_tables, pdf_info)

        background += '已知{}(简称:{},证券代码:{}){}年的资料如下:\n    '.format(company, abbr, code, year)
        matched_table_rows = []
        for keyword in question_keywords:
            matched_table_rows.extend(recall_pdf_tables(keyword, [year], pdf_table,
                                                        min_match_number=3,
                                                        valid_tables=table_dict[question_type]))

        if not matched_table_rows:
            for table_row in pdf_table:
                if table_row[0] in table_dict[question_type]:
                    matched_table_rows.append(table_row)

        table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
        background += table_text
        background += '\n'

        tot_matched_rows.extend(matched_table_rows)

    tot_matched_rows = add_text_compare_in_table(tot_matched_rows)
    tot_text = table_to_text(real_comp, ori_question, tot_matched_rows, with_year=True)

    if '相同' in tot_text or '不相同且不同' in tot_text:
        return tot_text

    question_for_model = type1.get_prompt(ori_question, company, abbr, years).format(background, ori_question)
    logger.info('Prompt length {}'.format(len(question_for_model)))
    if len(question_for_model) > 5120:
        question_for_model = question_for_model[:5120]
    logger.info(question_for_model.replace('<', ''))
    answer = model(question_for_model)
    logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
    return answer


def handle_type_d(model, question_type: str, ori_question: str, real_comp: str, years: List[str], company_abbrs: List[Tuple[str, str, str]],
                   question_keywords: List[str], pdf_tables: Dict, pdf_info: Dict) -> str:
    """处理 D 类问题"""
    if not company_abbrs:
        logger.warning('匹配到了类别{}, 但是不存在报表'.format(question_type))
        return '经查询，无法回答{}'.format(ori_question)

    logger.info('问题关键词: {}'.format(question_keywords))

    if type2.is_type2_growth_rate(ori_question):
        years_of_table = []
        for year in years:
            years_of_table.extend([year, str(int(year) - 1)])
        pdf_table = load_tables_of_years(company, years_of_table, pdf_tables, pdf_info)
        pdf_table = add_growth_rate_in_table(pdf_table)
    elif type2.is_type2_formula(ori_question):
        pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)
    else:
        logger.error('无法匹配, 该问题既不是增长率也不是公式计算')
        pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

    step_questions, step_keywords, variable_names, step_years, formula, question_formula = type2.get_step_questions(
        ori_question, ''.join(question_keywords), real_comp, years[0])
    step_answers = []
    variable_values = []
    if step_questions:
        for step_question, step_keyword, step_year in zip(step_questions, step_keywords, step_years):
            if not step_keyword:
                logger.error('关键词为空')
                continue

            background = '已知{}{}年的资料如下:\n'.format(real_comp, step_year)

            matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                    min_match_number=3, top_k=5)
            if not matched_table_rows:
                logger.warning('无法匹配keyword {}, 尝试不设置限制'.format(step_keyword))
                matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                        min_match_number=2, top_k=None)
            if not matched_table_rows:
                logger.error('仍然无法匹配keyword {}'.format(step_keyword))
                matched_table_rows = recall_pdf_tables(step_keyword, [step_year], pdf_table,
                                                        min_match_number=0, top_k=10)

            table_text = table_to_text(real_comp, ori_question, matched_table_rows, with_year=False)
            if table_text:
                background += table_text

            question_for_model = prompt_util.get_prompt_single_question(ori_question, real_comp,
                                                                                step_year).format(background,
                                                                                                  step_question)
            logger.opt(colors=True).info('<cyan>{}</>'.format(question_for_model.replace('<', '')))
            step_answer = model(question_for_model)
            variable_value = type2.get_variable_value_from_answer(step_answer)
            if variable_value is not None:
                step_answers.append(step_answer)
                variable_values.append(variable_value)
            logger.opt(colors=True).info(
                '<green>{}</><red>{}</>'.format(step_answer.replace('<', ''), variable_value))

    if len(step_questions) == len(variable_values):
        for name, value in zip(variable_names, variable_values):
            formula = formula.replace(name, str(value))
        try:
            result = eval(formula)
        except Exception as e:
            logger.error('Eval formula {} failed: {}'.format(formula, e))
            return '经查询，无法回答{}'.format(ori_question)

        answer = ''.join(step_answers)
        answer += question_formula
        answer += '得出结果{:.2f}({:.2f}%)'.format(result, result * 100)
        logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
        return answer

    return '经查询，无法回答{}'.format(ori_question)


def handle_type_e(model, ori_question: str, key_words: List[str], question: Dict, sql: Dict) -> str:
    """处理 E 类问题"""
    logger.info('这是个统计题')
    if sql is None:
        sql_csv = os.path.join(cfg.DATA_PATH, 'sql', '{}.csv'.format(question['id']))
        try:
            with open(sql_csv, 'r', encoding='utf-8') as f:
                sql_result = json.load(f)
                sql = sql_result['sql']
        except FileNotFoundError:
            logger.warning('SQL 文件不存在!')
            return '经查询，无法回答{}'.format(ori_question)

    if sql is not None:
        sql_cursor = get_sql_search_cursor()
        sql = sql["sql"]
        sql = sql.replace('总资产', '资产总计')
        sql = sql.replace('总负债', '负债合计')
        sql = sql.replace('资产总额', '资产总计')
        sql = sql.replace('其余资产', '其他流动资产')
        sql = sql.replace('公司注册地址', '注册地址')
        sql = sql_correct_util.correct_sql_number(sql, ori_question)
        logger.info(f"sql is {sql}")
        answer, exec_log = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
        logger.info(f"answer: {answer} exec_log: {exec_log}")

        if not answer:
            # sql错误尝试修复一次
            try:
                if 'no such column' in exec_log:
                    sql = sql_correct_util.correct_sql_field(sql, ori_question, model)
                    answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
                else:
                    logger.info('模型纠正前sql：{}'.format(sql.replace('<>', '')))
                    correct_sql_answer = model(
                        prompt_util.prompt_sql_correct.format(key_words, sql, exec_log))
                    logger.info('模型纠正sql结果：{}'.format(correct_sql_answer.replace('<>', '')))
                    sql_result = re.findall('```sql([\s\S]+)```', correct_sql_answer)
                    if sql_result:
                        sql = sql_result[0].replace('\n', '').strip()
                    logger.info('模型纠正后sql：{}'.format(sql.replace('<>', '')))
                    answer, _ = sql_correct_util.exc_sql(ori_question, sql, sql_cursor)
            except Exception as e:
                logger.error('纠正SQL[{}]错误! {}'.format(sql.replace('<>', ''), e))

        answer = ori_question + "\n" + answer

        logger.opt(colors=True).info('<green>{}</>'.format(sql.replace('<>', '')))
        logger.opt(colors=True).info('<magenta>{}</>'.format(str(answer).replace('<>', '')))
        return answer

    return '经查询，无法回答{}'.format(ori_question)


def handle_type_f(model, pdf_info, ori_question: str, real_comp: str, years: List[str], company_abbrs: List[Tuple[str, str, str]],
                  question_keywords: List[str], pdf_tables: Dict, mactched_pdf_names: List[str]) -> str:
    """处理 F 类问题"""
    logger.warning('匹配到非金融题目')
    if not years:
        return "this is not a financial question."
    if not company_abbrs:
        logger.warning('问题存在年份, 但没有匹配的年报')
        return '经查询，无法回答{}'.format(ori_question)

    anoy_question, _ = question_util.parse_question_keywords(model, ori_question, real_comp, years)
    logger.info('问题关键词: {}'.format(question_keywords))
    pdf_table = load_tables_of_years(company, years, pdf_tables, pdf_info)

    background = '***************{}{}年年报***************\n'.format(
        real_comp, years[0])
    matched_text = recall_annual_report_texts(model, anoy_question, ''.join(question_keywords),
                                              mactched_pdf_names[0], None)
    for block_idx, text_block in enumerate(matched_text):
        background += '{}片段:{}{}\n'.format('-' * 15, block_idx + 1, '-' * 15)
        background += text_block
        background += '\n'
    question_for_model = prompt_util.prompt_question_tp31.format(
        background, ori_question, ''.join(question_keywords),
        ''.join(question_keywords), ''.join(question_keywords))

    logger.info('Prompt length {}'.format(len(question_for_model)))
    if len(question_for_model) > 5120:
        question_for_model = question_for_model[:5120]
    logger.info(question_for_model.replace('<', ''))
    answer = model(question_for_model)
    logger.info('Answer length {}'.format(len(answer)))
    logger.opt(colors=True).info('<magenta>{}</>'.format(answer.replace('<', '')))
    return answer


def save_answer(question: Dict, answer: str, answer_csv: str):
    """保存答案"""
    try:
        result = copy.deepcopy(question)
        result['answer'] = answer
        with open(answer_csv, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
    except Exception as e:
        logger.exception('保存答案时发生错误: {}'.format(e))


def make_submit():
    submits = []

    test_questions = load_test_questions()

    answer_dir = os.path.join(cfg.DATA_PATH, 'answers')

    for question in test_questions:
        answer_csv = os.path.join(answer_dir, '{}.csv'.format(question['id']))
        if os.path.exists(answer_csv):
            with open(answer_csv, 'r', encoding='utf-8') as f:
                answer = json.load(f)
                question = answer
        else:
            question['answer'] = ''

        question['answer'] = re_util.rewrite_answer(question['answer'])
        submits.append(question)

    save_path = os.path.join(cfg.DATA_PATH, 'result_{}.json'.format(datetime.now().strftime('%Y%m%d')))
    
    with open(save_path, 'w', encoding='utf-8') as f:
        for submit in submits:
            try:
                line = json.dumps(submit, ensure_ascii=False).encode('utf-8').decode() + '\n'
            except:
                submit['answer'] = ''
                line = json.dumps(submit, ensure_ascii=False).encode('utf-8').decode() + '\n'
            f.write(line)