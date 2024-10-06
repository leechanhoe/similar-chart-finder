import pandas as pd
import FinanceDataReader as fdr
import exchange_calendars as ecals
import pytz
import os
import logging
import time
from typing import Dict
from get_stock_data import get_stock_data_fdr
from pyfile.data_reader import (
    get_stock_code,
    update_cache_code_name_industry_url,
    get_engine,
)
from pyfile.data_reader import get_compared_code_list, get_snp500_list
from pyfile.stock_data_reader import get_all_date_stock_data
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from pyfile.web_scraping import update_investing_url


def is_market_open(
    date: datetime, market: str, max_retries: int = 5, retry_delay: int = 3
) -> bool:
    """휴장일인지 체크"""

    date = date.strftime("%Y-%m-%d")
    date_str = date
    date = pd.Timestamp(date)

    if market == "nyse_naq":
        calendar = ecals.get_calendar("XNYS")

        for attempt in range(max_retries):
            try:
                all_open_date = (
                    get_stock_data_fdr("IXIC", "2000-01-01", date_str, market)
                    .index[:]
                    .strftime("%Y-%m-%d")
                    .tolist()
                )
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


def update_code_list(market: str):
    """종목 코드 리스트 업데이트"""

    logging.info(f"start update_code_list_{market}")
    engine = get_engine()
    lang = "en"

    # 주식 코드를 가져옵니다.
    df_codes_nyse, df_codes_nasdaq = _fetch_stock_listings_with_retry()

    # 주식 코드 데이터를 처리합니다.
    df_codes = _process_stock_listings(df_codes_nyse, df_codes_nasdaq, lang, market)

    with engine.begin() as connection:
        # 데이터베이스에서 기존 주식 코드를 가져옵니다.
        db_stock_data_df = _get_existing_stock_codes(connection, market, lang)

        # 신규 상장된 종목을 추가합니다.
        _add_new_stocks(connection, engine, market, df_codes, db_stock_data_df, lang)

        # 상장 폐지된 종목을 제거합니다.
        _remove_delisted_stocks(connection, market, df_codes, db_stock_data_df)

        # 변경된 종목 정보를 업데이트합니다.
        _update_changed_stocks(connection, market, df_codes, db_stock_data_df, lang)

        # 데이터베이스가 초기 상태이면 특정 랭킹 이상의 종목을 비활성화합니다.
        if len(db_stock_data_df) == 0:
            query = text(
                f"UPDATE stock_code_list_{market} SET valid = false WHERE ranking > 1000"
            )
            connection.execute(query)
        connection.execute(text("COMMIT;"))

    # 캐시를 업데이트합니다.
    update_cache_code_name_industry_url(market)
    get_snp500_list(cache_update=True)


def _fetch_stock_listings_with_retry():
    """NYSE와 NASDAQ의 종목 코드를 가져옵니다."""
    max_attempts = 100
    for i in range(max_attempts):
        try:
            df_codes_nyse = fdr.StockListing("NYSE")
            df_codes_nasdaq = fdr.StockListing("NASDAQ")
            break
        except Exception as e:
            logging.info(f"Attempt {i+1}/{max_attempts} failed. Error: {e}")
            if i < max_attempts - 1:
                logging.info("Waiting for 3 seconds before retrying.")
                time.sleep(3)
            else:
                logging.info(
                    "All attempts failed. Please check your network connection or the server status."
                )
                return None, None
    return df_codes_nyse, df_codes_nasdaq


