import pandas as pd
import FinanceDataReader as fdr
import exchange_calendars as ecals
import pytz
import os
import logging
import time
from get_stock_data import get_stock_data_fdr
from pyfile.data_reader import get_stock_code, update_cache_code_name_industry_url, get_engine
from pyfile.data_reader import get_compared_code_list, get_snp500_list
from pyfile.stock_data_reader import get_all_date_stock_data
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from pyfile.web_scraping import update_investing_url

# 휴장일인지 체크
def is_market_open(date, market, max_retries=5, retry_delay=3):
    date = date.strftime('%Y-%m-%d')
    date_str = date
    date = pd.Timestamp(date)

    if market == "nyse_naq":
        calendar = ecals.get_calendar('XNYS')

        for attempt in range(max_retries):
            try:
                all_open_date = get_stock_data_fdr("IXIC", "2000-01-01", date_str, market).index[:].strftime('%Y-%m-%d').tolist()
                break  # 성공 시 루프를 빠져나감
            except Exception as e:
                logging.info(f"is_market_open - error \n {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)  # 재시도 전 대기
                else:
                    raise  # 최대 재시도 횟수에 도달하면 예외를 다시 던짐

    if calendar.is_session(date) and date_str in all_open_date:
        logging.info(f"Market is open")
        return True  # Market is open
    else:
        logging.info(f"Market is closed")
        return False  # Market is closed

# 종목 코드 리스트 업데이트
def update_code_list(market):
    logging.info(f"start update_code_list_{market}")
    engine = get_engine()
    lang = 'en'

    max_attempts = 100
    for i in range(max_attempts):
        try:
            df_codes_nyse = fdr.StockListing('NYSE')
            df_codes_nasdaq = fdr.StockListing('NASDAQ')
            # 성공적으로 데이터를 불러왔다면 반복문을 빠져나갑니다.
            break
        except Exception as e:
            logging.info(f"Attempt {i+1}/{max_attempts} failed. Error: {e}")
            if i < max_attempts - 1:  # 마지막 시도가 아니라면
                logging.info("Waiting for 10 seconds before retrying.")
                time.sleep(3)  # 3초 대기 후 재시도
            else:
                logging.info("All attempts failed. Please check your network connection or the server status.")
                return
            
    # 알파벳으로만 이루어진 symbol만 취급 (알파벳이 아닌건 우선주)
    df_codes_nyse = df_codes_nyse[df_codes_nyse['Symbol'].apply(lambda x: x.isalpha())]
    df_codes_nyse = df_codes_nyse.reset_index(drop=True)

    df_codes_nasdaq = df_codes_nasdaq[df_codes_nasdaq['Symbol'].apply(lambda x: x.isalpha())]
    df_codes_nasdaq = df_codes_nasdaq.reset_index(drop=True)

    # 각 데이터프레임에 'rank' 열 추가
    df_codes_nyse['Rank'] = df_codes_nyse.index + 1
    df_codes_nasdaq['Rank'] = df_codes_nasdaq.index + 1

    df_codes = pd.concat([df_codes_nasdaq, df_codes_nyse])
    df_codes = df_codes.drop_duplicates(subset='Symbol')

    if len(df_codes) < 1000: # 종목 개수가 1000개 이하면 라이브러리 버그 의심
        logging.warn(f"update_code_list_{market} 종목 개수 경고 : {len(df_codes)}개 - 오류 의심")
        raise Exception(f"종목 개수가 {len(df_codes)}개로, 정상적이지 않습니다. 오류를 확인하세요.")

    df_codes = df_codes.rename(columns={'Symbol': 'Code'})
    df_codes = df_codes[['Code', 'Name', 'Rank', 'Industry']]
    df_codes['Industry'] = df_codes['Industry'].replace('', '정보 없음').fillna('정보 없음')
    df_codes = df_codes.reset_index(drop=True)
    df_codes.rename(columns={'Code': 'code', 'Name': f'name_{lang}', 'Rank': 'ranking', 'Industry' : f'industry_ko'}, inplace=True)
    
    # Get existing stock codes from the database
    query = f"""
    SELECT 
        scl.code, 
        sn.name_{lang},
        scl.ranking,
        si.industry_ko
    FROM 
        stock_code_list_{market} AS scl
    LEFT OUTER JOIN 
        stock_name_{market} AS sn ON scl.code = sn.code
    LEFT OUTER JOIN 
        stock_industry_{market} AS si ON scl.code = si.code
    """
    db_stock_data_df = pd.read_sql(query, engine)
    
    # Find newly listed stocks and add them to the table.
    new_stocks_df = df_codes[~df_codes['code'].isin(db_stock_data_df['code'])]
    duplicated_df = new_stocks_df[new_stocks_df.duplicated('code', keep=False)]
    logging.info(f"duplicated code : {duplicated_df}")
    new_stocks_df = new_stocks_df.drop_duplicates('code', keep='first')

    new_stocks_df[['code', 'ranking']].to_sql(f'stock_code_list_{market}', con=engine, if_exists='append', index=False)
    new_stocks_df[['code', f'name_{lang}']].to_sql(f'stock_name_{market}', con=engine, if_exists='append', index=False)
    new_stocks_df[['code', f'industry_ko']].to_sql(f'stock_industry_{market}', con=engine, if_exists='append', index=False)
    update_investing_url(new_stocks_df['code'].values, market)

    # Find delisted stocks and remove them from the table.
    delisted_stocks_df = db_stock_data_df[~db_stock_data_df['code'].isin(df_codes['code'])]
    with engine.begin() as connection:
        query = text(f"DELETE FROM stock_code_list_{market} WHERE code=:code")
        for idx, row in delisted_stocks_df.iterrows():
            connection.execute(query, {"code": row['code']})

        common_stocks_db_set = db_stock_data_df[db_stock_data_df['code'].isin(df_codes['code'])]
        common_stocks_fdr_set = df_codes[df_codes['code'].isin(db_stock_data_df['code'])]
        columns_to_update = [(f'name_{lang}', 'stock_name'), ('ranking', 'stock_code_list'), (f'industry_ko', 'stock_industry')]
        for column, table_name in columns_to_update:
            # Rename the column for merging
            common_stocks_db_set = common_stocks_db_set.rename(columns={column: f'old_{column}'})
            common_stocks_fdr_set = common_stocks_fdr_set.rename(columns={column: f'new_{column}'})
            
            # Merge the two dataframes on 'code'
            merged_df = pd.merge(common_stocks_db_set, common_stocks_fdr_set, on='code')
            
            # Find rows where the column value has changed
            changed_df = merged_df[merged_df[f'old_{column}'] != merged_df[f'new_{column}']]
            
            for idx, row in changed_df.iterrows():
                stmt = text(f"UPDATE {table_name}_{market} SET {column}= :value WHERE code= :code")
                connection.execute(stmt, {"value": row[f'new_{column}'], "code": row['code']})
            
            # Revert the column name change for the next iteration
            common_stocks_db_set = common_stocks_db_set.rename(columns={f'old_{column}': column})
            common_stocks_fdr_set = common_stocks_fdr_set.rename(columns={f'new_{column}': column})

        if len(db_stock_data_df) == 0: # db가 초기상태이면 RANK 1000 초과는 제외
            query = text(f"UPDATE stock_code_list_{market} SET valid = false WHERE ranking > 1000")
            connection.execute(query)

        connection.execute(text("COMMIT;"))

    update_cache_code_name_industry_url(market)
    get_snp500_list(cache_update=True)

# 최신 날짜의 주가 데이터 조회 (증자, 감자, 분할등의 체크를 위해)
def get_latest_stock_data(base_date, df_codes, day_ago_close, market):
    engine = get_engine()

    latest_date_query = f"""
        SELECT MAX(date) as latest_date 
        FROM stock_data_{market}
        """
    start_date = pd.read_sql_query(latest_date_query, engine).iat[0,0].strftime('%Y-%m-%d')
    end_date = base_date.strftime('%Y-%m-%d')
    base_date = base_date.strftime('%Y-%m-%d')

    df_list = []
    invalid = []
    reupdate = []
    # NYSE 종목들의 최신 주가 데이터 가져오기
    for i, row in df_codes.iterrows():
        code = row['code']
        
        stock_price = get_stock_data_fdr(code, start_date, end_date, market)
        if len(stock_price) == 0:
            invalid.append(code)
            continue

        stock_price['Code'] = code
        if code not in day_ago_close.keys():
            if len(stock_price) == 1:
                try:
                    df_list.append(stock_price.loc[base_date].to_frame().T)
                except KeyError as e:
                    logging.info(f"KeyError - {code} 에서 {base_date} 의 주가데이터가 없음")
                    invalid.append(code)
            elif len(stock_price) == 2:
                logging.info(f"{code} - db에 이전 데이터가 없었는데 라이브러리로 2일치 불러옴")
                invalid.append(code)
        else:
            if len(stock_price) == 1 or round(day_ago_close[row['code']], 2) == round(stock_price.loc[start_date]['Close'], 2):
                try:
                    df_list.append(stock_price.loc[base_date].to_frame().T)
                except KeyError as e:
                    logging.info(f"KeyError - {code} 에서 {base_date} 의 주가데이터가 없음")
                    invalid.append(code)
            else:
                reupdate.append(code)
        time.sleep(0.2)
    logging.info(f"all {market} stock data loaded - {base_date}")

    df = pd.concat(df_list, ignore_index=True)
    return df, reupdate, invalid

# 주가 데이터를 DB에 삽입
def insert_all_price_data(code, new_data_df, market, connection):
    if new_data_df.empty:
        logging.info(f"{code}'s new_data_df is empty")
        return
    
    rows_to_insert = [{
        "code": code,
        "date": idx.strftime('%Y-%m-%d'),
        "open_price" :row['Close'] if row['Open'] == 0 else row['Open'],
        "high_price" :row['Close'] if row['High'] == 0 else row['High'],
        "low_price" :row['Close'] if row['Low'] == 0 else row['Low'],
        "close_price" :row['Close'],
        "volume" :None if pd.isna(row['Volume']) else int(row['Volume']),
        "change_rate" :None if pd.isna(row['Change']) else row['Change']}
        for idx,row in new_data_df.iterrows()]

    if len(rows_to_insert) > 0:
        insert_query=f""" INSERT INTO `stock_data_{market}` (`code`, `date`, `open_price`, `high_price`,
                        `low_price`, `close_price`,`volume`,`change_rate`)
                        VALUES (:code,:date,:open_price,:high_price,:low_price,:close_price,
                        :volume,:change_rate)"""
        try:
            connection.execute(text(insert_query), rows_to_insert)
        except Exception as e:
            logging.info(f"{code}, 에서 {e} 오류 발생")
            return

# 주가 데이터 업데이트
def update_stock_data(base_date, market, month=130, recreate=False):
    logging.info(f"start update_stock_data_{market}")
    engine = get_engine()
    df_codes = get_stock_code(market)

    end_date = base_date.strftime('%Y-%m-%d')
    start_date = (base_date - relativedelta(months=month)).strftime('%Y-%m-%d')
    start_date2 = (base_date - relativedelta(months=12)).strftime('%Y-%m-%d')

    with engine.begin() as connection:
        if recreate:
            connection.execute(text(f"DELETE FROM stock_data_{market}"))

        count_records_query_result = connection.execute(
            text(f"SELECT COUNT(*) FROM stock_data_{market} LIMIT 1"))
        count_records_total = count_records_query_result.fetchone()[0]

        data_len = 0
        if count_records_total == 0: # 데이터베이스에 데이터가 없는상태면 다 넣어주기
            invalid = []
            compared_code_list = get_compared_code_list(market)
            if len(compared_code_list) != 0:
                # comparison 테이블에 비교당한 코드면 11년치 데이터를 모두 가지고 있도록 compared라는 열로 comparison 테이블에 속한여부확인
                df_codes['compared'] = df_codes['code'].isin(compared_code_list) | (df_codes['ranking'] <= int(os.getenv('COMPARED_STOCK_NUM')))
            else: # comparison 테이블이 초기상태라 아무것도 없으면 디폴트로 시총 800위 이하만 11년치 가져오기
                df_codes['compared'] = df_codes['ranking'] <= int(os.getenv('COMPARED_STOCK_NUM'))

            today = base_date.strftime('%Y-%m-%d')
            for idx, row in df_codes.iterrows():
                code = row['code']
                start = start_date if row['compared'] else start_date2
                new_data_df = get_stock_data_fdr(code, start, end_date, market)
                data_len += len(new_data_df)
                if len(new_data_df) == 0:
                    invalid.append(code)
                    continue

                # 'change_rate' 계산을 위한 'Adj Close'의 이전 행 값 계산
                new_data_df['Prev Close'] = new_data_df['Close'].shift(1)
                # 'change_rate' 계산
                new_data_df['Change'] = (new_data_df['Close'] - new_data_df['Prev Close']) / new_data_df['Prev Close']
                insert_all_price_data(code, new_data_df, market, connection)
                time.sleep(0.1)

            query = text(f"UPDATE stock_code_list_{market} SET valid=0, failed_to_load=1 WHERE code=:code")
            for code in invalid:
                connection.execute(query, {"code": code})
            logging.info(f"유효하지 않은 종목 {len(invalid)}개")
            logging.info(f"all {market} stock data loaded - {start} ~ {today}")
            
            update_cache_code_name_industry_url(market)

        else: # 데이터베이스가 초기화가 된 보통 상태이면 최신일자의 데이터만 넣기
            if not is_market_open(base_date, market):
                return
            
            #지정기간이 지난 데이터 삭제
            query = text(f"""
            DELETE FROM stock_data_{market}
            WHERE date < '{start_date}';
            """)
            connection.execute(query)

            # 최신 date의 code와 close_price를 조회하는 SQL 쿼리
            # 미국시장 최신 데이터는 change 정보가 없어 직접 전 거래일과 비교하여 생성
            query = f"""
            SELECT code, close_price 
            FROM stock_data_{market} 
            WHERE date = (SELECT max(date) FROM stock_data_{market})
            """
            df = pd.read_sql_query(query, connection)
            day_ago_close = df.set_index('code')['close_price'].to_dict()
            latest_df, reupdate, invalid = get_latest_stock_data(base_date, df_codes, day_ago_close, market)
            latest_df = latest_df[latest_df['Code'].isin(df_codes['code'].values)]
            duplicated_rows = latest_df[latest_df.duplicated(subset='Code', keep=False)]
            logging.info(f"duplicated_rows\n{duplicated_rows}")
            latest_df = latest_df.drop_duplicates(subset='Code')

            if reupdate:
                # 유상증자, 무상증자, 액면분할로 주가가 변경된 데이터는 삭제
                change_codes_str = ', '.join([f"'{code}'" for code in reupdate])
                delete_query = text(f"""
                DELETE FROM stock_data_{market} 
                WHERE code IN ({change_codes_str})
                """)
                connection.execute(delete_query)

            for code in reupdate:
                logging.info(f"유상증자, 무상증자, 액면분할로 주가가 변경된 종목 : {code}")
                new_data_df = get_stock_data_fdr(code, start_date, end_date, market) # 일단 11년치 다 불러오기 (어차피 주말에 조정됨)

                if len(new_data_df) == 0:
                    logging.info(f"{code} 의 정보가 없음")
                    invalid.append(code)
                    continue

                # 'change_rate' 계산을 위한 'Adj Close'의 이전 행 값 계산
                new_data_df['Prev Close'] = new_data_df['Close'].shift(1)
                # 'change_rate' 계산
                new_data_df['Change'] = (new_data_df['Close'] - new_data_df['Prev Close']) / new_data_df['Prev Close']
                insert_all_price_data(code, new_data_df, market, connection)
                time.sleep(0.2)
                
            query = text(f"UPDATE stock_code_list_{market} SET valid=0, failed_to_load=1 WHERE code=:code")
            for code in list(set(invalid)):
                connection.execute(query, {"code": code})
            logging.info(f"유효하지 않은 종목 {len(invalid)}개")
            
            today = base_date.strftime('%Y-%m-%d')
            logging.info(f"nan list \n {latest_df[latest_df.isna().any(axis=1)]}")
            latest_df = latest_df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'], how='all')
            
            rows_to_insert_today = [{
                "code": row['Code'],
                "date": today,
                "open_price" : None if pd.isna(row['Open']) else (row['Close'] if row['Open'] == 0 else row['Open']),
                "high_price" : None if pd.isna(row['High']) else (row['Close'] if row['High'] == 0 else row['High']),
                "low_price" : None if pd.isna(row['Low']) else (row['Close'] if row['Low'] == 0 else row['Low']),
                "close_price" :None if pd.isna(row['Close']) else row['Close'],
                "volume" :None if pd.isna(row['Volume']) else int(row['Volume']),
                "change_rate" :None if row['Code'] not in day_ago_close.keys() else (row['Close'] - day_ago_close[row['Code']]) / day_ago_close[row['Code']]}
                for idx, row in latest_df.iterrows()]

            insert_query=f""" INSERT INTO `stock_data_{market}` (`code`, `date`, `open_price`, `high_price`,
                            `low_price`, `close_price`,`volume`,`change_rate`)
                            VALUES (:code,:date,:open_price,:high_price,:low_price,:close_price,
                            :volume,:change_rate)"""
            
            connection.execute(text(insert_query), rows_to_insert_today)

            data_len = len(latest_df)

        if data_len == 0:
            connection.execute(text("ROLLBACK;"))
            raise Exception(f"삽입된 주가데이터가 없습니다.")
        
        # 가끔 고가와 저가가 적용이 잘 안되는 경우가 발생해서 제데로 적용해주기
        query = text(f"update stock_data_{market} set high_price = open_price where open_price > high_price;")
        connection.execute(query)
        query = text(f"update stock_data_{market} set low_price = open_price where open_price < low_price;")
        connection.execute(query)
        query = text(f"update stock_data_{market} set high_price = close_price where close_price > high_price;")
        connection.execute(query)
        query = text(f"update stock_data_{market} set low_price = close_price where close_price < low_price;")
        connection.execute(query)

        connection.execute(text("COMMIT;"))

    get_all_date_stock_data(code, market, reupdate=True)

# 일광 절약 시간제 적용 체크
def is_dst():
    # 현재 시간을 UTC로 가져옵니다.
    now_utc = datetime.now(pytz.timezone('UTC'))
    # UTC 시간을 미국 동부 시간으로 변환합니다.
    now_est = now_utc.astimezone(pytz.timezone('America/New_York'))
    # 현재 시간이 일광 절약 시간제(Daylight Saving Time, DST)를 적용하고 있는지 확인합니다.
    return now_est.dst() != timedelta(0)