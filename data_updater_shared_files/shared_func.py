from similar_generator import delete_old_similar_data
from pyfile.shared_data import get_day_num_list
from image_deleter import delete_stock_info_main_chart
from pyfile.data_reader import get_compared_code_list
from pyfile.db_engine import get_redis, get_engine
from pyfile.data_reader import (
    update_cache_code_name_industry_url,
    get_comparable_code_list,
    get_up_down_ranking,
    get_same_industry_code,
)
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from pyfile.image_manager import update_index_image
from image_deleter import delete_result_image
from get_stock_data import get_stock_data_fdr
import pandas as pd
import logging
import time


def update_caches(date, market):
    # 상승&하락율 랭킹 업데이트
    get_up_down_ranking(market, cache_update=True)

    # 종목별 동일업종 리스트 업데이트
    get_same_industry_code("", market, cache_update=True)

    # 8일치 이상이 되어 비교가 가능한 종목리스트 업데이트
    get_comparable_code_list(market, cache_update=True)
    get_compared_code_list(market, cache_update=True)

    update_latest_date(date, market)


def delete_old_data(date, market):
    # stock_info 페이지에 나오는 main_chart 캐시들 삭제
    delete_stock_info_main_chart(market)

    delete_result_image(date, market)
    delete_old_similar_data(date, market)

    # 간헐적으로 지워지지 않는 오류로 자주 삭제
    delete_stock_info_main_chart(market)


def update_latest_date(date, market):
    date_str = date.strftime("%Y-%m-%d")
    redis = get_redis()

    # 최신날짜 캐시 업데이트
    key = f"latest_update_date_{market}"
    redis.set(key, date_str)