def _process_stock_listings(df_codes_nyse, df_codes_nasdaq, lang, market):
    """주식 코드 데이터를 처리하고 병합합니다."""
    # 알파벳으로만 이루어진 symbol만 취급 (알파벳이 아닌건 우선주)
    df_codes_nyse = df_codes_nyse[df_codes_nyse["Symbol"].apply(lambda x: x.isalpha())]
    df_codes_nyse = df_codes_nyse.reset_index(drop=True)

    df_codes_nasdaq = df_codes_nasdaq[
        df_codes_nasdaq["Symbol"].apply(lambda x: x.isalpha())
    ]
    df_codes_nasdaq = df_codes_nasdaq.reset_index(drop=True)

    # 각 데이터프레임에 'Rank' 열 추가
    df_codes_nyse["Rank"] = df_codes_nyse.index + 1
    df_codes_nasdaq["Rank"] = df_codes_nasdaq.index + 1

    df_codes = pd.concat([df_codes_nasdaq, df_codes_nyse])
    df_codes = df_codes.drop_duplicates(subset="Symbol")

    if len(df_codes) < 1000:
        logging.warning(
            f"update_code_list_{market} 종목 개수 경고 : {len(df_codes)}개 - 오류 의심"
        )
        raise Exception(
            f"종목 개수가 {len(df_codes)}개로, 정상적이지 않습니다. 오류를 확인하세요."
        )

    df_codes = df_codes.rename(columns={"Symbol": "Code"})
    df_codes = df_codes[["Code", "Name", "Rank", "Industry"]]
    df_codes["Industry"] = (
        df_codes["Industry"].replace("", "정보 없음").fillna("정보 없음")
    )
    df_codes = df_codes.reset_index(drop=True)
    df_codes.rename(
        columns={
            "Code": "code",
            "Name": f"name_{lang}",
            "Rank": "ranking",
            "Industry": f"industry_ko",
        },
        inplace=True,
    )
    return df_codes


def _get_existing_stock_codes(connection, market, lang):
    """데이터베이스에서 기존 주식 코드를 조회합니다."""
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
    return pd.read_sql(query, connection)


def _add_new_stocks(connection, engine, market, df_codes, db_stock_data_df, lang):
    """신규 상장된 종목을 데이터베이스에 추가합니다."""
    new_stocks_df = df_codes[~df_codes["code"].isin(db_stock_data_df["code"])]
    duplicated_df = new_stocks_df[new_stocks_df.duplicated("code", keep=False)]
    logging.info(f"duplicated code : {duplicated_df}")
    new_stocks_df = new_stocks_df.drop_duplicates("code", keep="first")

    new_stocks_df[["code", "ranking"]].to_sql(
        f"stock_code_list_{market}", con=engine, if_exists="append", index=False
    )
    new_stocks_df[["code", f"name_{lang}"]].to_sql(
        f"stock_name_{market}", con=engine, if_exists="append", index=False
    )
    new_stocks_df[["code", f"industry_ko"]].to_sql(
        f"stock_industry_{market}", con=engine, if_exists="append", index=False
    )
    update_investing_url(new_stocks_df["code"].values, market)


def _remove_delisted_stocks(connection, market, df_codes, db_stock_data_df):
    """상장 폐지된 종목을 데이터베이스에서 삭제합니다."""
    delisted_stocks_df = db_stock_data_df[
        ~db_stock_data_df["code"].isin(df_codes["code"])
    ]
    query = text(f"DELETE FROM stock_code_list_{market} WHERE code=:code")
    for idx, row in delisted_stocks_df.iterrows():
        connection.execute(query, {"code": row["code"]})


def _update_changed_stocks(connection, market, df_codes, db_stock_data_df, lang):
    """변경된 종목 정보를 업데이트합니다."""
    common_stocks_db_set = db_stock_data_df[
        db_stock_data_df["code"].isin(df_codes["code"])
    ]
    common_stocks_fdr_set = df_codes[df_codes["code"].isin(db_stock_data_df["code"])]
    columns_to_update = [
        (f"name_{lang}", "stock_name"),
        ("ranking", "stock_code_list"),
        (f"industry_ko", "stock_industry"),
    ]
    for column, table_name in columns_to_update:
        # 컬럼명 변경하여 병합 준비
        common_stocks_db_set = common_stocks_db_set.rename(
            columns={column: f"old_{column}"}
        )
        common_stocks_fdr_set = common_stocks_fdr_set.rename(
            columns={column: f"new_{column}"}
        )

        # 'code'를 기준으로 병합
        merged_df = pd.merge(common_stocks_db_set, common_stocks_fdr_set, on="code")

        # 변경된 행 찾기
        changed_df = merged_df[merged_df[f"old_{column}"] != merged_df[f"new_{column}"]]

        for idx, row in changed_df.iterrows():
            stmt = text(
                f"UPDATE {table_name}_{market} SET {column}= :value WHERE code= :code"
            )
            connection.execute(
                stmt, {"value": row[f"new_{column}"], "code": row["code"]}
            )

        # 다음 반복을 위해 컬럼명 복원
        common_stocks_db_set = common_stocks_db_set.rename(
            columns={f"old_{column}": column}
        )
        common_stocks_fdr_set = common_stocks_fdr_set.rename(
            columns={f"new_{column}": column}
        )


