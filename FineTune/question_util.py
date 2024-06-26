import re
from loguru import logger




def get_prompt_single_question(question, company, year):
    if '人数' in question or '数量' in question or '人员' in question:
        unit = '人'
    else:
        unit = '元'
    prompt = """
{{}}

请回答问题: {{}}
注意你回答的要求如下:
1. 你回答的格式应该是:{}{}年的XXXX是XXXX{}。
2. 你只需要回答问题相关的内容, 不要回答无关内容。
3. 你不需要进行计算。
4. 你的回答只能来源于提供的资料。""""".format(company, year, unit)
    return prompt


# def get_prompt_growth_rate(background, ori_question, company, years):
#     prompt = '''
# {}
# ----------------------------------------
# 请根据背景知识回答下面的问题, 如果背景中没有提供, 则回答不知道:
# 1. {} 回答格式为: {}年{}的XXX增长率为XXX。
# '''.format(background, ori_question, years[0], company)
#     for i, year in enumerate(years):
#         prompt += '{}. {}回答格式为: {}年{}的XXX是XXX。\n'.format(
#             i+2, ori_question.replace('增长率', '').replace(years[0], year), year, company, year)
#     return prompt


def get_prompt_growth_rate(background, ori_question, company, years):
    prompt = '''
{}
----------------------------------------
请根据背景知识回答下面的问题, 如果背景中没有提供, 则回答不知道:
1. {}
'''.format(background, ori_question, years[0], company)
    for i, year in enumerate(years):
        prompt += '{}. {}请用元为单位。\n'.format(
            i+2, ori_question.replace('增长率', '').replace(years[0], year), year, company, year)
    prompt += '''
注意:
1. 你回答的数值只能来源于背景信息。
2. 回答问题的格式为: {}在XXXX年的XXXX是XXXX。
'''.format(company)
    return prompt



prompt_question_tp32 = '''
作为一个金融专家, 请回答以下问题:
问:{}'''


prompt_question_tp31 = '''
你需要阅读理解年报的片段来真实详细完整的回答用户的提问。
下面是年报内容格式的一些说明:
1. 片段由标题和正文内容组成。
1. 片段中的标题通常以中文数字如一二三四五或阿拉伯数字12345开始。
2. 片段中的表格采用制表符'\t'分隔。
3. "√适用"表示该项内容公司存在该事项, "√不适用"表示公司不存在该事项。
4. "√是"表示该项是或者有, "√否"表示该项不是或者没有。

{}
******************************
问: {}
'''

# 注意:
# 1. 不要回答和"{}"无关的内容。
# 2. 需要详细的包含全部和"{}"相关的正文内容。
# 3. 涉及到和"{}"相关的表格, 你需要包含表格中的内容进行回答。



# 在回答问题的时候, 你需要注意以下几点:
# 1. 你的回答的内容只能来源于片段中相关的小节, 不能源于其他信息。
# 2. 你的回答应该尽可能详细。
# 3. 你的回答应该包含片段中全部和问题相关的内容。
# 4. 不要遗漏和问题相关的内容。
# 5. 所有和问题相关的小节都需要进行回答。
# 6. 不要回答和问题无关的内容。


prompt_get_key_word = '''
这是文字提取器，你要从用户输入的文本中提取关键词
关键词是指：问题最终指向的词语，通常是名词或句子的宾语，通常出现在公司名称或时间状语后面
如：净利润、社会责任工作、企业名称、固定资产、外文名称、注册地址、财务费用、长期借款、短期借款、资产及负债、收回投资收到的现金、净利润率、企业研发经费与利润比值、企业研发经费与营业收入比值、研发人员占职工人数比例、企业硕士及以上人员占职工人数比例、企业研发经费占费用比例、收回投资所收到的现金、关键审计事项、法人代表、负债总金额、总负债、无。对象可以有多个。没有写“无”。
输出完毕后结束，不要生成新的用户输入，不要新增内容


示例模板：
"""
用户输入：能否根据的年报，给我简要介绍一下报告期内公司的社会责任工作情况？

关键词1:社会责任工作

用户输入：其他非流动金融资产第十一高的上市公司是哪家？

关键词1:其他非流动金融资产


用户输入：研发人员占职工人数比例是多少?请。？

关键词1:研发人员占职工人数比例


用户输入：办公地址是什么?

关键词1:办公地址


用户输入：法定代表人对比是否相同?。

关键词1:法定代表人


用户输入：法定代表人与上年相比相同吗？

关键词1:法定代表人


用户输入：根据的年报，请简要介绍报告期内公司主要销售客户的客户集中度如何？请结合同行业情况简要分析。?

关键词1:客户集中度

用户输入：在的现金比率是多少？请保留至小数点后两位。

关键词1:现金比率

用户输入：研发费用和财务费用分别是多少元?

关键词1:研发费用
关键词2:财务费用

"""

请根据以下文本，严格按照示例模版格式输出内容。
用户输入：{}
'''

prompt_sql_correct = '''你是一名mysql数据库开发人员，精通SQL编写，请根据错误信息对sql进行修复
已知表名：company_table
已知字段名：{}
已知sql：
···sql
{}
···
已知错误信息：“{}”
'''

prompt_most_like_word = '''你是一个同义词查询字典，从已知词语列表中，查找与查询词语最相近的一个词语
已知词语列表：{}
要求只返回语义最相近的1个词语，词语必须存在于已知的词语列表，不要生成新的用户输入，不要新增内容

示例模板：
"""
示例1：
查询词语：总负债
同义词：负债总计

示例2：
查询词语：资产总额
同义词：资产总计

示例3：
查询词语：其余资产
同义词：其它流动资产

示例4：
查询词语：公司注册地址
同义词：注册地址

示例5：
查询词语：利息收益
同义词：利息收入

"""

请根据以下用户输入文本，按照示例模版格式输出查询词语的同义词。
查询词语：{}
'''


