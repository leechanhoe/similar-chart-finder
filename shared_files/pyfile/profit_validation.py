from pyfile.db_engine import get_redis, get_engine
from sqlalchemy import text, bindparam
from pyfile.data_reader import get_name, get_snp500_list
import pandas as pd
import numpy as np
import logging
import io

VALIDATION_DAY = 10

# score_range 정의
SCORE_RANGES = [
    ("-inf", -4),
    (-3.99, -3),
    (-2.99, -2),
    (-1.99, -1),
    (-0.99, 0),
    (0.01, 0.99),
    (1, 1.99),
    (2, 2.99),
    (3, 3.99),
    (4, 4.99),
    (5, 5.99),
    (6, "inf"),
]
SCORE_RANGE_LABELS = [
    "~ -4",
    "-3.9 ~ -3",
    "-2.9 ~ -2",
    "-1.9 ~ -1",
    "-0.9 ~ 0",
    "0.1 ~ 0.9",
    "1 ~ 1.9",
    "2 ~ 2.9",
    "3 ~ 3.9",
    "4 ~ 4.9",
    "5 ~ 5.9",
    "6 ~",
]
MINUS_LABEL_NUM = 5


# 검증 관련 데이터 갱신
def update_profit_validation(date, market):
    date = date.strftime("%Y-%m-%d")

    insert_new_data(date, market)
    if market == "nyse_naq":
        insert_snp500_profit_validation(date)

    validate_profit(date, market)

    if market == "nyse_naq":
        get_validation_allday(market, "en", "rise", cache_update=True)
        get_validation_allday(market, "ko", "rise", cache_update=True)
        get_validation_allday(market, "en", "fall", cache_update=True)
        get_validation_allday(market, "ko", "fall", cache_update=True)
        get_total_validation(cache_update=True)
        get_all_validation_date(cache_update=True)


# 전체 데이터 한번에 삽입하는 개발용 코드
# def update_profit_validation_all_date(market):
# dates = _get_valid_date(market)
# for d in dates:
#     insert_new_data(d, market)
# for d in dates:
#     _update_score_plus_average(d, market)
# for d in dates:
#     validate_profit(d, market)

# get_snp500_list(cache_update=True)
# dates = _get_valid_date(market)
# for d in dates:
# insert_snp500_profit_validation(d)
# for d in dates:
#     past_date = _get_past_date(d, market)
#     if past_date is None:
#         logging.info(f"No valid date found {VALIDATION_DAY} days before {d}.")
#         continue
#     update_snp500_profit_validation(past_date)


def _get_statistics(date, market):
    engine = get_engine()
    query = text(
        f"""
    SELECT *
    FROM statistics_{market}
    WHERE date = :date"""
    )
    data = pd.read_sql(query, con=engine, params={"date": date})
    return data


def _get_close_price(date, market):
    engine = get_engine()
    query = text(
        f"""
    SELECT code, close_price
    FROM stock_data_{market}
    WHERE date = :date"""
    )
    data = pd.read_sql(query, con=engine, params={"date": date})
    return data


# 전체 기간 전 종목의 평균 점수 반환
def get_average_all_score(market, update_cache=False):
    engine = get_engine()
    redis = get_redis()
    key = f"average_all_score_{market}"
    average_score = redis.get(key)

    if average_score is not None and not update_cache:
        average_score = float(average_score)
    else:
        query = text(
            f"""SELECT AVG(score) AS average_score FROM profit_after_{VALIDATION_DAY}day_{market}"""
        )
        result = pd.read_sql(query, con=engine)

        average_score = result["average_score"].iloc[0]
        average_score = average_score if pd.notna(average_score) else 0
        redis.set(key, str(average_score))

    return round(average_score, 2)


# 특정 날짜의 전 종목 평균 점수 반환
def get_average_score(date, market, update_cache=False):
    engine = get_engine()
    redis = get_redis()
    key = f"average_score_{market}"
    average_score = redis.get(key)

    if average_score is not None and not update_cache:
        average_score = float(average_score)
    else:
        query = text(
            f"""
        SELECT AVG(score) AS average_score 
        FROM profit_after_{VALIDATION_DAY}day_{market} 
        WHERE date = :date"""
        )
        result = pd.read_sql(query, con=engine, params={"date": date})

        average_score = result["average_score"].iloc[0]
        average_score = average_score if pd.notna(average_score) else 0
        redis.set(key, str(average_score))

    return round(average_score, 2)


