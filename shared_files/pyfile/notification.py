import requests
import logging
import os

# 에러 발생시 aws lambda를 이용한 이메일 발송
def notify_via_lambda(error_message):
    url = os.getenv('ERROR_API_URL')
    payload = {
        'message': error_message
    }
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        logging.info('Notification sent successfully')
    else:
        logging.error(f'Failed to send notification: {response.text}')