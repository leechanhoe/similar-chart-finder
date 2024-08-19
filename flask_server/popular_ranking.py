from pyfile.data_reader import get_name
from pyfile.db_engine import get_redis
from pyfile.web_scraping import update_popular_stock
import pandas as pd
import io

# 웹페이지 상단에 사용되는 인기종목 리스트 반환
def get_popular_ranking(market, with_name=None):
    redis = get_redis()
    key = f'popular_{market}'
    data = redis.get(key)
    if data is None:
        data = update_popular_stock(market)
    else:
        data = pd.read_json(io.StringIO(data.decode('utf-8')), dtype={'code': str})  # 데이터를 역직렬화합니다.
    data['average'] = data['average'].round(2)

    if with_name is not None:
        data['name'] = data['code'].apply(get_name, args=(market, with_name))
        data = data.to_dict('records')
    return data