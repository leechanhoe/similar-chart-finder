from data_generator import is_market_open, is_dst
from datetime import datetime
from main_start import start
from pyfile.db_engine import log_error_to_db
from pyfile.notification import notify_via_lambda
import traceback
import time
import logging

market = "nyse_naq"
# 로그의 출력 형식을 설정합니다.
FORMAT = '[%(asctime)s] %(levelname)s: %(message)s'
# 로그 레벨을 INFO로 설정하고, 출력 형식을 적용합니다.
logging.basicConfig(level=logging.INFO, format=FORMAT)

start_time = datetime.now()
if not is_dst() and is_market_open(start_time, market):
    logging.info(f"일광 시간 절약제를 시행하지않으므로 1시간 대기 {start_time}")
    time.sleep(3600)

try:
    start(market)
except Exception as e:
    tb = traceback.format_exc()
    logging.error(f"{e}")

    # 에러 발생시 aws lambda를 이용한 이메일 발송
    notify_via_lambda(f"{e}\n{tb}")

    log_error_to_db(
        level='ERROR',
        service=f'data_updater_{market}',
        message=str(e),
        tb=tb
    )