def get_latest_stock_data(
    base_date: datetime,
    df_codes: pd.DataFrame,
    day_ago_close: Dict[str, float],
    market: str,
):
    """최신 날짜의 주가 데이터 조회 (증자, 감자, 분할등의 체크를 위해)"""

    engine = get_engine()

    latest_date_query = f"""
        SELECT MAX(date) as latest_date 
        FROM stock_data_{market}
        """
    start_date = (
        pd.read_sql_query(latest_date_query, engine).iat[0, 0].strftime("%Y-%m-%d")
    )
    end_date = base_date.strftime("%Y-%m-%d")
    base_date = base_date.strftime("%Y-%m-%d")

    df_list = []
    invalid = []
    reupdate = []
    # NYSE 종목들의 최신 주가 데이터 가져오기
    for i, row in df_codes.iterrows():
        code = row["code"]

        stock_price = get_stock_data_fdr(code, start_date, end_date, market)
        if len(stock_price) == 0:
            invalid.append(code)
            continue

        stock_price["Code"] = code
        if code not in day_ago_close.keys():
            if len(stock_price) == 1:
                try:
                    df_list.append(stock_price.loc[base_date].to_frame().T)
                except KeyError as e:
                    logging.info(
                        f"KeyError - {code} 에서 {base_date} 의 주가데이터가 없음"
                    )
                    invalid.append(code)
            elif len(stock_price) == 2:
                logging.info(
                    f"{code} - db에 이전 데이터가 없었는데 라이브러리로 2일치 불러옴"
                )
                invalid.append(code)
        else:
            if len(stock_price) == 1 or round(day_ago_close[row["code"]], 2) == round(
                stock_price.loc[start_date]["Close"], 2
            ):
                try:
                    df_list.append(stock_price.loc[base_date].to_frame().T)
                except KeyError as e:
                    logging.info(
                        f"KeyError - {code} 에서 {base_date} 의 주가데이터가 없음"
                    )
                    invalid.append(code)
            else:
                reupdate.append(code)
        time.sleep(0.2)
    logging.info(f"all {market} stock data loaded - {base_date}")

    df = pd.concat(df_list, ignore_index=True)
    return df, reupdate, invalid


def insert_all_price_data(code, new_data_df, market, connection):
    """주가 데이터를 DB에 삽입"""

    if new_data_df.empty:
        logging.info(f"{code}'s new_data_df is empty")
        return

    rows_to_insert = [
        {
            "code": code,
            "date": idx.strftime("%Y-%m-%d"),
            "open_price": row["Close"] if row["Open"] == 0 else row["Open"],
            "high_price": row["Close"] if row["High"] == 0 else row["High"],
            "low_price": row["Close"] if row["Low"] == 0 else row["Low"],
            "close_price": row["Close"],
            "volume": None if pd.isna(row["Volume"]) else int(row["Volume"]),
            "change_rate": None if pd.isna(row["Change"]) else row["Change"],
        }
        for idx, row in new_data_df.iterrows()
    ]

    if len(rows_to_insert) > 0:
        insert_query = f""" INSERT INTO `stock_data_{market}` (`code`, `date`, `open_price`, `high_price`,
                        `low_price`, `close_price`,`volume`,`change_rate`)
                        VALUES (:code,:date,:open_price,:high_price,:low_price,:close_price,
                        :volume,:change_rate)"""
        try:
            connection.execute(text(insert_query), rows_to_insert)
        except Exception as e:
            logging.info(f"{code}, 에서 {e} 오류 발생")
            return


