from data_generator import is_market_open, update_code_list, update_stock_data
from shared_func import (
    update_caches,
    delete_old_data,
    update_valid_stock_code,
    update_view,
    load_index_data,
)
from similar_generator import update_all_similar_data, generate_all_normed_data
from statistics_generator import update_statistics
from prepared_data import save_all_prepared_data
from image_deleter import delete_cache_image
from pyfile.web_scraping import (
    update_popular_stock_all_market,
    update_translated_name,
    update_industry_en,
)
from pyfile.data_reader import get_stock_code, update_cache_code_name_industry_url
from datetime import datetime
from pyfile.web_scraping import update_investing_url
from pyfile.profit_validation import update_profit_validation
from pyfile.candle_pattern_search import save_pattern
from pyfile.drawing_search import save_interval
from pyfile.statistics_reader import delete_past_statistics_cache
import logging


# 주식시장이 열리는 날 실행
def _market_open_day(market, start_time):
    update_code_list(market)
    update_stock_data(
        start_time, market
    )  # 맨 초기 db에 아무것도 없을 땐 recreate=True로 해줘야 메모리누수 안남

    update_all_similar_data(start_time, market)

    update_statistics(start_time, market)
    update_profit_validation(start_time, market)

    update_caches(start_time, market)
    delete_old_data(start_time, market)
    load_index_data(start_time, market)

    save_interval(market)  # 드로잉 검색을 위한 파일 최신 업데이트


# 주식시장이 닫힌 날 실행
def _market_close_day(market, start_time):
    weekday = datetime.today().weekday()
    if weekday == 5:  # 토요일이면
        update_valid_stock_code(
            market, base_on_ranking=10000 if market == "kospi_daq" else 1000
        )  # (in)valid 종목 리스트 업데이트
        update_stock_data(start_time, market, recreate=True)  # 주가 데이터

        generate_all_normed_data(market, start_time)

        # url, name, industry 일주일에 한번씩 전체삭제후 업데이트 해주기
        update_investing_url(
            get_stock_code(market, only_code=True), market, recreate=True
        )
        update_industry_en(market)

        save_pattern(start_time, market, 4)  # 패턴 검색을 위한 데이터 갱신
        delete_cache_image()
        delete_past_statistics_cache()  # 검증 페이지용 통계 데이터 삭제

    elif weekday == 6:
        update_translated_name(market)


# 매일 실행되어야하는 함수
def _every_day(market, start_time):
    update_view(market)
    update_cache_code_name_industry_url(market)


def start(market):
    start_time = datetime.now()
    logging.info(f"start at : {start_time}")

    update_popular_stock_all_market()
    if is_market_open(start_time, market):
        _market_open_day(market, start_time)
    else:
        _market_close_day(market, start_time)

    _every_day(market, start_time)
    update_popular_stock_all_market()

    if is_market_open(start_time, market):
        save_all_prepared_data(market, start_time)
    logging.info(f"fin{datetime.now() - start_time}")
