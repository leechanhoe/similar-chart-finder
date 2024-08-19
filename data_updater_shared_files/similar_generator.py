from pyfile.data_reader import get_stock_code
from pyfile.db_engine import get_redis, get_engine
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pyfile.shared_data import get_day_num_list
import prepared_data
import pandas as pd
import os
import gc
import direction_method
import candle_color_method
import logging

# day_num일치의 비슷한 차트 탐색 시작
def _update_similar_data(base_date, market, day_num, code_list, prepare=True):
    logging.info(f"start update_similar_data_{day_num}days_{market}")
    engine = get_engine()
    base_date = base_date.strftime('%Y-%m-%d')
    only_close = False if day_num != 128 else True

    if day_num in [16, 32, 64, 128]:
        if prepare:
            change, no_change = prepared_data.classify_is_hi_lo_changed(base_date, market, day_num, code_list, only_close=only_close)
            similar, invalid_code = prepared_data.search_prepared_similar_data(base_date, market, day_num, code_list=no_change, only_close=only_close)
            similar = similar | direction_method.get_similar_data(base_date, market, day_num, code_list=change + invalid_code, only_close=only_close)
        else:
            similar = direction_method.get_similar_data(base_date, market, day_num, code_list=code_list, only_close=only_close)
    elif day_num == 8:
        similar = candle_color_method.get_similar_data(base_date, market, day_num, code_list=code_list, batch=15)

    #유사도 순으로 정렬
    for code in code_list:
        similar[code].sort()

    # 찾은 비슷한 차트 중 종목 코드가 같고 일자가 얼마 차이나지 않으면 중복제거
    data_to_insert = []
    all_code_list = get_stock_code(market, True)
    for base_stock_code in code_list:
        # create a dictionary to store the maximum distance for each (compare_stock_code, compare_date) pair
        min_distance_data = {}
        for similar_chart_data in similar[base_stock_code]:
            distance, compare_stock_code, compare_date, after_close_change = similar_chart_data
            if compare_stock_code not in all_code_list:
                continue

            compare_date = datetime.strptime(compare_date, '%Y-%m-%d')
            distance = abs(distance)

            # iterate over the keys in the max_distance_data
            for key in list(min_distance_data.keys()):
                stored_compare_code, stored_compare_date = key
                # if the compare_stock_code is the same and the dates are within 7 days of each other
                if stored_compare_code == compare_stock_code and abs((compare_date - stored_compare_date).days) <= 10:
                    # if the new distance is greater than the stored distance
                    if distance < min_distance_data[key][4]: 
                        # update the data
                        min_distance_data[key] = (base_stock_code, base_date, compare_stock_code, compare_date.strftime('%Y-%m-%d'), distance, after_close_change)
                    break
            else:
                # if not a duplicate, add the data
                min_distance_data[(compare_stock_code, compare_date)] = (base_stock_code, base_date, compare_stock_code, compare_date.strftime('%Y-%m-%d'), distance, after_close_change)

        min_distance_data = sorted(list(min_distance_data.values()), key=lambda x : x[4])
        # convert the data to a list and add to the result / 12개까지만
        data_to_insert.extend(min_distance_data[:min(12, len(min_distance_data))])


    del similar
    gc.collect()
    # Convert the list of tuples to a DataFrame
    data_to_insert = pd.DataFrame(data_to_insert, columns=['base_stock_code', 'base_date', 'compare_stock_code', 'compare_date', 
                                                        'distance', 'after_close_change'])

    # Insert the data into the MySQL table
    data_to_insert.to_sql(f'comparison_result_{day_num}day_{market}', con=engine, if_exists='append', index=False)
    del data_to_insert
    gc.collect()

    target_dir = f'/app/shared_files/static/image_data/{market}/'
    current_dir = os.path.join(target_dir, base_date)
    os.makedirs(current_dir, exist_ok=True)

# save_period 변경 시 drawing 검색의 SAVE_PRRIOD도 변경할 것
# 오래된 비슷한 차트 데이터 삭제
def delete_old_similar_data(base_date, market, save_period=30):
    engine = get_engine()
    redis = get_redis()
    # 1달을 초과한 데이터 삭제
    old_date = (base_date - relativedelta(days=save_period)).strftime('%Y-%m-%d')
    logging.info(f"delete {old_date} 이전의 데이터")
    with engine.connect() as connection:
        for day_num in (get_day_num_list()):
            query = text(f"""
                DELETE FROM comparison_result_{day_num}day_{market}
                WHERE base_date < '{old_date}';
                """)
            connection.execute(query).rowcount
            connection.execute(text("COMMIT;"))
        
        keys_to_delete = redis.keys(f'similar_data_range_{market}*')
        for key in keys_to_delete:
            redis.delete(key)

# 모든 N일치의 비슷한 차트 탐색 시작
def update_all_similar_data(start_time, market, batch=10000):
    all_code_list = get_stock_code(market).sort_values('ranking')['code'].tolist()
    for rank in range(0, len(all_code_list), batch):
        start = rank
        end = min(len(all_code_list), rank+batch)
        code_list = all_code_list[start:end]
        
        for day_num in get_day_num_list():
            _update_similar_data(start_time, market, day_num, code_list)
            logging.info(f"update_similar_data {day_num}day {start} ~ {end} done {datetime.now() - start_time}")

# 비슷한 차트 탐색을 위해 미리 정규화된 주가 데이터 생성
def generate_all_normed_data(market, start_time, period=120):
    start_date = start_time - relativedelta(months=period)
    end_date = start_time - relativedelta(months=1)
    direction_method.delete_normed_data(market)
    direction_method.generate_normed_data(start_date, end_date, market, 128, batch=30)
    direction_method.generate_normed_data(start_date, end_date, market, 64, batch=30)
    direction_method.generate_normed_data(start_date, end_date, market, 32, batch=30)
    direction_method.generate_normed_data(start_date, end_date, market, 16, batch=30)
    candle_color_method.generate_normed_data(start_date, end_date, market, 8, batch=15)

    direction_method.generate_normed_data(start_date, end_date, market, 128, batch=30, prepare=True)
    direction_method.generate_normed_data(start_date, end_date, market, 64, batch=30, prepare=True)
    direction_method.generate_normed_data(start_date, end_date, market, 32, batch=30, prepare=True)
    direction_method.generate_normed_data(start_date, end_date, market, 16, batch=30, prepare=True)