def update_stock_data(base_date, market, month=130, recreate=False):
    """주가 데이터 업데이트"""
    logging.info(f"start update_stock_data_{market}")
    engine = get_engine()
    df_codes = get_stock_code(market)

    end_date = base_date.strftime("%Y-%m-%d")
    start_date = (base_date - relativedelta(months=month)).strftime("%Y-%m-%d")
    start_date2 = (base_date - relativedelta(months=12)).strftime("%Y-%m-%d")

    with engine.begin() as connection:
        if recreate:
            connection.execute(text(f"DELETE FROM stock_data_{market}"))

        count_records_query_result = connection.execute(
            text(f"SELECT COUNT(*) FROM stock_data_{market} LIMIT 1")
        )
        count_records_total = count_records_query_result.fetchone()[0]

        data_len = 0
        if (
            count_records_total == 0
        ):  # 데이터베이스에 데이터가 없는 상태면 전체 데이터를 삽입
            data_len = _initialize_stock_data(
                connection,
                df_codes,
                base_date,
                market,
                start_date,
                start_date2,
                end_date,
            )
        else:  # 데이터베이스에 데이터가 있으면 최신 일자의 데이터만 업데이트
            data_len = _update_latest_stock_data(
                connection, df_codes, base_date, market, start_date, end_date
            )

        if data_len == 0:
            connection.execute(text("ROLLBACK;"))
            raise Exception(f"삽입된 주가데이터가 없습니다.")

        _adjust_price_data(connection, market)

        # 트랜잭션 커밋은 engine.begin() 블록이 끝날 때 자동으로 이루어집니다.

    get_all_date_stock_data("AAPL", market, reupdate=True)


def _initialize_stock_data(
    connection, df_codes, base_date, market, start_date, start_date2, end_date
):
    """초기 주가 데이터 삽입"""
    invalid = []
    compared_code_list = get_compared_code_list(market)
    if len(compared_code_list) != 0:
        df_codes["compared"] = df_codes["code"].isin(compared_code_list) | (
            df_codes["ranking"] <= int(os.getenv("COMPARED_STOCK_NUM"))
        )
    else:
        df_codes["compared"] = df_codes["ranking"] <= int(
            os.getenv("COMPARED_STOCK_NUM")
        )

    today = base_date.strftime("%Y-%m-%d")
    data_len = 0
    for idx, row in df_codes.iterrows():
        code = row["code"]
        start = start_date if row["compared"] else start_date2
        new_data_df = get_stock_data_fdr(code, start, end_date, market)
        data_len += len(new_data_df)
        if len(new_data_df) == 0:
            invalid.append(code)
            continue

        # 'change_rate' 계산을 위한 이전 종가 계산
        new_data_df["Prev Close"] = new_data_df["Close"].shift(1)
        new_data_df["Change"] = (
            new_data_df["Close"] - new_data_df["Prev Close"]
        ) / new_data_df["Prev Close"]
        insert_all_price_data(code, new_data_df, market, connection)
        time.sleep(0.1)

    query = text(
        f"UPDATE stock_code_list_{market} SET valid=0, failed_to_load=1 WHERE code=:code"
    )
    for code in invalid:
        connection.execute(query, {"code": code})
    logging.info(f"유효하지 않은 종목 {len(invalid)}개")
    logging.info(f"all {market} stock data loaded - {start} ~ {today}")

    update_cache_code_name_industry_url(market)

    return data_len


