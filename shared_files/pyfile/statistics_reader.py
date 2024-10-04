from sqlalchemy import text
from pyfile.shared_data import get_day_num_list
from pyfile.db_engine import get_redis, get_engine
import pandas as pd
import io


# 통계 페이지용 데이터 가져오기
def get_statistics(
    market="kospi_daq", rank=10, up=True, rise_rate=False, day_num="all", update=False
):
    engine = get_engine()
    r = get_redis()

    # 키를 만듭니다.
    key = f"{market}_{up}_{rise_rate}_{day_num}"
    # Redis에서 데이터를 가져옵니다.
    data = r.get(key)
    # Redis에 데이터가 없는 경우에만 데이터베이스에서 데이터를 가져옵니다.
    if data is not None and not update:
        data = pd.read_json(
            io.StringIO(data.decode("utf-8")), dtype={"code": str}
        )  # 데이터를 역직렬화합니다.
    else:
        # 정렬 방식 결정
        order = "DESC" if up else "ASC"

        # 순위 책정 방식 결정
        if rise_rate:
            order_by = f"rise_count_{day_num}day {order}, average_{day_num}day {order}"
        else:
            order_by = f"average_{day_num}day {order}, rise_count_{day_num}day {order}"

        # 유의미한 상승차트비율을 계산하기 위한 최소 데이터 개수
        if day_num == "all":
            minimum_data = len(get_day_num_list()) * 9
        else:
            minimum_data = 10

        # SQL 쿼리 작성
        query = f"""
        SELECT *
        FROM statistics_{market}
        WHERE date = (
            SELECT MAX(date)
            FROM statistics_{market}
        ) AND average_{day_num}day IS NOT NULL
        AND data_num_{day_num}day >= {minimum_data}
        ORDER BY {order_by}
        LIMIT {rank}"""

        # pandas를 이용하여 SQL 쿼리 실행 결과를 데이터프레임으로 읽기
        data = pd.read_sql(query, con=engine)
        data = data[
            [
                "code",
                "date",
                f"average_{day_num}day",
                f"rise_count_{day_num}day",
                f"data_num_{day_num}day",
            ]
        ]
        data.dropna(inplace=True)
        data.rename(
            columns={
                f"average_{day_num}day": "average",
                f"rise_count_{day_num}day": "rise_count",
                f"data_num_{day_num}day": "data_num",
            },
            inplace=True,
        )
        data["rise_rate"] = (data["rise_count"] / data["data_num"] * 100).astype(int)
        r.set(key, data.to_json())  # 데이터를 Redis에 저장합니다.

    return data


# 모든 종목의 모든 통계속성 가져오기
def get_statistics_all_stock(market):
    engine = get_engine()

    # 파라미터화된 쿼리 작성
    query = text(
        f"""
    SELECT *
    FROM statistics_{market}
    WHERE date = (
        SELECT MAX(date)
        FROM statistics_{market})"""
    )

    # 쿼리 실행
    data = pd.read_sql(query, con=engine)
    return data


# 한 종목의 통계 가져오기(개별 종목 정보용)
def get_statistics_one_stock(code, market, only_average=False):
    engine = get_engine()
    r = get_redis()

    key = f"latest_statistics_{code}"
    # Redis에서 데이터를 가져옵니다.
    data = r.get(key)
    # Redis에 데이터가 없는 경우에만 데이터베이스에서 데이터를 가져옵니다.
    if data is not None:
        data = pd.read_json(
            io.StringIO(data.decode("utf-8")), dtype={"code": str}
        )  # 데이터를 역직렬화합니다.
    else:
        query = text(
            f"""
        SELECT *
        FROM statistics_{market}
        WHERE code = :code
        AND date = (
            SELECT MAX(date)
            FROM statistics_{market})
        """
        )

        # 쿼리 실행
        data = pd.read_sql(query, con=engine, params={"code": code})
        r.set(key, data.to_json())

    if only_average:
        return data[data["code"] == code]["average_allday"].iloc[0]
    else:
        return data[data["code"] == code]


# 한 종목의 과거 통계 가져오기(검증 페이지용)
def get_past_statistics(code, market, date):
    engine = get_engine()
    r = get_redis()

    key = f"past_statistics_{code}_{date}"
    # Redis에서 데이터를 가져옵니다.
    data = r.get(key)
    # Redis에 데이터가 없는 경우에만 데이터베이스에서 데이터를 가져옵니다.
    if data is not None:
        data = pd.read_json(
            io.StringIO(data.decode("utf-8")), dtype={"code": str}
        )  # 데이터를 역직렬화합니다.
    else:
        query = text(
            f"""
        SELECT *
        FROM statistics_{market}
        WHERE code = :code
        AND date = :date
        """
        )

        # 쿼리 실행
        data = pd.read_sql(query, con=engine, params={"code": code, "date": date})
        r.set(key, data.to_json())

    return data[data["code"] == code]


# 과거 통계 데이터 캐시 삭제
def delete_past_statistics_cache():
    redis = get_redis()
    keys_to_delete = redis.keys(f"past_statistics*")
    for key in keys_to_delete:
        redis.delete(key)


# 서로 다른 종목들의 통계를 in 쿼리로 한번에 가져오기 (index페이지용)
def get_statistics_stocks(code_list, market):
    engine = get_engine()

    code_str = ", ".join(f"'{code}'" for code in code_list)

    query = text(
        f"""
    SELECT code, date, average_allday, rise_count_allday, data_num_allday
    FROM statistics_{market}
    WHERE code IN ({code_str})
    AND date = (
        SELECT MAX(date)
        FROM statistics_{market})"""
    )

    # 쿼리 실행
    df = pd.read_sql(query, con=engine)
    df.set_index("code", inplace=True)
    # 'code_list'의 순서에 따라 행 재배열
    df = df.reindex(code_list)
    # 인덱스를 다시 컬럼으로 변환
    df.reset_index(inplace=True)
    df.rename(
        columns={
            f"average_allday": "average",
            f"rise_count_allday": "rise_count",
            "data_num_allday": "data_num",
        },
        inplace=True,
    )
    df["rise_rate"] = (df["rise_count"] / df["data_num"] * 100).astype(int)
    return df


# 128일치 이상의 데이터가 있어 통계 집계가 가능한 종목 리스트 얻기
def get_valid_statistics_list(market):
    engine = get_engine()

    query = text(
        f"""
    SELECT DISTINCT code
    FROM statistics_{market}
    WHERE average_allday IS NOT NULL
    AND code IN (SELECT code FROM stock_code_list_{market} WHERE valid = 1)
    AND date = (
        SELECT MAX(date)
        FROM statistics_{market})"""
    )
    df = pd.read_sql(query, con=engine)

    return df["code"].values
