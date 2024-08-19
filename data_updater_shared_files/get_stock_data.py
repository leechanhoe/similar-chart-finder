import concurrent.futures
import logging
import FinanceDataReader as fdr
import pandas as pd

def get_data(code, start, end):
    return fdr.DataReader(code, start, end)

none_stock_data = pd.DataFrame()

# 간헐적으로 발생하는 FinanceDataReader 라이브러리 자체 예외 처리
def get_stock_data_fdr(code, start, end):
    retry_count = 0
    retry_limit = 5
    while retry_count < retry_limit:  # 재시도 횟수를 제한
        executor = concurrent.futures.ThreadPoolExecutor()
        future = executor.submit(get_data, code, start, end)
        try:
            new_data_df = future.result(timeout=2)
            break  # 성공적으로 데이터를 가져왔다면 while 문을 벗어남
        except concurrent.futures.TimeoutError:
            logging.info(f"{code}에서 시간 초과로 인한 오류 발생, 재시도 중..")
            retry_count += 1
            executor.shutdown(wait=False)  # 명시적으로 executor 종료
            continue
        except Exception as e:
            logging.info(f"{code}에서 {e} 오류 발생")
            executor.shutdown(wait=False)  # 명시적으로 executor 종료
            new_data_df = none_stock_data
            break  # 다른 오류가 발생했다면 while 문을 벗어남
        finally:
            executor.shutdown(wait=False)  # 어떤 경우에도 executor를 종료

    if retry_count == retry_limit:  # 재시도를 3번 했음에도 실패했다면
        logging.info(f"{code}에서 데이터를 가져오는데 실패했습니다.")
        new_data_df = none_stock_data

    if len(new_data_df) == 0:
        logging.info(f"{code} 의 정보가 없음")
        new_data_df = none_stock_data

    return new_data_df