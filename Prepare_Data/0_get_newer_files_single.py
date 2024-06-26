import random
import requests
import os
from tqdm import tqdm


def get_company_full_name(sec_code):
    url = f"https://www.szse.cn/api/report/index/companyGeneralization?random={random.random():.16f}&secCode={sec_code}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['data']['gsqc']
    else:
        print(f"Failed to get company full name for {sec_code}")
        return None


def download_pdf(base_url, download_dir, years):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    session = requests.Session()
    page_num = 1
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
            if any(year in ann['title'] and "年度报告" in ann['title'] and "摘要" not in ann['title'] for year in years)
        ]

        if not relevant_announcements:
            print("No more relevant announcements found.")
            break

        for ann in tqdm(relevant_announcements, desc=f'Page {page_num}'):
            company_full_name = get_company_full_name(ann['secCode'][0])
            if company_full_name is None:
                continue

            publish_time_formatted = ann['publishTime'].split(" ")[0]
            title_parts = ann['title'].split('年年度报告')
            year = title_parts[0].split("：")[1]  # Extract the year (e.g., '2023年')
            print(title_parts)
            report_type = '年度报告' if title_parts[1] == '' else title_parts[1]

            file_name = f"{publish_time_formatted}__{company_full_name}__{ann['secCode'][0]}__{ann['secName'][0]}__{year}年__{report_type}.pdf"
            file_path = os.path.join(download_dir, file_name)

            pdf_url = base_url + 'api/disc/info/download'
            params = {'id': ann['id']}
            pdf_response = session.get(pdf_url, params=params)

            if pdf_response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(pdf_response.content)
            else:
                print(f"Failed to download {ann['title']}")

        page_num += 1


if __name__ == "__main__":
    BASE_URL = 'https://www.szse.cn/'
    DOWNLOAD_DIR = './downloaded_reports'
    YEARS = ['2023', '2022']  # Update years to match the title splitting logic

    download_pdf(BASE_URL, DOWNLOAD_DIR, YEARS)