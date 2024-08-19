def get_day_num_list(type='int'):
    if type == 'int':
        return [8, 16, 32, 64, 128]
    elif type == 'str':
        return ['8', '16', '32', '64', '128']

def get_market_list():
    return ['kospi_daq', 'nyse_naq']

def get_lang_list():
    return ['ko', 'en']