# 전 기간 평균 점수와 특정 날짜의 평균 점수의 차 반환
def get_average_dif(date, market, update_cache=False):
    redis = get_redis()
    key = f"average_dif_{market}"
    average_dif = redis.get(key)

    if average_dif is not None and not update_cache:
        average_dif = float(average_dif)
    else:
        average_dif = get_average_score(
            date, market, update_cache
        ) - get_average_all_score(market, update_cache)
        redis.set(key, str(average_dif))

    return round(max(min(average_dif, 1.0), -1.0), 1)


# 기존 점수에 전 기간 평균 점수와 해당 날짜의 평균 점수의 차 더하기
def _update_score_plus_average(date, market):
    engine = get_engine()
    average_dif = get_average_dif(date, market, update_cache=True)
    update_query = text(
        f"""
    UPDATE profit_after_{VALIDATION_DAY}day_{market}
    SET score_plus_avg = GREATEST(-10.0, LEAST(score + :average_dif, 10.0))
    WHERE date = :date"""
    )

    with engine.connect() as conn:
        conn.execute(update_query, {"average_dif": average_dif, "date": date})
        conn.execute(text("COMMIT;"))


# 최신 통계 데이터 삽입 (검증은 아직)
def insert_new_data(date, market):
    all_statistics = _get_statistics(date, market)
    all_close_price = _get_close_price(date, market)

    # 필터링: close_price가 NaN인 코드 제거
    all_close_price = all_close_price.dropna(subset=["close_price"])

    # 교집합 코드 찾기
    common_codes = set(all_statistics["code"]).intersection(
        set(all_close_price["code"])
    )

    # 공통 코드에 해당하는 행만 필터링
    all_statistics = all_statistics[all_statistics["code"].isin(common_codes)]
    all_close_price = all_close_price[all_close_price["code"].isin(common_codes)]

    # 필터링: data_num_allday가 45 미만 또는 average_allday가 NaN인 행 제거
    all_statistics = all_statistics[all_statistics["data_num_allday"] >= 45]
    all_statistics = all_statistics.dropna(subset=["average_allday"])
    all_statistics["rise_rate_allday"] = round(
        all_statistics["rise_count_allday"] / all_statistics["data_num_allday"] * 100, 1
    )

    # score 계산
    all_statistics["score"] = all_statistics.apply(
        lambda row: round(
            max(
                min(
                    max(min(row["average_allday"] * 0.7, 5), -5)
                    + (row["rise_rate_allday"] - 50) * 0.2,
                    10.0,
                ),
                -10.0,
            ),
            1,
        ),
        axis=1,
    )

    # 매핑을 위한 close_price dictionary 생성
    price_dict = all_close_price.set_index("code")["close_price"].to_dict()

    # 삽입할 데이터프레임 생성
    all_statistics["base_close_price"] = all_statistics["code"].map(price_dict)
    insert_data = all_statistics[["code", "date", "score", "base_close_price"]].copy()
    insert_data["after_close_price"] = pd.NA
    insert_data["profit"] = pd.NA

    # 데이터베이스에 데이터 삽입
    engine = get_engine()
    insert_data.to_sql(
        f"profit_after_{VALIDATION_DAY}day_{market}",
        con=engine,
        if_exists="append",
        index=False,
    )

    # 캐시 업데이트
    _update_score_plus_average(date, market)

    logging.info(f"profit_after_{VALIDATION_DAY}day_{market} / {date} is inserted")


# 장이 열린 유효날짜 리스트 반환
def _get_valid_date(market):
    engine = get_engine()

    query = f"SELECT DISTINCT date FROM statistics_{market} ORDER BY date;"
    # query = f"SELECT DISTINCT date FROM profit_after_{VALIDATION_DAY}day_{market} ORDER BY date;"
    df_dates = pd.read_sql(query, engine)

    # 날짜 형식을 '%Y-%m-%d'로 변환하고 리스트로 변환
    df_dates["date"] = pd.to_datetime(df_dates["date"])
    date_list = df_dates["date"].dt.strftime("%Y-%m-%d").tolist()
    return date_list


# VALIDATION_DAY 거래일 전의 날짜 반환
def _get_past_date(base_date, market):
    date_list = _get_valid_date(market)
    try:
        index = date_list.index(base_date)
    except ValueError:
        logging.info(f"_get_past_date : invalid date in statistics table - {base_date}")
        return None

    if index >= VALIDATION_DAY:
        return date_list[index - VALIDATION_DAY]
    else:
        return None


