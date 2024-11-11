# '비슷한 차트 검색기 - 주가 예측' 프로젝트

전 종목의 최근 10년치 차트 중 사용자가 원하는 특정 차트와 가장 비슷한 차트를 제공하는 웹 & 앱 서비스 입니다.

- Web : https://www.similarchart.com
- App(Android) : https://play.google.com/store/apps/details?id=com.similarchart.chartfinder

<br>
<br>
<br>
<br>
 
## 주요기능
- 8, 16, 32, 64, 128일 치의 다양한 비교 결과 제공
- 한국주식, 미국주식 지원
- 한국어, 영어 지원
- 각 종목별 차트 평가 제공
- 랭킹 페이지, 검증 페이지 제공
- 네이버 증권, 야후 증권 연동(앱버전)
- 사용자가 직접 차트를 그릴 수 있는 드로잉검색, 패턴검색 지원(앱버전)
  
<br>
<br>
<br>

## 성과
- 하루 평균 트래픽 **11200** (미국 48.73%, 싱가포르 20.25%, 한국 16.11%, 기타 14.91% / 24.9.1 ~ 24.9.30)
- MAU(월간 활성 사용자 수) **11280** (24.9.1 ~ 24.9.30)
- 비슷한 차트들이 주가 예측에 도움을 주는 것을 검증 (https://www.similarchart.com/validation)
  
![image](https://github.com/user-attachments/assets/a259a4ae-d118-4e57-b98e-bfdc7729f0a5)

![image](https://github.com/user-attachments/assets/1974d3bb-3a17-43d2-a65e-aa56285d8b57)

<br>
<br>
<br>
<br>

## 프로젝트 수행 내용

![image](https://github.com/user-attachments/assets/4a5f2ebc-2bc8-456e-b0f7-a18fb35ba766)

![image](https://github.com/user-attachments/assets/4a1abaca-b3d4-4d1e-8033-9ead41c68966)

![image](https://github.com/user-attachments/assets/8ba521a6-d68c-40c9-ace9-11d15bb23fc0)

![image](https://github.com/user-attachments/assets/20a0dcc1-9083-4354-8931-5211dab2a0fd)

![image](https://github.com/user-attachments/assets/d1ebe9bc-69cc-4bcc-b88f-ae895ba71189)

![image](https://github.com/user-attachments/assets/d53d0812-edfa-4522-882d-d1e74834ddcd)



<br>
<br>
<br>
<br>

## 시스템 아키텍처

![architecture](https://github.com/user-attachments/assets/502e266d-be36-4137-a390-098f7652b593)

관련 글 : https://blog.similarchart.com/140

<br>
<br>
<br>
<br>

## 폴더별 소스코드
소스코드의 일부분입니다. 보안적으로 중요한 부분은 제외하였습니다.

- **`data_updater_kospi_daq`** : 한국 주식 ETL 데이터 파이프라인
- **`data_updater_nyse_naq`** : 미국 주식 ETL 데이터 파이프라인
- **`data_updater_shared_files`** : data_updater 컨테이너들이 공유하는 파일
- **`database`** : 데이터베이스 설정정보 (개발 환경)
- **`flask_server`** : http 요청/응답을 수행하는 서버
- **`redis`** : 레디스 컨테이너 설정정보
- **`nginx_server`** : nginx 컨테이너 설정정보
- **`shared_files`** : 모든 컨테이너에서 공유하는 파일

<br>
<br>
<br>
<br>

## Airflow 도입 검토 중
[관련 블로그 글](https://blog.similarchart.com/253)
