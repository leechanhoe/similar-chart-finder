from pyfile.data_reader import get_name, get_predict_day
from pyfile.stock_data_reader import get_stock_data_pre_fol
from mplfinance.original_flavor import candlestick_ohlc
from matplotlib.patches import Patch
from scipy.interpolate import interp1d
from matplotlib.lines import Line2D
from PIL import Image
from plotly.subplots import make_subplots
from pyfile.shared_data import get_day_num_list, get_lang_list
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np
import math
import matplotlib.gridspec as gridspec
import matplotlib
import matplotlib.pyplot as plt
import os
import logging
import base64
import io

plt.rc("font", family="NanumBarunGothic")
matplotlib.use("Agg")


class InsufficientDataError(Exception):
    pass


# result 페이지의 두 이미지 생성
def update_result_images(code, base_date, market, day_num, lang, similar_data):
    if (
        os.path.exists(
            f"/app/shared_files/static/image_data/{market}/{base_date}/expected_chart_{code}_{base_date}_{str(day_num)}_{lang}.png"
        )
    ) and (
        os.path.exists(
            f"/app/shared_files/static/image_data/{market}/{base_date}/compare_chart_{code}_{base_date}_{str(day_num)}_{lang}.png"
        )
    ):
        return
    plt.clf()
    plt.close("all")
    base_data = get_stock_data_pre_fol(code, base_date, market, preceding=day_num - 1)

    draw_expected_chart(code, base_date, similar_data, base_data, market, day_num, lang)
    draw_compare_chart(code, base_date, similar_data, market, day_num, lang)
    plt.clf()
    plt.close("all")


# stock 페이지에 필요한 이미지 생성
def draw_all_after_change_chart(
    code, market, lang, statistics_data, validation_date=""
):
    if validation_date != "":
        path = f"/app/shared_files/static/image_data/cache/change_{code}_{validation_date}_{lang}.png"
    else:
        path = f"/app/shared_files/static/image_data/{market}/main_chart/change_{code}_{lang}.png"
    if os.path.exists(path):
        _draw_all_after_change_chart2(
            code, market, lang, statistics_data, validation_date
        )
        _draw_all_data_num_chart(code, market, lang, statistics_data, validation_date)
        return

    base_date = statistics_data["date"]
    base_data = get_stock_data_pre_fol(code, base_date, market, preceding=31)

    fig = plt.figure(figsize=(7, 5))
    fig.set_facecolor("w")
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])
    axes = []
    axes.append(plt.subplot(gs[0]))
    axes.append(plt.subplot(gs[1], sharex=axes[0]))
    axes[0].get_xaxis().set_visible(False)

    x = np.arange(len(base_data.index))
    ohlc = base_data[["Open", "High", "Low", "Close"]].values
    dohlc = np.hstack((np.reshape(x, (-1, 1)), ohlc))

    # 봉차트 그리기
    color_up = "r" if lang == "ko" else "g"
    color_down = "b" if lang == "ko" else "r"
    candlestick_ohlc(axes[0], dohlc, width=0.6, colorup=color_up, colordown=color_down)

    last_close = base_data.iloc[-1]["Close"]
    # 마지막 캔들스틱의 x축 인덱스
    last_index = len(base_data.index) - 1
    # 변동률을 적용할 5일 후의 x축 인덱스
    future_index = last_index + 5

    for day_num in get_day_num_list():
        after_change = statistics_data[f"average_{day_num}day"]
        if after_change is None:
            continue
        future_change = last_close * (
            1 + after_change * 0.01
        )  # 종가에 변동률을 적용한 미래 가격

        # 현재 종가에서 미래 가격을 연결하는 선 그리기
        axes[0].plot(
            [last_index, future_index],
            [last_close, future_change],
            label=f"{day_num}",
            alpha=0.5,
            linewidth=1,
        )

    after_change = statistics_data[f"average_allday"]
    if after_change is None:
        logging.info(f"{code}'s average_allday is None")
    else:
        average_change = last_close * (1 + after_change * 0.01)
        axes[0].plot(
            [last_index, future_index],
            [last_close, average_change],
            color=color_up if after_change >= 0 else color_down,
            linewidth=3.0,
            marker="o",
            label=("평균" if lang == "ko" else "Average"),
            alpha=0.8,
        )

        # 선에 대한 설명 달기
        axes[0].legend(loc="upper left")

        average_text = "{:.2f}".format(statistics_data[f"average_allday"]) + (
            "% ▲" if 0 <= statistics_data[f"average_allday"] else "% ▼"
        )
        axes[0].text(
            future_index + 2.5,
            average_change,
            average_text,
            fontsize=12,
            verticalalignment="center",
            color=color_up if after_change >= 0 else color_down,
            fontweight="bold",
        )

    # 거래량 차트 그리기
    axes[1].bar(x, base_data["Volume"], color="grey", width=0.65, align="center")
    axes[1].set_xticks(range(len(x)))

    base_dates = base_data.index.strftime(
        "%m.%d"
    )  # 첫 번째 값과 마지막 값을 포함해 총 6개의 날짜를 선택
    indices = np.linspace(0, len(base_dates) - 1, 6, dtype=int)
    x_labels = [base_dates[i] if i in indices else "" for i in range(len(base_dates))]
    axes[1].set_xticklabels(x_labels, fontsize=9)
    axes[1].get_yaxis().set_visible(False)

    # Get the positions of the yticks
    yticks = axes[0].get_yticks()
    # Draw a horizontal line at each ytick+
    for y in yticks:
        axes[0].axhline(y, color="gray", linestyle="dashed", linewidth=0.5)

    plt.savefig(path, bbox_inches="tight", pad_inches=0.1)
    plt.clf()
    plt.close("all")
    _draw_all_after_change_chart2(code, market, lang, statistics_data, validation_date)
    _draw_all_data_num_chart(code, market, lang, statistics_data, validation_date)