# VALIDATION_DAY이 지난 후, 검증 진행하기
def validate_profit(date, market):
    import FinanceDataReader as fdr

    past_date = _get_past_date(date, market)
    if past_date is None:
        logging.info(f"No valid date found {VALIDATION_DAY} days before {date}.")
        return

    # 현재 날짜의 종목별 종가 가져오기
    close_price_now = _get_close_price(date, market)
    close_price_dict = close_price_now.set_index("code")["close_price"].to_dict()
    # 과거 날짜의 종목별 종가 가져오기
    close_price_past = _get_close_price(past_date, market)
    past_close_price_dict = close_price_past.set_index("code")["close_price"].to_dict()

    # 데이터베이스 연결 및 엔진 설정
    engine = get_engine()
    with engine.begin() as conn:

        # 기존 데이터 가져오기
        query = f"SELECT * FROM profit_after_{VALIDATION_DAY}day_{market} WHERE date = '{past_date}'"
        df = pd.read_sql(query, conn)

        # 새로운 after_close_price와 profit 계산
        df["after_close_price"] = df["code"].map(close_price_dict)

        # close_price_dict에 없는 코드에 대해 FinanceDataReader를 사용하여 종가 조회
        missing_codes = df[df["after_close_price"].isna()]["code"].unique()
        for code in missing_codes:
            try:
                stock_data = fdr.DataReader(code, date, date)
            except Exception as e:
                logging.error(f"Error retrieving data for {code}: {e}")
                df = df[df["code"] != code]
                continue

            if stock_data.empty:
                logging.warning(
                    f"No data found for {code} on {past_date}. Removing from dataset."
                )
                df = df[df["code"] != code]  # 데이터가 없으면 해당 행 삭제
            else:
                close_price = stock_data["Close"].iloc[0]
                df.loc[df["code"] == code, "after_close_price"] = close_price

        df["base_close_price"] = (
            df["code"].map(past_close_price_dict).fillna(df["base_close_price"])
        )
        df["profit"] = (
            (df["after_close_price"] - df["base_close_price"])
            / df["base_close_price"]
            * 100
        ).where(pd.notna(df["after_close_price"]), None)

        # 기존 데이터 삭제
        delete_stmt = text(
            f"DELETE FROM profit_after_{VALIDATION_DAY}day_{market} WHERE date = '{past_date}'"
        )
        conn.execute(delete_stmt)

        # 데이터를 다시 삽입
        df.to_sql(
            f"profit_after_{VALIDATION_DAY}day_{market}",
            con=conn,
            if_exists="append",
            index=False,
        )

    if market == "nyse_naq":
        update_snp500_profit_validation(past_date)
    logging.info(
        f"validate profit done for {market} / {date} - {VALIDATION_DAY}days ago : {past_date}"
    )


# 메인 검증 페이지 하단의 상승/하락 목록을 위한 데이터 반환
def get_validation_allday(market, lang, type, cache_update=False):
    engine = get_engine()
    redis = get_redis()
    key = f"validation_allday_{market}_{type}_{lang}"

    data = redis.get(key)
    if data and not cache_update:
        data = pd.read_json(io.StringIO(data.decode("utf-8")), dtype={"date": str})
    else:
        # 특정 점수 구간에 해당하고 snp500_profit_validation 테이블에 있는 종목 데이터프레임 반환
        query = text(
            f"""
            SELECT p.code, p.date, p.score_plus_avg AS score, p.profit
            FROM profit_after_10day_nyse_naq p
            JOIN snp500_profit_validation s
            ON p.date = s.date
            WHERE s.score_range = :target_range
            AND (
                s.all_stock_code LIKE CONCAT('%, ', p.code, ', %')
                OR s.all_stock_code LIKE CONCAT(p.code, ', %')
                OR s.all_stock_code LIKE CONCAT('%, ', p.code)
                OR s.all_stock_code = p.code
            )
            ORDER BY date DESC;"""
        )

        target_range = (
            SCORE_RANGE_LABELS[0] if type == "fall" else SCORE_RANGE_LABELS[-1]
        )
        data = pd.read_sql(query, engine, params={"target_range": target_range})
        data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
        data["formated_date"] = pd.to_datetime(data["date"]).dt.strftime("%y.%m.%d")
        data["name"] = data["code"].apply(get_name, args=("nyse_naq", lang))

        # # profit 열의 dtype을 object로 변경
        data["profit"] = data["profit"].astype(object)
        # 최신 10개의 날짜를 구하고, 해당 날짜의 profit 값을 "D-N" 형식으로 업데이트
        unique_dates = _get_valid_date(market)[-VALIDATION_DAY:]
        for i, date in enumerate(unique_dates):
            d_n_value = f"D-{i+1}"
            data.loc[data["date"] == date, "profit"] = data.loc[
                data["date"] == date, "profit"
            ].apply(lambda x: d_n_value if pd.isna(x) else round(x, 2))

        redis.set(key, data.to_json())
        logging.info(f"{key} cache updated")

    return data


