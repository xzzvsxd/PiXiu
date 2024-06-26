import random
import re

import requests
import os
from tqdm import tqdm
import concurrent.futures

def get_company_full_name(sec_code):
    url = f"https://www.szse.cn/api/report/index/companyGeneralization?random={random.random():.16f}&secCode={sec_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['data']['gsqc']
    else:
        print(f"获取公司全名失败 {sec_code}")
        return None

def download_announcement_pdf(session, base_url, ann, download_dir):
    company_full_name = get_company_full_name(ann['secCode'][0])
    if company_full_name is None:
        return

    publish_time_formatted = ann['publishTime'].split(" ")[0]
    title_parts = ann['title'].split('年年度报告')
    year_match = re.search(r'\d{4}', title_parts[0])  # 使用正则表达式查找年份
    if not year_match:
        print(f"无法在标题中找到年份 {ann['title']}")
        return
    year = year_match.group()  # 提取匹配到的年份字符串
    # report_type = '年度报告' if title_parts[1] == '' else title_parts[1]

    file_name = f"{publish_time_formatted}__{company_full_name}__{ann['secCode'][0]}__{ann['secName'][0]}__{year}年__年度报告.pdf"
    file_path = os.path.join(download_dir, file_name)

    pdf_url = base_url + 'api/disc/info/download'
    params = {'id': ann['id']}
    pdf_response = session.get(pdf_url, params=params)

    if pdf_response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(pdf_response.content)
        print(f"下载完成: {file_name}")
    else:
        print(f"下载失败 {ann['title']}")

def download_pdf(base_url, download_dir, years, max_workers=5):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    session = requests.Session()
    page_num = 1
    no_announcement_count = 0  # 初始化计数器

    while True:
        payload = {
            "channelCode": ["fixed_disc"],
            "pageSize": 50,
            "pageNum": page_num,
            "stock": []
        }
        random_number_str = f"{random.random():.16f}"
        response = session.post(base_url + 'api/disc/announcement/annList?random=' + random_number_str, json=payload)
        data = response.json()

        relevant_announcements = [
            ann for ann in data['data']
            if any(year in ann['title'] and "年度报告" in ann['title'] and "半年度" not in ann['title'] and "摘要" not in ann['title'] and "英文" not in ann['title'] for year in years)
        ]

        if relevant_announcements:
            no_announcement_count = 0  # 重置计数器
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                for ann in relevant_announcements:
                    executor.submit(download_announcement_pdf, session, base_url, ann, download_dir)
        else:
            no_announcement_count += 1  # 递增计数器
            print(f"没有更多相关公告。连续第 {no_announcement_count} 次未发现公告。页数：{page_num}")
            if no_announcement_count >= 10:  # 检查是否达到连续10次
                break

        page_num += 1

if __name__ == "__main__":
    BASE_URL = 'https://www.szse.cn/'
    DOWNLOAD_DIR = './downloaded_reports'
    YEARS = ['2023', '2022']  # 根据需要更新年份
    MAX_WORKERS = 10  # 根据你的网络环境和服务器承受能力调整

    download_pdf(BASE_URL, DOWNLOAD_DIR, YEARS, MAX_WORKERS)