# 각 N일치 향후 추이를 더 자세하게 정사각형 이미지로 만들기
def _draw_all_after_change_chart2(
    code, market, lang, statistics_data, validation_date=""
):
    if validation_date != "":
        path = f"/app/shared_files/static/image_data/cache/change2_{code}_{validation_date}_{lang}.png"
    else:
        path = f"/app/shared_files/static/image_data/{market}/main_chart/change2_{code}_{lang}.png"
    if os.path.exists(path):
        return

    base_date = statistics_data["date"]
    base_data = get_stock_data_pre_fol(code, base_date, market, preceding=0)

    fig = plt.figure(figsize=(5, 5))
    fig.set_facecolor("w")
    ax = fig.add_subplot(111)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    x = np.arange(len(base_data.index))
    ohlc = base_data[["Open", "High", "Low", "Close"]].values
    dohlc = np.hstack((np.reshape(x, (-1, 1)), ohlc))

    # 봉차트 그리기
    color_up = "r" if lang == "ko" else "g"
    color_down = "b" if lang == "ko" else "r"
    candlestick_ohlc(ax, dohlc, width=0.6, colorup=color_up, colordown=color_down)

    last_close = base_data.iloc[-1]["Close"]
    # 마지막 캔들스틱의 x축 인덱스
    last_index = len(base_data.index) - 1
    # 변동률을 적용할 5일 후의 x축 인덱스
    future_index = last_index + 5

    for day_num in get_day_num_list():
        after_change = statistics_data[f"average_{day_num}day"]
        if after_change is None:
            continue
        future_change = last_close * (
            1 + after_change * 0.01
        )  # 종가에 변동률을 적용한 미래 가격

        # 현재 종가에서 미래 가격을 연결하는 선 그리기
        ax.plot(
            [last_index, future_index],
            [last_close, future_change],
            label=f"{day_num}",
            alpha=0.5,
            linewidth=2,
        )

    if after_change is None:
        logging.info(f"{code}'s average_allday is None")
    else:
        after_change = statistics_data[f"average_allday"]
        average_change = last_close * (1 + after_change * 0.01)
        ax.plot(
            [last_index, future_index],
            [last_close, average_change],
            color=color_up if after_change >= 0 else color_down,
            linewidth=7,
            marker="o",
            alpha=0.8,
        )

    plt.savefig(path, bbox_inches="tight", pad_inches=0.1)
    plt.clf()
    plt.close("all")


# 향후 상승, 하락 비율을 원형 차트로 그린 이미지
def _draw_all_data_num_chart(code, market, lang, statistics_data, validation_date=""):
    if validation_date != "":
        path = f"/app/shared_files/static/image_data/cache/ratio_{code}_{validation_date}_{lang}.png"
    else:
        path = f"/app/shared_files/static/image_data/{market}/main_chart/ratio_{code}_{lang}.png"
    if os.path.exists(path):
        return

    color_up = "#ff7272" if lang == "ko" else "#00aa00"
    color_down = "#7272FF" if lang == "ko" else "#ff7272"

    # 데이터 추출
    rise_count_allday = statistics_data["rise_count_allday"]
    data_num_allday = statistics_data["data_num_allday"]

    # 비율 계산
    up_ratio = rise_count_allday / data_num_allday
    down_ratio = (data_num_allday - rise_count_allday) / data_num_allday

    # 원형 차트 데이터와 색상 설정
    sizes = [up_ratio, down_ratio]
    colors = [color_up, color_down]

    # 원형 차트 그리기
    plt.figure(figsize=(5, 5))
    plt.pie(
        sizes,
        colors=colors,
        autopct=lambda pct: f"{pct:.0f}%\n",
        startangle=90,
        textprops={"fontsize": 32, "fontweight": 900, "color": "white"},
    )
    plt.axis("equal")  # 원형 차트가 원으로 보이도록 설정

    plt.savefig(path, bbox_inches="tight", pad_inches=0.1)
    plt.clf()
    plt.close("all")


# 색상 혼합
def _alpha_blend(color1, color2, alpha):
    return [
        int((color1[0] * alpha + color2[0] * (1 - alpha))),
        int((color1[1] * alpha + color2[1] * (1 - alpha))),
        int((color1[2] * alpha + color2[2] * (1 - alpha))),
    ]


def _convert_value(n):  # 이동평균선 기준을 캔들 가운데에 위치시키기 위한 값
    if n == 64:
        return 3
    elif n == 32:
        return 6
    elif n == 16:
        return 11
    elif n == 8:
        return 22
    elif n == 4:
        return 44
    else:
        return 2