# 해당 code, date에 맞는 [code, date, name, score, profit] 시리즈 반환
# validation/detail 페이지에 사용
def find_one_profit_validation(code, date, market, lang):
    rise_df = get_validation_allday(market, lang, type="rise")
    rise_entry = rise_df[(rise_df["code"] == code) & (rise_df["date"] == date)]
    if not rise_entry.empty:
        return rise_entry.iloc[0].to_dict()

    fall_df = get_validation_allday(market, lang, type="fall")
    fall_entry = fall_df[(fall_df["code"] == code) & (fall_df["date"] == date)]
    if not fall_entry.empty:
        return fall_entry.iloc[0].to_dict()

    return None


# target_date 이전의 최신 날짜의 각 범위별 range_total_num, total_rise_num을 가져오기
# 최신 데이터의 range_total_num, total_rise_num 을 빠르게 계산하기 위함
def _get_latest_range_total_counts(target_date, engine):
    query_prev_day = text(
        """
        SELECT MAX(date) AS previous_date
        FROM snp500_profit_validation
        WHERE date < :target_date
    """
    )
    prev_date_result = pd.read_sql(
        query_prev_day, engine, params={"target_date": target_date}
    )
    previous_date = prev_date_result["previous_date"].iloc[0]

    if pd.isnull(previous_date):
        # 최신 데이터가 없으면 초기화
        return {
            label: {"range_total_num": 0, "total_rise_num": 0}
            for label in SCORE_RANGE_LABELS
        }, None

    query_latest_counts = text(
        """
        SELECT score_range, range_total_num, total_rise_num
        FROM snp500_profit_validation
        WHERE date = :previous_date
    """
    )
    latest_counts_result = pd.read_sql(
        query_latest_counts, engine, params={"previous_date": previous_date}
    )

    range_total_counts = {
        row["score_range"]: {
            "range_total_num": row["range_total_num"],
            "total_rise_num": row["total_rise_num"],
        }
        for idx, row in latest_counts_result.iterrows()
    }
    return range_total_counts, previous_date


# 점수별 검증목록(상승/전체) 삽입
def insert_snp500_profit_validation(target_date):
    engine = get_engine()
    snp500_list = get_snp500_list()

    # 최신 range_total_counts 가져오기
    range_total_counts, latest_date = _get_latest_range_total_counts(
        target_date, engine
    )

    # range_total_counts 초기화
    for label in SCORE_RANGE_LABELS:
        if label not in range_total_counts:
            range_total_counts[label] = {"range_total_num": 0, "total_rise_num": 0}

    # 현재 날짜의 데이터 가져오기
    query_current = text(
        f"""
        SELECT code, score_plus_avg
        FROM profit_after_{VALIDATION_DAY}day_nyse_naq
        WHERE date = :target_date
        AND code IN :snp500_list
    """
    ).bindparams(bindparam("snp500_list", expanding=True))
    params = {"target_date": target_date, "snp500_list": snp500_list}
    current_data = pd.read_sql(query_current, engine, params=params)

    results = []

    for (low, high), label in zip(SCORE_RANGES, SCORE_RANGE_LABELS):
        if low == "-inf":
            filtered = current_data[current_data["score_plus_avg"] <= high]
        elif high == "inf":
            filtered = current_data[current_data["score_plus_avg"] >= low]
        else:
            filtered = current_data[
                (current_data["score_plus_avg"] >= low)
                & (current_data["score_plus_avg"] <= high)
            ]

        num = len(filtered)
        all_stock_code = ", ".join(filtered["code"].tolist())

        # 새로운 range_total_num 계산
        range_total_num = range_total_counts[label]["range_total_num"] + num
        range_total_counts[label]["range_total_num"] = range_total_num

        # 결과 저장
        result = {
            "date": target_date,
            "score_range": label,
            "num": num,
            "range_total_num": range_total_num,
            "all_stock_code": all_stock_code,
        }
        results.append(result)

    # 모든 score_range에 대해 데이터가 존재하도록 보장
    for label in SCORE_RANGE_LABELS:
        if not any(res["score_range"] == label for res in results):
            results.append(
                {
                    "date": target_date,
                    "score_range": label,
                    "num": 0,
                    "range_total_num": range_total_counts[label]["range_total_num"],
                    "all_stock_code": "",
                }
            )

    # 결과를 데이터프레임으로 변환하여 데이터베이스에 삽입
    result_df = pd.DataFrame(results)
    result_df.to_sql(
        "snp500_profit_validation", engine, if_exists="append", index=False
    )
    logging.info(f"snp500_profit_validation / {target_date} is inserted")


