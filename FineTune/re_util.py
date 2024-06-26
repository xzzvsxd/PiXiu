import itertools
import re
from difflib import SequenceMatcher

from fastbm25 import fastbm25
from langchain.embeddings import HuggingFaceEmbeddings
from loguru import logger



def keep_chinese(str):
    return ''.join([c for c in str if '\u4e00' <= c <= '\u9fa5'])


def clean_row_name(name):
    return re.sub('[一二三四五六七八九十\d（）、 \n\.]', '', name)


def find_years(s):
    years = re.findall('\d{4}', s)
    return years


def find_numbers(s):
    numbers = re.findall('[-\d,\.]+', s)
    float_numbers = []
    for number in numbers:
        try:
            float_numbers.append(float(number))
        except:
            pass
            # logger.info('Invalid number {} in {}'.format(number, s))
    return float_numbers


def is_valid_number(s):
    # 0~99
    two_digits = re.findall('\d\d{0,1}', s)
    if len(two_digits) == 1 and two_digits[0] == s:
        return False
    # 7-1, 1-2
    digit_broken_digit = re.findall('\d+-\d+', s)
    if len(digit_broken_digit) == 1 and digit_broken_digit[0] == s:
        return False
    return True


def sep_numbers(line):
    pos_to_add_sep = []
    for match in re.finditer('\.\d\d +[+\-\d]{1}', line):
        pos_to_add_sep.append(match.start())
    new_line = line
    for pos in sorted(pos_to_add_sep, reverse=True):
        new_line = new_line[:pos+3] + '|' + new_line[pos+3:]
    # if new_line != line:
    #     print(line, new_line)
    return new_line


def is_header_footer(line):
    line = line.replace(' ', '')
    if re.findall('\d{4}年?年度报告', line):
        return True
    res = ['[\d]+', '[\d第页/]+']
    for pattern in res:
        matched_str = re.findall(pattern, line)
        if len(matched_str) == 1 and matched_str[0] == line:
            return True
    
    return False


def rewrite_answer(answer):
    numbers = re.findall('-?\d+.\d+元', answer)
    new_answer = answer
    for number in numbers:
        number = number.replace('元', '')
        try:
            f_num = float(number)
            if str(float(number)) != '{:.2f}'.format(float(number)):
                new_answer = new_answer.replace(number, '{:.0f}元{:.1f}元{:.2f}'.format(f_num, f_num, f_num))
        except:
            print('invalid number {}'.format(number))
    # print(new_answer)
    return new_answer


def rewrite_compute_result(answer):
    new_answer = answer
    # [\d+-/()\.=≈%元×]+
    equations = re.findall('[\d%元,\.\(\)（）+\-×/=≈]+', new_answer.replace(' ', ''))
    print(equations)
    recomputes = []
    for equation in equations:
        
            # result = eval(equation)
            # if equation == str(result):
            #     continue
            # print(equation)
        for t in re.split('[=≈]+', equation):
            t = t.replace('×', '*')
            t = t.replace('（', '(')
            t = t.replace('）', ')')
            t = t.replace(',', '')
            try:
                t_to_eval = re.sub('[%元]+', '', t)
                # print(t_to_eval)
                result = eval(t_to_eval)
                if str(result) != t_to_eval:
                    if t.endswith('%'):
                        recomputes.append('其中{}={:.2f}%'.format(t, result))
                    elif t.endswith('元'):
                        recomputes.append('其中{}={:.2f}元'.format(t, result))
                    else:
                        recomputes.append('其中{}={:.2f}%({:.2f})'.format(t, result*100, result))
            except:
                continue
    if len(recomputes) != 0:
        new_answer += '\n<green>{}</>\n'.format('\n'.join(recomputes))

    # equations = re.findall('[\d+-/()\.]+[=≈][\d+-/() \.]+%*', answer)
    # print(new_answer)
    # for equation in equations:
    #     spe = '=' if '=' in equation else '≈'
    #     left, right = equation.split(spe)
    #     print(equation)
    #     result = eval(left)
    #     new_equation = '{}={:.2f}%({:.2f})'.format(left, result*100, result)
    #     new_answer = new_answer.replace(equation, new_equation)
    #     print(equation, new_equation)

    return new_answer


