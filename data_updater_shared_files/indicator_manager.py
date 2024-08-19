# from data_reader import get_comparable_code_list
# from pyfile.stock_data_reader import get_stock_data_start_end
# from pyfile.db_engine import get_redis
# from ta.momentum import RSIIndicator, StochasticOscillator
# from dateutil.relativedelta import relativedelta
# import logging
# import pandas as pd
# import numpy as np
# import io
# import pickle
# pd.options.mode.chained_assignment = None

# # 지표 계산 함수
# def calculate_rsi(data):
#     rsi = RSIIndicator(close=data['Close']).rsi()
#     return rsi[(rsi >= 0) & (rsi <= 100)]

# def calculate_stochastic(data):
#     stochastic = StochasticOscillator(high=data['High'], low=data['Low'], close=data['Close'], window=12, smooth_window=5).stoch_signal()
#     return stochastic[(stochastic >= 0) & (stochastic <= 100)]

# def calculate_consecutive(stock_data):
#     # 연속성을 추적하기 위한 그룹 ID 생성
#     stock_data['Group'] = (stock_data['Trend'] != stock_data['Trend'].shift(1)).cumsum()
    
#     # 각 그룹 내 'Volume'이 0인 행이 있는지 체크
#     volume_zero_groups = stock_data[stock_data['Volume'] == 0]['Group'].unique()

#     # 연속 카운트 계산
#     stock_data['Consecutive'] = stock_data.groupby('Group').cumcount() + 1
#     stock_data['Consecutive'] *= stock_data['Trend']
    
#     # 연속된 마지막 날만 추출
#     last_consecutive = stock_data.groupby('Group').tail(1)
#     # 'Volume'이 0인 행이 있는 그룹 제외
#     last_consecutive = last_consecutive[~last_consecutive['Group'].isin(volume_zero_groups)]
#     # 연속성이 1 이상인 행만 필터링
#     last_consecutive = last_consecutive[last_consecutive['Consecutive'].abs() >= 1]

#     return last_consecutive

# def calculate_consecutive_candles(stock_data):
#     # 양봉과 음봉을 식별합니다.
#     stock_data['Trend'] = np.where(stock_data['Close'] >= stock_data['Open'], 1, 
#                                                np.where(stock_data['Close'] < stock_data['Open'], -1, 0))
#     return calculate_consecutive(stock_data)

# def calculate_consecutive_trends(stock_data):
#     # 연속 상승(1) 또는 하락(-1) 표시
#     stock_data['Trend'] = np.where(stock_data['Close'] > stock_data['Close'].shift(1), 1,
#                                    np.where(stock_data['Close'] < stock_data['Close'].shift(1), -1, 0))
#     return calculate_consecutive(stock_data)

# # 지표별 결과 집계 함수
# def aggregate_indicator_results(data, indicator_values, indicator_name):
#     data[indicator_name] = indicator_values
#     data = data.dropna(subset=[indicator_name])
#     data = data[data['Volume'] != 0]
#     data['Future Close'] = data['Close'].shift(-5)
#     data['Return'] = (data['Future Close'] - data['Close']) / data['Close']
#     data.dropna(subset=['Future Close', 'Return'], inplace=True)
#     data['Is Positive'] = data['Return'] >= 0

#     agg_results = data.groupby(data[indicator_name].apply(int)).agg(
#         Average_Return=('Return', 'mean'),
#         Positive_Count=('Is Positive', 'sum'),
#         Total_Count=(indicator_name, 'size')
#     )
#     return agg_results

# def aggregate_consecutive_candle_results(last_consecutive):
#     # 연속 카운트 별로 평균 수익률, 상승 횟수, 전체 데이터 수를 집계합니다.
#     agg_data = last_consecutive.groupby('Consecutive').agg(
#         Average_Return=('Return', 'mean'),
#         Positive_Count=('Is Positive', 'sum'),
#         Total_Count=('Consecutive', 'size')
#     )
    
#     return agg_data

# def update_indicator(market, start_time, period=120):
#     logging.info(f"update_indicator {market}")
#     code_list = get_comparable_code_list(market)
#     start_date = (start_time - relativedelta(months=period)).strftime('%Y-%m-%d')
#     end_date = start_time.strftime('%Y-%m-%d')

#     indicators = {
#         'RSI': calculate_rsi, 
#         'Stochastic': calculate_stochastic, 
#         'ConsecutiveCandles': calculate_consecutive_candles, 
#         'ConsecutiveTrends': calculate_consecutive_trends  # 새로운 지표 추가
#     }
#     final_results = {indicator_name: [] for indicator_name in indicators.keys()}

#     for i, code in enumerate(code_list):
#         data = get_stock_data_start_end(code, market, start_date, end_date)
#         if len(data) <= 20:
#             continue

#         # 연속 양봉/음봉 지표 계산을 위한 사전 준비
#         data['Future Close'] = data['Close'].shift(-5)
#         data['Return'] = (data['Future Close'] - data['Close']) / data['Close']
#         data.dropna(subset=['Future Close', 'Return'], inplace=True)
#         data['Is Positive'] = data['Return'] >= 0

#         for indicator_name, indicator_func in indicators.items():
#             if indicator_name == 'ConsecutiveCandles' or indicator_name == 'ConsecutiveTrends':
#                 # 연속 양봉/음봉 지표의 경우 다른 처리 방식
#                 last_consecutive = indicator_func(data.copy())
#                 agg_results = aggregate_consecutive_candle_results(last_consecutive)

#             elif indicator_name == 'RSI' or indicator_name == 'Stochastic':
#                 # RSI, Stochastic과 같은 기타 지표들
#                 indicator_values = indicator_func(data.copy())
#                 agg_results = aggregate_indicator_results(data.copy(), indicator_values, indicator_name)
            
#             final_results[indicator_name].append(agg_results)
    
#     # 각 지표별로 모든 결과 합치기 및 평균/합계 처리
#     for indicator_name in final_results:
#         combined_results = pd.concat(final_results[indicator_name], axis=0)
#         combined_agg = combined_results.groupby(level=0).agg({
#             'Average_Return': 'mean',
#             'Positive_Count': 'sum',
#             'Total_Count': 'sum'
#         })
#         combined_agg['Average_Return'] = combined_agg['Average_Return'] * 100
#         combined_agg['Positive_rate'] = combined_agg['Positive_Count'] / combined_agg['Total_Count'] * 100
#         final_results[indicator_name] = combined_agg

#     with open(f"/app/shared_files/shared_data/indicator_{market}.pkl", "wb") as f:
#         pickle.dump(final_results, f)

#     for indicator_name in final_results.keys():
#         final_results[indicator_name].to_csv(f"/app/shared_files/shared_data/indicator_{market}_{indicator_name}.csv")
    
#     logging.info(f"update_indicator {market} done")
#     return final_results

# def get_indicator(market):
#     redis = get_redis()
#     key = f'indicator_{market}'
#     data = redis.get(key)
#     if data is None:
#         with open(f"/app/shared_files/shared_data/indicator_{market}.pkl", "rb") as f:
#             data = pickle.load(f)
#         redis.set(key, data.to_json())
#         logging.info(f"get_indicator {market} from file")
#     else:
#         data = pd.read_json(io.StringIO(data.decode('utf-8')), dtype={'code': str})
    
#     return data