# 직전날짜의 snp500_profit_validation 데이터를 조회
# 직전 날짜의 데이터를 참고하여 빠르게 최신 데이터를 계산하기 위함
def _get_previous_day_data(target_date, engine):
    # 이전 날짜의 데이터를 가져옴
    query_prev_day = text(
        """
        SELECT MAX(date) AS previous_date
        FROM snp500_profit_validation
        WHERE date < :target_date
    """
    )
    prev_date_result = pd.read_sql(
        query_prev_day, engine, params={"target_date": target_date}
    )
    previous_date = prev_date_result["previous_date"].iloc[0]

    if pd.isnull(previous_date):
        # 이전 데이터가 없으면 초기화
        return {
            label: {"range_total_num": 0, "average_profit": 0, "total_rise_num": 0}
            for label in SCORE_RANGE_LABELS
        }, None

    query_prev_data = text(
        """
        SELECT score_range, range_total_num, average_profit, total_rise_num
        FROM snp500_profit_validation
        WHERE date = :previous_date
    """
    )
    prev_data_result = pd.read_sql(
        query_prev_data, engine, params={"previous_date": previous_date}
    )

    prev_data = {
        row["score_range"]: {
            "range_total_num": row["range_total_num"],
            "average_profit": row["average_profit"],
            "total_rise_num": row["total_rise_num"],
        }
        for idx, row in prev_data_result.iterrows()
    }
    return prev_data, previous_date


# profit_after_10day_nyse_naq 테이블에서 특정 target_date의 데이터를 가져오기
def _get_profit_after_10day_data(engine, target_date):
    # target_date의 all_stock_code 가져오기
    query_all_stock_code = text(
        """
        SELECT all_stock_code
        FROM snp500_profit_validation
        WHERE date = :target_date
    """
    )
    params = {"target_date": target_date}
    all_stock_code_df = pd.read_sql(query_all_stock_code, engine, params=params)
    all_stock_code_list = all_stock_code_df["all_stock_code"].tolist()

    # all_stock_code 파싱하여 리스트로 변환
    all_stock_codes = []
    for stock_code_str in all_stock_code_list:
        all_stock_codes.extend(stock_code_str.split(", "))

    # profit_after_10day_nyse_naq 테이블에서 특정 target_date의 데이터를 가져오기
    query_current = text(
        f"""
        SELECT code, score_plus_avg, profit
        FROM profit_after_{VALIDATION_DAY}day_nyse_naq
        WHERE date = :target_date
        AND code IN :snp500_list
        AND profit IS NOT NULL
    """
    ).bindparams(bindparam("snp500_list", expanding=True))

    params = {"target_date": target_date, "snp500_list": all_stock_codes}
    current_data = pd.read_sql(query_current, engine, params=params)
    return current_data


