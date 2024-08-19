from flask import request, Blueprint, render_template
from pyfile.data_reader import get_predict_day, get_name, get_industry, get_valid_day_num
from pyfile.similar_data_reader import get_similar_chart, get_one_comparison_result, get_similar_data_range
from pyfile.db_engine import get_redis
from pyfile.data_reader import get_latest_update_date
from translation import translations
from popular_ranking import get_popular_ranking
from validation_value import validate_lang, validate_market, validate_day_num, validate_code, validate_date_format
from  pyfile.image_manager import update_result_images, draw_detail_chart
from controller.stock_info import get_url
import main
import logging

PAGE_NAME = 'result'
RESULT_NUM = 10

bp = Blueprint(PAGE_NAME, __name__, url_prefix=f'/{PAGE_NAME}')
@bp.route('/', methods=['GET'])
def result():
    code = request.args.get('code', None)
    base_date = get_param('base-date')
    market = request.args.get('market', None)
    day_num = get_param('day-num')
    lang = request.args.get('lang', 'ko')
    
    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    # 이상한 값 오류처리
    if (not validate_market(market, PAGE_NAME) or not validate_code(code, market, PAGE_NAME) 
        or not validate_day_num(day_num, PAGE_NAME) or not validate_date_format(base_date)):
        return main.page_not_found404(lang=lang)
    
    name = get_name(code, market, lang)
    
    similar_data_range = get_similar_data_range(code, day_num, market)
    if len(similar_data_range) == 0:
        logging.info(f"{code}/{base_date}/{day_num} is not in comparison_result table")
        return main.page_not_found404(lang=lang)
    
    update_date=get_latest_update_date(market)
    if base_date not in similar_data_range:
        base_date = update_date
    
    day_num = int(day_num)
    update_result_images(code, base_date, market, day_num, lang)

    similar_chart_data = get_similar_chart(code, base_date, market, day_num)

    if len(similar_chart_data) == 0:
        return render_template('none_result.html', market=market, translations=translations[lang], lang=lang)
    after_close_mean = round(similar_chart_data['after_close_change'].mean(), 2)

    # 'compare_stock_code' 열의 각 값에 'get_name' 함수를 적용하여 새로운 열 'compare_stock_name'을 생성합니다.
    similar_chart_data['compare_stock_name'] = similar_chart_data['compare_stock_code'].apply(get_name, args=(market, lang, ))
    similar_chart_data['compare_stock_industry'] = similar_chart_data['compare_stock_code'].apply(get_industry, args=(market, lang, ))

    similar_chart_list = similar_chart_data.to_dict('records')
    valid_day_num = get_valid_day_num(code, day_num, market)
    investing_url, naver_url = get_url(code, market, lang)
    
    _up_view(market, code)
    logging.info(f"visited {PAGE_NAME} : ({get_name(code, market, lang)}){code} {base_date} {day_num} mean : {after_close_mean}")
    return render_template(f'{PAGE_NAME}.html', code=code, base_date=base_date, name=name, market=market, day_num=str(day_num), after_close_mean=after_close_mean,
                           predict_day=get_predict_day(day_num), similar_chart_list=similar_chart_list, base_industry=get_industry(code, market, lang), lang=lang,
                           translations=translations[lang], popular_ranking=get_popular_ranking(market, with_name=lang),
                           valid_day_num=valid_day_num, similar_data_range=similar_data_range,
                           update_date=update_date, naver_url=naver_url)

@bp.route('/detail', methods=['GET'])
def detail():
    base_stock_code = get_param('base-stock-code')
    base_date = get_param('base-date')
    compare_stock_code = get_param('compare-stock-code')
    compare_date = get_param('compare-date')
    market = get_param('market')
    lang = get_param('lang') or 'ko'
    day_num = get_param('day-num')

    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    
    # 이상한 값 처리
    if (not validate_market(market, PAGE_NAME) or not validate_day_num(day_num, PAGE_NAME) or 
        not validate_code(base_stock_code, market, PAGE_NAME) or not validate_code(compare_stock_code, market, PAGE_NAME)):
        return main.page_not_found404(lang=lang)
    
    if not validate_date_format(base_date) or not validate_date_format(compare_date):
        logging.info(f"{PAGE_NAME} invalid access - base_date : {base_date} / compare_date : {compare_date}")
        return main.page_not_found404(lang=lang)
    
    day_num = int(day_num)
    result = get_one_comparison_result(base_stock_code, base_date, compare_stock_code, compare_date, day_num, market)
    if len(result) != 1: # db에 저장된 비교결과에 없으면
        return main.page_not_found404(lang=lang)
    compare_stock_name = get_name(compare_stock_code, market, lang)

    detail_chart = draw_detail_chart(compare_stock_code, compare_date, market, day_num, lang)

    logging.info(f"visited detail_chart : (base: {get_name(base_stock_code, market, lang)}){base_stock_code} {base_date} {day_num} / compare : {get_name(compare_stock_code, market, lang)}){compare_stock_code}")
    return render_template(f'detail_chart.html', base_date=base_date, base_stock_code=base_stock_code, 
                           market=market, day_num=str(day_num), after_close_change=result['after_close_change'].iloc[0],
                           compare_stock_code=compare_stock_code, compare_stock_name=compare_stock_name, 
                           compare_date=compare_date, detail_chart=detail_chart, predict_day=get_predict_day(day_num), 
                           lang=lang, translations=translations[lang], popular_ranking=get_popular_ranking(market, with_name=lang))

def _up_view(market, code):
    key = f'views_{market}_{code}'
    redis = get_redis()
    # Redis에서 데이터를 가져옵니다.
    views = redis.get(key)
    # Redis에 데이터가 없는 경우에만 데이터베이스에서 데이터를 가져옵니다.
    if views is None:
        redis.set(key, '1')  # 데이터를 Redis에 저장합니다.
    else:
        redis.incr(key)

def get_param(param_name):
        return request.args.get(param_name) or request.args.get(param_name.replace('-', '_'))