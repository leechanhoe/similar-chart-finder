from validation_value import validate_lang
from pyfile.data_reader import  get_comparable_code_list, get_all_name, get_up_down_ranking
from pyfile.data_reader import get_code, get_latest_update_date
from flask import request, Blueprint, render_template, url_for, redirect, session
from translation import translations
from popular_ranking import get_popular_ranking
from pyfile.profit_validation import get_average_dif
import logging
import main

# main_market에 대한 url은 많지만 로직은 같으므로 통일된 응답 로직 실행
def _handle_get_request(request, market):
    lang = request.args.get('lang', 'ko')
    if not validate_lang(lang, f'main_{market}'):
        return main.page_not_found404()
    
    # Flash messages for errors
    error_message_code = session.pop('error_message_code', None)
    code = session.pop('code', None)
    name = session.pop('name', None)

    update_date = get_latest_update_date(market)
    up_ranking, down_ranking = get_up_down_ranking(market, lang)
    average_score = get_average_dif(update_date, market)
    gauge_name = "{:.1f}".format(average_score)
    gauge_name = f"{gauge_name}_{lang}"
    logging.info(f"visited main_{market} - GET")

    template_kwargs = {
        'name_list': _get_name_list(market, lang),
        'update_date': update_date,
        'lang': lang,
        'translations': translations[lang],
        'popular_ranking': get_popular_ranking(market, with_name=lang),
        'up_ranking': up_ranking,
        'down_ranking': down_ranking,
        'market': market,
        'average_score': average_score,
        'gauge_name': gauge_name,
        'error_message_code': error_message_code,
        'code': code,
        'name': name
    }
    return render_template(f'main_{market}.html', **template_kwargs)

# 검색 버튼 로직
def _handle_post_request(request, market):
    code = request.form['code']
    lang = request.form['lang']
    if not validate_lang(lang, f'main_{market}'):
        return redirect(url_for(f'main_{market}.main_{market}'))

    update_date = get_latest_update_date(market)
    up_ranking, down_ranking = get_up_down_ranking(market, lang)
    average_score = get_average_dif(update_date, market)
    gauge_name = "{:.1f}".format(average_score)
    gauge_name = f"{gauge_name}_{lang}"
    template_kwargs = {
        'code': code,
        'market': market,
        'lang': lang,
        'translations': translations[lang],
        'popular_ranking': get_popular_ranking(market, with_name=lang),
        'up_ranking': up_ranking,
        'down_ranking': down_ranking,
        'update_date': update_date,
        'average_score': average_score,
        'gauge_name': gauge_name
    }

    df_names = get_all_name(market)
    template_kwargs['name_list'] = _get_name_list(market, lang)
    name = None

    uppercased_names_ko = df_names[f'name_ko'].str.replace(' ', '').str.upper()
    uppercased_names_en = df_names[f'name_en'].str.replace(' ', '').str.upper()
    uppercased_input = code.replace(' ', '').upper()

    if uppercased_input in uppercased_names_ko.values:
        code = df_names.loc[uppercased_names_ko == uppercased_input, f'name_ko'].values[0]
        name = code
        code = get_code(name, market, 'ko')
    if uppercased_input in uppercased_names_en.values:
        code = df_names.loc[uppercased_names_en == uppercased_input, f'name_en'].values[0]
        name = code
        code = get_code(name, market, 'en')

    uppercased_codes = df_names['code'].str.replace(' ', '').str.upper()
    uppercased_input = code.replace(' ', '').upper()

    # 사용자가 자주 실수하는 예외사항 직접 변환
    if uppercased_input == 'TSMC':
        uppercased_input = 'TSM'
    if uppercased_input == '아마존':
        uppercased_input = 'AMZN'
    if uppercased_input == '구글':
        uppercased_input = 'GOOGL'
    if uppercased_input == '메타':
        uppercased_input = 'META'
    if uppercased_input == '네이버':
        uppercased_input = '035420'
    if uppercased_input == 'SOIL':
        uppercased_input = '010950'
    if uppercased_input in ['앨앤에프', '앨엔에프', '엘엔에프']:
        uppercased_input = '066970'

    if uppercased_input in uppercased_codes.values:
        code = df_names.loc[uppercased_codes == uppercased_input, 'code'].values[0]

    if name is not None:
        template_kwargs['name'] = name
    template_kwargs['code'] = code

    if not code in df_names['code'].values:
        another_market = 'nyse_naq' if market == 'kospi_daq' else 'kospi_daq'
        another_market_name = get_all_name(another_market)
        if (uppercased_input in another_market_name[f'name_ko'].str.replace(' ', '').str.upper().values or 
        uppercased_input in another_market_name[f'name_en'].str.replace(' ', '').str.upper().values or
        uppercased_input in another_market_name['code'].values):
            error_message_code = translations[lang]["코스피 & 코스닥 검색기를 이용해주세요."] if another_market == 'kospi_daq' else translations[lang]["뉴욕증권 & 나스닥 검색기를 이용해주세요."]
        else:
            error_message_code = translations[lang]["해당 종목명 또는 종목코드가 존재하지 않거나 지원하지 않는 종목입니다."]
        
        session['error_message_code'] = error_message_code
        session['code'] = code
        session['name'] = name
        logging.info(f"visited main_{market} - {code} / {error_message_code}")
        return redirect(url_for(f'main_{market}.main_{market}', lang=lang))
    
    comparable_code_list = get_comparable_code_list(market)
    if code not in comparable_code_list:
        error_message_code = translations[lang]["신규상장/신규지원 또는 잦은 거래정지로 비교가 불가능한 종목입니다."]
        session['error_message_code'] = error_message_code
        session['code'] = code
        session['name'] = name
        logging.info(f"visited main_{market} - {code} / {error_message_code}")
        return redirect(url_for(f'main_{market}.main_{market}', lang=lang))
    
    logging.info(f"visited main_{market} - stock_info")
    return redirect(url_for('stock.stock', code=code, market=market, lang=lang))

