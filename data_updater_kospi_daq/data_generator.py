import pandas as pd
import FinanceDataReader as fdr
import exchange_calendars as ecals
import logging
import os
import time
import requests
from pyfile.data_reader import (
    get_stock_code,
    update_cache_code_name_industry_url,
    get_engine,
)
from pyfile.data_reader import get_compared_code_list
from pyfile.stock_data_reader import get_all_date_stock_data
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from pyfile.web_scraping import update_investing_url
from get_stock_data import get_stock_data_fdr
from io import BytesIO
from datetime import datetime


def is_market_open(
    date: datetime, market: str, max_retries: int = 5, retry_delay: int = 3
) -> bool:
    """휴장일인지 체크"""

    date = date.strftime("%Y-%m-%d")
    date_str = date
    date = pd.Timestamp(date)

    krx_calendar = ecals.get_calendar("XKRX")

    for attempt in range(max_retries):
        try:
            all_open_date = (
                get_stock_data_fdr("KS11", "2000-01-01", date_str, market)
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

    if krx_calendar.is_session(date) and date_str in all_open_date:
        logging.info(f"Market is open")
        return True  # Market is open
    else:
        logging.info(f"Market is closed")
        return False  # Market is closed


def _get_krx_code() -> None:
    """fdr.StockListing이 오류 발생시 한국 주식 종목 리스트를 불러오는 대체함수"""

    gen_url = "http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
    gen_parms = {
        "mktId": "ALL",
        "share": "1",
        "csvxls_isNo": "false",
        "name": "fileDown",
        "url": "dbms/MDC/STAT/standard/MDCSTAT01901",
    }
    headers = {
        "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020101",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    }
    r = requests.get(url=gen_url, params=gen_parms, headers=headers)

    down_url = "http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
    data = {"code": r.content}
    r = requests.post(url=down_url, data=data, headers=headers)

    stock_code = pd.read_csv(BytesIO(r.content), encoding="cp949")
    stock_code = stock_code[["한글 종목약명", "단축코드", "시장구분", "상장주식수"]]
    stock_code = stock_code.rename(
        columns={
            "시장구분": "Market",
            "한글 종목약명": "Name",
            "단축코드": "Code",
            "상장주식수": "total_shrs",
        }
    )

    stock_code = stock_code.sort_values(by="total_shrs", ascending=False)
    stock_code.reset_index(drop=True, inplace=True)
    return stock_code


def update_code_list(market: str):
    """종목 코드 리스트 업데이트"""

    logging.info(f"start update_code_list_{market}")
    engine = get_engine()
    lang = "ko"

    try:  # fdr.StockListing('KRX')에서 간헐적으로 라이브러리 자체의 오류발생
        df_codes = fdr.StockListing("KRX")
    except Exception as e:
        df_codes = _get_krx_code()
        logging.warning(f"update_code_list_{market} fdr.StockListing error\n{e}")

    if len(df_codes) < 1000:  # 종목 개수가 1000개 이하면 라이브러리 버그 의심
        logging.warning(
            f"update_code_list_{market} 종목 개수 경고 : {len(df_codes)}개 - 오류 의심"
        )
        raise Exception(
            f"종목 개수가 {len(df_codes)}개로, 정상적이지 않습니다. 오류를 확인하세요."
        )

    df_codes = df_codes[df_codes["Market"] != "KONEX"]
    df_codes = df_codes[["Code", "Name"]]
    df_codes = df_codes.reset_index(drop=True)
    df_codes["Rank"] = df_codes.index + 1

    df_industry = pd.read_html(
        "http://kind.krx.co.kr/corpgeneral/corpList.do?method=download",
        header=0,
        encoding="cp949",
    )[0]
    df_industry = df_industry[["종목코드", "업종"]]
    df_industry.rename(columns={"종목코드": "Code", "업종": "Industry"}, inplace=True)

    # 'Code' 열의 데이터를 문자열로 변환하고, 6자리로 맞춥니다.
    df_industry["Code"] = df_industry["Code"].astype(str).str.zfill(6)

    # 업종정보 df_codes에 추가
    df_codes = df_codes.merge(df_industry, on="Code", how="left")
    df_codes["Industry"] = (
        df_codes["Industry"]
        .replace("", "우선주 또는 정보 없음")
        .fillna("우선주 또는 정보없음")
    )
    df_codes.rename(
        columns={
            "Code": "code",
            "Name": f"name_{lang}",
            "Rank": "ranking",
            "Industry": f"industry_ko",
        },
        inplace=True,
    )

    with engine.begin() as connection:
        # 데이터베이스 연결 객체를 함수에 전달하여 트랜잭션 유지
        db_stock_data_df = _get_existing_stock_codes(connection, market, lang)

        # 신규종목 추가
        _add_new_stocks(connection, market, df_codes, db_stock_data_df, lang)

        # 상장폐지된 종목 제거
        _remove_delisted_stocks(connection, market, df_codes, db_stock_data_df)

        # 업데이트가 필요한 종목 정보 수정
        _update_changed_stocks(connection, market, df_codes, db_stock_data_df, lang)

        # 특정 조건에 따라 valid 값을 업데이트
        query = text(
            f"""UPDATE stock_code_list_{market} SET valid = 0 WHERE user_request = 0 AND code IN 
                     (SELECT code FROM stock_industry_{market} WHERE industry_ko = '우선주 또는 정보없음')"""
        )
        connection.execute(query)
        connection.execute(text("COMMIT;"))

    update_cache_code_name_industry_url(market)


def _get_existing_stock_codes(connection, market: str, lang: str) -> pd.DataFrame:
    """데이터베이스에서 기존 주식 코드 조회"""

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


def _add_new_stocks(
    connection,
    market: str,
    df_codes: pd.DataFrame,
    db_stock_data_df: pd.DataFrame,
    lang: str,
):
    """신규 상장된 종목을 데이터베이스에 추가"""

    new_stocks_df = df_codes[~df_codes["code"].isin(db_stock_data_df["code"])]
    new_stocks_df = new_stocks_df.drop_duplicates("code", keep="first")

    new_stocks_df[["code", "ranking"]].to_sql(
        f"stock_code_list_{market}", con=connection, if_exists="append", index=False
    )
    new_stocks_df[["code", f"name_{lang}"]].to_sql(
        f"stock_name_{market}", con=connection, if_exists="append", index=False
    )
    new_stocks_df[["code", f"industry_ko"]].to_sql(
        f"stock_industry_{market}", con=connection, if_exists="append", index=False
    )
    update_investing_url(new_stocks_df["code"].values, market)


def _remove_delisted_stocks(
    connection, market: str, df_codes: pd.DataFrame, db_stock_data_df: pd.DataFrame
):
    """상장 폐지된 종목을 데이터베이스에서 삭제"""

    delisted_stocks_df = db_stock_data_df[
        ~db_stock_data_df["code"].isin(df_codes["code"])
    ]
    query = text(f"DELETE FROM stock_code_list_{market} WHERE code=:code")
    for idx, row in delisted_stocks_df.iterrows():
        connection.execute(query, {"code": row["code"]})


def _update_changed_stocks(
    connection,
    market: str,
    df_codes: pd.DataFrame,
    db_stock_data_df: pd.DataFrame,
    lang: str,
):
    """변경된 종목 정보를 업데이트"""

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
        # Rename the column for merging
        common_stocks_db_set = common_stocks_db_set.rename(
            columns={column: f"old_{column}"}
        )
        common_stocks_fdr_set = common_stocks_fdr_set.rename(
            columns={column: f"new_{column}"}
        )

        # Merge the two dataframes on 'code'
        merged_df = pd.merge(common_stocks_db_set, common_stocks_fdr_set, on="code")

        # Find rows where the column value has changed
        changed_df = merged_df[merged_df[f"old_{column}"] != merged_df[f"new_{column}"]]

        for idx, row in changed_df.iterrows():
            stmt = text(
                f"UPDATE {table_name}_{market} SET {column}= :value WHERE code= :code"
            )
            connection.execute(
                stmt, {"value": row[f"new_{column}"], "code": row["code"]}
            )

        # Revert the column name change for the next iteration
        common_stocks_db_set = common_stocks_db_set.rename(
            columns={f"old_{column}": column}
        )
        common_stocks_fdr_set = common_stocks_fdr_set.rename(
            columns={f"new_{column}": column}
        )


def _insert_all_price_data(code, new_data_df, market, connection):
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


def _get_latest_stock_data(base_date, df_codes, day_ago_close, market):
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
            # 신규상장종목이거나 or db에 있는 전날 가격과 새로 불러운 전날 가격이 같으면 데이터 정합성을 지킨다고 판단
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
        time.sleep(0.1)
    logging.info(f"all {market} stock data loaded - {base_date}")

    df = pd.concat(df_list, ignore_index=True)
    return df, reupdate, invalid


def _recreate_stock_data(
    connection, df_codes, market, start_date, start_date2, end_date
):
    """전체 주가 데이터 삭제 후 다시 생성"""

    compared_code_list = get_compared_code_list(market)
    if len(compared_code_list) != 0:
        # comparison 테이블에 비교당한 코드면 11년치 데이터를 모두 가지고 있도록 compared라는 열로 comparison 테이블에 속한 여부 확인
        df_codes["compared"] = df_codes["code"].isin(compared_code_list) | (
            df_codes["ranking"] <= int(os.getenv("COMPARED_STOCK_NUM"))
        )
    else:  # comparison 테이블이 초기 상태라 아무것도 없으면 디폴트로 시총 1000위 이하만 11년치 가져오기
        df_codes["compared"] = df_codes["ranking"] <= int(
            os.getenv("COMPARED_STOCK_NUM")
        )

    invalid = []
    data_len = 0
    for idx, row in df_codes.iterrows():
        code = row["code"]
        start = (
            start_date if row["compared"] else start_date2
        )  # comparison 테이블에 있는 코드면 11년치 데이터
        new_data_df = get_stock_data_fdr(code, start, end_date, market)
        data_len += len(new_data_df)
        if len(new_data_df) == 0:
            invalid.append(code)
            continue

        _insert_all_price_data(code, new_data_df, market, connection)
        time.sleep(0.2)

    query = text(
        f"UPDATE stock_code_list_{market} SET valid=0, failed_to_load=1 WHERE code=:code"
    )
    for code in invalid:
        connection.execute(query, {"code": code})
    logging.info(f"유효하지 않은 종목 {len(invalid)}개")
    logging.info(f"all {market} stock data loaded - {start} ~ {end_date}")

    update_cache_code_name_industry_url(market)
    return data_len


def _update_latest_stock_data(
    connection, df_codes, base_date, market, start_date, end_date
):
    """최신 일자의 데이터만 업데이트"""

    # 지정 기간이 지난 데이터 삭제
    query = text(
        f"""
    DELETE FROM stock_data_{market}
    WHERE date < '{start_date}';
    """
    )
    connection.execute(query)

    logging.info("Insert Only Latest Stock Price Data")

    # 가장 최근 날짜의 종목별 종가 데이터를 가져오는 코드
    latest_closing_prices_query = f"""
    SELECT code, close_price 
    FROM stock_data_{market} 
    WHERE date = (SELECT MAX(date) FROM stock_data_{market})
    """
    latest_closing_prices = pd.read_sql_query(latest_closing_prices_query, connection)

    try:  # fdr.StockListing('KRX')에서 간헐적으로 라이브러리 자체의 오류 발생
        latest_df = fdr.StockListing("KRX")
        latest_df = latest_df[latest_df["Market"] != "KONEX"]
        latest_df = latest_df[latest_df["Code"].isin(df_codes["code"].values)]
        latest_df = latest_df[
            ["Code", "Open", "High", "Low", "Close", "Volume", "ChagesRatio"]
        ]
        latest_df = latest_df.reset_index(drop=True)

        # 종목별 종가 데이터를 코드를 기준으로 딕셔너리로 변환
        latest_closing_dict = latest_closing_prices.set_index("code")[
            "close_price"
        ].to_dict()

        # DB 주가 데이터와 정합성 체크
        reupdate = []
        for idx, row in latest_df.iterrows():
            if row["Code"] in latest_closing_dict:
                # 마지막 종가 데이터와 최신 종가 데이터의 차이를 계산하여 변동률 계산
                close_change = (
                    int(row["Close"]) - latest_closing_dict[row["Code"]]
                ) / latest_closing_dict[row["Code"]]
                # 계산된 변동률과 최신 데이터의 변동률이 다른 경우 (소수점 둘째 자리까지 비교)
                if round(close_change * 100) != round(row["ChagesRatio"]):
                    logging.info(
                        f"{row['Code']}에서 변동률 {round(close_change * 100)} 와 {round(row['ChagesRatio'])} 가 다름"
                    )
                    reupdate.append(row["Code"])

        # 변동률이 다른 종목을 제외하고 최신 데이터 업데이트
        latest_df = latest_df[~latest_df["Code"].isin(reupdate)]

        latest_df["ChagesRatio"] = latest_df["ChagesRatio"] / 100
        latest_df.rename(columns={"ChagesRatio": "Change"}, inplace=True)

    except (
        Exception
    ) as e:  # fdr.StockListing('KRX') 오류 발생 시 다른 로직으로 데이터 업데이트
        logging.warning(f"fdr.StockListing('KRX') error : \n{e}")

        day_ago_close = latest_closing_prices.set_index("code")["close_price"].to_dict()
        latest_df, reupdate, invalid = _get_latest_stock_data(
            base_date, df_codes, day_ago_close, market
        )
        latest_df = latest_df[latest_df["Code"].isin(df_codes["code"].values)]
        latest_df = latest_df.drop_duplicates(subset="Code")

    if reupdate:
        # 유상증자, 무상증자, 액면분할로 주가가 변경된 데이터는 삭제
        change_codes_str = ", ".join([f"'{code}'" for code in reupdate])
        delete_query = text(
            f"""
        DELETE FROM stock_data_{market} 
        WHERE code IN ({change_codes_str})
        """
        )
        connection.execute(delete_query)

    # 유상증자, 무상증자, 액면분할로 주가가 변경된 종목 다시 불러와서 삽입
    for code in reupdate:
        logging.info(f"유상증자, 무상증자, 액면분할로 주가가 변경된 종목 : {code}")
        try:
            new_data_df = get_stock_data_fdr(code, start_date, end_date, market)
        except Exception as e:
            logging.info(f"Error occurred while fetching data for {code}: {e}")
            continue

        _insert_all_price_data(code, new_data_df, market, connection)
        time.sleep(0.3)

    today = base_date.strftime("%Y-%m-%d")
    latest_df["Volume"] = latest_df["Volume"].astype("int", errors="ignore")
    latest_df["Open"] = latest_df["Open"].astype("int", errors="ignore")
    latest_df["High"] = latest_df["High"].astype("int", errors="ignore")
    latest_df["Low"] = latest_df["Low"].astype("int", errors="ignore")
    latest_df["Close"] = latest_df["Close"].astype("int", errors="ignore")
    latest_df["Change"] = latest_df["Change"].astype("float", errors="ignore")
    logging.info(f"nan list \n {latest_df[latest_df.isna().any(axis=1)]}")

    rows_to_insert_today = [
        {
            "code": row["Code"],
            "date": today,
            "open_price": (int(row["Close"]) if row["Open"] == 0 else int(row["Open"])),
            "high_price": (int(row["Close"]) if row["High"] == 0 else int(row["High"])),
            "low_price": (int(row["Close"]) if row["Low"] == 0 else int(row["Low"])),
            "close_price": int(row["Close"]),
            "volume": None if pd.isna(row["Volume"]) else int(row["Volume"]),
            "change_rate": (None if pd.isna(row["Change"]) else float(row["Change"])),
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
    """가격 데이터 수정"""

    # 고가와 저가가 제대로 적용되지 않는 경우를 수정
    adjustments = [
        f"UPDATE stock_data_{market} SET high_price = open_price WHERE open_price > high_price;",
        f"UPDATE stock_data_{market} SET low_price = open_price WHERE open_price < low_price;",
        f"UPDATE stock_data_{market} SET high_price = close_price WHERE close_price > high_price;",
        f"UPDATE stock_data_{market} SET low_price = close_price WHERE close_price < low_price;",
    ]
    for adjustment in adjustments:
        connection.execute(text(adjustment))


def update_stock_data(base_date, market, month=130, recreate=False):
    """주가 데이터 업데이트"""
    logging.info(f"start update_stock_data_{market}")
    engine = get_engine()
    df_codes = get_stock_code(market)

    end_date = base_date.strftime("%Y-%m-%d")
    start_date = (base_date - relativedelta(months=month)).strftime("%Y-%m-%d")
    start_date2 = (base_date - relativedelta(months=12)).strftime(
        "%Y-%m-%d"
    )  # 인기가 없는 종목은 비슷한차트 탐색 시 제외

    with engine.begin() as connection:
        if recreate:
            # 주가 데이터의 무결성을 위해 주기적으로 데이터 전체 삭제 후 전체 다시 생성
            connection.execute(text(f"DELETE FROM stock_data_{market}"))

        count_records_query_result = connection.execute(
            text(f"SELECT COUNT(*) FROM stock_data_{market} LIMIT 1")
        )
        count_records_total = count_records_query_result.fetchone()[0]

        data_len = 0
        if count_records_total == 0:
            # 초기 상태: 데이터베이스에 데이터가 없는 상태면 전체 데이터를 넣어주기
            data_len = _recreate_stock_data(
                connection, df_codes, market, start_date, start_date2, end_date
            )
        else:  # 데이터베이스가 초기화된 상태이면 최신 일자의 데이터만 넣기
            if not is_market_open(base_date, market):
                return
            data_len = _update_latest_stock_data(
                connection, df_codes, base_date, market, start_date, end_date
            )

        if data_len == 0:
            connection.execute(text("ROLLBACK;"))
            raise Exception(f"삽입된 주가 데이터가 없습니다.")

        _adjust_price_data(connection, market)

        # 트랜잭션 커밋은 engine.begin() 블록이 끝날 때 자동으로 이루어집니다.

    get_all_date_stock_data("005930", market, reupdate=True)
