from flask import Flask, render_template, request, send_from_directory
from controller.main_market import kospi_daq_bp, kospi_daq_bp_hyphen
from controller.main_market import nyse_naq_bp, nyse_naq_bp_hyphen
from controller.stock_info import stock_info_bp, stock_bp
from controller.result import bp as result_bp
from controller.statistics import bp as statistics_bp
from controller.pattern_search import bp as pattern_search_bp
from controller.validation import bp as validation_bp
from controller.secret import bp as secret_bp
from controller.secret import login_manager
from api import api_bp
from translation import translations
from popular_ranking import get_popular_ranking
from pyfile.shared_data import get_lang_list
from pyfile.profit_validation import get_rise_ratio
import os
import logging

# 로그의 출력 형식을 설정합니다.
FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
# 로그 레벨을 DEBUG로 설정하고, 출력 형식을 적용합니다.
logging.basicConfig(level=logging.INFO, format=FORMAT)

app = Flask(__name__, static_folder="/app/shared_files/static")
app.secret_key = os.getenv("SECRET_KEY")
blueprints = [
    kospi_daq_bp,
    kospi_daq_bp_hyphen,
    nyse_naq_bp,
    nyse_naq_bp_hyphen,
    stock_info_bp,
    stock_bp,
    result_bp,
    statistics_bp,
    secret_bp,
    api_bp,
    pattern_search_bp,
    validation_bp,
]

for bp in blueprints:
    app.register_blueprint(bp)
login_manager.init_app(app)


@app.context_processor
def inject_user_agent():  # 앱에서 온 요청인지 체크
    is_app = request.args.get("app", None) is not None
    user_agent = request.headers.get("SimilarChart-App")
    if is_app or user_agent:
        logging.info("App request")
    return dict(user_agent=user_agent, is_app=is_app)


# @app.before_request
# def under_maintenance():
#     # 서버 점검 중이며, 요청이 robots.txt나 ads.txt가 아닐 경우
#     if request.path not in ['/robots.txt', '/ads.txt']:
#         # maintenance.html을 반환
#         return render_template('maintenance.html'), 503  # 503 Service Unavailable 상태 코드 사용


@app.route("/", methods=["GET"])
def index():
    lang = request.args.get("lang", None)
    if lang is None or lang not in get_lang_list():
        # 사용자의 헤더에 따라 언어설정
        user_language = request.headers.get("Accept-Language")
        if user_language and "ko" in user_language:
            lang = "ko"
        else:
            lang = "en"

    market = "kospi_daq" if lang == "ko" else "nyse_naq"
    range_low = get_rise_ratio("~ -4")
    range_high = get_rise_ratio("6 ~")

    logging.info(f"visited index : lang : {lang}")

    template_kwargs = {
        "lang": lang,
        "translations": translations[lang],
        "range_low": range_low,
        "range_high": range_high,
        "popular_ranking": get_popular_ranking(market, with_name=lang),
    }
    return render_template("index.html", **template_kwargs)


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(405)
@app.errorhandler(410)
@app.errorhandler(500)
@app.errorhandler(502)
@app.errorhandler(503)
def page_not_found(e):
    user_language = request.headers.get("Accept-Language")
    if user_language and "ko" in user_language:
        lang = "ko"
    else:
        lang = "en"

    referrer = request.referrer  # 이전 페이지 URL을 가져옵니다.
    requested_url = request.url

    if referrer:
        logging.info(
            f"visited error - lang : {lang} / referrer : {referrer} / requested URL : {requested_url}"
        )
    else:
        logging.info(f"visited error - lang : {lang} / requested URL : {requested_url}")

        return render_template("error.html", translations=translations[lang], lang=lang)


@app.errorhandler(404)
def page_not_found404(e=None, lang=None):
    user_language = request.headers.get("Accept-Language")

    if lang is None:
        if user_language and "ko" in user_language:
            lang = "ko"
        else:
            lang = "en"

    referrer = request.referrer
    requested_url = request.url

    if referrer:
        logging.info(
            f"visited error - lang : {lang} / referrer : {referrer} / requested URL : {requested_url}"
        )
    else:
        logging.info(f"visited error - lang : {lang} / requested URL : {requested_url}")

    return render_template("error404.html", translations=translations[lang], lang=lang)


if __name__ == "__main__":
    port = int(os.environ.get("PORT"))
    app.run(host="0.0.0.0", port=port, debug=False)
    # app.run(debug=True)


@app.route("/robots.txt")
def static_from_root_robots():
    return send_from_directory(app.static_folder, request.path[1:])


@app.route("/sitemap.xml")
def static_from_root_sitemap():
    return send_from_directory(app.static_folder, request.path[1:])


@app.route("/ads.txt")
def static_from_root_ads():
    return send_from_directory(app.static_folder, request.path[1:])


@app.route("/app-ads.txt")
def static_from_root_app_ads():
    return send_from_directory(app.static_folder, request.path[1:])


@app.route("/privacy_policy", methods=["GET"])
def notice():
    lang = "ko"
    return render_template(
        "privacy_policy.html", translations=translations[lang], lang=lang
    )
