import shutil
import os
import glob
import logging
import pandas as pd
from dateutil.relativedelta import relativedelta

# result 이미지들 삭제
def delete_result_image(base_date, market, save_period=30):
    base_date = base_date.strftime('%Y-%m-%d')
    
    #먼저 3달이 지난 이미지들 삭제
    target_dir = f'/app/shared_files/static/image_data/{market}/'
    for i in range(save_period + 1, save_period + 30):
        old_date = pd.to_datetime(base_date).date() - relativedelta(days=i)
    
        # Generate the directory name for the date
        dir_to_delete = os.path.join(target_dir, old_date.strftime('%Y-%m-%d'))
        
        if os.path.exists(dir_to_delete):
            shutil.rmtree(dir_to_delete)
    logging.info(f"result cache image is deleted")

# 캐시 이미지 삭제
def delete_cache_image():
    files = glob.glob(f'/app/shared_files/static/image_data/cache/*')
    # 디렉토리가 존재하는지 확인하고, 존재하면 삭제합니다.
    for f in files:
        os.remove(f)
    logging.info(f"cache image is deleted")

# stock_info 페이지에 나오는 main_chart 캐시들 삭제
def delete_stock_info_main_chart(market):
    files = glob.glob(f'/app/shared_files/static/image_data/{market}/main_chart/*')
    for f in files:
        os.remove(f)
    logging.info(f"main_chart cache image is deleted")