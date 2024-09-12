from main_start import start
from pyfile.db_engine import log_error_to_db
from pyfile.notification import notify_via_lambda
import traceback
import logging

# 로그의 출력 형식을 설정합니다.
FORMAT = '[%(asctime)s] %(levelname)s: %(message)s'
# 로그 레벨을 INFO로 설정하고, 출력 형식을 적용합니다.
logging.basicConfig(level=logging.INFO, format=FORMAT)

market = "kospi_daq"

try:
    start(market)
except Exception as e:
    tb = traceback.format_exc()
    logging.error(f"{e}\n{tb}")

    # 에러 발생시 aws lambda를 이용한 이메일 발송
    notify_via_lambda(f"{e}\n{tb}")

    log_error_to_db(
        level='ERROR',
        service=f'data_updater_{market}',
        message=str(e),
        tb=tb
    )