# VALIDATION_DAY일이 지난 후 검증 결과(상승 데이터 수) 업데이트
def update_snp500_profit_validation(target_date):
    engine = get_engine()

    # profit_after_10day_nyse_naq 테이블에서 특정 target_date의 데이터를 가져오기
    current_data = _get_profit_after_10day_data(engine, target_date)

    # 바로 이전날짜의 데이터 가져오기
    prev_data, previous_date = _get_previous_day_data(target_date, engine)
    results = []
    for (low, high), label in zip(SCORE_RANGES, SCORE_RANGE_LABELS):
        if low == "-inf":
            filtered = current_data[current_data["score_plus_avg"] <= high]
        elif high == "inf":
            filtered = current_data[current_data["score_plus_avg"] >= low]
        else:
            filtered = current_data[
                (current_data["score_plus_avg"] >= low)
                & (current_data["score_plus_avg"] <= high)
            ]

        num = len(filtered)
        all_stock_code = ", ".join(filtered["code"].tolist())

        rise_stocks = filtered[filtered["profit"] >= 0]
        fall_stocks = filtered[filtered["profit"] < 0]

        rise_num = len(rise_stocks)
        rise_stock_code = ", ".join(rise_stocks["code"].tolist())
        fall_stock_code = ", ".join(fall_stocks["code"].tolist())

        old_range_total_num = prev_data[label]["range_total_num"]
        old_average_profit = (
            prev_data[label]["average_profit"]
            if prev_data[label]["average_profit"] is not None
            else 0
        )
        old_total_rise_num = prev_data[label]["total_rise_num"]

        new_range_total_num = old_range_total_num + num
        new_total_rise_num = old_total_rise_num + rise_num
        sum_new_profits = filtered["profit"].sum()

        # 새로운 average_profit 계산
        if new_range_total_num > 0:
            new_average_profit = (
                old_average_profit * old_range_total_num + sum_new_profits
            ) / new_range_total_num
        else:
            new_average_profit = 0

        # 결과 저장
        result = {
            "date": target_date,
            "score_range": label,
            "num": num,
            "range_total_num": new_range_total_num,
            "average_profit": new_average_profit,
            "all_stock_code": all_stock_code,
            "rise_num": rise_num,
            "rise_stock_code": rise_stock_code,
            "fall_stock_code": fall_stock_code,
            "total_rise_num": new_total_rise_num,
        }
        results.append(result)

    # 모든 score_range에 대해 데이터가 존재하도록 보장
    for label in SCORE_RANGE_LABELS:
        if not any(res["score_range"] == label for res in results):
            results.append(
                {
                    "date": target_date,
                    "score_range": label,
                    "num": 0,
                    "range_total_num": prev_data[label]["range_total_num"],
                    "average_profit": (
                        prev_data[label]["average_profit"]
                        if prev_data[label]["average_profit"] is not None
                        else 0
                    ),
                    "all_stock_code": "",
                    "rise_num": 0,
                    "rise_stock_code": "",
                    "fall_stock_code": "",
                    "total_rise_num": prev_data[label]["total_rise_num"],
                }
            )

    # 결과를 데이터프레임으로 변환하여 데이터베이스에 업데이트
    result_df = pd.DataFrame(results)

    with engine.connect() as connection:
        for index, row in result_df.iterrows():
            query_update = text(
                """
                UPDATE snp500_profit_validation
                SET num = :num,
                    range_total_num = :range_total_num,
                    average_profit = :average_profit,
                    all_stock_code = :all_stock_code,
                    rise_num = :rise_num,
                    average_profit = :average_profit,
                    rise_stock_code = :rise_stock_code,
                    fall_stock_code = :fall_stock_code,
                    total_rise_num = :total_rise_num
                WHERE date = :date
                AND score_range = :score_range
            """
            )
            connection.execute(
                query_update,
                {
                    "num": row["num"],
                    "range_total_num": row["range_total_num"],
                    "average_profit": row["average_profit"],
                    "all_stock_code": row["all_stock_code"],
                    "rise_num": row["rise_num"],
                    "average_profit": row["average_profit"],
                    "rise_stock_code": row["rise_stock_code"],
                    "fall_stock_code": row["fall_stock_code"],
                    "total_rise_num": row["total_rise_num"],
                    "date": row["date"],
                    "score_range": row["score_range"],
                },
            )
        connection.execute(text("COMMIT;"))

    logging.info(f"snp500_profit_validation / {target_date} is updated")