def process_line(s):
    # numbers like 1,000,00 0.00
    def f(t):
        return '{}'.format(t.group().replace(' ', ''))
    s = s.strip(' ')
    space_groups = list(re.finditer(' +', s))
    for gidx in range(len(space_groups)-1):
        current_span = space_groups[gidx].span()
        next_span = space_groups[gidx+1].span()
        current_num = current_span[1] - current_span[0]
        next_num = next_span[1] - next_span[0]
        if next_num >= current_num:
            s = s[:current_span[0]] + '*'*current_num + s[current_span[1]:]
    s = s.replace('*', '')
    
    s = re.sub(' {3,}', '   ', s)
    s = re.sub('[\d,\.+-] {1,2}', f, s)
    s = re.sub('[\d\+\-%] {1,3}[\d\+\-%]', lambda t: re.sub(' {1,3}', '|', t.group()), s)
    # s = re.sub('[^\d ] [^\d ]', f, s)
    # print(s.replace(' ', '*'))
    s = re.sub('[^\d ] {1,2}', f, s)
    # print(s.replace(' ', ''))
    # print(s)
    return s


def recall_pdf_tables(keywords, years, tables, valid_tables=None, invalid_tables=None,
                      min_match_number=3, top_k=None):
    logger.info('recall words {}'.format(keywords))

    # valid_keywords = re.sub('(公|司|的|主|要)', '', keywords)
    valid_keywords = keywords

    matched_lines = []
    for table_row in tables:
        table_name, row_year, row_name, row_value = table_row
        row_name = row_name.replace('"', '')
        if row_year not in years:
            continue
        # min_match_number = 2 if table_name in ['basic_info', 'employee_info'] else 3

        if valid_tables is not None and table_name not in valid_tables:
            continue

        if invalid_tables is not None and table_name in invalid_tables:
            continue

        # find exact match, only return this row
        if row_name == valid_keywords:
            matched_lines = [(table_row, len(row_name))]
            break

        tot_match_size = 0
        matches = SequenceMatcher(None, valid_keywords, row_name, autojunk=False)
        for match in matches.get_matching_blocks():
            inter_text = valid_keywords[match.a:match.a + match.size]
            # if match.size >= min_match_number or inter_text in ['存货']:
            # matched_lines.append(table_row)
            # break
            tot_match_size += match.size
        if tot_match_size >= min_match_number or row_name in valid_keywords:
            # print(table_row, tot_match_size)
            matched_lines.append([table_row, tot_match_size])
        # if len(matched_lines) > 0:
        #     # if name in ['basic_info', 'employee_info']:
        #     #     macthed_tables[name] = lines
        #     # else:
        #     macthed_tables[name] = matched_lines
    matched_lines = sorted(matched_lines, key=lambda x: x[1], reverse=True)
    matched_lines = [t[0] for t in matched_lines]
    if top_k is not None and len(matched_lines) > top_k:
        matched_lines = matched_lines[:top_k]
    return matched_lines

def merge_idx(indexes, total_len, prefix=0, suffix=1):
    merged_idx = []
    for index in indexes:
        start = max(0, index-prefix)
        end = min(total_len, index+suffix+1)
        merged_idx.extend([i for i in range(start, end)])
    merged_idx = sorted(list(set(merged_idx)))

    block_idxes = []

    if len(merged_idx) == 0:
        return block_idxes

    current_block_idxes = [merged_idx[0]]
    for i in range(1, len(merged_idx)):
        if merged_idx[i] - merged_idx[i-1] > 1:
            # block = [lines[idx] for idx in current_block_idxes]
            # text_blocks.append('\n'.join(block))
            block_idxes.append(current_block_idxes)
            current_block_idxes = [merged_idx[i]]
        else:
            current_block_idxes.append(merged_idx[i])
    if len(current_block_idxes) > 0:
        block_idxes.append(current_block_idxes)

    return block_idxes