# 주가 데이터를 기반으로 정사각 차트 이미지 생성
def convert_image(data, day_num, lang, center_yellow=False):
    only_close = True if day_num == 128 else False

    all_data = data
    data = data.iloc[-day_num:]

    if len(data) < day_num:
        print("종목 데이터 부족")
        return []

    stock_data = data[-day_num:]
    # 이미지 크기 설정
    width, height = 384, 384

    # 이미지 생성
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    if center_yellow:
        img[:, 100:292, :] = [220, 255, 220]

    # High, Low, Close, Volume 데이터 정규화
    high_prices = stock_data["High"].values
    low_prices = stock_data["Low"].values
    open_prices = stock_data["Open"].values
    close_prices = stock_data["Close"].values

    max_price = np.max(close_prices if only_close else high_prices)
    min_price = np.min(close_prices if only_close else low_prices)
    max_min_dif = max_price - min_price
    if max_min_dif == 0:
        return img

    if not only_close:
        high_prices_norm = (high_prices - min_price) / max_min_dif
        low_prices_norm = (low_prices - min_price) / max_min_dif
        open_prices_norm = (open_prices - min_price) / max_min_dif
    close_prices_norm = (close_prices - min_price) / max_min_dif

    stock_data_ma20 = all_data["Close"].rolling(window=20).mean()
    stock_data_ma20 = (stock_data_ma20 - min_price) / max_min_dif
    stock_data_ma10 = all_data["Close"].rolling(window=10).mean()
    stock_data_ma10 = (stock_data_ma10 - min_price) / max_min_dif
    stock_data_ma5 = all_data["Close"].rolling(window=5).mean()
    stock_data_ma5 = (stock_data_ma5 - min_price) / max_min_dif

    adjust_width = 128 // day_num
    adjust_width2 = _convert_value(day_num)
    for day in range(day_num):
        x_start_orig = day * 3 * adjust_width
        x_start = x_start_orig + (
            32 // day_num * 2
        )  # (32 // day_num)은 캔들사이 간격을 주기 위함
        x_end_orig = x_start_orig + 3 * adjust_width
        x_end = x_start + 3 * adjust_width - (32 // day_num * 2)

        close_price = int(close_prices_norm[day] * (height - 1))

        if only_close:
            for x in range(x_start, x_end):
                for y in range(max(close_price - 5, 0), min(close_price + 6, height)):
                    img[height - 1 - y, x] = [80, 188, 223]
                for y in range(0, max(close_price - 4, 0)):
                    img[height - 1 - y, x] = [210, 243, 248]
        else:
            high_price = int(high_prices_norm[day] * (height - 1))
            low_price = int(low_prices_norm[day] * (height - 1))
            open_price = int(open_prices_norm[day] * (height - 1))

            # 시가, 종가, 고가, 저가 막대그래프
            # 막대 왼쪽, 오른쪽 그리기 (시가, 종가 범위)
            for x in range(x_start, x_end):
                if close_prices[day] > open_prices[day]:
                    color = [255, 0, 0] if lang == "ko" else [0, 180, 0]  # 상승: 빨강
                    tail_color = (
                        [200, 0, 0] if lang == "ko" else [0, 140, 0]
                    )  # 상승 시 꼬리: 어두운 빨강
                elif close_prices[day] < open_prices[day]:
                    color = [0, 0, 255] if lang == "ko" else [255, 0, 0]  # 하락: 파랑
                    tail_color = (
                        [0, 0, 200] if lang == "ko" else [200, 0, 0]
                    )  # 하락 시 꼬리: 어두운 파랑
                else:  # 시가와 종가가 같을경우 어제보다 같거나 올랐으면 빨강, 아니면 파랑
                    if 0 <= stock_data["Change"].values[day]:
                        color = (
                            [255, 0, 0] if lang == "ko" else [0, 180, 0]
                        )  # 상승: 빨강
                        tail_color = (
                            [200, 0, 0] if lang == "ko" else [0, 140, 0]
                        )  # 상승 시 꼬리: 어두운 빨강
                    else:
                        color = (
                            [0, 0, 255] if lang == "ko" else [255, 0, 0]
                        )  # 하락: 파랑
                        tail_color = (
                            [0, 0, 200] if lang == "ko" else [200, 0, 0]
                        )  # 하락 시 꼬리: 어두운 파랑

                for y in range(
                    min(open_price, close_price), max(open_price, close_price) + 1
                ):
                    img[height - 1 - y, x] = color

                # 맨 위, 맨 아래 쩜상, 쩜하는 기본적으로 보이도록 두께 4만큼 그려주기
                if open_price <= 3 and close_price <= 3:
                    for y in range(1, 5):
                        img[height - y, x] = color
                elif height - 4 <= open_price and height - 4 <= close_price:
                    for y in range(4):
                        img[y, x] = color
                else:
                    for y in range(
                        min(open_price, close_price), max(open_price, close_price) + 1
                    ):
                        img[height - 1 - y, x] = color

            # 꼬리 그리기 (High, Low 범위)
            for x in range(x_start + adjust_width, x_end - adjust_width):
                for y in range(low_price, high_price + 1):
                    if (
                        img[height - 1 - y, x][0] != 0
                        and img[height - 1 - y, x][2] != 0
                    ):
                        img[height - 1 - y, x] = tail_color

        # 이동평균선 그리기 부분
        if 0 < day and not only_close:
            # 혹시 신규상장되어 이평선 데이터를 불러오지 못할 경우를 위한 -로 인덱싱
            idx = -day_num + day

            ma20_norm = stock_data_ma20.iloc[idx]
            if not np.isnan(ma20_norm) and not np.isnan(stock_data_ma20.iloc[idx - 1]):
                ma20_y = int(ma20_norm * (height - 1))
                if 0 <= ma20_y < height:
                    # 이전 day의 이동평균선 값
                    prev_ma20_norm = stock_data_ma20.iloc[idx - 1]
                    prev_ma20_y = int(prev_ma20_norm * (height - 1))

                    # 선형 보간을 위한 x, y 값 설정
                    x = np.array(
                        [x_start_orig - adjust_width2, x_end_orig - adjust_width2]
                    )  # 시작과 끝 지점을 day의 반만큼 왼쪽으로 이동
                    y = np.array([prev_ma20_y, ma20_y])

                    # 선형 보간 함수 생성
                    f = interp1d(x, y)

                    # 보간할 x값 생성
                    xnew = np.arange(
                        x_start_orig - adjust_width2, x_end_orig - adjust_width2, 1
                    )

                    # 보간한 y값 생성
                    ynew = f(xnew).astype(int)

                    for i, y in enumerate(ynew):
                        x = x_start_orig + i - adjust_width2
                        if 0 <= y < height and x < width:
                            for y_offset in range(
                                y - 4, y + 5
                            ):  # 이동평균선 주변에 블렌딩 처리
                                if 0 <= y_offset < height:
                                    new_color = _alpha_blend(
                                        [252, 190, 0],
                                        img[height - 1 - y_offset, x],
                                        0.3,
                                    )  # 노란색으로 변경
                                    img[height - 1 - y_offset, x] = new_color

            ma10_norm = stock_data_ma10.iloc[idx]
            if not np.isnan(ma10_norm) and not np.isnan(stock_data_ma10.iloc[idx - 1]):
                ma10_y = int(ma10_norm * (height - 1))
                if 0 <= ma10_y < height:
                    # 이전 day의 이동평균선 값
                    prev_ma10_norm = stock_data_ma10.iloc[idx - 1]
                    prev_ma10_y = int(prev_ma10_norm * (height - 1))

                    # 선형 보간을 위한 x, y 값 설정
                    x = np.array(
                        [x_start_orig - adjust_width2, x_end_orig - adjust_width2]
                    )  # 시작과 끝 지점을 day의 반만큼 왼쪽으로 이동
                    y = np.array([prev_ma10_y, ma10_y])

                    # 선형 보간 함수 생성
                    f = interp1d(x, y)

                    # 보간할 x값 생성
                    xnew = np.arange(
                        x_start_orig - adjust_width2, x_end_orig - adjust_width2, 1
                    )

                    # 보간한 y값 생성
                    ynew = f(xnew).astype(int)

                    for i, y in enumerate(ynew):
                        x = x_start_orig + i - adjust_width2
                        if 0 <= y < height and x < width:
                            for y_offset in range(
                                y - 4, y + 5
                            ):  # 이동평균선 주변에 블렌딩 처리
                                if 0 <= y_offset < height:
                                    new_color = _alpha_blend(
                                        [48, 48, 48], img[height - 1 - y_offset, x], 0.3
                                    )  # 회색으로 변경
                                    img[height - 1 - y_offset, x] = new_color

            ma5_norm = stock_data_ma5.iloc[idx]
            if not np.isnan(ma5_norm) and not np.isnan(stock_data_ma5.iloc[idx - 1]):
                ma5_y = int(ma5_norm * (height - 1))
                if 0 <= ma5_y < height:
                    # 이전 day의 이동평균선 값
                    prev_ma5_norm = stock_data_ma5.iloc[idx - 1]
                    prev_ma5_y = int(prev_ma5_norm * (height - 1))

                    # 선형 보간을 위한 x, y 값 설정
                    x = np.array(
                        [x_start_orig - adjust_width2, x_end_orig - adjust_width2]
                    )  # 시작과 끝 지점을 day의 반만큼 왼쪽으로 이동
                    y = np.array([prev_ma5_y, ma5_y])

                    # 선형 보간 함수 생성
                    f = interp1d(x, y)

                    # 보간할 x값 생성
                    xnew = np.arange(
                        x_start_orig - adjust_width2, x_end_orig - adjust_width2, 1
                    )

                    # 보간한 y값 생성
                    ynew = f(xnew).astype(int)

                    for i, y in enumerate(ynew):
                        x = x_start_orig + i - adjust_width2
                        if 0 <= y < height and x < width:
                            for y_offset in range(
                                y - 4, y + 5
                            ):  # 이동평균선 주변에 블렌딩 처리
                                if 0 <= y_offset < height:
                                    new_color = _alpha_blend(
                                        [139, 0, 255],
                                        img[height - 1 - y_offset, x],
                                        0.3,
                                    )  # 노란색으로 변경
                                    img[height - 1 - y_offset, x] = new_color

    if (
        day_num == 4
    ):  # 4일치를 그리는 경우는 오른쪽에 공백이 아예 없는것이 티가 나 8px만큼 생성
        img = np.roll(img, -8, axis=1)
        img[:, -8:] = [255, 255, 255]

    return img


# result 페이지의 비슷한 차트 10개 한번에 그려진 이미지 생성
def draw_compare_chart(code, base_date, similar_chart, market, day_num, lang):
    # Compute the number of rows for the grid
    nrows = math.ceil(len(similar_chart) / 5) + 1

    fig, axs = plt.subplots(nrows=nrows, ncols=5, figsize=(8, nrows * 2))

    # Add an image to the new row at the third column
    ax_top_center = axs[0][2]
    img_top_center = convert_image(
        get_stock_data_pre_fol(code, base_date, market, preceding=day_num + 18),
        day_num,
        lang,
    )

    if len(img_top_center) > 0:
        ax_top_center.imshow(img_top_center)
        ax_top_center.set_xticks([])
        ax_top_center.set_yticks([])

    ax_top_center.set_xlabel(
        ("기존 차트" if lang == "ko" else "original"), fontsize=11, fontweight="bold"
    )

    for i in [0, 1, 3, 4]:
        axs[0][i].axis("off")

    for i in range(1, nrows):
        for j in range(5):
            axs[i][j].axis("off")

    # Create the images in a grid
    for cnt, (i, row) in enumerate(similar_chart.iterrows()):
        similar_data = get_stock_data_pre_fol(
            row["compare_stock_code"],
            row["compare_date"],
            market,
            preceding=day_num + 18,
        )

        ax = axs[(cnt // 5) + 1][cnt % 5]

        img = convert_image(similar_data, day_num, lang)
        similar_data = similar_data.iloc[-day_num:]

        if len(img) > 0:
            ax.imshow(img)

            text = (
                get_name(row["compare_stock_code"], market, lang="ko")
                if market == "kospi_daq"
                else row["compare_stock_code"]
            )
            ax.set_xlabel(
                f"{cnt + 1}. {text}\n{similar_data.index[0].strftime('%y.%m.%d')}~{similar_data.index[-1].strftime('%y.%m.%d')}",
                fontsize=9,
                fontweight="bold",
            )
        else:
            ax.imshow(np.ones((1, 1, 3), dtype=np.uint8) * 255)  # 그냥 흰 이미지
            ax.set_xlabel(f"No Info", fontsize=9, fontweight="bold")
        ax.axis("on")
        ax.set_xticks([])
        ax.set_yticks([])

    # Create legend
    legend_elements = [
        Line2D([0], [0], color=[139 / 255, 0, 255 / 255], lw=3, label="5"),
        Line2D([0], [0], color=[96 / 255, 96 / 255, 96 / 255], lw=3, label="10"),
        Line2D([0], [0], color=[252 / 255, 190 / 255, 0], lw=3, label="20"),
    ]
    ax_legend = axs[0][4]
    ax_legend.legend(handles=legend_elements, loc="center", title="MA")
    ax_legend.axis("off")

    plt.savefig(
        f"/app/shared_files/static/image_data/{market}/{base_date}/compare_chart_{code}_{base_date}_{str(day_num)}_{lang}.png",
        dpi=200,
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.clf()
    plt.close("all")


# result 페이지의 향후 변동의 평균을 표기한 이미지 생성
def draw_expected_chart(
    code, base_date, similar_data, base_data, market, day_num, lang
):
    similar_chart_num = len(similar_data)
    fig = plt.figure(figsize=(7, 5))
    fig.set_facecolor("w")
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])
    axes = []
    axes.append(plt.subplot(gs[0]))
    axes.append(plt.subplot(gs[1], sharex=axes[0]))
    axes[0].get_xaxis().set_visible(False)

    x = np.arange(len(base_data.index))
    ohlc = base_data[["Open", "High", "Low", "Close"]].values
    dohlc = np.hstack((np.reshape(x, (-1, 1)), ohlc))

    # 봉차트 그리기
    color_up = "r" if lang == "ko" else "g"
    color_down = "b" if lang == "ko" else "r"
    candlestick_ohlc(axes[0], dohlc, width=0.6, colorup=color_up, colordown=color_down)

    last_close = base_data.iloc[-1]["Close"]
    predicted_changes = []
    for cnt, (i, row) in enumerate(similar_data.iterrows()):
        # logging.info(f"base_stock_code={row['base_stock_code']} / compare_stock_code={row['compare_stock_code']}")
        after_change = get_stock_data_pre_fol(
            row["compare_stock_code"],
            row["compare_date"],
            market,
            following=get_predict_day(day_num),
        )
        if len(after_change) == 0:
            continue
        after_change = after_change["Change"].iloc[1:]

        predicted_prices = [last_close] + [
            last_close * change for change in np.cumprod(1 + np.array(after_change))
        ]
        future_x = range(
            len(base_data.index) - 1, len(base_data.index) - 1 + len(predicted_prices)
        )
        if cnt != similar_chart_num - 1:
            axes[0].plot(future_x, predicted_prices, color="grey", alpha=0.3)
        else:
            axes[0].plot(
                future_x,
                predicted_prices,
                color="grey",
                alpha=0.3,
                label=("향후 추이" if lang == "ko" else "Future Trends"),
            )
        predicted_changes.append(after_change)

    # Compute average change
    average_change = np.mean(predicted_changes, axis=0)
    # Compute predicted prices based on average change
    predicted_prices_avg = [last_close] + [
        last_close * change for change in np.cumprod(1 + np.array(average_change))
    ]
    # Add predicted prices to the chart with a red thick line
    future_x_avg = range(
        len(base_data.index) - 1, len(base_data.index) - 1 + len(predicted_prices_avg)
    )
    after_close_mean = round(similar_data["after_close_change"].mean(), 2)
    if after_close_mean < 0:
        axes[0].plot(
            future_x_avg,
            predicted_prices_avg,
            color=color_down,
            linewidth=2.0,
            alpha=0.5,
            label=("평균 향후 추이" if lang == "ko" else "Average Future Trends"),
        )
    else:
        axes[0].plot(
            future_x_avg,
            predicted_prices_avg,
            color=color_up,
            linewidth=2.0,
            alpha=0.5,
            label=("평균 향후 추이" if lang == "ko" else "Average Future Trends"),
        )

    # 선에 대한 설명 달기
    axes[0].legend(loc="upper left")

    # 거래량 차트 그리기
    axes[1].bar(x, base_data["Volume"], color="grey", width=0.65, align="center")
    axes[1].set_xticks(range(len(x)))

    base_dates = base_data.index.strftime(
        "%m.%d"
    )  # 첫 번째 값과 마지막 값을 포함해 총 6개의 날짜를 선택
    indices = np.linspace(0, len(base_dates) - 1, 6, dtype=int)
    x_labels = [base_dates[i] if i in indices else "" for i in range(len(base_dates))]
    axes[1].set_xticklabels(x_labels, fontsize=9)
    axes[1].get_yaxis().set_visible(False)

    # Get the positions of the yticks
    yticks = axes[0].get_yticks()
    # Draw a horizontal line at each ytick
    for y in yticks:
        axes[0].axhline(y, color="gray", linestyle="dashed", linewidth=0.5)

    plt.savefig(
        f"/app/shared_files/static/image_data/{market}/{base_date}/expected_chart_{code}_{base_date}_{str(day_num)}_{lang}.png",
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.clf()
    plt.close("all")


# 향후 추이 페이지의 이미지 생성
def draw_detail_chart(code, base_date, market, day_num, lang):
    predict_day = get_predict_day(day_num)
    data = get_stock_data_pre_fol(
        code, base_date, market, preceding=day_num + 18, following=predict_day
    )
    base_data = (data.iloc[-(day_num + predict_day) :]).copy()
    if len(base_data) == 0:
        raise InsufficientDataError()
    # Create an array of indices for the x values
    x_values = list(range(len(base_data)))

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.85, 0.15],
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        dragmode=False,
        autosize=True,
        margin=dict(l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Create a list of date strings
    date_strings = [date.strftime("%Y-%m-%d") for date in base_data.index]
    change_percentage = base_data["Change"].map(lambda x: f"<b>Change:</b> {x:.2%}")
    hover_texts = [
        f"<b>Date:</b> {date}<br>{change}"
        for date, change in zip(date_strings, change_percentage)
    ]
    # Add candlestick trace to the first row,
    # and specify the colors for increasing and decreasing days
    color_up = "red" if lang == "ko" else "green"
    color_down = "blue" if lang == "ko" else "red"
    fig.add_trace(
        go.Candlestick(
            x=x_values,
            open=base_data["Open"],
            high=base_data["High"],
            low=base_data["Low"],
            close=base_data["Close"],
            hovertext=hover_texts,
            showlegend=False,
            increasing_line_color=color_up,
            decreasing_line_color=color_down,
        ),
        row=1,
        col=1,
    )

    # Add volume bar chart trace to the second row
    fig.add_trace(
        go.Bar(
            x=x_values,
            y=base_data["Volume"],
            showlegend=False,
            marker=dict(color="#808080"),
        ),
        row=2,
        col=1,
    )

    # Remove x-axis tick labels for the first subplot (candlestick chart)
    fig.update_xaxes(showticklabels=False, row=1, col=1)

    # Calculate moving averages
    base_data["MA5"] = data["Close"].rolling(window=5).mean()
    base_data["MA10"] = data["Close"].rolling(window=10).mean()
    base_data["MA20"] = data["Close"].rolling(window=20).mean()

    # Add moving averages to the chart
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=base_data["MA5"],
            mode="lines",
            name="5",
            line=dict(color="rgba(139, 0, 255, 0.5)"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=base_data["MA10"],
            mode="lines",
            name="10",
            line=dict(color="rgba(96, 96, 96, 0.5)"),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=base_data["MA20"],
            mode="lines",
            name="20",
            line=dict(color="rgba(252, 190, 0, 0.5)"),
            hoverinfo="skip",
        )
    )

    # Calculate the range for the yellow rectangle
    start_of_yellow = len(base_data) - (predict_day + 0.5)
    end_of_yellow = len(base_data)

    # Add a yellow rectangle to the background of the last 10 days
    fig.add_shape(
        type="rect",
        xref="x",
        yref="paper",
        x0=start_of_yellow,
        y0=0,
        x1=end_of_yellow,
        y1=1,
        fillcolor="yellow",
        opacity=0.2,
        layer="below",
        line_width=0,
    )
    trend = "향후 추이" if lang == "ko" else "Future Trends"
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name=trend,
            marker_symbol="square",
            marker=dict(color="yellow"),
            hoverinfo="skip",
        )
    )

    # Convert the figure to HTML
    div = pio.to_html(fig, full_html=False)
    del fig
    return div


