from flask import Blueprint, render_template, request, redirect, url_for, session
from pyfile.data_reader import get_name
from pyfile.statistics_reader import get_statistics
from translation import translations
from popular_ranking import get_popular_ranking
from pyfile.shared_data import get_day_num_list, get_market_list
from validation_value import validate_lang
import main
import logging

PAGE_NAME = 'statistics'

bp = Blueprint(PAGE_NAME, __name__, url_prefix=f'/{PAGE_NAME}')

@bp.route('/', methods=['GET'])
def statistics():
    # POST 요청 처리 결과를 세션에서 가져옵니다.
    market = session.get('market', 'kospi_daq')
    up = session.get('up', True)
    rise_rate = session.get('rise_rate', False)
    day_num = session.get('day_num', 'all')
    lang = request.args.get('lang', 'ko')

    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()
    
    if market not in get_market_list() or up not in [True, False] or rise_rate not in [True, False] or day_num not in get_day_num_list(type='str') + ['all']:
        logging.info(f"{PAGE_NAME} invalid access - market : {market} / up : {up} / rise_rate : {rise_rate} / day_num : {day_num}")
        return main.page_not_found404(lang=lang)
    
    data = get_statistics(market, rank=10, up=up, rise_rate=rise_rate, day_num=day_num)
    data['average'] = data['average'].round(2)
    data['name'] = data['code'].apply(get_name, args=(market, lang, ))
    key = f'{market}_{up}_{rise_rate}_{day_num}'
    logging.info(f"visited {PAGE_NAME} - {key} / {lang}")

    return render_template(f'{PAGE_NAME}.html', data=data.to_dict('records'), date=data.iloc[0]['date'].strftime('%Y-%m-%d'),
                           market_type=market, up=up, rise_rate=rise_rate, day_num=day_num, image_name=key, lang=lang,
                           translations=translations[lang], popular_ranking=get_popular_ranking(market, with_name=lang))

@bp.route('/submit', methods=['POST'])
def submit():
    # 폼 데이터를 세션에 저장합니다.
    session['market'] = request.form.get('market', 'kospi_daq')
    session['up'] = request.form.get('up', 'True') == 'True'
    session['rise_rate'] = request.form.get('rise_rate', 'True') == 'True'
    session['day_num'] = request.form.get('day_num', 'all')
    lang = request.form.get('lang', 'ko')

    # 처리 결과를 나타내는 페이지로 리다이렉션합니다.
    return redirect(url_for(f'{PAGE_NAME}.{PAGE_NAME}', lang=lang))