# 유효한 종목명 리스트 반환
def _get_name_list(market, lang):
    df_names = get_all_name(market)
    name_list = list(df_names[f'name_{lang}'].values) + list(df_names['code'].values)
    name_list.sort(key=lambda x: (x[0].isdigit(), x)) # 숫자보다 문자가 먼저오게, 알파벳(가나다)순 정렬
    return name_list

kospi_daq_bp = Blueprint('main_kospi_daq_old', __name__, url_prefix='/main_kospi_daq')
@kospi_daq_bp.route('/', methods=['GET', 'POST'], endpoint='main_kospi_daq_old')
def main_kospi_daq():
    market = "kospi_daq"
    if request.method == 'POST':
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)

kospi_daq_bp_hyphen = Blueprint('main_kospi_daq', __name__, url_prefix='/main-kospi-daq')
@kospi_daq_bp_hyphen.route('/', methods=['GET', 'POST'], endpoint='main_kospi_daq')
def main_kospi_daq_hyphen():
    market = "kospi_daq"
    if request.method == 'POST':
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)

nyse_naq_bp = Blueprint('main_nyse_naq_old', __name__, url_prefix='/main_nyse_naq')
@nyse_naq_bp.route('/', methods=['GET', 'POST'], endpoint='main_nyse_naq_old')
def main_nyse_naq():
    market = "nyse_naq"
    if request.method == 'POST':
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)

nyse_naq_bp_hyphen = Blueprint('main_nyse_naq', __name__, url_prefix='/main-nyse-naq')
@nyse_naq_bp_hyphen.route('/', methods=['GET', 'POST'], endpoint='main_nyse_naq')
def main_nyse_naq_hyphen():
    market = "nyse_naq"
    if request.method == 'POST':
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)