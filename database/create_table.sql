-- 주식 종목의 코드를 저장하는 중심 테이블
CREATE TABLE IF NOT EXISTS stock_code_list_kospi_daq (
    code VARCHAR(10) PRIMARY KEY, -- 종목 코드
    ranking INT, -- 종목의 시가총액 순위
    valid BOOLEAN DEFAULT true, -- 유효 여뷰
    failed_to_load BOOLEAN DEFAULT false, -- 데이터 로드 실패 여부
    user_request BOOLEAN DEFAULT false, -- 사용자 요청 종목 여부
);

CREATE TABLE IF NOT EXISTS stock_code_list_nyse_naq (
    code VARCHAR(10) PRIMARY KEY,
    ranking INT,
    valid BOOLEAN DEFAULT true,
    failed_to_load BOOLEAN DEFAULT false,
    user_request BOOLEAN DEFAULT false,
);

-- 각 주식 종목의 이름 정보 저장
CREATE TABLE IF NOT EXISTS stock_name_kospi_daq (
    code VARCHAR(10) PRIMARY KEY,
    name_ko VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) DEFAULT '',
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_name_nyse_naq (
    code VARCHAR(10) PRIMARY KEY,
    name_ko VARCHAR(100) DEFAULT '',
    name_en VARCHAR(100) NOT NULL,
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

-- 각 주식 종목의 업종 분류 정보 저장
CREATE TABLE IF NOT EXISTS stock_industry_kospi_daq (
    code VARCHAR(10) PRIMARY KEY,
    industry_ko VARCHAR(100) NOT NULL,
    industry_en VARCHAR(100) DEFAULT '',
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_industry_nyse_naq (
    code VARCHAR(10) PRIMARY KEY,
    industry_ko VARCHAR(100) NOT NULL,
    industry_en VARCHAR(100) DEFAULT '',
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

-- 각 주식 종목의 일별 거래 데이터 저장
CREATE TABLE IF NOT EXISTS stock_data_kospi_daq (
    code VARCHAR(10),
    date DATE,
    open_price INT,
    high_price INT,
    low_price INT,
    close_price INT,
    volume BIGINT,
    change_rate FLOAT,

	PRIMARY KEY (code, date),
	FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock_data_nyse_naq (
    code VARCHAR(10),
    date DATE,
    open_price FLOAT,
    high_price FLOAT,
    low_price FLOAT,
    close_price FLOAT,
    volume BIGINT,
    change_rate FLOAT,

	PRIMARY KEY (code, date),
	FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

-- 각 주식 차트의 비교 결과 저장
CREATE TABLE IF NOT EXISTS comparison_result_128day_kospi_daq (
    base_stock_code VARCHAR(10), -- 기준 주식 종목 코드
    base_date DATE, -- 기준 날짜
    compare_stock_code VARCHAR(10), -- 비교 주식 종목 코드
    compare_date DATE, -- 비교 종목의 기준 날짜
    distance FLOAT, -- 차트 간 차이
    after_close_change FLOAT, -- 비슷한 차트의 향후 변동률

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_128day_nyse_naq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_64day_kospi_daq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_64day_nyse_naq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_32day_kospi_daq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_32day_nyse_naq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_16day_kospi_daq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_16day_nyse_naq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_8day_kospi_daq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

CREATE TABLE IF NOT EXISTS comparison_result_8day_nyse_naq (
    base_stock_code VARCHAR(10),
    base_date DATE,
    compare_stock_code VARCHAR(10),
    compare_date DATE,
    distance FLOAT,
    after_close_change FLOAT,

    PRIMARY KEY (base_stock_code, base_date, compare_stock_code, compare_date),
	FOREIGN KEY (base_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
	FOREIGN KEY (compare_stock_code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE,
    INDEX idx_base (base_stock_code, base_date)
);

-- 각 주식 종목의 통계 데이터 저장
CREATE TABLE IF NOT EXISTS statistics_kospi_daq (
    code VARCHAR(10),
    date DATE,
    average_8day FLOAT, -- 비슷한 차트들의 향후 평균
    average_16day FLOAT,
    average_32day FLOAT,
    average_64day FLOAT,
    average_128day FLOAT,
    average_allday FLOAT,
    rise_count_8day INT NOT NULL DEFAULT 0, -- 비슷한 차트들 중 향후 상승한 수
    rise_count_16day INT NOT NULL DEFAULT 0,
    rise_count_32day INT NOT NULL DEFAULT 0,
    rise_count_64day INT NOT NULL DEFAULT 0,
    rise_count_128day INT NOT NULL DEFAULT 0,
    rise_count_allday INT NOT NULL DEFAULT 0,
    data_num_8day INT NOT NULL DEFAULT 0, -- 찾은 비슷한 차트 수
    data_num_16day INT NOT NULL DEFAULT 0,
    data_num_32day INT NOT NULL DEFAULT 0,
    data_num_64day INT NOT NULL DEFAULT 0,
    data_num_128day INT NOT NULL DEFAULT 0,
    data_num_allday INT NOT NULL DEFAULT 0,
    PRIMARY KEY (code, date),
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS statistics_nyse_naq (
    code VARCHAR(10),
    date DATE,
    average_8day FLOAT,
    average_16day FLOAT,
    average_32day FLOAT,
    average_64day FLOAT,
    average_128day FLOAT,
    average_allday FLOAT,
    rise_count_8day INT NOT NULL DEFAULT 0,
    rise_count_16day INT NOT NULL DEFAULT 0,
    rise_count_32day INT NOT NULL DEFAULT 0,
    rise_count_64day INT NOT NULL DEFAULT 0,
    rise_count_128day INT NOT NULL DEFAULT 0,
    rise_count_allday INT NOT NULL DEFAULT 0,
    data_num_8day INT NOT NULL DEFAULT 0,
    data_num_16day INT NOT NULL DEFAULT 0,
    data_num_32day INT NOT NULL DEFAULT 0,
    data_num_64day INT NOT NULL DEFAULT 0,
    data_num_128day INT NOT NULL DEFAULT 0,
    data_num_allday INT NOT NULL DEFAULT 0,
    PRIMARY KEY (code, date),
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profit_after_10day_kospi_daq (
    code VARCHAR(10),
    date DATE,
    score DECIMAL(3,1) CHECK (score >= -10.0 AND score <= 10.0) NOT NULL,
    score_plus_avg DECIMAL(3,1) CHECK (score_plus_avg >= -10.0 AND score_plus_avg <= 10.0),
    base_close_price INT NOT NULL,
    after_close_price INT,
    profit FLOAT,
    
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS profit_after_10day_nyse_naq (
    code VARCHAR(10),
    date DATE,
    score DECIMAL(3,1) CHECK (score >= -10.0 AND score <= 10.0) NOT NULL,
    score_plus_avg DECIMAL(3,1) CHECK (score_plus_avg >= -10.0 AND score_plus_avg <= 10.0),
    base_close_price FLOAT NOT NULL,
    after_close_price FLOAT,
    profit FLOAT,
    
    PRIMARY KEY (code, date)
);

-- 인베스팅닷컴 각 종목의 사이트 URL 저장
CREATE TABLE IF NOT EXISTS investing_info_kospi_daq (
    code VARCHAR(10),
    url VARCHAR(100) DEFAULT '',
    PRIMARY KEY (code),
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS investing_info_nyse_naq (
    code VARCHAR(10),
    url VARCHAR(100) DEFAULT '',
    PRIMARY KEY (code),
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS naver_info_nyse_naq (
    code VARCHAR(10),
    url VARCHAR(100) DEFAULT '',
    PRIMARY KEY (code),
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

-- 사용자가 요청한 주식 종목 코드 저장.
CREATE TABLE IF NOT EXISTS requested_stock_code_kospi_daq (
    code VARCHAR(10),
    date TIMESTAMP NOT NULL,
    validate BOOLEAN NOT NULL, -- 유효하게 할지 / 유효하지 않게 할지 여부
    applied BOOLEAN DEFAULT false, -- 적용 여부
    PRIMARY KEY (code, date),
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS requested_stock_code_nyse_naq (
    code VARCHAR(10),
    date TIMESTAMP NOT NULL,
    validate BOOLEAN NOT NULL,
    applied BOOLEAN DEFAULT false,
    PRIMARY KEY (code, date),
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

-- 각 주식 종목의 조회수 저장
CREATE TABLE IF NOT EXISTS view_kospi_daq (
    code VARCHAR(10) PRIMARY KEY,
    view BIGINT DEFAULT 0, -- 전체 조회수
    daily_view BIGINT DEFAULT 0, -- 일일 조회수
    FOREIGN KEY (code) REFERENCES stock_code_list_kospi_daq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS view_nyse_naq (
    code VARCHAR(10) PRIMARY KEY,
    view BIGINT DEFAULT 0,
    daily_view BIGINT DEFAULT 0,
    FOREIGN KEY (code) REFERENCES stock_code_list_nyse_naq(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS snp500_profit_validation (
    date DATE,
    score_range VARCHAR(10),
    num INT NOT NULL,
    rise_num INT,
    range_total_num INT NOT NULL,
    total_rise_num INT,
    average_profit DECIMAL(10, 2),
    all_stock_code VARCHAR(5000) NOT NULL,
    rise_stock_code VARCHAR(5000),
    fall_stock_code VARCHAR(5000),
    
    PRIMARY KEY (date, score_range)
);

CREATE TABLE IF NOT EXISTS error_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 고유 식별자
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 오류 발생 시간
    level VARCHAR(10),  -- 오류 수준 (예: ERROR, WARN, INFO 등)
    service VARCHAR(100),  -- 오류가 발생한 서비스 또는 모듈 이름
    message TEXT,  -- 오류 메시지
    traceback TEXT,  -- 오류의 스택 추적 (traceback)
    additional_info JSON,  -- 추가 정보 (선택 사항)
    INDEX idx_timestamp (timestamp)
);