def recall_annual_report_texts(question, key, embeddings: HuggingFaceEmbeddings):
    text_blocks = []

    # text_lines = load_pdf_text(key)

    from .file import load_pdf_pages
    text_pages = load_pdf_pages(key)
    for idx, page in text_pages:
        overlap_words = list(set(question) & set(page))
        text_blocks.append((page, overlap_words))

    text_blocks = sorted(text_blocks, key=lambda x: len(x[1]), reverse=True)
    text_blocks = [text_block[0] for text_block in text_blocks[:3]]
    return text_blocks


def filter_header_footer(text_block):
    lines = text_block.split('\n')
    lines = [line for line in lines if not is_header_footer(line)]
    return '\n'.join(lines)


def recall_annual_report_texts(glm_model, anoy_question: str, keywords: str, key, embeddings: HuggingFaceEmbeddings):
    anoy_question = re.sub(r'(公司|年报|根据|数据|介绍)', '', anoy_question)
    logger.info('anoy_question: {}'.format(anoy_question.replace('<', '')))

    from .file import load_pdf_pages

    text_pages = load_pdf_pages(key)
    text_lines = list(itertools.chain(*[page.split('\n') for page in text_pages]))
    text_lines = [line for line in text_lines if len(line) > 0]
    if len(text_lines) == 0:
        return []
    model = fastbm25(text_lines)
    result_keywords = model.top_k_sentence(keywords, k=3)
    result_question = model.top_k_sentence(anoy_question, k=3)
    top_match_indexes = [t[1] for t in result_question + result_keywords]
    block_line_indexes = merge_idx(top_match_indexes, len(text_lines), 0, 30)

    text_blocks = ['\n'.join([text_lines[idx] for idx in line_indexes]) for line_indexes in block_line_indexes]
    # text_blocks = [filter_header_footer(text_block) for text_block in text_blocks]
    text_blocks = [re.sub(' {3,}', '\t', text_block) for text_block in text_blocks]

    text_blocks = [(t, SequenceMatcher(None, anoy_question, t, autojunk=False).find_longest_match().size) for t in
                   text_blocks]
    for text_block, match_size in text_blocks:
        match = SequenceMatcher(None, anoy_question, text_block, autojunk=False).find_longest_match()
        print(anoy_question[match.a: match.a + match.size])
    max_match_size = max([t[1] for t in text_blocks])
    text_blocks = [t[0] for t in text_blocks if t[1] == max_match_size]

    if sum([len(t) for t in text_blocks]) > 2000:
        max_avg_len = int(2000 / len(text_blocks))
        text_blocks = [t[:max_avg_len] for t in text_blocks]

    text_blocks = [rewrite_text_block(t) for t in text_blocks]
    text_blocks = ['```\n{}\n```'.format(t) for t in text_blocks]
    return text_blocks


def rewrite_text_block(text):
    for word in ['是', '否', '适用', '不适用']:
        text = text.replace('□{}'.format(word), '')
    return text


def recall_annual_names(question):
    pass





if __name__ == '__main__':
    # print((388969421.15-378737577.28)/378737577.28*100)

#     print(rewrite_compute_result('''
# （2453215434.28 - 1622278319.25）/ 1622278319.25 × 100% ≈ 79.72%
# '''))
    # print(re.sub('[×%元]+', '', '(50449943.70 - (-5146737.73)) / (-5146737.73) × 100%'))


    print(sep_numbers('预付款项|674,558,351.89435,646,053.30\n'))

    # print(is_header_footer('2020  2021  上海证券交             年度报告及其摘要的议案》、《关于 2020 年度财务决算'))

    # print(find_numbers('287571813.28元'))

    # print(is_valid_number('15-51'))

    print(re.findall('人民币.{0,3}元', '人民币百万元'))
    # rewrite_answer('北京同仁堂股份有限公司2019年的营业利润是1968133334.00元。北京同仁堂股份有限公司2019年的营业收入是13277123199.46元。公式为:营业利润率=营业利润/营业收入得出结果0.15(14.82%)')