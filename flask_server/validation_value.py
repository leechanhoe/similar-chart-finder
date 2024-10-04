# 유효값 검증

from pyfile.shared_data import get_day_num_list, get_market_list, get_lang_list
from pyfile.data_reader import get_comparable_code_list
from datetime import datetime
import logging


def validate_lang(lang, page_name):
    if lang not in get_lang_list():
        logging.info(f"{page_name} invalid access - lang = {lang}")
        return False
    return True


def validate_market(market, page_name):
    if market not in get_market_list():
        logging.info(f"{page_name} invalid access - market : {market}")
        return False
    return True


def validate_day_num(day_num, page_name, type="str"):
    if day_num not in get_day_num_list(type=type):
        logging.info(f"{page_name} invalid access - day_num : {day_num}")
        return False
    return True


def validate_code(code, market, page_name):
    code_list = get_comparable_code_list(market)
    if code not in code_list:
        logging.info(f"{page_name} invalid access - code : {code} / market : {market}")
        return False
    return True


def validate_date_format(date_string):
    if date_string is None:
        return False

    try:
        # 문자열을 datetime 객체로 변환 시도
        datetime.strptime(date_string, "%Y-%m-%d")
        return True  # 변환이 성공하면 True 반환
    except ValueError:
        return False  # 변환 중 예외가 발생하면 False 반환
