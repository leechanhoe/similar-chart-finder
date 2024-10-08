# from pyfile.data_reader import get_comparable_code_list, get_stock_data_start_end, get_redis, get_stock_data_pre_fol
# from ta.momentum import RSIIndicator, StochasticOscillator
# from dateutil.relativedelta import relativedelta
# import logging
# import pandas as pd
# import numpy as np
# import pickle
# pd.options.mode.chained_assignment = None

# # 지표 계산 함수
# def _calculate_rsi(data, return_one=False):
#     rsi = RSIIndicator(close=data['Close']).rsi()
#     if not return_one:
#         return rsi[(rsi > 0) & (rsi < 100)]
#     else:
#         return rsi.iloc[-1] if len(rsi) > 0 else -1

# def _calculate_stochastic(data, return_one=False):
#     stochastic = StochasticOscillator(high=data['High'], low=data['Low'], close=data['Close'], window=12, smooth_window=5, fillna=True).stoch_signal()
#     if not return_one:
#         return stochastic[(stochastic > 0) & (stochastic < 100)]
#     else:
#         return stochastic.iloc[-1] if len(stochastic) > 0 else -1

# # def _calculate_consecutive(stock_data, return_one=False):
# #     # 연속성을 추적하기 위한 그룹 ID 생성
# #     stock_data['Group'] = (stock_data['Trend'] != stock_data['Trend'].shift(1)).cumsum()

# #     # 각 그룹 내 'Volume'이 0인 행이 있는지 체크
# #     volume_zero_groups = stock_data[stock_data['Volume'] == 0]['Group'].unique()

# #     # 연속 카운트 계산
# #     stock_data['Consecutive'] = stock_data.groupby('Group').cumcount() + 1
# #     stock_data['Consecutive'] *= stock_data['Trend']

# #     # 연속된 마지막 날만 추출
# #     # last_consecutive = stock_data.groupby('Group').tail(1)
# #     # 'Volume'이 0인 행이 있는 그룹 제외
# #     last_consecutive = stock_data[~stock_data['Group'].isin(volume_zero_groups)]
# #     # 연속성이 1 이상인 행만 필터링
# #     last_consecutive = last_consecutive[last_consecutive['Consecutive'].abs() >= 1]

# #     if not return_one:
# #         return last_consecutive
# #     else:
# #         return last_consecutive.iloc[-1]['Consecutive'] if len(last_consecutive) > 0 else last_consecutive

# # def _calculate_consecutive_candles(stock_data, return_one=False):
# #     # 양봉과 음봉을 식별합니다.
# #     stock_data['Trend'] = np.where(stock_data['Close'] >= stock_data['Open'], 1,
# #                                                np.where(stock_data['Close'] < stock_data['Open'], -1, 0))
# #     return _calculate_consecutive(stock_data, return_one=return_one)

# # def _calculate_consecutive_trends(stock_data, return_one=False):
# #     # 연속 상승(1) 또는 하락(-1) 표시
# #     stock_data['Trend'] = np.where(stock_data['Close'] > stock_data['Close'].shift(1), 1,
# #                                    np.where(stock_data['Close'] < stock_data['Close'].shift(1), -1, 0))
# #     return _calculate_consecutive(stock_data, return_one=return_one)

# # 지표별 결과 집계 함수
# def _aggregate_indicator_results(data, indicator_values, indicator_name):
#     data[indicator_name] = indicator_values
#     data = data.dropna(subset=[indicator_name])
#     data = data[data['Volume'] != 0]
#     data['Future Close'] = data['Close'].shift(-5)
#     data['Return'] = (data['Future Close'] - data['Close']) / data['Close']
#     data.dropna(subset=['Future Close', 'Return'], inplace=True)
#     data['Is Positive'] = data['Return'] > 0
#     data['Is Negative'] = data['Return'] < 0

#     agg_results = data.groupby(data[indicator_name].apply(int)).agg(
#         average_return=('Return', 'mean'),
#         rise_count=('Is Positive', 'sum'),
#         fall_count=('Is Negative', 'sum'),
#         total_count=(indicator_name, 'size')
#     )
#     return agg_results

# def _aggregate_consecutive_candle_results(last_consecutive):
#     last_consecutive = last_consecutive[last_consecutive['Return'] != 0]
#     # 연속 카운트 별로 평균 수익률, 상승 횟수, 전체 데이터 수를 집계합니다.
#     agg_data = last_consecutive.groupby('Consecutive').agg(
#         average_return=('Return', 'mean'),
#         rise_count=('Is Positive', 'sum'),
#         fall_count=('Is Negative', 'sum'),
#         total_count=('Consecutive', 'size')
#     )

#     return agg_data

# indicators = {
#         'RSI': _calculate_rsi,
#         'Stochastic': _calculate_stochastic
#         # 'ConsecutiveCandles': _calculate_consecutive_candles,
#         # 'ConsecutiveTrends': _calculate_consecutive_trends  # 새로운 지표 추가
#     }

