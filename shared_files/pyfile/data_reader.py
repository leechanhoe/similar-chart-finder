from sqlalchemy import text
from pyfile.shared_data import get_day_num_list
from pyfile.statistics_reader import get_statistics_one_stock, get_statistics_stocks, get_valid_statistics_list
from pyfile.db_engine import get_engine, get_redis
import pandas as pd
import json
import io
import logging
import random

# 종목 코드, 종목명, 업종, url정보 등의 레디스 캐시 업데이트
def update_cache_code_name_industry_url(market):
    update_cache_stock_code(market)
    update_cache_stock_code(market, valid=False)
    get_comparable_code_list(market, cache_update=True)
    get_up_down_ranking(market, cache_update=True)
    update_cache_stock_name(market)
    update_cache_stock_industry(market)
    update_cache_investing_url(market)

    if market == 'nyse_naq':
        update_cache_naver_url(market)

# 종목 코드 리스트 레디스 캐시 업데이트
def update_cache_stock_code(market, valid=True):
    redis = get_redis()
    engine = get_engine()

    if valid:
        # Load all data from the table
        df_code = pd.read_sql(f"SELECT code, ranking FROM stock_code_list_{market} WHERE valid=1 ORDER BY ranking", engine)
        key = f"valid_stock_codes_{market}"
        redis.set(key, df_code.to_json())
        logging.info(f"Completed updating the valid_cache_stock_code - {market}")

    else:
        df_code = pd.read_sql(f"SELECT * FROM stock_code_list_{market} ORDER BY ranking", engine)
        code_list = df_code['code'].to_list()
        key = f"all_code_list_{market}"
        redis.set(key, json.dumps(code_list))
        logging.info(f"Completed updating the cache_stock_code - {market}")

    return df_code

# 종목 코드 리스트 반환
def get_stock_code(market, only_code=False, only_valid=True, cache_update=False):
    redis = get_redis()
    engine = get_engine()

    if only_valid:
        key = f"valid_stock_codes_{market}"
        data_json = redis.get(key)
        if data_json is None or cache_update:
            df_code = update_cache_stock_code(market)
        else:
            df_code = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

        return df_code['code'].values if only_code else df_code
    
    else:
        if only_code:
            key = f"all_code_list_{market}"
            code_list = redis.get(key)
            if code_list is None or cache_update:
                code_list = update_cache_stock_code(market, valid=False)
            else:
                # Redis에서 가져온 JSON 문자열을 파이썬 리스트로 변환합니다.
                code_list = json.loads(code_list)
            return code_list
        else:
            df_code = pd.read_sql(f"SELECT * FROM stock_code_list_{market} ORDER BY ranking", engine)
            return df_code

# 종목명 레디스 캐시 업데이트
def update_cache_stock_name(market):
    engine = get_engine()
    redis = get_redis()

    lang = 'ko' if market == 'kospi_daq' else 'en'
    another_lang = 'en' if market == 'kospi_daq' else 'ko' 
    query = text(f"""UPDATE stock_name_{market} SET name_{another_lang} = name_{lang} 
                 WHERE name_{another_lang} = '' OR name_{another_lang} IS NULL""")
    with engine.begin() as connection:
        connection.execute(query) # 공백이나 NULL 처리

    df_name = pd.read_sql(f"""SELECT * FROM stock_name_{market}""", engine)

    key = f"names_{market}"
    redis.set(key, df_name.to_json())
    logging.info(f"Completed updating the cache_stock_name - {market}")
    return df_name

# 종목코드를 인수로 받아 해당하는 종목명 조회
def get_name(code, market, lang):
    redis = get_redis()

    key = f"names_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_name = update_cache_stock_name(market)
    else:
        df_name = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

    try:
        return df_name.loc[df_name['code'] == code, f'name_{lang}'].values[0]
    except IndexError:
        logging.info(f"get_name : 종목 코드 {code}는 존재하지 않습니다.")
        return None

