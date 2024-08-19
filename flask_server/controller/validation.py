from flask import Blueprint, request, render_template
from pyfile.profit_validation import get_validation_allday, get_all_validation_date, is_verified_date
from pyfile.profit_validation import get_snp500_profit_validation, get_total_validation
from pyfile.profit_validation import find_one_profit_validation
from pyfile.image_manager import draw_all_after_change_chart, draw_plt_stock_chart
from pyfile.stock_data_reader import get_stock_data_pre_fol
from validation_value import validate_lang, validate_date_format
from translation import translations
from popular_ranking import get_popular_ranking
from controller.stock_info import get_statistics_data, get_url
import main
import logging

PAGE_NAME = 'validation'
ITEMS_PER_PAGE = 30  # 한 페이지에 보여질 항목 수

bp = Blueprint(PAGE_NAME, __name__, url_prefix=f'/{PAGE_NAME}')

@bp.route('/', methods=['GET'])
def validation():
    type = request.args.get('type', 'date')
    lang = request.args.get('lang', 'ko')
    page = request.args.get('page', default=1, type=int)

    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    
    if type == 'rise' or type == 'fall':
        detail_data = get_validation_allday("nyse_naq", lang, type)
    elif type == 'date':
        detail_data = get_all_validation_date()
    else:
        return main.page_not_found404(lang=lang)

    # 페이지네이션 처리
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_data = detail_data.iloc[start:end]
    total_pages = (len(detail_data) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE  # 전체 페이지 수 계산
    # 페이지 범위 계산
    page_range = range(max(1, page - 2), min(total_pages + 1, page + 3))

    total_validation = get_total_validation()
    validation_date = total_validation.loc[0, 'date']

    logging.info(f"visited {PAGE_NAME} - type={type} / page={page} / lang={lang}")
    return render_template('validation.html', detail_data=paginated_data.to_dict('records'), 
                           total_pages=total_pages, current_page=page, lang=lang, type=type,
                           page_range=page_range, validation_date=validation_date,
                           translations=translations[lang],
                           popular_ranking=get_popular_ranking('kospi_daq' if lang == 'ko' else 'nyse_naq', with_name=lang),
                           total_validation=total_validation.to_dict('records'))

@bp.route('/daliy', methods=['GET'])
def daliy():
    date = request.args.get('date', None)
    lang = request.args.get('lang', 'ko')

    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    
    if not validate_date_format(date):
        return main.page_not_found404(lang=lang)
    
    detail_data = get_snp500_profit_validation(date)
    verified_date, d_day = is_verified_date(date)

    logging.info(f"visited {PAGE_NAME}/daliy - date={date} / lang={lang}")
    return render_template('daliy_validation.html', detail_data=detail_data.to_dict('records'), lang=lang,
                           translations=translations[lang], verified_date=verified_date, 
                           d_day=d_day, date=date,
                           popular_ranking=get_popular_ranking('kospi_daq' if lang == 'ko' else 'nyse_naq', with_name=lang))

@bp.route('/detail', methods=['GET'])
def detail():
    date = request.args.get('date', None)
    code = request.args.get('code', None)
    lang = request.args.get('lang', 'ko')
    market = 'nyse_naq'
    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()

    profit_validation = find_one_profit_validation(code, date, market, lang)
    if profit_validation is None:
        logging.info(f"validation/detail error - date : {date} / code : {code} / lang : {lang}")
        return main.page_not_found404(lang=lang)
    
    statistics_data = get_statistics_data(code, market, lang, date)
    if statistics_data is None:
        logging.info(f"validation/detail no statistics_data - date : {date} / code : {code} / lang : {lang}")
        return render_template('none_stock_info.html', code=code, name="", market=market, 
                               translations=translations[lang], lang=lang)

    statistics_data['date'] = statistics_data['date'].strftime('%Y-%m-%d')

    # 상승차트비율 추가
    if statistics_data['data_num_allday'] > 0:
        statistics_data['rise_rate_allday'] = round(statistics_data['rise_count_allday'] / statistics_data['data_num_allday'] * 100, 1)
    else:
        statistics_data['rise_rate_allday'] = 0
        
    verified_date, d_day = is_verified_date(date)
    if verified_date:
        draw_plt_stock_chart(code, date, lang, get_stock_data_pre_fol(code, date, market, preceding=31, following=10), validation_chart=True)
    draw_all_after_change_chart(code, market, lang, statistics_data, validation_date=date)
    
    profit = profit_validation['profit']
    score = profit_validation['score']
    score_str = "{:.1f}".format(score)
    gauge_name = f"{score_str}_{lang}"
    average_dif = _get_average_dif(statistics_data, score)
    investing_url, naver_url = get_url(code, market, lang)

    logging.info(f"visited {PAGE_NAME}/detail - date={date} / code={code} / lang={lang}")
    return render_template('detail_validation.html', statistics_data=statistics_data, lang=lang,
                           translations=translations[lang], verified_date=verified_date, 
                           d_day=d_day, date=date, naver_url=naver_url,
                           profit=profit,
                           gauge_name=gauge_name, score=score, average_dif=average_dif,
                           popular_ranking=get_popular_ranking('kospi_daq' if lang == 'ko' else 'nyse_naq', with_name=lang))

# 당시 날짜의 전 종목 평균 점수 역산하기
def _get_average_dif(data, origin):
    score = max(min(data['average_allday'] * 0.7, 5), -5)
    score += (data['rise_rate_allday'] - 50) * 0.2
    score = max(min(score, 10.0), -10.0) 
    score = round(score, 1)
    dif = round(origin - score, 1)
    
    return dif