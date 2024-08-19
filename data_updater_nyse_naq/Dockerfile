# data_updater/Dockerfile

FROM python:3.10-slim-buster

WORKDIR /app 

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 
RUN pip install flask sqlalchemy pymysql cryptography

# PYTHONPATH 환경 변수 설정
ENV PYTHONPATH "${PYTHONPATH}:/app/shared_files"
ENV PYTHONPATH "${PYTHONPATH}:/app/data_updater_shared_files"

RUN mkdir -p /app/shared_files/nginx_cache/

COPY . .
COPY ./NanumBarunGothic.ttf /usr/share/fonts/truetype/

CMD [ "python", "-u", "./main.py" ]