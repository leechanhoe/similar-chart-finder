from flask import request, Blueprint, render_template
from pyfile.data_reader import get_investing_url
from pyfile.db_engine import get_redis
from pyfile.data_reader import (
    get_name,
    get_naver_url,
    get_same_industry_code,
    get_valid_day_num,
    get_stock_code,
)
from translation import translations
from popular_ranking import get_popular_ranking
from pyfile.shared_data import get_day_num_list
from validation_value import validate_market, validate_lang, validate_code
from pyfile.image_manager import draw_all_after_change_chart, draw_stock_info_charts
from pyfile.statistics_reader import get_statistics_one_stock, get_past_statistics
from pyfile.profit_validation import get_average_dif, get_rise_ratio

# from indicator_manager import get_indicators
import main
import numpy as np
import logging
import random

PAGE_NAME = "stock_info"

stock_info_bp = Blueprint(PAGE_NAME, __name__, url_prefix=f"/{PAGE_NAME}")


@stock_info_bp.route("/", methods=["GET"])
def stock_info():
    code = request.args.get("code", None)
    market = request.args.get("market", None)
    lang = request.args.get("lang", "ko")

    if not validate_lang(lang, PAGE_NAME):
        return main.page_not_found404()

    if market is None:
        kospi_daq_codes = get_stock_code("kospi_daq", only_code=True, only_valid=False)
        nyse_naq_codes = get_stock_code("nyse_naq", only_code=True, only_valid=False)
        if code in kospi_daq_codes:
            market = "kospi_daq"
        elif code in nyse_naq_codes:
            market = "nyse_naq"
        else:
            market = "kospi_daq" if lang == "ko" else "nyse_naq"
            logging.info(f"none_stock_info_invalid_code - {code}")
            return render_template(
                "none_stock_info_invalid_code.html",
                code=code,
                market=market,
                translations=translations[lang],
                lang=lang,
                popular_ranking=get_popular_ranking(market, with_name=lang),
            )

    if not validate_market(market, PAGE_NAME):
        return main.page_not_found404(lang=lang)

    if not validate_code(code, market, PAGE_NAME):
        if code in get_stock_code(market, only_code=True, only_valid=False):
            return render_template(
                "none_stock_info.html",
                code=code,
                name=get_name(code, market, lang),
                market=market,
                translations=translations[lang],
                lang=lang,
                popular_ranking=get_popular_ranking(market, with_name=lang),
            )
        else:
            return render_template(
                "none_stock_info_invalid_code.html",
                market=market,
                translations=translations[lang],
                lang=lang,
                popular_ranking=get_popular_ranking(market, with_name=lang),
            )

    data = get_statistics_data(code, market, lang)
    if data is None:
        return render_template(
            "none_stock_info.html",
            code=code,
            name=get_name(code, market, lang),
            market=market,
            translations=translations[lang],
            lang=lang,
        )
    data["date"] = data["date"].strftime("%Y-%m-%d")

    none_result = None
    if data["data_num_allday"] > 0:
        data["rise_rate_allday"] = round(
            data["rise_count_allday"] / data["data_num_allday"] * 100, 1
        )
    else:
        data["rise_rate_allday"] = 0
        none_result = True

    draw_all_after_change_chart(code, market, lang, data)
    draw_stock_info_charts(code, data["date"], market, lang)

    score, gauge_name = _get_score(data, lang, market)
    plus_view(code, market)
    investing_url, naver_url = get_url(code, market, lang)
    same_industry = _get_same_industry(code, market, lang)
    valid_day_num = get_valid_day_num(code, 0, market)
    average_dif = get_average_dif(data["date"], market)
    analysis = _get_chart_analysis(score, lang)
    range_low = get_rise_ratio("~ -4")
    range_high = get_rise_ratio("6 ~")
    # indicator = get_indicators(market, code, data['date'], lang, update=True).to_dict('records')

    logging.info(
        f"visited {PAGE_NAME} : ({get_name(code, market, lang)}){code} - score : {score}"
    )

    template_kwargs = {
        "data": data,
        "gauge_name": gauge_name,
        "lang": lang,
        "market": market,
        "investing_url": investing_url,
        "update_date": data["date"],
        "translations": translations[lang],
        "naver_url": naver_url,
        "none_result": none_result,
        "same_industry": same_industry,
        "popular_ranking": get_popular_ranking(market, with_name=lang),
        "score": score,
        "valid_day_num": valid_day_num,
        "average_dif": average_dif,
        "analysis": analysis,
        "range_low": range_low,
        "range_high": range_high,
    }
    return render_template(f"{PAGE_NAME}.html", **template_kwargs)