def get_years_of_question(question):
    years = re.findall('\d{4}', question)

    if len(years) == 1:
        if re.search('(([上前去]的?[1一]|[上去])年|[1一]年(前|之前))', question) and '上上年' not in question:
            last_year = int(years[0]) - 1
            years.append(str(last_year))
        if re.search('((前|上上)年|[2两]年(前|之前))', question):
            last_last_year = int(years[0]) - 2
            years.append(str(last_last_year))
        if re.search('[上前去]的?[两2]年', question):
            last_year = int(years[0]) - 1
            last_last_year = int(years[0]) - 2
            years.append(str(last_year))
            years.append(str(last_last_year))

        if re.search('([后下]的?[1一]年|[1一]年(后|之后|过后))', question):
            next_year = int(years[0]) + 1
            years.append(str(next_year))
        if re.search('[2两]年(后|之后|过后)', question):
            next_next_year = int(years[0]) + 2
            years.append(str(next_next_year))
        if re.search('(后|接下来|下)的?[两2]年', question):
            next_year = int(years[0]) + 1
            next_next_year = years[0] + 2
            years.append(str(next_year))
            years.append(str(next_next_year))

    if len(years) == 2:
        if re.search('\d{4}年?[到\-至]\d{4}年?', question):
            year0 = int(years[0])
            year1 = int(years[1])
            for year in range(min(year0, year1) + 1, max(year0, year1)):
                years.append(str(year))

    return years


def get_match_company_names(question, pdf_info):
    question = re.sub('[\(\)（）]', '', question)

    matched_companys = []
    for k, v in pdf_info.items():
        company = v['company']
        abbr = v['abbr']
        if company in question:
            matched_companys.append(company)
        if abbr in question:
            matched_companys.append(abbr)
    return matched_companys


def get_match_pdf_names(question, pdf_info):
    def get_matching_substrs(a, b):
        return ''.join(set(a).intersection(b))
    
    years = get_years_of_question(question)
    match_keys = []
    for k, v in pdf_info.items():
        company = v['company']
        abbr = v['abbr']
        year = v['year'].replace('年', '').replace(' ', '')
        if company in question and year in years:
            match_keys.append(k)
        if abbr in question and year in years:
            match_keys.append(k)
    match_keys = list(set(match_keys))
    # 前面已经完全匹配了年份, 所以可以删除年份
    overlap_len = [len(get_matching_substrs(x, re.sub('\d?', '', question))) for x in match_keys]
    match_keys = sorted(zip(match_keys, overlap_len), key=lambda x: x[1], reverse=True)
    # print(match_keys)
    if len(match_keys) > 1:
        # logger.info(question)
        # 多个结果重合率完全相同
        if len(set([t[1] for t in match_keys])) == 1:
            pass
        else:
            logger.warning('匹配到多个结果{}'.format(match_keys))
            match_keys = match_keys[:1]
        # for k in match_keys:
        #     print(k[0])
    match_keys = [k[0] for k in match_keys]
    return match_keys


def get_company_name_and_abbr_code_of_question(pdf_keys, pdf_info):
    company_names = []
    for pdf_key in pdf_keys:
        company_names.append((pdf_info[pdf_key]['company'], pdf_info[pdf_key]['abbr'], pdf_info[pdf_key]['code']))
    return company_names


def parse_keyword_from_answer(anoy_question, answer):
    key_words = set()
    key_word_list = answer.split('\n')
    for key_word in key_word_list:
        key_word = key_word.replace(' ', '')
        # key_word = re.sub('年报|报告|是否', '', key_word)
        if (key_word.endswith('公司') and not key_word.endswith('股公司')) or re.search(
                r'(年报|财务报告|是否|最高|最低|相同|一样|相等|在的?时候|财务数据|详细数据|单位为|年$)', key_word):
            continue
        if key_word.startswith('关键词'):
            key_word = re.sub("关键词[1-9][:|：]", "", key_word)
            if key_word in ['金额', '单位','数据']:
                continue
            if  key_word in anoy_question and len(key_word) > 1:
                key_words.add(key_word)
    return list(key_words)


def anoy_question_xx(question, real_company, years):
    question_new = question
    question_new = question_new.replace(real_company, 'XX公司')
    for year in years:
        question_new = question_new.replace(year, 'XXXX')

    return question_new


def parse_question_keywords(model, question, real_company, years):
    question = re.sub('[\(\)（）]', '', question).replace('为？','是什么？').replace('是？','是什么？').replace('为多少','是多少')
    anoy_question = anoy_question_xx(question, real_company, years)
    anoy_question = re.sub(r'(XX公司|XXXX年|XXXX|保留两位小数|对比|相比|报告期内|哪家|上市公司|第[1234567890一二三四五六七八九十]+[高低]|最[高低](的|的前|的后)?[1234567890一二三四五六七八九十]+家)', '', anoy_question)
    if anoy_question[0] == '的':
        anoy_question = anoy_question[1:]
    answer = model(prompt_get_key_word.format(anoy_question))

    key_words = parse_keyword_from_answer(anoy_question, answer)
    # 无法提取，删除的再试一次
    if len(key_words) == 0:
        anoy_question = anoy_question.replace('的', '')
        answer = model(prompt_get_key_word.format(anoy_question))
        key_words = parse_keyword_from_answer(anoy_question, answer)
    if len(key_words) == 0:
        logger.warning('无法提取关键词')
        key_words = [anoy_question]

    return anoy_question, key_words