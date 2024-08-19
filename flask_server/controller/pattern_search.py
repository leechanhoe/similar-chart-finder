from flask import request, Blueprint, render_template
from pyfile.data_reader import get_name, get_naver_url
from pyfile.stock_data_reader import get_stock_data_pre_fol
from translation import translations
from popular_ranking import get_popular_ranking
from validation_value import validate_lang, validate_market, validate_code, validate_date_format
import main
import logging
from pyfile.image_manager import draw_plt_stock_chart, draw_drawing_search_chart

PAGE_NAME = 'pattern_search'
    
bp = Blueprint(PAGE_NAME, __name__, url_prefix=f'/{PAGE_NAME}')
@bp.route('/', methods=['GET'])
def pattern_search():
    code = request.args.get('code', None)
    base_date  = request.args.get('base_date', None)
    market = request.args.get('market', None)
    lang = request.args.get('lang', 'ko')
    user_agent = request.headers.get('SimilarChart-App')

    if user_agent is None or not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    
    # 이상한 값 처리
    if (not validate_market(market, PAGE_NAME) or not validate_code(code, market, PAGE_NAME)):
        return main.page_not_found404(lang=lang)
    
    if not validate_date_format(base_date):
        logging.info(f"{PAGE_NAME} invalid access - date : {base_date}")
        return main.page_not_found404(lang=lang)

    stock_data = get_stock_data_pre_fol(code, base_date, market, preceding=17, following=14)
    draw_plt_stock_chart(code, base_date, lang, stock_data)
    draw_drawing_search_chart(code, base_date, 8, market, lang, pattern=True)

    name = get_name(code, market, lang)
    after_close_change_5, after_close_change_10 = _get_after_close_change_5_10(stock_data, base_date)
    first_pattern_day = stock_data.index[stock_data.index.get_loc(base_date)-3].strftime('%Y-%m-%d')
    naver_url = _get_naver_url(code, market)

    logging.info(f"visited {PAGE_NAME} : {name}({code}) / {base_date}")
    return render_template(f'{PAGE_NAME}.html', base_date=base_date, code=code, name=name,
                           market=market, after_close_change_5=after_close_change_5,
                           after_close_change_10=after_close_change_10,
                           lang=lang, translations=translations[lang],
                           first_pattern_day=first_pattern_day,
                           naver_url=naver_url,
                           popular_ranking=get_popular_ranking(market, with_name=lang))

# 5일 후와 10일 후 변동률 반환
def _get_after_close_change_5_10(stock_data, base_date):
    base_index = stock_data.index.get_loc(base_date)
    close_prices = stock_data['Close'].values
    after_5 = None
    after_10 = None

    if base_index + 5 < len(close_prices):
        after_5 = (close_prices[base_index + 5] - close_prices[base_index]) / close_prices[base_index] * 100
    if base_index + 10 < len(close_prices):
        after_10 = (close_prices[base_index + 10] - close_prices[base_index]) / close_prices[base_index] * 100
    return round(after_5, 2), round(after_10, 2)

def _get_naver_url(code, market):
    if market == 'kospi_daq':
        naver_url = 'https://m.stock.naver.com/domestic/stock/' + code + '/total'
    elif market == 'nyse_naq':
        naver_url = 'https://m.stock.naver.com/worldstock/stock/' + code + get_naver_url(code, market)
        
    return naver_url