FROM nginx

# 비-privileged 사용자 생성
RUN adduser --disabled-password --gecos "" nginx_user

# 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && \
    apt-get install -y cron certbot python3-certbot-nginx

# Nginx 설정 파일 복사
COPY nginx.conf /etc/nginx/nginx.conf
# maintenance.html 파일 복사
COPY maintenance.html /var/www/maintenance.html

# logrotate 파일 복사
COPY nginx-logrotate /etc/logrotate.d/nginx

# logrotate 파일 권한 수정
RUN chmod 644 /etc/logrotate.d/nginx

# Certbot 갱신 스크립트 추가 및 실행 가능하게 설정
COPY renew-certs.sh /etc/cron.daily/renew-certs
RUN chmod +x /etc/cron.daily/renew-certs

CMD ["sh", "-c", "cron && nginx -g 'daemon off;'"]