# 특정 날짜의 점수 구간별 통계 조회
# validation/daily 에서 사용
def get_snp500_profit_validation(date, code_list=True):
    engine = get_engine()

    query = text(
        """
        SELECT *
        FROM snp500_profit_validation
        WHERE date = :date
    """
    )

    result_df = pd.read_sql(query, engine, params={"date": date})

    if not code_list:
        columns_to_keep = [
            "score_range",
            "num",
            "rise_num",
            "range_total_num",
            "total_rise_num",
        ]
        result_df = result_df[columns_to_keep]
    else:
        result_df["date"] = pd.to_datetime(result_df["date"]).dt.strftime("%Y-%m-%d")

        result_df["rise_ratio"] = np.where(
            result_df["range_total_num"] == 0,
            0,
            result_df["total_rise_num"] / result_df["range_total_num"] * 100,
        )
        result_df["rise_ratio"] = result_df["rise_ratio"].round(2)

        # 직전의 데이터에서 어떻게 변화했는지 한 눈에 확인하기 위해 직전 데이터 추가
        result_df["prev_total_num"] = result_df["range_total_num"] - result_df["num"]
        result_df["prev_total_rise_num"] = (
            result_df["total_rise_num"] - result_df["rise_num"]
        )

    # 앞 5개의 행을 선택하고 역전 -> 라벨이 -인것을 앞으로 배치하기 위함
    reversed_top5 = result_df.iloc[:MINUS_LABEL_NUM].iloc[::-1]
    # 역전된 5개의 행과 나머지 데이터프레임을 결합
    result_df = pd.concat(
        [reversed_top5, result_df.iloc[MINUS_LABEL_NUM:]]
    ).reset_index(drop=True)
    return result_df


# 최신 날짜의 점수 구간별 통계 조회
def get_total_validation(cache_update=False):
    engine = get_engine()
    redis = get_redis()
    key = "total_validation"
    data = redis.get(key)

    if data is None or cache_update:
        query = text(
            """
            SELECT date, score_range, num, rise_num, range_total_num, total_rise_num
            FROM snp500_profit_validation
            WHERE date = (SELECT MAX(date) 
                        FROM snp500_profit_validation
                        WHERE rise_num IS NOT NULL)
        """
        )
        data = pd.read_sql(query, engine)
        data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")

        data["rise_ratio"] = np.where(
            data["range_total_num"] == 0,
            0,
            data["total_rise_num"] / data["range_total_num"] * 100,
        )
        data["rise_ratio"] = data["rise_ratio"].round(2)

        # 직전의 데이터에서 어떻게 변화했는지 한 눈에 확인하기 위해 직전 데이터 추가
        data["prev_total_num"] = data["range_total_num"] - data["num"]
        data["prev_total_rise_num"] = data["total_rise_num"] - data["rise_num"]

        # 앞 5개의 행을 선택하고 역전
        reversed_top5 = data.iloc[:MINUS_LABEL_NUM].iloc[::-1]
        # 역전된 5개의 행과 나머지 데이터프레임을 결합
        data = pd.concat([reversed_top5, data.iloc[MINUS_LABEL_NUM:]]).reset_index(
            drop=True
        )

        redis.set(key, data.to_json())

    else:
        data = pd.read_json(io.StringIO(data.decode("utf-8")), dtype={"date": str})

    return data


# 특정 점수 구간의 최신 정보 조회
# 메인 페이지, 종목 페이지에서 특정 점수 구간의 상승 확률을 표기하기 위함
def get_rise_ratio(score_range):
    data = get_total_validation()
    result = data[data["score_range"] == score_range]

    if not result.empty:
        return result["rise_ratio"].iloc[0]
    else:
        return None


# 검증 테이블의 날짜 리스트 조회
def get_all_validation_date(cache_update=False):
    engine = get_engine()
    redis = get_redis()
    key = "all_validation_date"
    df_dates = redis.get(key)
    if df_dates is None or cache_update:
        query = (
            f"SELECT DISTINCT date FROM snp500_profit_validation ORDER BY date DESC;"
        )
        df_dates = pd.read_sql(query, engine)

        # 날짜 형식을 '%Y-%m-%d'로 변환하고 리스트로 변환
        df_dates["date"] = pd.to_datetime(df_dates["date"]).dt.strftime("%Y-%m-%d")
        df_dates["remarks"] = ""
        for i in range(min(VALIDATION_DAY, len(df_dates))):
            df_dates.at[i, "remarks"] = f"D-{VALIDATION_DAY - i}"

        redis.set(key, df_dates.to_json())
    else:
        df_dates = pd.read_json(
            io.StringIO(df_dates.decode("utf-8")), dtype={"date": str}
        )

    return df_dates


# VALIDATION_DAY가 지나 검증이 완료된 날짜인지 체크
def is_verified_date(date):
    df_dates = get_all_validation_date(date)
    remarks = df_dates.loc[df_dates["date"] == date, "remarks"].values[0]
    return remarks == "", remarks
