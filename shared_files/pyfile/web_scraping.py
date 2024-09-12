import requests
import time
import logging
import pandas as pd
import os
import shutil
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from pyfile.db_engine import get_redis, get_engine
from pyfile.data_reader import get_investing_url_all, get_all_name, get_all_industry, get_stock_code
from pyfile.data_reader import update_cache_stock_name, update_cache_stock_industry, update_cache_investing_url, update_cache_naver_url
from pyfile.image_manager import draw_statistics_chart
from pyfile.statistics_reader import get_statistics_stocks, get_valid_statistics_list
from sqlalchemy import text
from googletrans import Translator
from pyfile.shared_data import get_market_list
from sqlalchemy.exc import OperationalError

# 인기 종목 업데이트 - 상단에 인기 종목 리스트에 사용
def update_popular_stock_all_market():
    for market in get_market_list():
        update_popular_stock(market)
    delete_nginx_cache()
    logging.info("Completed updating the cache_popular_stock")

# 웹 스크래핑으로 현재 인기 종목 top 10 가져오기
def update_popular_stock(market):
    valid_code_list = get_valid_statistics_list(market)
    if len(valid_code_list) == 0:
        return
    
    redis = get_redis()
    if market == 'kospi_daq':
        # 한국
        url = 'https://finance.naver.com/sise/lastsearch2.naver'
        try:
            response = requests.get(url)
        except Exception as e:
            logging.error(f"update_popular_stock_kospi_daq error {e}")
            return
        # BeautifulSoup 객체 생성
        soup = BeautifulSoup(response.text, 'html.parser')
        # class가 "tltle"인 a 태그의 리스트를 가져옴
        tags = soup.find_all('a', {'class': 'tltle'})
        # 각 태그에서 href 속성의 값을 가져와 'code' 파라미터의 값을 리스트에 저장
        kospi_daq_codes = [tag.get('href').split('code=')[-1] for tag in tags]
        kospi_daq_codes = [code for code in kospi_daq_codes if code in valid_code_list]
        kospi_daq_codes = kospi_daq_codes[:10]

        if len(kospi_daq_codes) != 10:
            logging.warn(f"popular_{market}_codes length is not 10: {kospi_daq_codes}")
            kospi_daq_codes = get_stock_code(market, only_code=True)[:10]

        kospi_daq_data = get_statistics_stocks(kospi_daq_codes, market)
        draw_statistics_chart(kospi_daq_data, market, 64, f'popular_ranking_{market}')
        key = f'popular_{market}'
        redis.set(key, kospi_daq_data.to_json())

        logging.info(f"update popular_{market}: {kospi_daq_codes}")
        return kospi_daq_data
    
    elif market == 'nyse_naq':
        # 미국
        url = "https://finance.yahoo.com/markets/stocks/most-active/"
        headers = {"User-Agent": "Mozilla/5.0"}  # investing.com은 헤더가 없으면 접근을 제한합니다.
        try:
            response = requests.get(url, headers=headers)
        except Exception as e:
            logging.error(f"update_popular_stock_nyse_naq error {e}")
            return
        # BeautifulSoup 객체 생성
        soup = BeautifulSoup(response.text, 'html.parser')
        # class가 'CommTable_name__'으로 시작하는 span 태그의 리스트를 가져옴
        tags = soup.find_all('span', {'class': "symbol"})
        # 각 태그에서 텍스트를 가져와 리스트에 저장
        nyse_naq_codes = [tag.text for tag in tags]
        nyse_naq_codes = [code for code in nyse_naq_codes if code in valid_code_list]
        nyse_naq_codes = nyse_naq_codes[:10]

        if len(nyse_naq_codes) != 10:
            logging.warn(f"popular_{market}_codes length is not 10: {nyse_naq_codes}")
            nyse_naq_codes = get_stock_code(market, only_code=True)[:10]

        nyse_naq_data = get_statistics_stocks(nyse_naq_codes, market)
        draw_statistics_chart(nyse_naq_data, market, 64, f'popular_ranking_{market}')
        key = f'popular_{market}'
        redis.set(key, nyse_naq_data.to_json())

        logging.info(f"update popular_{market}: {nyse_naq_codes}")
        return nyse_naq_data

