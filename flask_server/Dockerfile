FROM python:3.12-slim-bookworm

WORKDIR /app 

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 

# PYTHONPATH 환경 변수 설정
ENV PYTHONPATH "${PYTHONPATH}:/app/shared_files"

# Matplotlib font cache 제거
RUN rm -rf ~/.cache/matplotlib

# 이 부분에 빈 디렉토리를 생성하는 명령어를 추가합니다.
RUN mkdir -p /app/shared_files/nginx_cache/

COPY . .
COPY ./NanumBarunGothic.ttf /usr/share/fonts/truetype/

CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT} --timeout 60 main:app"]