# 모든 종목명 리스트 반환
def get_all_name(market, only_valid=True):
    redis = get_redis()

    key = f"names_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_name = update_cache_stock_name(market)
    else:
        df_name = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})
    if only_valid:
        return df_name[df_name['code'].isin(get_stock_code(market, only_valid=True, only_code=True))]
    else:
        return df_name

# 종목명을 인수로 받아 해당하는 종목코드 조회
def get_code(name, market, lang):
    redis = get_redis()

    key = f"names_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_name = update_cache_stock_name(market)
    else:
        df_name = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

    try:
        return df_name.loc[df_name[f'name_{lang}'] == name, 'code'].values[0]
    except IndexError:
        logging.info(f"get_code : 종목명 {name}는 존재하지 않습니다.")
        return None

# 업종 리스트 레디스 캐시 업데이트
def update_cache_stock_industry(market):
    redis = get_redis()
    engine = get_engine()

    query = text(f"""UPDATE stock_industry_{market} SET industry_en = industry_ko 
                 WHERE industry_en = '' OR industry_en IS NULL""")
    with engine.begin() as connection:
        connection.execute(query) # 공백이나 NULL 처리

    df_industry = pd.read_sql(f"""SELECT * FROM stock_industry_{market} WHERE code IN 
                          (SELECT code FROM stock_code_list_{market} WHERE valid=1)""", engine)

    key = f"industrys_{market}"
    redis.set(key, df_industry.to_json())
    logging.info(f"Completed updating the cache_stock_industry - {market}")
    return df_industry

# 종목 코드를 인수로 받아 해당하는 업종 반환
def get_industry(code, market, lang):
    redis = get_redis()

    key = f"industrys_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_industry = update_cache_stock_industry(market)
    else:
        df_industry = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

    try:
        return df_industry.loc[df_industry['code'] == code, f'industry_{lang}'].values[0]
    except IndexError:
        logging.info(f"get_industry : 종목 코드 {code}는 존재하지 않습니다.")
        return None

# 모든 업종 리스트 반환
def get_all_industry(market, only_valid=False):
    redis = get_redis()
    engine = get_engine()

    if only_valid:
        key = f"industrys_{market}"
        data_json = redis.get(key)
        if data_json is None:
            df_industry = update_cache_stock_industry(market)
        else:
            df_industry = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})
    else:
        query = text(f"""UPDATE stock_industry_{market} SET industry_en = industry_ko 
                    WHERE industry_en = '' OR industry_en IS NULL""")
        with engine.begin() as connection:
            connection.execute(query)

        df_industry = pd.read_sql(f"SELECT * FROM stock_industry_{market}", engine)

    return df_industry

# 인베스팅 url 레디스 캐시 업데이트
def update_cache_investing_url(market):
    redis = get_redis()
    engine = get_engine()

    df_investing_url = pd.read_sql(f"""SELECT * FROM investing_info_{market} WHERE code IN 
                          (SELECT code FROM stock_code_list_{market} WHERE valid=1)""", 
                          engine, dtype={'code': str, 'url': str})

    key = f"investing_url_{market}"
    redis.set(key, df_investing_url.to_json())
    logging.info(f"Completed updating the cache_investing_url - {market}")
    return df_investing_url

# code와 동일업종인 code들 데이터프레임으로 반환
def get_same_industry_code(code, market, num=11, cache_update=False):
    redis = get_redis()

    if cache_update:
        keys_to_delete = redis.keys(f'same_industry_{market}*')
        for key in keys_to_delete:
            redis.delete(key)
        return
            
    industry = get_industry(code, market, 'ko')
    key = f'same_industry_{market}_{industry}'
    same_industry = redis.get(key)
    if same_industry is not None:
        same_industry = pd.read_json(io.StringIO(same_industry.decode('utf-8')), dtype={'code': str})
    else:
        # code와 동일업종인 code들 가져오기
        df_industry = get_all_industry(market, only_valid=True)
        comparable_code_list = get_valid_statistics_list(market)
        df_industry = df_industry[df_industry['code'].isin(comparable_code_list)]
        same_industry_codes = df_industry[df_industry['industry_ko'] == industry]['code'].tolist()
        
        # 개수가 부족하면 code중 아무거나 랜덤으로 채우기
        if len(same_industry_codes) < num:
            other_codes = list(set(comparable_code_list) - set(same_industry_codes))
            if len(other_codes) >= num - len(same_industry_codes):
                same_industry_codes += random.sample(other_codes, num - len(same_industry_codes))
        
        # 시가총액 순위로 정렬
        df_code = get_stock_code(market)[['code', 'ranking']]
        same_industry = df_code[df_code['code'].isin(same_industry_codes)].sort_values(by='ranking')
        
        # 개수가 기준보다 많으면 줄이기
        if len(same_industry) > num:
            same_industry_codes = same_industry.iloc[:num]
        same_industry['average'] = same_industry['code'].apply(get_statistics_one_stock, args=(market, True))

        redis.set(key, same_industry.to_json())

    return same_industry

