from pyfile.data_reader import get_stock_code
from pyfile.db_engine import get_redis, get_engine
from pyfile.statistics_reader import get_statistics, get_statistics_all_stock
from sqlalchemy import text
from dateutil.relativedelta import relativedelta
from pyfile.image_manager import draw_statistics_chart
from pyfile.shared_data import get_day_num_list
import logging
import pandas as pd

# 랭킹에 관한 레디스 캐시 업데이트
def update_cache(market, up, rise_rate, day_num):
    redis = get_redis()
    # 데이터베이스에서 데이터를 가져옵니다.
    data = get_statistics(market, up=up, rise_rate=rise_rate, day_num=day_num, update=True)
    # 직렬화된 데이터를 Redis에 저장합니다. 키는 market, up, rise_count의 조합으로 만듭니다.
    key = f'{market}_{up}_{rise_rate}_{day_num}'
    redis.set(key, data.to_json())
    
    if day_num == 'all':
        day_num = '64'
    draw_statistics_chart(data=data, market=market, day_num=int(day_num), file_name=key)

# 모든 종목의 개별 통계 캐시 업데이트(종목정보용)
def update_stock_info_cache(market):
    redis = get_redis()
    all_statistics_data = get_statistics_all_stock(market)
    for idx, row in all_statistics_data.iterrows():
        key = f"latest_statistics_{row['code']}"
        row = pd.DataFrame([row.values], columns=all_statistics_data.columns)
        redis.set(key, row.to_json())

# 랭킹 데이터 업데이트
def update_statistics(base_date, market, save_period=36):
    logging.info(f"Start updating statistics")
    engine = get_engine()
    base_date = base_date.strftime('%Y-%m-%d')
    # 각 테이블에서 데이터를 가져옵니다.
    df_list = []
    for i in get_day_num_list():
        query = f"""
        SELECT base_stock_code as code, after_close_change
        FROM (
            SELECT base_stock_code, after_close_change, distance,
                   ROW_NUMBER() OVER(PARTITION BY base_stock_code ORDER BY distance) as rn
            FROM comparison_result_{i}day_{market}
            WHERE base_date = '{base_date}'
        ) t
        WHERE rn <= 10
        """
        df = pd.read_sql(query, engine)
        df_list.append(df)

    # 각 종목별로 평균을 구합니다.
    result_df_list = []
    for i, df in enumerate(df_list):  # enumerate를 사용하여 i 인덱스를 추가
        result_df = df.groupby('code')['after_close_change'].mean().reset_index()
        # result_df = df.groupby('code').apply(lambda x: x.iloc[1:-1]['after_close_change'].mean()).reset_index() # 절사평균
        result_df.columns = ['code', f'average_{2**(i+3)}day']  # 'after_close_change' 컬럼 이름을 변경
        result_df_list.append(result_df)
    # 결과를 합칩니다.
    final_df = get_stock_code(market)

    # 중복된 'code' 값을 가진 행을 제거합니다. 첫 번째 중복 값만 남기고 나머지는 제거합니다.
    final_df = final_df.drop_duplicates(subset='code', keep='first')

    final_df = final_df[['code']]
    for next_df in result_df_list:
        final_df = final_df.merge(next_df, on='code', how='left')
    final_df['average_allday'] = final_df[[f'average_{day}day' for day in get_day_num_list()]].mean(axis=1, skipna=False)

    # 데이터 개수, 그 중 상승한 개수 세기
    for i, df in enumerate(df_list):
        df['rise_count'] = df['after_close_change'].apply(lambda x: 1 if x >= 0 else 0)
        rise_df = df.groupby('code')[f'rise_count'].sum().reset_index()
        rise_df.columns = ['code', f'rise_count_{2**(i+3)}day']
        final_df = final_df.merge(rise_df, on='code', how='left')

        count_df = df.groupby('code').size().reset_index()
        count_df.columns = ['code', f'data_num_{2**(i+3)}day']
        final_df = final_df.merge(count_df, on='code', how='left')
    columns_to_fill = [[f'rise_count_{day}day' for day in get_day_num_list()] + [f'data_num_{day}day' for day in get_day_num_list()]]
    for column in columns_to_fill:
        final_df[column] = final_df[column].fillna(0).infer_objects().astype(int)
    final_df['rise_count_allday'] = final_df[[f'rise_count_{day}day' for day in get_day_num_list()]].sum(axis=1, skipna=False)
    final_df['data_num_allday'] = final_df[[f'data_num_{day}day' for day in get_day_num_list()]].sum(axis=1, skipna=False)

    # date 칼럼을 추가합니다.
    final_df['date'] = base_date

    #소수점 2자리까지만
    cols_to_round = [f'average_{day}day' for day in get_day_num_list() + ['all']]
    final_df[cols_to_round] = final_df[cols_to_round].round(2)
    # SQLAlchemy 트랜잭션을 시작합니다.
    with engine.begin() as connection:
        # 테이블에서 date가 base_date로부터 한 달이 지난 데이터를 삭제합니다.
        old_date = (pd.to_datetime(base_date).date() - relativedelta(months=save_period)).strftime('%Y-%m-%d')
        delete_query = text(f"DELETE FROM statistics_{market} WHERE date < '{old_date}'")
        connection.execute(delete_query)

        # 최종 결과를 데이터베이스에 삽입합니다.
        final_df.to_sql(f'statistics_{market}', con=connection, if_exists='append', index=False)

    # 레디스 업데이트
    day_num_list = ['all'] + get_day_num_list(type='str')
    for up in [True, False]:
        for rise_count in [True, False]:
            for days in day_num_list:
                update_cache(market, up, rise_count, days)
    
    update_stock_info_cache(market)
    logging.info(f"Completed updating statistics")