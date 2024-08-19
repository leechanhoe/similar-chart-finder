from sqlalchemy import text
from pyfile.data_reader import get_stock_code, get_compared_code_list
from pyfile.db_engine import get_engine, get_redis
import pandas as pd
import io
import logging
import datetime

none_stock_data = pd.DataFrame()

# 특정 종목의 주가 데이터 조회(DB에 존재하는 모든 기간)
def get_all_date_stock_data(code, market, reupdate=False):
    redis = get_redis()

    code_list = list(set(get_stock_code(market, only_code=True)) | set(get_compared_code_list(market)))
    if code not in code_list:
        logging.info(f"{code}라는 종목은 없음")
        return none_stock_data
    
    price_data = redis.get(f'price_data_{market}_{code}')
    if price_data is None or reupdate:
        raw_keys = redis.keys(f'price_data_{market}_*')
        keys_to_delete = set(key.decode('utf-8') for key in raw_keys)  # byte 문자열을 utf-8로 디코드

        for stock_code in code_list:
            stock_data = _get_stock_data_in_database(stock_code, market)
            key = f'price_data_{market}_{stock_code}'
            redis.set(key, stock_data.to_json())
            keys_to_delete.discard(key)

        logging.info(f"Completed updating the cache latest_stock_datas - {market}")
        
        for key in keys_to_delete:
            logging.info(f"{key}")
            redis.delete(key)

        price_data = redis.get(f'price_data_{market}_{code}')

    price_data = pd.read_json(io.StringIO(price_data.decode('utf-8')), dtype={'code': str})
    if len(price_data) == 0:
        return none_stock_data
    
    return price_data

# DB에서 주가 데이터를 start_date부터 end_date까지 가져오기
def get_stock_data_start_end(code, market, start_date, end_date=pd.Timestamp.now().strftime('%Y-%m-%d')):
    valid_code_list = list(set(get_stock_code(market, only_code=True)) | set(get_compared_code_list(market)))
    if code not in valid_code_list:
        logging.info(f"{code}라는 종목은 없음")
        return none_stock_data

    stock_data = get_all_date_stock_data(code, market)

    if isinstance(start_date, datetime.date):
        start_date = start_date.strftime('%Y-%m-%d')
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    return stock_data.loc[start_date:end_date]

# DB에서 특정 종목의 주가 데이터를 특정일 기준으로 앞 preceding 거래일치 ~ 뒤 following 거래일치만큼 가져오기
# date는 YYYY-MM-DD 형식의 문자열
def get_stock_data_pre_fol(code, date, market, preceding=0, following=0):
    valid_code_list = list(set(get_stock_code(market, only_code=True)) | set(get_compared_code_list(market)))
    if code not in valid_code_list:
        logging.info(f"{code}라는 종목은 없음")
        return none_stock_data
    
    if isinstance(date, datetime.date):
        date = date.strftime('%Y-%m-%d')
    stock_data = get_all_date_stock_data(code, market)
    target_date = pd.to_datetime(date)

    # 주어진 date부터 하루씩 앞으로 이동하면서 유효한 날짜 찾기
    while target_date not in stock_data.index and target_date >= stock_data.index.min():
        target_date -= pd.Timedelta(days=1)

    if target_date not in stock_data.index:
        logging.info(f"{date}부터 유효한 데이터가 존재하지 않습니다.")
        return none_stock_data

    target_date = target_date.strftime('%Y-%m-%d')
    pos = stock_data.index.get_loc(target_date)
    start_pos = max(0, pos - preceding)
    end_pos = min(len(stock_data), pos + following + 1)
    return stock_data.iloc[start_pos:end_pos]