# 메인 페이지의 코스피or나스닥 지수 이미지 업데이트
def load_index_data(start_date, market):
    symbol = "KS11" if market == "kospi_daq" else "IXIC"
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        try:
            data = get_stock_data_fdr(
                symbol,
                (start_date - relativedelta(years=1)).strftime("%Y-%m-%d"),
                start_date.strftime("%Y-%m-%d"),
                market,
                index=True,
            ).iloc[-83:]

            # Low보다 Close나 Open이 낮은 경우를 찾아 Low로 설정합니다.
            data["Close"] = data.apply(
                lambda row: row["Low"] if row["Close"] < row["Low"] else row["Close"],
                axis=1,
            )
            data["Open"] = data.apply(
                lambda row: row["Low"] if row["Open"] < row["Low"] else row["Open"],
                axis=1,
            )

            # High보다 Close나 Open이 높은 경우를 찾아 High로 설정합니다.
            data["Close"] = data.apply(
                lambda row: row["High"] if row["Close"] > row["High"] else row["Close"],
                axis=1,
            )
            data["Open"] = data.apply(
                lambda row: row["High"] if row["Open"] > row["High"] else row["Open"],
                axis=1,
            )

            update_index_image(data, market)
            break

        except Exception as e:
            logging.info(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            if attempt < max_attempts:
                time.sleep(5)  # 재시도 전 잠시 대기

    if attempt == max_attempts:
        logging.info(f"Failed to update index image after 5 attempts.")


# 종목별 조회수 업데이트
def update_view(market):
    logging.info(f"Start update_view - {market}")
    # 레디스에 있던 조회수 db에 업데이트
    engine = get_engine()
    redis = get_redis()
    valid_code = get_comparable_code_list(market)
    with engine.begin() as connection:
        keys_to_update = redis.keys(f"views_{market}*")
        for key in keys_to_update:
            view = redis.get(key)
            key = key.decode()
            code = key.split("_")[-1]
            if code not in valid_code:
                redis.delete(key)
                continue

            # 행 삽입 또는 업데이트
            update_query = text(
                f"""
                INSERT INTO view_{market} (code, daily_view, view) 
                VALUES (:code, :view, :view) 
                ON DUPLICATE KEY 
                UPDATE daily_view = :view, view = view + :view
            """
            )
            connection.execute(update_query, {"code": code, "view": view})

            redis.set(key, "0")


# 유효한 종목(시총 상위 N개)의 무결성을 위한 로직
def update_valid_stock_code(market, base_on_ranking=10000):
    delete_invalid_comparison_result(
        market
    )  # valid를 업데이트하기 전이나 후나 한번이라도 invalid가 됐으면 삭제
    update_valid_requested_stock_code(
        market
    )  # 관리자가 특정 코드를 (in)validate하라는 요청이 있는지 확인 후 실행
    update_valid_base_on_ranking(
        market, base_on_ranking
    )  # 시총 순위가 ranking 이하인 종목은 유효한 종목이라고 판단
    update_cache_code_name_industry_url(
        market
    )  # 위 2 함수로 valid가 업데이트 된 것을 레디스 캐시에 반영
    delete_invalid_comparison_result(market)  # invalid된 종목들의 비교 결과들은 삭제


# 시총이 커트라인보다 낮아지면 유효코드리스트에서 삭제 / 높아지면 추가
def update_valid_base_on_ranking(market, cutline=10000):
    logging.info(f"Start update_valid_base_on_ranking - {market}")
    engine = get_engine()

    with engine.begin() as connection:
        # 하락하여 시총 상위 커트라인 아래로 내려간 종목은 삭제
        query = text(
            f"SELECT code, ranking FROM stock_code_list_{market} WHERE {cutline} < ranking AND valid = 1 AND user_request = 0"
        )  # 유저 요청종목은 제외
        delist = pd.read_sql(query, engine)
        delist = delist[
            ~delist["code"].isin(get_compared_code_list(market))
        ]  # 비교 테이블에 없는 행만 삭제
        logging.info(f"number of delist : {len(delist)}")

        update_query = text(
            f"UPDATE stock_code_list_{market} SET valid = 0 WHERE code=:code"
        )
        for idx, row in delist.iterrows():
            connection.execute(update_query, {"code": row["code"]})
            logging.info(
                f"{row['code']}'s ranking is {row['ranking']}. valid is updated to 0"
            )

        # 상승하여 시총 상위 커트라인 위로 올라온 종목은 추가
        query = text(
            f"SELECT code, ranking FROM stock_code_list_{market} WHERE ranking <= {cutline} AND valid = 0 AND user_request = 0"
        )
        enlist = pd.read_sql(query, engine)
        logging.info(f"number of enlist : {len(enlist)}")

        update_query = text(
            f"UPDATE stock_code_list_{market} SET valid = 1, failed_to_load = 0 WHERE code=:code"
        )
        for idx, row in enlist.iterrows():
            connection.execute(update_query, {"code": row["code"]})
            logging.info(
                f"{row['code']}'s ranking is {row['ranking']}. valid is updated to 1"
            )

        if market == "kospi_daq":
            query = text(
                f"""UPDATE stock_code_list_{market} SET valid = 0 WHERE code IN 
                        (SELECT code FROM stock_industry_kospi_daq WHERE industry_ko = '우선주 또는 정보없음')"""
            )
            invalid_num = connection.execute(query).rowcount
            logging.info(f"우선주 또는 정보없음으로 invalid된 개수 : {invalid_num}")


# requested_stock_code 테이블에 사용자 요청들을 보고 stock_code들을 (in)validate 하기
def update_valid_requested_stock_code(market):
    logging.info(f"start update_valid_requested_stock_code - {market}")
    engine = get_engine()

    query = text(
        f"""SELECT t1.*
                        FROM requested_stock_code_{market} t1
                        JOIN (
                            SELECT code, MAX(date) as max_date
                            FROM requested_stock_code_{market}
                            WHERE applied=0
                            GROUP BY code
                        ) t2
                        ON t1.code = t2.code AND t1.date = t2.max_date
                        ORDER BY t1.date;"""
    )  # code 별로 가장 최신 날짜의 행만을 가져오는 쿼리
    requested_stock_df = pd.read_sql(query, engine)

    with engine.begin() as connection:
        update_stock_code_list = text(
            f"""UPDATE stock_code_list_{market} 
                                        SET valid = :valid, user_request = 1
                                        WHERE code = :code"""
        )

        for idx, row in requested_stock_df.iterrows():
            connection.execute(
                update_stock_code_list, {"valid": row["validate"], "code": row["code"]}
            )
            logging.info(f"{row['code']}'s valid is updated to {row['validate']}")
        connection.execute(
            text(f"UPDATE requested_stock_code_{market} SET applied=1 WHERE applied=0")
        )


# 시총이 기준 이하로 내려가 invalid한 종목의 비슷한 탐색 결과들은 삭제
def delete_invalid_comparison_result(market, delist=None):
    logging.info(f"start delete_invalid_comparison_result - {market}")
    engine = get_engine()

    with engine.begin() as connection:
        if delist is None:
            delist = pd.read_sql(
                text(f"SELECT code FROM stock_code_list_{market} WHERE valid=0"), engine
            )
        logging.info(f"number of delist : {len(delist)}")

        valid_code_list = get_compared_code_list(market)
        for code in delist["code"].tolist():
            if (
                code in valid_code_list
            ):  # conparison 테이블에 비교당한 종목으로 있으면 삭제하지 않음
                continue

            deleted_num = 0
            for day_num in get_day_num_list():
                delete_comparison_result = text(
                    f"DELETE FROM comparison_result_{day_num}day_{market} WHERE base_stock_code=:code"
                )
                deleted_num += connection.execute(
                    delete_comparison_result, {"code": code}
                ).rowcount

            if deleted_num > 0:
                logging.info(
                    f"{code}'s comparison_result are Deleted - num : {deleted_num}"
                )