#인베스팅닷컴의 종목정보 url
def get_investing_url(code, market):
    redis = get_redis()

    key = f"investing_url_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_investing_url = update_cache_investing_url(market)
    else:
        df_investing_url = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

    try:
        return df_investing_url.loc[df_investing_url['code'] == code, f'url'].values[0]
    except IndexError:
        logging.info(f"get_investing_url : 종목 코드 {code}는 존재하지 않습니다.")
        return None

# 네이버 url 레디스 캐시 업데이트
def update_cache_naver_url(market):
    redis = get_redis()
    engine = get_engine()

    df_naver_url = pd.read_sql(f"""SELECT * FROM naver_info_{market} WHERE code IN 
                          (SELECT code FROM stock_code_list_{market} WHERE valid=1)""", engine)

    key = f"naver_url_{market}"
    redis.set(key, df_naver_url.to_json())
    logging.info(f"Completed updating the cache_naver_url - {market}")
    return df_naver_url
    
# 네이버증권의 종목정보 url
def get_naver_url(code, market):
    redis = get_redis()

    key = f"naver_url_{market}"
    data_json = redis.get(key)
    if data_json is None:
        df_naver_url = update_cache_naver_url(market)
    else:
        df_naver_url = pd.read_json(io.StringIO(data_json.decode('utf-8')), dtype={'code': str})

    try:
        return df_naver_url.loc[df_naver_url['code'] == code, f'url'].values[0]
    except IndexError:
        logging.info(f"get_naver_url : 종목 코드 {code}는 존재하지 않습니다.")
        return None
    
# 인베스팅닷컴의 모든 종목정보 페이지 url 가져오기
def get_investing_url_all(market):
    engine = get_engine()

    query = text(f"""SELECT * FROM investing_info_{market}""")
    df = pd.read_sql(query, con=engine, dtype={'code': str, 'url': str})
    return df

# day거래일치 비교는 향후 predict_day거래일 후의 변동을 기준으로 가짐
def get_predict_day(day):
    predict_day = {128 : 10, 64 : 10, 32 : 10, 16 : 5, 8 : 3, 4 : 6}
    return predict_day[day]

# 최신 업데이트 날짜 가져오기
def get_latest_update_date(market):
    redis = get_redis()
    engine = get_engine()

    key = f"latest_update_date_{market}"
    date = redis.get(key)

    if date is None:
        query = text(f"""
        SELECT MAX(date) 
        FROM statistics_{market};""")

        with engine.connect() as connection:
            date_tuple = connection.execute(query).fetchone()
        date = date_tuple[0].strftime('%Y-%m-%d')
        redis.set(key, date)
    else:
        date = date.decode()

    return date

# 8일치 이상 데이터가 있어 비교가 가능한 종목 반환
def get_comparable_code_list(market, cache_update=False):
    redis = get_redis()
    engine = get_engine()

    key = f'comparable_code_list_{market}'
    code_list = redis.get(key)
    if code_list is None or cache_update:
        code_list = pd.read_sql(f"""SELECT code FROM stock_data_{market} WHERE code in 
                                (SELECT code from stock_code_list_{market} WHERE valid = 1) 
                                GROUP BY code HAVING COUNT(*) >= 8""", engine)['code'].to_list()
        redis.set(key, json.dumps(code_list))
        logging.info(f"Completed updating the cache comparable_code_list - {market}")
    else:
        code_list = json.loads(code_list)
    return code_list