# 레디스를 거치지 않고 특정 종목의 주가 데이터 DB에서 조회(모든 기간)
def _get_stock_data_in_database(code, market):
    engine = get_engine()

    query = text(f"""
        SELECT * 
        FROM stock_data_{market}
        WHERE code = :code
        ORDER BY date ASC
    """)

    df = pd.read_sql_query(query, engine, params={'code': code})
    df.rename(columns={
        'code': 'Code',
        'date': 'Date',
        'open_price': 'Open',
        'high_price': 'High',
        'low_price': 'Low',
        'close_price': 'Close',
        'volume': 'Volume',
        'change_rate': 'Change'
    }, inplace=True)

    df.set_index('Date', inplace=True)
    df.drop('Code', axis=1, inplace=True)
    df.index = pd.to_datetime(df.index)
    return df

# DB에서 모든 종목의 주가 데이터를 특정일 기준으로 앞 preceding 거래일치 ~ 뒤 following 거래일치만큼 가져오기
def get_stock_data_pre_fol_all(date, market, preceding=0, following=0, all_date=False):
    engine = get_engine()

    if all_date:
        # SQL 쿼리 작성 - 필요한 거래일에 해당하는 모든 종목의 데이터 가져오기
        query_range = text(f"""
            SELECT * 
            FROM stock_data_{market}  
            ORDER BY code ASC, date ASC
        """)

        # SQL 쿼리 실행 및 결과 DataFrame으로 가져오기 (필요한 거래일만 선택)
        df_range=pd.read_sql_query(query_range, engine)
    else:
        # SQL 쿼리 작성 - 해당 종목의 모든 거래일 가져오기
        query = text(f"""
            SELECT DISTINCT date 
            FROM stock_data_{market} 
            ORDER BY date ASC
        """)

        if isinstance(date, datetime.date):
            date = date.strftime('%Y-%m-%d')

        # SQL 쿼리 실행 및 결과 DataFrame으로 가져오기
        df_all_dates = pd.read_sql_query(query, engine) # SQL 쿼리 작성 - 모든 종목의 날짜 데이터 가져오기
        date = pd.to_datetime(date).date()
        idx = 0
        # 입력받은 날짜가 데이터에 있는지 확인
        if not df_all_dates[df_all_dates['date'] == date].empty:
            idx = df_all_dates.index[df_all_dates['date'] == date][0]

        else:
            # 입력받은 날짜와 가장 근접한 과거의 날짜 찾기 (입력받은 날짜가 없는 경우)
            nearest_past_date = df_all_dates[df_all_dates['date'] < date].max()['date']
            
            if pd.isna(nearest_past_date):
                logging.info(f"No data found date {date}")
                return none_stock_data

            idx = df_all_dates.index[df_all_dates['date'] == nearest_past_date][0]

        # 필요한 거래일만 선택하기
        start_date = df_all_dates.iloc[max(0,idx-preceding)]['date']
        end_date = df_all_dates.iloc[min(len(df_all_dates)-1, idx+following)]['date']

        # SQL 쿼리 작성 - 필요한 거래일에 해당하는 모든 종목의 데이터 가져오기
        query_range = text(f"""
            SELECT * 
            FROM stock_data_{market} 
            WHERE date BETWEEN :start_date AND :end_date 
            ORDER BY code ASC, date ASC
        """)

        # SQL 쿼리 실행 및 결과 DataFrame으로 가져오기 (필요한 거래일만 선택)
        df_range=pd.read_sql_query(query_range, engine, params={'start_date':start_date,'end_date':end_date})

    df_range.rename(columns={
        'code': 'Code',
        'date': 'Date',
        'open_price': 'Open',
        'high_price': 'High',
        'low_price': 'Low',
        'close_price': 'Close',
        'volume': 'Volume',
        'change_rate': 'Change'
    }, inplace=True)

    result_dict={}
    code_list = get_stock_code(market, True)
    for code, group in df_range.groupby('Code'):
        if code not in code_list:
            continue
        group.set_index('Date', inplace=True)
        group.drop('Code', axis=1, inplace=True)
        group.index = pd.to_datetime(group.index)
        result_dict[code]=group

    return result_dict