# 웹 스크래핑으로 인베스팅닷컴 url 가져오기
def update_investing_url(code_list, market, recreate=False):
    logging.info("Start updating the investing url")

    # 웹 스크래핑
    base_url = "https://kr.investing.com/search/?q="
    headers = {"User-Agent": "Mozilla/5.0"}  # investing.com은 헤더가 없으면 접근을 제한합니다.
    url_list = {code: "" for code in code_list}
    category = ['주식 - 서울 equities', '주식 - 코스닥 equities', '주식 - 코넥스 equities'] if market == 'kospi_daq' else ['주식 - 나스닥 equities', '주식 - 뉴욕 equities']

    for i, code in enumerate(code_list):
        # investing의 특정 종목의 페이지 url을 알아내기 위한 코드 - 검색창에 검색하여 url을 알아냄
        url = base_url + code
        # 최대 10번 재시도
        for _ in range(10):  
            try:
                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                search_result = soup.find('div', class_='js-inner-all-results-quotes-wrapper newResultsContainer quatesTable')
                if search_result is not None:  # None 검사 추가
                    a = search_result.find_all('a')
                    a = [tag for tag in a if tag.find('span', class_='fourth').get_text() in category]
                    if a:  # None 검사 추가
                        url_list[code] = a[0]['href']
                        logging.info(f"{i}. update url {code} : {a[0]['href']}")
                    else:
                        logging.info(f"No href for {code}")
                else:
                    logging.info(f"No search result for {code}")
                break  # 성공적으로 데이터를 가져오면 재시도 루프를 빠져나옵니다.
            except RequestException as e:
                logging.info(f"Request to {url} failed, retrying {i} in 1 seconds...")
                time.sleep(0.3)  # 잠시 대기 후 재시도합니다.

        time.sleep(0.1)

    data = {'code': list(url_list.keys()), 'url': list(url_list.values())}
    df = pd.DataFrame(data)

    try:
        _save_investing_url_to_db(df, f'investing_info_{market}', recreate)
    except OperationalError as e:
        print(f"Failed to save to database after several retries: {e}")

    update_cache_investing_url(market)
    logging.info("Completed updating the investing url")