def _update_latest_stock_data(
    connection, df_codes, base_date, market, start_date, end_date
):
    """최신 주가 데이터 업데이트"""
    if not is_market_open(base_date, market):
        return 0

    # 지정 기간이 지난 데이터 삭제
    query = text(
        f"""
    DELETE FROM stock_data_{market}
    WHERE date < '{start_date}';
    """
    )
    connection.execute(query)

    # 최신 종가 데이터를 가져옴
    query = f"""
    SELECT code, close_price 
    FROM stock_data_{market} 
    WHERE date = (SELECT max(date) FROM stock_data_{market})
    """
    df = pd.read_sql_query(query, connection)
    day_ago_close = df.set_index("code")["close_price"].to_dict()
    latest_df, reupdate, invalid = get_latest_stock_data(
        base_date, df_codes, day_ago_close, market
    )
    latest_df = latest_df[latest_df["Code"].isin(df_codes["code"].values)]
    duplicated_rows = latest_df[latest_df.duplicated(subset="Code", keep=False)]
    logging.info(f"duplicated_rows\n{duplicated_rows}")
    latest_df = latest_df.drop_duplicates(subset="Code")

    if reupdate:
        # 주가가 변경된 데이터 삭제
        change_codes_str = ", ".join([f"'{code}'" for code in reupdate])
        delete_query = text(
            f"""
        DELETE FROM stock_data_{market} 
        WHERE code IN ({change_codes_str})
        """
        )
        connection.execute(delete_query)

    for code in reupdate:
        logging.info(f"주가가 변경된 종목 : {code}")
        new_data_df = get_stock_data_fdr(code, start_date, end_date, market)

        if len(new_data_df) == 0:
            logging.info(f"{code} 의 정보가 없음")
            invalid.append(code)
            continue

        # 'change_rate' 계산을 위한 이전 종가 계산
        new_data_df["Prev Close"] = new_data_df["Close"].shift(1)
        new_data_df["Change"] = (
            new_data_df["Close"] - new_data_df["Prev Close"]
        ) / new_data_df["Prev Close"]
        insert_all_price_data(code, new_data_df, market, connection)
        time.sleep(0.2)

    query = text(
        f"UPDATE stock_code_list_{market} SET valid=0, failed_to_load=1 WHERE code=:code"
    )
    for code in list(set(invalid)):
        connection.execute(query, {"code": code})
    logging.info(f"유효하지 않은 종목 {len(invalid)}개")

    today = base_date.strftime("%Y-%m-%d")
    logging.info(f"nan list \n {latest_df[latest_df.isna().any(axis=1)]}")
    latest_df = latest_df.dropna(
        subset=["Open", "High", "Low", "Close", "Volume"], how="all"
    )

    rows_to_insert_today = [
        {
            "code": row["Code"],
            "date": today,
            "open_price": (
                None
                if pd.isna(row["Open"])
                else (row["Close"] if row["Open"] == 0 else row["Open"])
            ),
            "high_price": (
                None
                if pd.isna(row["High"])
                else (row["Close"] if row["High"] == 0 else row["High"])
            ),
            "low_price": (
                None
                if pd.isna(row["Low"])
                else (row["Close"] if row["Low"] == 0 else row["Low"])
            ),
            "close_price": None if pd.isna(row["Close"]) else row["Close"],
            "volume": None if pd.isna(row["Volume"]) else int(row["Volume"]),
            "change_rate": (
                None
                if row["Code"] not in day_ago_close.keys()
                else (row["Close"] - day_ago_close[row["Code"]])
                / day_ago_close[row["Code"]]
            ),
        }
        for idx, row in latest_df.iterrows()
    ]

    insert_query = f""" INSERT INTO `stock_data_{market}` (`code`, `date`, `open_price`, `high_price`,
                        `low_price`, `close_price`, `volume`, `change_rate`)
                        VALUES (:code, :date, :open_price, :high_price, :low_price, :close_price,
                        :volume, :change_rate)"""

    connection.execute(text(insert_query), rows_to_insert_today)

    data_len = len(latest_df)
    return data_len


def _adjust_price_data(connection, market):
    """가격 데이터 조정"""
    # 고가와 저가를 올바르게 수정
    queries = [
        f"UPDATE stock_data_{market} SET high_price = open_price WHERE open_price > high_price;",
        f"UPDATE stock_data_{market} SET low_price = open_price WHERE open_price < low_price;",
        f"UPDATE stock_data_{market} SET high_price = close_price WHERE close_price > high_price;",
        f"UPDATE stock_data_{market} SET low_price = close_price WHERE close_price < low_price;",
    ]
    for query in queries:
        connection.execute(text(query))