# Duplicate the blueprint with 'stock' URL prefix
stock_bp = Blueprint("stock", __name__, url_prefix="/stock")
stock_bp.add_url_rule("/", view_func=stock_info, endpoint="stock")


# 조회수 상승
def plus_view(code, market):
    key = f"views_{market}_{code}"
    redis = get_redis()
    # Redis에서 데이터가 없는 경우 초기값을 1로 설정하고, 있으면 값을 증가시킵니다.
    redis.incr(key)


def get_url(code, market, lang):
    # 사용자에게 해당 링크로 리다이렉트. 사용자의 언어 설정에 따라 URL이 달라집니다.
    if lang == "ko":
        investing_url = "https://kr.investing.com"
    else:
        investing_url = "https://investing.com"
    investing_url += get_investing_url(code, market)
    if market == "kospi_daq":
        naver_url = "https://m.stock.naver.com/domestic/stock/" + code + "/total"
    elif market == "nyse_naq":
        naver_url = (
            "https://m.stock.naver.com/worldstock/stock/"
            + code
            + get_naver_url(code, market)
        )
    return investing_url, naver_url


# 동일 업종 체크
def _get_same_industry(code, market, lang):
    same_industry = get_same_industry_code(code, market, 10)

    same_industry = same_industry[same_industry["code"] != code].head(9)
    same_industry["name"] = same_industry["code"].apply(
        get_name,
        args=(
            market,
            lang,
        ),
    )
    same_industry = same_industry.to_dict("records")
    return same_industry


def _get_score(data, lang, market):
    if data["average_allday"] is None or data["data_num_allday"] < 45:
        gauge_name = f"none_{lang}"
        score = 0
    else:
        rate = max(min(data["average_allday"] * 0.7, 5), -5)
        rate += (data["rise_rate_allday"] - 50) * 0.2
        rate += get_average_dif(data["date"], market)
        rate = max(min(rate, 10.0), -10.0)
        score = round(rate, 1)
        rate = "{:.1f}".format(rate)
        gauge_name = f"{rate}_{lang}"

    return score, gauge_name


# 종목 정보에 사용되는 통계 데이터 가져오기
def get_statistics_data(code, market, lang, past_date=""):
    if past_date == "":
        data = get_statistics_one_stock(code, market)
    else:
        data = get_past_statistics(code, market, past_date)
    if len(data) == 0 or data["data_num_allday"].iloc[0] == 0:
        return None

    data["name"] = data["code"].apply(
        get_name,
        args=(
            market,
            lang,
        ),
    )
    data.replace({np.nan: None}, inplace=True)
    cols_to_round = [f"average_{day}day" for day in get_day_num_list(type="str")]
    data[cols_to_round] = data[cols_to_round].round(
        2
    )  # redis에 넣다 빼면 데이터 손실이 있어 다시 반올림
    data["average_allday"] = data[cols_to_round].mean(axis=1)
    data = data.to_dict("index")[0]
    return data


