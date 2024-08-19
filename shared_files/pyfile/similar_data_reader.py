from sqlalchemy import text
from pyfile.db_engine import get_engine, get_redis
import pandas as pd
import json

# 특정 종목, 특정 일자의 비슷한 차트 정보 반환
def get_similar_chart(code, date, market, day_num, limit=10):
    engine = get_engine()

    # Prepare SQL query to SELECT records from the database.
    sql = f"""SELECT * FROM comparison_result_{day_num}day_{market} 
            WHERE base_stock_code=%s AND base_date=%s 
            ORDER BY distance 
            LIMIT {limit}"""

    df = pd.read_sql_query(sql, engine, params=(code,date))
    df = df.sort_values('distance')
    return df

# 비슷한 차트 쌍 하나 반환 - result/detail 에서 사용
def get_one_comparison_result(base_stock_code, base_date, compare_stock_code, compare_date, day_num, market):
    engine = get_engine()
    
    query = text(f"""SELECT * from comparison_result_{day_num}day_{market}
                 WHERE base_stock_code = :base_stock_code AND base_date = :base_date
                 AND compare_stock_code = :compare_stock_code AND compare_date = :compare_date""")
    return pd.read_sql_query(query, engine, params={'base_stock_code': base_stock_code, 'base_date': base_date,
                            'compare_stock_code': compare_stock_code, 'compare_date': compare_date})

# result 페이지에서 과거 날짜의 정보도 볼 수 있도록 유효한 data_range 반환
def get_similar_data_range(code, day_num, market):
    redis = get_redis()
    engine = get_engine()

    key = f'similar_data_range_{market}_{code}_{day_num}'
    data_range_str = redis.get(key)
    
    if data_range_str is None:
        query = text(f"SELECT DISTINCT base_date FROM comparison_result_{day_num}day_{market} WHERE base_stock_code = :code")
        data_range_df = pd.read_sql(query, engine, params={'code': code})
        # base_date 열을 datetime 타입으로 변환
        data_range_df['base_date'] = pd.to_datetime(data_range_df['base_date'])
        data_range_list = sorted(data_range_df['base_date'].dt.strftime('%Y-%m-%d').tolist())
        redis.set(key, json.dumps(data_range_list))
    else:
        data_range_list = json.loads(data_range_str)
    
    return data_range_list