# indicators_lang = {
#     'en': {
#         'RSI': 'RSI(14)',
#         'Stochastic': 'Stochastic(12,5,5)'
#         # 'ConsecutiveCandles1': 'Consecutive + Candles',
#         # 'ConsecutiveCandles0': 'Consecutive - Candles',
#         # 'ConsecutiveTrends1': 'Consecutive Rises',
#         # 'ConsecutiveTrends0': 'Consecutive Falls',
#     },
#     'ko': {
#         'RSI': 'RSI(14)',
#         'Stochastic': 'Stochastic(12,5,5)'
#         # 'ConsecutiveCandles1': '연속 양봉 수',
#         # 'ConsecutiveCandles0': '연속 음봉 수',
#         # 'ConsecutiveTrends1': '연속 상승 수',
#         # 'ConsecutiveTrends0': '연속 하락 수'
#     }
# }

# def update_indicator(market, start_time, period=120):
#     logging.info(f"update_indicator {market}")
#     code_list = get_comparable_code_list(market)
#     start_date = (start_time - relativedelta(months=period)).strftime('%Y-%m-%d')
#     end_date = start_time.strftime('%Y-%m-%d')

#     final_results = {indicator_name: [] for indicator_name in indicators.keys()}

#     for i, code in enumerate(code_list):
#         data = get_stock_data_start_end(code, market, start_date, end_date)
#         if len(data) <= 146:
#             continue

#         # 연속 양봉/음봉 지표 계산을 위한 사전 준비
#         data['Future Close'] = data['Close'].shift(-1)
#         data['Return'] = (data['Future Close'] - data['Close']) / data['Close']
#         data.dropna(subset=['Future Close', 'Return'], inplace=True)
#         data['Is Positive'] = data['Return'] > 0
#         data['Is Negative'] = data['Return'] < 0

#         for indicator_name, indicator_func in indicators.items():
#             if indicator_name == 'ConsecutiveCandles' or indicator_name == 'ConsecutiveTrends':
#                 # 연속 양봉/음봉 지표의 경우 다른 처리 방식
#                 last_consecutive = indicator_func(data.copy())
#                 agg_results = _aggregate_consecutive_candle_results(last_consecutive)

#             elif indicator_name == 'RSI' or indicator_name == 'Stochastic':
#                 # RSI, Stochastic과 같은 기타 지표들
#                 indicator_values = indicator_func(data.copy())
#                 agg_results = _aggregate_indicator_results(data.copy(), indicator_values, indicator_name)

#             final_results[indicator_name].append(agg_results)

#     # 각 지표별로 모든 결과 합치기 및 평균/합계 처리
#     for indicator_name in final_results:
#         combined_results = pd.concat(final_results[indicator_name], axis=0)
#         combined_agg = combined_results.groupby(level=0).agg({
#             'average_return': 'mean',
#             'rise_count': 'sum',
#             'fall_count': 'sum',
#             'total_count': 'sum'
#         })
#         combined_agg['average_return'] = combined_agg['average_return'] * 100
#         combined_agg['rise_rate'] = combined_agg['rise_count'] / (combined_agg['rise_count'] + combined_agg['fall_count']) * 100
#         final_results[indicator_name] = combined_agg

#     with open(f"/app/shared_files/shared_data/indicator_{market}.pkl", "wb") as f:
#         pickle.dump(final_results, f)

#     for indicator_name in final_results.keys():
#         final_results[indicator_name].to_csv(f"/app/shared_files/shared_data/indicator_{market}_{indicator_name}.csv")

#     logging.info(f"update_indicator {market} done")
#     return final_results

# def get_indicators(market, code, date, lang, update=False):
#     stock_data = get_stock_data_pre_fol(code, date, market, preceding=146)
#     redis = get_redis()
#     key = f'indicator_{market}'
#     indicator_data = redis.get(key)
#     if indicator_data is None or update:
#         with open(f"/app/shared_files/shared_data/indicator_{market}.pkl", "rb") as f:
#             indicator_data = pickle.load(f)
#         redis.set(key, pickle.dumps(indicator_data))
#         logging.info(f"get_indicator {market} from file")
#     else:
#         indicator_data = pickle.loads(indicator_data)

#     for indicator_name in indicator_data.keys():
#         indicator_data[indicator_name]['average_return'] = indicator_data[indicator_name]['average_return'].round(2)
#         indicator_data[indicator_name]['rise_rate'] = indicator_data[indicator_name]['rise_rate'].round(2)

#     return_data = []
#     for indicator_name, indicator_func in indicators.items():
#         value = int(indicator_func(stock_data, return_one=True))
#         if value == -1:
#             continue
#         try:
#             tmp = indicator_data[indicator_name].loc[value]
#         except KeyError:
#             continue

#         name = indicators_lang[lang][indicator_name]
#         color_limit = 30 if indicator_name == 'RSI' else 20
#         new_data = pd.Series({"value": value, "name": name, "color_limit": color_limit}, name=value)
#         # 원래 시리즈와 새로운 데이터를 합친 새로운 데이터프레임 생성
#         tmp_df = pd.DataFrame(tmp).transpose()  # tmp 시리즈를 데이터프레임으로 변환
#         new_data_df = pd.DataFrame(new_data).transpose()  # 새 데이터 시리즈를 데이터프레임으로 변환
#         combined_df = pd.concat([tmp_df, new_data_df], axis=1).iloc[0]  # 두 데이터프레임을 연결하고 첫 번째 행 선택
#         for name in ['rise_count', 'fall_count', 'total_count']:
#             combined_df[name] = combined_df[name].astype(int)

#         return_data.append(combined_df)

#     return_data = pd.concat(return_data, axis=1).transpose()
#     return return_data
