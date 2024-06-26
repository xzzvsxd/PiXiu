import random
import os
from datetime import datetime

import requests
import re
from tqdm import tqdm
import concurrent.futures

def convert_timestamp_to_date(timestamp):
    return datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')

def get_company_full_name(sec_code):
    url = f"http://www.cninfo.com.cn/data20/companyOverview/getCompanyIntroduction?scode={sec_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['data']['records'][0]['basicInformation'][0]['ORGNAME']
    else:
        print(f"获取公司全名失败 {sec_code}")
        return None

def download_announcement_pdf(session, base_url, ann, download_dir):
    company_full_name = get_company_full_name(ann['secCode'])
    if company_full_name is None:
        return

    # 判断公告标题是否符合条件
    title = ann['announcementTitle']
    if '年度报告' not in title or '摘要' in title or '英文' in title:
        # print(f"不是目标年度报告: {title}")
        return

    # 从标题中提取年份
    year_match = re.search(r'\d{4}', title)
    if not year_match:
        print(f"无法从标题中提取年份: {title}")
        return
    year = year_match.group()

    publish_time_formatted = convert_timestamp_to_date(ann['announcementTime'])

    file_name = f"{publish_time_formatted}__{company_full_name}__{ann['secCode']}__{ann['secName']}__{year}年__年度报告.pdf"
    file_path = os.path.join(download_dir, file_name)

    pdf_url = base_url + 'new/announcement/download'
    params = {'bulletinId': ann['announcementId']}
    pdf_response = session.get(pdf_url, params=params)

    if pdf_response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(pdf_response.content)
        print(f"下载完成: {file_name}")
    else:
        print(f"下载失败 {title}")

    # print(f"当前页数: {page_num}")
    # print(f"已下载文件数: {total_downloaded}")


def download_pdf(base_url, download_dir, start_date, end_date, max_workers=5):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    session = requests.Session()
    page_num = 1
    no_announcement_count = 0  # 初始化计数器

    while True:
        payload = {
            "pageNum": page_num,
            "pageSize": 30,
            "column": "szse",
            "tabName": "fulltext",
            "plate": None,
            "stock": None,
            "searchkey": None,
            "secid": None,
            "category": "category_ndbg_szsh",
            "trade": None,
            "seDate": f"{start_date}~{end_date}",
            "sortName": None,
            "sortType": None,
            "isHLtitle": True
        }
        response = session.post(base_url + 'new/hisAnnouncement/query', data=payload)
        data = response.json()
        # print(data)
        print(page_num)

        total_num = data['totalpages'] + 1
        print(f'total_num: {total_num}')
        if total_num > 100 or total_num == 0 or page_num > total_num:
            return

        relevant_announcements = data['announcements']
        # print(relevant_announcements)

        if relevant_announcements:
            no_announcement_count = 0  # 重置计数器
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                for ann in relevant_announcements:
                    # print(ann)
                    executor.submit(download_announcement_pdf, session, base_url, ann, download_dir)
        else:
            no_announcement_count += 1  # 递增计数器
            print(f"没有更多相关公告。连续第 {no_announcement_count} 次未发现公告。页数：{page_num}")
            if no_announcement_count >= 10:  # 检查是否达到连续10次
                break

        page_num += 1

if __name__ == "__main__":
    BASE_URL = 'http://www.cninfo.com.cn/'
    DOWNLOAD_DIR = './downloaded_reports'
    START_DATE = '2022-05-01'
    END_DATE = '2023-01-01'
    MAX_WORKERS = 10  # 根据你的网络环境和服务器承受能力调整

    download_pdf(BASE_URL, DOWNLOAD_DIR, START_DATE, END_DATE, MAX_WORKERS)