def _get_chart_analysis(value, lang):
    # Define the messages for each range in Korean
    messages_ko = {
        "below_minus_5": [
            "과거 비슷한 차트 대부분이 이후 하락했어요. 물론 반드시 하락하는 건 아니지만 주의하는 게 좋을 것 같아요.",
            "차트상으로는 하락을 나타내고 있어요. 물론 반드시 하락하는 건 아니지만 주의하는 게 좋을 것 같아요.",
        ],
        "minus_5_to_minus_3": [
            "과거 비슷한 차트들은 이후 하락하는 경우가 조금 더 많았어요. 하지만 하락 확률이 많이 높은 건 아니에요.",
            "차트상으로는 하락하는 경우가 조금 더 많았어요. 하지만 상승하는 경우도 있으니 괜찮아요.",
        ],
        "minus_3_to_minus_2": [
            "과거 비슷한 차트들로 분석했을 때 큰 문제는 없어 보이지만 주의하세요.",
            "차트상으로는 큰 문제는 없어 보이지만 주의하세요.",
        ],
        "minus_2_to_3": [
            "과거 비슷한 차트들을 봤을 때 큰 문제는 없어 보여요.",
            "과거 비슷한 차트들을 보면 크게 걱정하지 않으셔도 될 것 같아요.",
            "애매할 땐 관망하는 것도 나쁘지 않아 보여요.",
            "차트상으로는 큰 문제는 없어 보여요.",
            "상승/하락 어느 쪽도 이상하지 않아 보여요.",
            "차트상으로는 크게 걱정하지 않으셔도 될 것 같아요.",
        ],
        "3_to_5": [
            "과거 비슷한 차트들은 이후 상승하는 경우가 조금 더 많았어요. 하지만 확률이 많이 높은 건 아니에요.",
            "조금 긍정적으로 봐도 괜찮을 것 같아요.",
        ],
        "5_to_7": [
            "과거 비슷한 차트들이 상승하는 경우가 많았어요. 꽤 괜찮아 보이지만 100%는 아니니 주의하세요.",
            "차트상으로는 상승하는 경우가 더 많았어요. 하지만 하락하는 경우도 있으니 조심하세요.",
        ],
        "above_7": [
            "과거 비슷한 차트들이 대부분 상승했어요. 매수를 고려해 볼 만 하지만 100%는 아니니 주의하세요.",
            "차트상으로는 상승을 나타내고 있어요. 하지만 하락하는 경우도 있으니 조심하세요.",
        ],
    }

    # Define the messages for each range in English
    messages_en = {
        "below_minus_5": [
            "Most similar charts in the past have declined afterward. Although it may not necessarily decline, it's better to be cautious.",
            "The chart indicates a decline. Although it may not necessarily decline, it's better to be cautious.",
        ],
        "minus_5_to_minus_3": [
            "Similar charts in the past have tended to decline slightly more often afterward. However, the probability of a decline is not very high.",
            "The chart indicates a slightly higher chance of decline. However, there are also instances of rises, so it should be fine.",
        ],
        "minus_3_to_minus_2": [
            "Analysis of similar charts in the past shows no major issues, but be cautious.",
            "The chart indicates no major issues, but be cautious.",
        ],
        "minus_2_to_3": [
            "Similar charts in the past have shown no major issues.",
            "Based on similar charts in the past, there's no need to worry much.",
            "When uncertain, observing the situation might not be a bad idea.",
            "The chart indicates no major issues.",
            "Neither a rise nor a fall seems unusual based on the chart.",
            "The chart indicates there's no need to worry much.",
        ],
        "3_to_5": [
            "Similar charts in the past have shown a slightly higher chance of a rise afterward. However, the probability is not very high.",
            "You can look at it a bit optimistically.",
        ],
        "5_to_7": [
            "Similar charts in the past have often shown a rise. It looks quite good, but it's not 100%, so be cautious.",
            "The chart indicates more cases of rise. However, there are also instances of decline, so be cautious.",
        ],
        "above_7": [
            "Most similar charts in the past have risen afterward. It might be worth considering a purchase, but it's not 100%, so be cautious.",
            "The chart indicates a rise. However, there are also instances of decline, so be cautious.",
        ],
    }

    # Select the appropriate messages based on the language
    messages = messages_ko if lang == "ko" else messages_en

    # Select the appropriate message based on the value
    if value < -5:
        return random.choice(messages["below_minus_5"])
    elif -5 <= value < -3:
        return random.choice(messages["minus_5_to_minus_3"])
    elif -3 <= value < -2:
        return random.choice(messages["minus_3_to_minus_2"])
    elif -2 <= value < 3:
        return random.choice(messages["minus_2_to_3"])
    elif 3 <= value < 5:
        return random.choice(messages["3_to_5"])
    elif 5 <= value < 7:
        return random.choice(messages["5_to_7"])
    else:
        return random.choice(messages["above_7"])