# 비교 테이블에 있는 모든 종목 중복없이 가져오기
def get_compared_code_list(market, cache_update=False):
    redis = get_redis()
    engine = get_engine()

    key = f'compared_code_list_{market}'
    code_list = redis.get(key)
    if code_list is None or cache_update:
        query = text(f"""
                    SELECT DISTINCT compare_stock_code FROM comparison_result_8day_{market}
                    UNION
                    SELECT DISTINCT compare_stock_code FROM comparison_result_16day_{market}
                    UNION
                    SELECT DISTINCT compare_stock_code FROM comparison_result_32day_{market}
                    UNION
                    SELECT DISTINCT compare_stock_code FROM comparison_result_64day_{market}
                    UNION
                    SELECT DISTINCT compare_stock_code FROM comparison_result_128day_{market};""")
        code_list = pd.read_sql(query, con=engine)['compare_stock_code'].to_list()
        redis.set(key, json.dumps(code_list))
        logging.info(f"Completed updating the cache compared_code_list - {market}")
    else:
        code_list = json.loads(code_list)

    return code_list

# 상승, 하락 랭킹 불러오기
def get_up_down_ranking(market, lang='ko', cache_update=False):
    redis = get_redis()
    engine = get_engine()

    updown = []
    for change in ['up', 'down']:
        key = f"{change}_ranking_{market}"
        data = redis.get(key)

        if data is None or cache_update:
            sort_key = 'DESC' if change == 'up' else 'ASC'
            query = text(f"""
            SELECT code
            FROM stock_data_{market}
            WHERE date = (
                SELECT MAX(date)
                FROM statistics_{market})
            ORDER BY change_rate {sort_key}
            LIMIT 30""")
            data = pd.read_sql(query, con=engine)
            code_list = data[data['code'].isin(get_valid_statistics_list(market))]['code'].tolist()[:10]
            if len(code_list) == 0:
                return
            data = get_statistics_stocks(code_list, market)
            from pyfile.image_manager import draw_statistics_chart
            draw_statistics_chart(data, market, 64, key)
            redis.set(key, data.to_json())

            logging.info(f"{market} {change} ranking cache is updated")
        else:
            data = pd.read_json(io.StringIO(data.decode('utf-8')), dtype={'code': str})

        data['name'] = data['code'].apply(get_name, args=(market, lang))
        data['average'] = data['average'].round(2)
        data = data.to_dict('records')
        updown.append(data)
    return updown[0], updown[1]

# 특정 종목의 N일치 비교 중 유효한 N들 반환
def get_valid_day_num(code, day_num, market):
    statistics_data = get_statistics_one_stock(code, market)

    non_zero_columns = []  # N들을 저장할 리스트를 초기화합니다.

    # 확인하고 싶은 열들을 리스트로 지정합니다.
    columns_to_check = [f'data_num_{day}day' for day in get_day_num_list(type='str')]

    # 각 열을 순회하면서, 그 열의 값들 중 0이 아닌 것이 있는지 확인합니다.
    for column in columns_to_check:
        if any(statistics_data[column] != 0):  # 만약 0이 아닌 값이 하나라도 있다면,
            n = column.split('_')[2][:-3]  # 열 이름에서 N을 추출합니다.
            if n != str(day_num):
                non_zero_columns.append(n)  # N을 리스트에 추가합니다.
    return non_zero_columns

# snp500의 종목 리스트 반환
def get_snp500_list(cache_update=False):
    redis = get_redis()

    key = 'snp500_list'
    snp500_list = redis.get(key)
    
    if snp500_list is None or cache_update:
        # snp500_list = fdr.StockListing('S&P500')['Symbol'].to_list()
        df_codes = get_stock_code('nyse_naq')
        df_codes = df_codes[df_codes['ranking'] <= 100]
        snp500_list = df_codes['code'].to_list()
        redis.set(key, json.dumps(snp500_list))
    else:
        snp500_list = json.loads(snp500_list)
        
    return snp500_list