# 랭킹 페이지 하단의 차트 10개가 그려진 이미지 생성
def draw_statistics_chart(data, market, day_num, file_name):
    for lang in get_lang_list():
        # Compute the number of rows for the grid
        nrows = math.ceil(len(data) / 5) + 1

        fig, axs = plt.subplots(nrows=nrows, ncols=5, figsize=(8, nrows * 2))

        # Add an image to the new row at the third column
        ax_top_center = axs[0][2]
        img_top_center = convert_image(
            get_stock_data_pre_fol(
                data.iloc[0]["code"],
                data.iloc[0]["date"],
                market,
                preceding=day_num + 18,
            ),
            day_num,
            lang,
        )

        if len(img_top_center) > 0:
            ax_top_center.imshow(img_top_center)
            ax_top_center.set_xticks([])
            ax_top_center.set_yticks([])

        ax_top_center.set_xlabel(
            (
                get_name(data.iloc[0]["code"], market, lang="ko")
                if market == "kospi_daq"
                else data.iloc[0]["code"]
            ),
            fontsize=13,
            fontweight="bold",
        )

        for i in [0, 1, 3, 4]:
            axs[0][i].axis("off")

        # Create the images in a grid
        for cnt, (i, row) in enumerate(data.iterrows()):
            stock_data = get_stock_data_pre_fol(
                row["code"], row["date"], market, preceding=day_num + 18
            )

            ax = axs[(cnt // 5) + 1][cnt % 5]
            img = convert_image(stock_data, day_num, lang)
            stock_data = stock_data.iloc[-day_num:]

            if len(img) > 0:
                ax.imshow(img)
                text = (
                    get_name(row["code"], market, lang="ko")
                    if market == "kospi_daq"
                    else row["code"]
                )
                if lang == "ko":
                    color = "red" if row["average"] >= 0 else "blue"
                else:
                    color = "green" if row["average"] >= 0 else "red"
                ax.set_xlabel(
                    f"{cnt + 1}. {text}", fontsize=10, fontweight="bold", color=color
                )
            else:
                ax.imshow(np.ones((1, 1, 3), dtype=np.uint8) * 255)  # 그냥 흰 이미지
                text = "정보없음" if lang == "ko" else "No Info"
                ax.set_xlabel(text, fontsize=11, fontweight="bold")
            ax.set_xticks([])
            ax.set_yticks([])

        axs[0][0].text(
            0.5,
            0.8,
            f"{stock_data.index[0].strftime('%y.%m.%d')}~{stock_data.index[-1].strftime('%y.%m.%d')}",
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
        )

        # Create legend
        legend_elements = [
            Line2D([0], [0], color=[139 / 255, 0, 255 / 255], lw=3, label="5"),
            Line2D([0], [0], color=[96 / 255, 96 / 255, 96 / 255], lw=3, label="10"),
            Line2D([0], [0], color=[252 / 255, 190 / 255, 0], lw=3, label="20"),
        ]
        ax_legend = axs[0][4]
        ax_legend.legend(handles=legend_elements, loc="center", title="MA")
        ax_legend.axis("off")

        plt.savefig(
            f"/app/shared_files/static/image_data/statistics/{file_name}_{lang}.png",
            dpi=200,
            bbox_inches="tight",
            pad_inches=0.1,
        )
        plt.clf()
        plt.close("all")


# stock 페이지의 N일치 비교를 나타내는 각 정사각 차트 이미지 생성
def draw_stock_info_charts(code, base_date, market, lang):
    all_exist = True
    for day in get_day_num_list(type="str"):
        if not os.path.exists(
            f"/app/shared_files/static/image_data/cache/{code}_{base_date}_{day}_{lang}.png"
        ):
            all_exist = False
    if all_exist:
        return

    for day_num in get_day_num_list():
        stock_data = get_stock_data_pre_fol(
            code, base_date, market, preceding=day_num + 18
        )
        img = convert_image(stock_data, day_num, lang)
        if len(img) == 0:
            img = np.ones((1, 1, 3), dtype=np.uint8) * 255
        img = Image.fromarray(img, "RGB")
        img.save(
            f"/app/shared_files/static/image_data/cache/{code}_{base_date}_{day_num}_{lang}.png"
        )


# 앱의 드로잉 검색 결과화면에 사용하는 정사각 차트 이미지 생성
def draw_drawing_search_chart(code, base_date, day_num, market, lang, pattern=False):
    if pattern:
        file_path = f"/app/shared_files/static/image_data/cache/pattern_{code}_{base_date}_{lang}.png"
    else:
        file_path = f"/app/shared_files/static/image_data/cache/{code}_{base_date}_{day_num}_{lang}.png"
    # 이미지가 이미 존재하면 해당 이미지를 읽어 Base64로 인코딩하여 반환
    if os.path.exists(file_path):
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string

    if pattern:
        stock_data = get_stock_data_pre_fol(
            code, base_date, market, preceding=day_num + 16, following=2
        )
    else:
        stock_data = get_stock_data_pre_fol(
            code, base_date, market, preceding=day_num + 18
        )

    # 이미지가 없으면 새로 생성
    img = convert_image(stock_data, day_num, lang, center_yellow=pattern)
    if len(img) == 0:
        img = np.ones((1, 1, 3), dtype=np.uint8) * 255  # 기본 이미지 생성
    img = Image.fromarray(img, "RGB")

    # 이미지를 파일 시스템에 저장하는 대신 메모리에서 직접 Base64로 인코딩
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    encoded_string = base64.b64encode(buffered.getvalue()).decode("utf-8")

    img.save(file_path)
    return encoded_string


# 패턴 검색 결과 이미지 생성
def draw_plt_stock_chart(code, base_date, lang, stock_data, validation_chart=False):
    if validation_chart:
        path = f"/app/shared_files/static/image_data/cache/detail_validation_{code}_{base_date}_{lang}.png"
    else:
        path = f"/app/shared_files/static/image_data/cache/pattern_result_{code}_{base_date}_{lang}.png"
    if os.path.exists(path):
        return

    fig = plt.figure(figsize=(7, 5))
    fig.set_facecolor("w")
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1])
    axes = []
    axes.append(plt.subplot(gs[0]))
    axes.append(plt.subplot(gs[1], sharex=axes[0]))
    axes[0].get_xaxis().set_visible(False)

    x = np.arange(len(stock_data.index))
    ohlc = stock_data[["Open", "High", "Low", "Close"]].values
    dohlc = np.hstack((np.reshape(x, (-1, 1)), ohlc))

    # 연한 초록색 배경 설정
    base_index = stock_data.index.get_loc(base_date)
    light_green = [220 / 255, 255 / 255, 220 / 255]
    light_blue = [220 / 255, 220 / 255, 255 / 255]
    if not validation_chart:
        for i in range(base_index - 3, base_index + 1):
            axes[0].axvspan(i - 0.5, i + 0.5, facecolor=light_green, edgecolor="none")
        label = "발견된 패턴" if lang == "ko" else "Detected Pattern"
        legend_patch1 = Patch(facecolor=light_green, edgecolor="none", label=label)
        axes[0].legend(
            handles=[
                legend_patch1,
            ],
            loc="upper left",
        )
    else:
        for i in range(len(stock_data) - 1, len(stock_data) - 11, -1):
            axes[0].axvspan(i - 0.5, i + 0.5, facecolor=light_green, edgecolor="none")
        axes[0].axvspan(
            base_index - 0.5, base_index + 0.5, facecolor=light_blue, edgecolor="none"
        )

        legend_patch1 = Patch(
            facecolor=light_green,
            edgecolor="none",
            label="향후 추이" if lang == "ko" else "Future Trends",
        )
        legend_patch2 = Patch(
            facecolor=light_blue,
            edgecolor="none",
            label="평가일" if lang == "ko" else "Evaluation Date",
        )
        axes[0].legend(handles=[legend_patch1, legend_patch2], loc="upper left")

    # 봉차트 그리기
    color_up = "r" if lang == "ko" else "g"
    color_down = "b" if lang == "ko" else "r"
    candlestick_ohlc(axes[0], dohlc, width=0.6, colorup=color_up, colordown=color_down)

    # 거래량 차트 그리기
    axes[1].bar(x, stock_data["Volume"], color="grey", width=0.65, align="center")
    axes[1].set_xticks(range(len(x)))

    base_dates = stock_data.index.strftime(
        "%m.%d"
    )  # 첫 번째 값과 마지막 값을 포함해 총 6개의 날짜를 선택
    indices = np.linspace(0, len(base_dates) - 1, 6, dtype=int)
    x_labels = [base_dates[i] if i in indices else "" for i in range(len(base_dates))]
    axes[1].set_xticklabels(x_labels, fontsize=9)
    axes[1].get_yaxis().set_visible(False)

    # Get the positions of the yticks
    yticks = axes[0].get_yticks()
    # Draw a horizontal line at each ytick+
    for y in yticks:
        axes[0].axhline(y, color="gray", linestyle="dashed", linewidth=0.5)

    plt.savefig(path, bbox_inches="tight", pad_inches=0.1)
    plt.clf()
    plt.close("all")


# 지수 차트 이미지 업데이트
def update_index_image(data, market):
    for lang in ["ko", "en"]:
        img = convert_image(data, 64, lang)
        img = Image.fromarray(img, "RGB")
        file_name = "kospi" if market == "kospi_daq" else "nasdaq"
        img.save(
            f"/app/shared_files/static/image_data/{market}/{file_name}_chart_{lang}.png"
        )