def _save_investing_url_to_db(df, table_name, recreate, max_retries=5, delay=2):
    engine = get_engine()

    for attempt in range(max_retries):
        try:
            with engine.begin() as connection:
                if recreate:
                    connection.execute(text(f'DELETE FROM {table_name}'))  # 모든 데이터 삭제
                df.to_sql(table_name, con=connection, if_exists='append', index=False)
            print("Data saved successfully.")
            return
        except OperationalError as e:
            print(f"OperationalError on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # 지수적으로 지연 시간 증가
            else:
                print("Max retries reached. Failed to save to database.")
                raise

# 웹 스크래핑을 활용해 각 종목명의 한국어 & English 저장
def update_translated_name(market):
    logging.info("Start updating the translated names")
    engine = get_engine()
    
    base_url = "https://investing.com" if market == 'kospi_daq' else "https://m.stock.naver.com/worldstock/stock/"
    headers = {"User-Agent": "Mozilla/5.0"}  # investing.com은 헤더가 없으면 접근을 제한합니다.

    df_name = get_all_name(market)
    lang = 'ko' if market == 'kospi_daq' else 'en'
    lang_another = 'en' if market == 'kospi_daq' else 'ko'
    df_name = df_name[['code', f'name_{lang}']]
    df_name[f'name_{lang_another}'] = df_name[f'name_{lang}']

    null_rows = df_name[df_name['code'].isnull()]
    if null_rows.shape[0] > 0:
        raise Exception("Null row(s) exist in the 'code' column of the df_name dataframe", null_rows)

    if market == 'kospi_daq':
        # df_name = df_name.merge(get_investing_url_all(market), on='code', how='left') # investing url을 df_name에 붙이기
        for idx, row in df_name.iterrows():
            try:
                url = f"https://www.forecaster.biz/instrument/ksc/{row['code']}.ks/fundamentals"
            except Exception as e:
                logging.error(f"{base_url} + {row['url']} ? {e}")
                continue
            for i in range(2):
                try:
                    response = requests.get(url, headers=headers)
                    # BeautifulSoup 객체 생성
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # class가 text-[#232526]인 h1 태그의 리스트를 가져옴
                    result = soup.find('h1', {'class': "select-text"})
                    if result is not None:  # None 검사 추가
                        new_name = result.text
                        for check in ['Co.', 'co.', 'CO.']:
                            if check in new_name:
                                new_name = new_name.split(check)[0]
                                break
                        if len(new_name) == 0:
                            logging.warning(f"{idx}. {row['code']}({row[f'name_{lang}']})'s name_{lang_another} is blank!")
                        else:
                            df_name.at[idx, f'name_{lang_another}'] = new_name
                            logging.info(f"{idx}. update name_{lang_another} : {row['code']} to {new_name}")
                            break
                    else:
                        url = f"https://www.forecaster.biz/instrument/koe/{row['code']}.kq/fundamentals"
                        continue

                    logging.info(f"No name for {row['code']}")
                    
                except RequestException as e:
                    logging.info(f"Request to {url} failed, retrying {i} in 1 seconds...")
                    time.sleep(0.3)  # 잠시 대기 후 재시도합니다.

            time.sleep(0.2)
        
    elif market == 'nyse_naq':
        df_name['url'] = ''
        alphabets = ['', '.K', '.O'] + ['.' + alphabet for alphabet in [chr(i) for i in range(ord('A'), ord('Z')+1)]]
        for idx, row in df_name.iterrows():
            for ch in alphabets:
                url = base_url + row['code'] + ch
                try:
                    response = requests.get(url, headers=headers)
                except RequestException as e:
                    logging.info(f"Request to {url} failed: {e}")
                    time.sleep(60)
                # BeautifulSoup 객체 생성
                soup = BeautifulSoup(response.text, 'html.parser')
                meta_og_title = soup.find('meta', {'property': 'og:title'})
                new_name = meta_og_title['content'].split('-')[0].strip()

                if new_name != '네이버페이 증권':
                    if len(new_name) == 0:
                        logging.warning(f"{idx}. {row['code']}({row[f'name_{lang}']})'s name_{lang_another} is blank!")
                    else:
                        df_name.at[idx, f'name_{lang_another}'] = new_name
                        df_name.at[idx, 'url'] = ch
                        logging.info(f"{idx}. update name_{lang_another} : {row['code']} to {new_name}")
                        break  # 성공적으로 데이터를 가져오면 재시도 루프를 빠져나옵니다.

                time.sleep(0.1)

    table_name = f'stock_name_{market}'
    with engine.begin() as connection:
        update_query = text(f"UPDATE {table_name} SET name_{lang_another} = :name_lang_another WHERE code = :code")
        for idx, row in df_name[['code', 'name_ko', 'name_en']].iterrows():
            connection.execute(update_query, {"name_lang_another": row[f'name_{lang_another}'] , "code": row['code']})
        
        if market == 'nyse_naq': # 탐색하며 얻어낸 naver url도 테이블에 저장
            update_query = text(f"""INSERT INTO naver_info_nyse_naq (code, url)
                                    VALUES (:code, :url)
                                    ON DUPLICATE KEY UPDATE url = :url;""")
            for idx, row in df_name[['code', 'url']].iterrows():
                connection.execute(update_query, {"url": row['url'] , "code": row['code']})

        connection.execute(text("COMMIT;"))

    update_cache_stock_name(market)
    if market == 'nyse_naq':
        update_cache_naver_url(market)
    logging.info("Completed updating the translated names")

# 번역 라이브러리를 이용해 업종 영어로 번역
def update_industry_en(market):
    logging.info("Start Updating the industry_en")
    industry_list = get_all_industry(market)['industry_ko'].unique().tolist()
    translator = Translator()
    engine = get_engine()

    with engine.begin() as connection:
        update_query = text(f"""
            UPDATE stock_industry_{market} 
            SET industry_en = :industry_en 
            WHERE industry_ko = :industry_ko""")
        
        for i, industry_ko in enumerate(industry_list):
            if industry_ko is None or len(industry_ko) == 0:
                continue
            try:
                industry_en = translator.translate(industry_ko, dest='en').text
            except Exception as e:
                logging.error(f"Error occurred while translating {industry_ko}: {e}")
                continue
            if 50 < len(industry_en):
                industry_en = industry_en[:50] + '..'
            if 50 < len(industry_ko):
                industry_ko = industry_ko[:50] + '..'
            if len(industry_en) == 0:
                industry_en = 'No Information'

            connection.execute(update_query, {"industry_en": industry_en, "industry_ko": industry_ko})
            logging.info(f"{i}. update industry_ko : {industry_ko} to {industry_en}")
            time.sleep(0.1)
            
        connection.execute(text("COMMIT;"))

    update_cache_stock_industry(market)
    logging.info("Completed updating the industry_en")

# nginx로 저장된 캐시 주기적으로 삭제
def delete_nginx_cache():
    target_dir = '/app/shared_files/nginx_cache/'

    # 디렉토리가 존재하는지 확인
    if os.path.exists(target_dir):
        # 디렉토리 내의 모든 파일/하위 디렉토리 삭제
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')
    else:
        print(f'The directory {target_dir} does not exist')