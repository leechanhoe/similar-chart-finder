from validation_value import validate_lang
from pyfile.data_reader import (
    get_comparable_code_list,
    get_all_name,
    get_up_down_ranking,
    get_latest_update_date,
)
from flask import request, Blueprint, render_template, url_for, redirect, session
from translation import translations
from popular_ranking import get_popular_ranking
from pyfile.profit_validation import get_average_dif
import logging
import main


# main_market에 대한 url은 많지만 로직은 같으므로 통일된 응답 로직 실행
def _handle_get_request(request, market):
    lang = request.args.get("lang", "ko")
    if not validate_lang(lang, f"main_{market}"):
        return main.page_not_found404()

    # Flash messages for errors
    error_message_code = session.pop("error_message_code", None)
    code = session.pop("code", None)
    name = session.pop("name", None)

    update_date = get_latest_update_date(market)
    up_ranking, down_ranking = get_up_down_ranking(market, lang)
    average_score = get_average_dif(update_date, market)
    gauge_name = "{:.1f}".format(average_score)
    gauge_name = f"{gauge_name}_{lang}"
    logging.info(f"visited main_{market} - GET")

    template_kwargs = {
        "name_list": _get_name_list(market, lang),
        "update_date": update_date,
        "lang": lang,
        "translations": translations[lang],
        "popular_ranking": get_popular_ranking(market, with_name=lang),
        "up_ranking": up_ranking,
        "down_ranking": down_ranking,
        "market": market,
        "average_score": average_score,
        "gauge_name": gauge_name,
        "error_message_code": error_message_code,
        "code": code,
        "name": name,
    }
    return render_template(f"main_{market}.html", **template_kwargs)


def _normalize_string(s):
    return s.replace(" ", "").upper()


def _handle_common_mistakes(input_code):
    exceptions = {
        "TSMC": "TSM",
        "아마존": "AMZN",
        "구글": "GOOGL",
        "메타": "META",
        "네이버": "035420",
        "SOIL": "010950",
        "앨앤에프": "066970",
        "앨엔에프": "066970",
        "엘엔에프": "066970",
    }
    return exceptions.get(input_code, input_code)


# 존재하는 입력인지 체크 후 해당 값 반환
def _find_code(input_code_normalized, market, lang):
    df_names = get_all_name(market)

    # 먼저 정확한 일치를 시도
    for lang_suffix in ["ko", "en"]:
        name_column = f"name_{lang_suffix}"
        uppercased_names = df_names[name_column].str.replace(" ", "").str.upper()
        if input_code_normalized in uppercased_names.values:
            idx = uppercased_names[uppercased_names == input_code_normalized].index[0]
            name = df_names.loc[idx, name_column]
            code = df_names.loc[idx, "code"]
            return code, name
    uppercased_codes = df_names["code"].str.replace(" ", "").str.upper()
    if input_code_normalized in uppercased_codes.values:
        idx = uppercased_codes[uppercased_codes == input_code_normalized].index[0]
        code = df_names.loc[idx, "code"]
        name_column = f"name_{lang}"
        name = df_names.loc[idx, name_column]
        return code, name

    # 정확한 일치가 없을 경우, 부분 일치를 시도
    potential_matches = []

    # 이름에서 검색
    for lang_suffix in ["ko", "en"]:
        name_column = f"name_{lang_suffix}"
        uppercased_names = df_names[name_column].str.replace(" ", "").str.upper()
        mask = uppercased_names.str.contains(input_code_normalized)
        matched_indices = df_names[mask].index
        if len(matched_indices) == 1:
            idx = matched_indices[0]
            name = df_names.loc[idx, name_column]
            code = df_names.loc[idx, "code"]
            return code, name
        elif len(matched_indices) > 1:
            potential_matches.extend(
                df_names.loc[matched_indices, [name_column, "code"]].values.tolist()
            )

    # 코드에서 검색
    mask = uppercased_codes.str.contains(input_code_normalized)
    matched_indices = df_names[mask].index
    if len(matched_indices) == 1:
        idx = matched_indices[0]
        code = df_names.loc[idx, "code"]
        name_column = f"name_{lang}"
        name = df_names.loc[idx, name_column]
        return code, name
    elif len(matched_indices) > 1:
        potential_matches.extend(
            df_names.loc[matched_indices, ["name_ko", "code"]].values.tolist()
        )

    # 결과가 없거나 여러 개인 경우 None을 반환합니다.
    return None, None


# 다른 시장의 항목인지 체크
def _check_in_another_market(input_code_normalized, another_market):
    another_market_names = get_all_name(another_market)

    # 먼저 정확한 일치를 시도
    for col_name in ["name_ko", "name_en", "code"]:
        uppercased_values = (
            another_market_names[col_name].str.replace(" ", "").str.upper()
        )
        if input_code_normalized in uppercased_values.values:
            return True

    # 정확한 일치가 없을 경우, 부분 일치를 시도
    potential_matches = []
    for col_name in ["name_ko", "name_en", "code"]:
        uppercased_values = (
            another_market_names[col_name].str.replace(" ", "").str.upper()
        )
        mask = uppercased_values.str.contains(input_code_normalized)
        matched_indices = another_market_names[mask].index
        if len(matched_indices) == 1:
            # 부분 일치 결과가 하나뿐이라면 True를 반환
            return True
        elif len(matched_indices) > 1:
            # 부분 일치 결과가 여러 개일 경우, 잠재적 매칭에 추가
            potential_matches.extend(
                another_market_names.loc[matched_indices, col_name].values.tolist()
            )

    # 결과가 없거나 여러 개인 경우 False를 반환
    return False


# 검색 버튼 로직
def _handle_post_request(request, market):
    code = request.form["code"]
    lang = request.form["lang"]

    if not validate_lang(lang, f"main_{market}"):
        return redirect(url_for(f"main_{market}.main_{market}"))

    # Fetch data
    update_date = get_latest_update_date(market)
    up_ranking, down_ranking = get_up_down_ranking(market, lang)
    average_score = get_average_dif(update_date, market)
    gauge_name = f"{average_score:.1f}_{lang}"

    # Prepare template kwargs
    template_kwargs = {
        "code": code,
        "market": market,
        "lang": lang,
        "translations": translations[lang],
        "popular_ranking": get_popular_ranking(market, with_name=lang),
        "up_ranking": up_ranking,
        "down_ranking": down_ranking,
        "update_date": update_date,
        "average_score": average_score,
        "gauge_name": gauge_name,
        "name_list": _get_name_list(market, lang),
    }

    name = None
    input_code_normalized = _normalize_string(code)

    input_code_normalized = _handle_common_mistakes(input_code_normalized)

    # Find code and name in the dataframe
    code_found, name_found = _find_code(input_code_normalized, market, lang)
    if code_found:
        code = code_found
        name = name_found
        template_kwargs["name"] = name
        template_kwargs["code"] = code
    else:
        another_market = "nyse_naq" if market == "kospi_daq" else "kospi_daq"
        if _check_in_another_market(input_code_normalized, another_market):
            error_key = (
                "코스피 & 코스닥 검색기를 이용해주세요."
                if another_market == "kospi_daq"
                else "뉴욕증권 & 나스닥 검색기를 이용해주세요."
            )
        else:
            error_key = (
                "해당 종목명 또는 종목코드가 존재하지 않거나 지원하지 않는 종목입니다."
            )
        error_message_code = translations[lang][error_key]

        session["error_message_code"] = error_message_code
        session["code"] = code
        session["name"] = name
        logging.info(f"visited main_{market} - {code} / {error_message_code}")
        return redirect(url_for(f"main_{market}.main_{market}", lang=lang))

    # Check if code is in comparable_code_list
    comparable_code_list = get_comparable_code_list(market)
    if code not in comparable_code_list:
        error_message_code = translations[lang][
            "신규상장/신규지원 또는 잦은 거래정지로 비교가 불가능한 종목입니다."
        ]
        session["error_message_code"] = error_message_code
        session["code"] = code
        session["name"] = name
        logging.info(f"visited main_{market} - {code} / {error_message_code}")
        return redirect(url_for(f"main_{market}.main_{market}", lang=lang))

    logging.info(f"visited main_{market} - stock_info")
    return redirect(url_for("stock.stock", code=code, market=market, lang=lang))


# 유효한 종목명 리스트 반환
def _get_name_list(market, lang):
    df_names = get_all_name(market)
    name_list = list(df_names[f"name_{lang}"].values) + list(df_names["code"].values)
    name_list.sort(
        key=lambda x: (x[0].isdigit(), x)
    )  # 숫자보다 문자가 먼저오게, 알파벳(가나다)순 정렬
    return name_list


kospi_daq_bp = Blueprint("main_kospi_daq_old", __name__, url_prefix="/main_kospi_daq")


@kospi_daq_bp.route("/", methods=["GET", "POST"], endpoint="main_kospi_daq_old")
def main_kospi_daq():
    market = "kospi_daq"
    if request.method == "POST":
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)


kospi_daq_bp_hyphen = Blueprint(
    "main_kospi_daq", __name__, url_prefix="/main-kospi-daq"
)


@kospi_daq_bp_hyphen.route("/", methods=["GET", "POST"], endpoint="main_kospi_daq")
def main_kospi_daq_hyphen():
    market = "kospi_daq"
    if request.method == "POST":
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)


nyse_naq_bp = Blueprint("main_nyse_naq_old", __name__, url_prefix="/main_nyse_naq")


@nyse_naq_bp.route("/", methods=["GET", "POST"], endpoint="main_nyse_naq_old")
def main_nyse_naq():
    market = "nyse_naq"
    if request.method == "POST":
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)


nyse_naq_bp_hyphen = Blueprint("main_nyse_naq", __name__, url_prefix="/main-nyse-naq")


@nyse_naq_bp_hyphen.route("/", methods=["GET", "POST"], endpoint="main_nyse_naq")
def main_nyse_naq_hyphen():
    market = "nyse_naq"
    if request.method == "POST":
        return _handle_post_request(request, market)
    return _handle_get_request(request, market)
