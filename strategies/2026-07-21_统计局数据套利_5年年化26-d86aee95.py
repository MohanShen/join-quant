# Clone from JoinQuant
# postId: d86aee952623e40026f246f73cb3e04b
# backtestId: 5b36376dcd9f2f7317bf81f73242972f
# title: 统计局数据套利 5年年化26%

# -*- coding: utf-8 -*-
"""JoinQuant strategy template for NBS industry-profit ETF signals.

Upload nbs_etf_signals.json to JoinQuant's file area, then run this strategy.
The strategy reads the prepared signal file and trades fixed event windows:
buy at release +4 trading days, sell at release +24 trading days.
"""

import datetime
import json


SIGNAL_FILE = "nbs_etf_signals.json"
NBS_ETFS = ["512480.XSHG", "516110.XSHG", "561560.XSHG", "159745.XSHE"]
USE_READ_FILE = False

# nbs_sync_strategy_to_jq.py replaces the JSON text between these markers.
EMBEDDED_SIGNAL_JSON = r'''{"core_etfs":["512480.XSHG","516110.XSHG","561560.XSHG"],"default_rule":{"buy_offset":4,"hold_days":20,"selection":"core profit_yoy Top1; if no core signal, building materials Top1","sell_offset":24,"take_profit":null},"events":[{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":38.7,"profit_yoy_delta":3.9000000000000057,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901263.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2021-10-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":38.7,"profit_yoy_delta":3.9000000000000057,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901263.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901263.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":15.2,"profit_yoy_delta":0.5,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901289.html"}],"etfs":["159745.XSHE"],"hold_days":20,"release_date":"2021-11-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":15.2,"profit_yoy_delta":0.5,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901289.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901289.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":15.4,"profit_yoy_delta":0.20000000000000107,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901319.html"}],"etfs":["159745.XSHE"],"hold_days":20,"release_date":"2021-12-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":15.4,"profit_yoy_delta":0.20000000000000107,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901319.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901319.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":38.9,"profit_yoy_delta":9.099999999999998,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901360.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":1.9,"profit_yoy_delta":5.3,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901360.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2022-01-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":38.9,"profit_yoy_delta":9.099999999999998,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901360.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901360.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":2.8,"profit_yoy_delta":10.1,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901448.html"},{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":11.0,"profit_yoy_delta":5.8,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901448.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2022-04-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":2.8,"profit_yoy_delta":10.1,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901448.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901448.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":11.4,"profit_yoy_delta":13.4,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901638.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2022-10-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":11.4,"profit_yoy_delta":13.4,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901638.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901638.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":28.1,"profit_yoy_delta":16.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901664.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":0.8,"profit_yoy_delta":2.7,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901664.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2022-11-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":28.1,"profit_yoy_delta":16.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901664.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901664.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":86.3,"profit_yoy_delta":58.199999999999996,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901735.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-01-31","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":86.3,"profit_yoy_delta":58.199999999999996,"url":"https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901735.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901735.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":2.5,"profit_yoy_delta":26.7,"url":"https://www.stats.gov.cn/sj/zxfb/202305/t20230526_1940198.html"}],"etfs":["516110.XSHG"],"hold_days":20,"release_date":"2023-05-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":2.5,"profit_yoy_delta":26.7,"url":"https://www.stats.gov.cn/sj/zxfb/202305/t20230526_1940198.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202305/t20230526_1940198.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":24.3,"profit_yoy_delta":21.8,"url":"https://www.stats.gov.cn/sj/zxfb/202306/t20230628_1940873.html"}],"etfs":["516110.XSHG"],"hold_days":20,"release_date":"2023-06-28","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":24.3,"profit_yoy_delta":21.8,"url":"https://www.stats.gov.cn/sj/zxfb/202306/t20230628_1940873.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202306/t20230628_1940873.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":46.5,"profit_yoy_delta":0.6000000000000014,"url":"https://www.stats.gov.cn/sj/zxfb/202307/t20230726_1941552.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-07-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":46.5,"profit_yoy_delta":0.6000000000000014,"url":"https://www.stats.gov.cn/sj/zxfb/202307/t20230726_1941552.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202307/t20230726_1941552.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":51.2,"profit_yoy_delta":4.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202308/t20230827_1942335.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-08-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":51.2,"profit_yoy_delta":4.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202308/t20230827_1942335.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202308/t20230827_1942335.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":53.4,"profit_yoy_delta":2.1999999999999957,"url":"https://www.stats.gov.cn/sj/zxfb/202309/t20230927_1943230.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":2.4,"profit_yoy_delta":1.4,"url":"https://www.stats.gov.cn/sj/zxfb/202309/t20230927_1943230.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-09-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":53.4,"profit_yoy_delta":2.1999999999999957,"url":"https://www.stats.gov.cn/sj/zxfb/202309/t20230927_1943230.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202309/t20230927_1943230.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":50.1,"profit_yoy_delta":0.10000000000000142,"url":"https://www.stats.gov.cn/sj/zxfb/202311/t20231127_1944914.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":0.5,"profit_yoy_delta":0.4,"url":"https://www.stats.gov.cn/sj/zxfb/202311/t20231127_1944914.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-11-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":50.1,"profit_yoy_delta":0.10000000000000142,"url":"https://www.stats.gov.cn/sj/zxfb/202311/t20231127_1944914.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202311/t20231127_1944914.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":58.2,"profit_yoy_delta":8.100000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202312/t20231226_1945798.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":2.9,"profit_yoy_delta":2.4,"url":"https://www.stats.gov.cn/sj/zxfb/202312/t20231226_1945798.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2023-12-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":58.2,"profit_yoy_delta":8.100000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202312/t20231226_1945798.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202312/t20231226_1945798.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":71.9,"profit_yoy_delta":13.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202401/t20240126_1946914.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":5.9,"profit_yoy_delta":3.0000000000000004,"url":"https://www.stats.gov.cn/sj/zxfb/202401/t20240126_1946914.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2024-01-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":71.9,"profit_yoy_delta":13.700000000000003,"url":"https://www.stats.gov.cn/sj/zxfb/202401/t20240126_1946914.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202401/t20240126_1946914.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":210.9,"profit_yoy_delta":219.5,"url":"https://www.stats.gov.cn/sj/zxfb/202403/t20240327_1948176.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":50.1,"profit_yoy_delta":44.2,"url":"https://www.stats.gov.cn/sj/zxfb/202403/t20240327_1948176.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2024-03-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":210.9,"profit_yoy_delta":219.5,"url":"https://www.stats.gov.cn/sj/zxfb/202403/t20240327_1948176.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202403/t20240327_1948176.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":25.1,"profit_yoy_delta":1.1000000000000014,"url":"https://www.stats.gov.cn/sj/zxfb/202408/t20240827_1956106.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2024-08-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":25.1,"profit_yoy_delta":1.1000000000000014,"url":"https://www.stats.gov.cn/sj/zxfb/202408/t20240827_1956106.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202408/t20240827_1956106.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":8.4,"profit_yoy_delta":1.3000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202411/t20241127_1957580.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2024-11-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":8.4,"profit_yoy_delta":1.3000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202411/t20241127_1957580.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202411/t20241127_1957580.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":17.8,"profit_yoy_delta":4.300000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202501/t20250127_1958485.html"},{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":3.4,"profit_yoy_delta":0.5,"url":"https://www.stats.gov.cn/sj/zxfb/202501/t20250127_1958485.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2025-01-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":17.8,"profit_yoy_delta":4.300000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202501/t20250127_1958485.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202501/t20250127_1958485.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":11.7,"profit_yoy_delta":19.7,"url":"https://www.stats.gov.cn/sj/zxfb/202503/t20250327_1959147.html"}],"etfs":["516110.XSHG"],"hold_days":20,"release_date":"2025-03-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":11.7,"profit_yoy_delta":19.7,"url":"https://www.stats.gov.cn/sj/zxfb/202503/t20250327_1959147.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202503/t20250327_1959147.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":3.2,"profit_yoy_delta":12.600000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202504/t20250427_1959477.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-04-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":3.2,"profit_yoy_delta":12.600000000000001,"url":"https://www.stats.gov.cn/sj/zxfb/202504/t20250427_1959477.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202504/t20250427_1959477.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":11.6,"profit_yoy_delta":8.399999999999999,"url":"https://www.stats.gov.cn/sj/zxfb/202505/t20250527_1959963.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-05-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":11.6,"profit_yoy_delta":8.399999999999999,"url":"https://www.stats.gov.cn/sj/zxfb/202505/t20250527_1959963.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202505/t20250527_1959963.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":11.9,"profit_yoy_delta":0.3000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202506/t20250627_1960270.html"},{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":5.7,"profit_yoy_delta":0.10000000000000053,"url":"https://www.stats.gov.cn/sj/zxfb/202506/t20250627_1960270.html"},{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":0.6,"profit_yoy_delta":2.2,"url":"https://www.stats.gov.cn/sj/zxfb/202506/t20250627_1960270.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-06-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":11.9,"profit_yoy_delta":0.3000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202506/t20250627_1960270.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202506/t20250627_1960270.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":3.6,"profit_yoy_delta":15.5,"url":"https://www.stats.gov.cn/sj/zxfb/202507/t20250727_1960504.html"}],"etfs":["516110.XSHG"],"hold_days":20,"release_date":"2025-07-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":3.6,"profit_yoy_delta":15.5,"url":"https://www.stats.gov.cn/sj/zxfb/202507/t20250727_1960504.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202507/t20250727_1960504.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":6.7,"profit_yoy_delta":3.2,"url":"https://www.stats.gov.cn/sj/zxfb/202508/t20250827_1960884.html"},{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":6.3,"profit_yoy_delta":0.7000000000000002,"url":"https://www.stats.gov.cn/sj/zxfb/202508/t20250827_1960884.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-08-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":6.7,"profit_yoy_delta":3.2,"url":"https://www.stats.gov.cn/sj/zxfb/202508/t20250827_1960884.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202508/t20250827_1960884.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":13.0,"profit_yoy_delta":6.7,"url":"https://www.stats.gov.cn/sj/zxfb/202509/t20250927_1961400.html"},{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":7.2,"profit_yoy_delta":0.5,"url":"https://www.stats.gov.cn/sj/zxfb/202509/t20250927_1961400.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2025-09-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":13.0,"profit_yoy_delta":6.7,"url":"https://www.stats.gov.cn/sj/zxfb/202509/t20250927_1961400.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202509/t20250927_1961400.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":14.4,"profit_yoy_delta":1.4000000000000004,"url":"https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"},{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":12.0,"profit_yoy_delta":4.8,"url":"https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":3.4,"profit_yoy_delta":3.6999999999999997,"url":"https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"},{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":5.1,"profit_yoy_delta":7.3,"url":"https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"}],"etfs":["561560.XSHG"],"hold_days":20,"release_date":"2025-10-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":14.4,"profit_yoy_delta":1.4000000000000004,"url":"https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202510/t20251027_1961695.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":12.8,"profit_yoy_delta":0.8000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202511/t20251127_1961933.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":4.4,"profit_yoy_delta":1.0000000000000004,"url":"https://www.stats.gov.cn/sj/zxfb/202511/t20251127_1961933.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-11-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":12.8,"profit_yoy_delta":0.8000000000000007,"url":"https://www.stats.gov.cn/sj/zxfb/202511/t20251127_1961933.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202511/t20251127_1961933.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":15.0,"profit_yoy_delta":2.1999999999999993,"url":"https://www.stats.gov.cn/sj/zxfb/202512/t20251227_1962158.html"},{"etf":"516110.XSHG","industry":"汽车制造业","profit_yoy":7.5,"profit_yoy_delta":3.0999999999999996,"url":"https://www.stats.gov.cn/sj/zxfb/202512/t20251227_1962158.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2025-12-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":15.0,"profit_yoy_delta":2.1999999999999993,"url":"https://www.stats.gov.cn/sj/zxfb/202512/t20251227_1962158.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202512/t20251227_1962158.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":19.5,"profit_yoy_delta":4.5,"url":"https://www.stats.gov.cn/sj/zxfb/202601/t20260127_1962382.html"},{"etf":"561560.XSHG","industry":"电力、热力生产和供应业","profit_yoy":13.9,"profit_yoy_delta":2.0999999999999996,"url":"https://www.stats.gov.cn/sj/zxfb/202601/t20260127_1962382.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2026-01-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":19.5,"profit_yoy_delta":4.5,"url":"https://www.stats.gov.cn/sj/zxfb/202601/t20260127_1962382.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202601/t20260127_1962382.html"]},{"buy_offset":4,"candidate_signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":203.5,"profit_yoy_delta":184.0,"url":"https://www.stats.gov.cn/sj/zxfb/202603/t20260327_1962868.html"},{"etf":"159745.XSHE","industry":"非金属矿物制品业","profit_yoy":16.2,"profit_yoy_delta":17.9,"url":"https://www.stats.gov.cn/sj/zxfb/202603/t20260327_1962868.html"}],"etfs":["512480.XSHG"],"hold_days":20,"release_date":"2026-03-27","selection_rule":"core_profit_yoy_top1_else_building_materials_top1","sell_offset":24,"signals":[{"etf":"512480.XSHG","industry":"计算机、通信和其他电子设备制造业","profit_yoy":203.5,"profit_yoy_delta":184.0,"url":"https://www.stats.gov.cn/sj/zxfb/202603/t20260327_1962868.html"}],"source_urls":["https://www.stats.gov.cn/sj/zxfb/202603/t20260327_1962868.html"]}],"industry_to_etf":{"汽车制造业":"516110.XSHG","电力、热力生产和供应业":"561560.XSHG","计算机、通信和其他电子设备制造业":"512480.XSHG","非金属矿物制品业":"159745.XSHE"},"satellite_etfs":["159745.XSHE"],"strategy":"nbs_industry_profit_etf_event_v2_core_top1_building_satellite","updated_at":"2026-07-02 02:21:33"}'''

POSITION_RATIO = 0.95
BUY_TIME = "09:35"
SELL_TIME = "14:50"

# Keep False to match the research scan exactly. If True, the strategy may buy
# after a missed buy date while the event is still active.
BUY_IF_MISSED = False
MAX_MISSED_BUY_DAYS = 2


def initialize(context):
    set_option("use_real_price", True)
    g.current_event_key = None
    g.current_targets = []
    run_daily(check_buy_signal, time=BUY_TIME)
    run_daily(check_event_exit, time=SELL_TIME)
    log.info("[NBS ETF] initialized, signal_file=%s" % SIGNAL_FILE)


def load_signal_payload():
    raw = None
    if USE_READ_FILE:
        try:
            raw = read_file(SIGNAL_FILE)
        except Exception as exc:
            log.warn("[NBS ETF] cannot read %s, fallback to embedded json: %s" % (SIGNAL_FILE, str(exc)))
    if raw is None:
        raw = EMBEDDED_SIGNAL_JSON
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        payload = json.loads(raw)
        if not payload or not payload.get("events"):
            log.warn("[NBS ETF] empty signal payload")
            return None
        return payload
    except Exception as exc:
        log.error("[NBS ETF] invalid signal json: %s" % str(exc))
        return None


def today_str(context):
    current = context.current_dt
    if hasattr(current, "date"):
        return current.date().strftime("%Y-%m-%d")
    return str(current)[:10]


def event_offset(event, today):
    release = event.get("release_date")
    if not release or release > today:
        return None
    try:
        prices = get_price(NBS_ETFS[0], start_date=release, end_date=today, frequency="daily", fields=["close"])
    except Exception as exc:
        log.error("[NBS ETF] cannot count trade days from %s to %s: %s" % (release, today, str(exc)))
        return None
    if prices is None or len(prices) == 0:
        return None
    return len(prices) - 1


def event_key(event):
    return "%s|%s" % (event.get("release_date"), ",".join(sorted(event.get("etfs", []))))


def latest_buy_candidate(events, today):
    candidates = []
    for event in events:
        offset = event_offset(event, today)
        if offset is None:
            continue
        buy_offset = int(event.get("buy_offset", 4))
        sell_offset = int(event.get("sell_offset", 24))
        exact_buy = offset == buy_offset
        missed_buy = BUY_IF_MISSED and buy_offset < offset < sell_offset and offset <= buy_offset + MAX_MISSED_BUY_DAYS
        if exact_buy or missed_buy:
            candidates.append((event.get("release_date"), offset, event))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0])
    picked = candidates[-1]
    return picked[2], picked[1]


def active_event_by_key(events, key):
    if not key:
        return None
    for event in events:
        if event_key(event) == key:
            return event
    return None


def managed_positions(context):
    positions = []
    for code in NBS_ETFS:
        pos = context.portfolio.positions.get(code)
        if pos is not None and pos.total_amount > 0:
            positions.append(code)
    return positions


def close_managed_positions(context):
    for code in managed_positions(context):
        order_target_value(code, 0)
        log.info("[NBS ETF] close %s" % code)


def rebalance_to_targets(context, targets):
    if not targets:
        return
    for code in NBS_ETFS:
        if code not in targets:
            order_target_value(code, 0)
    total_value = context.portfolio.total_value * POSITION_RATIO
    each_value = total_value / float(len(targets))
    for code in targets:
        order_target_value(code, each_value)
        log.info("[NBS ETF] target %s value=%.2f" % (code, each_value))


def check_buy_signal(context):
    payload = load_signal_payload()
    if not payload:
        return
    today = today_str(context)
    event, offset = latest_buy_candidate(payload.get("events", []), today)
    if event is None:
        return
    key = event_key(event)
    targets = sorted(event.get("etfs", []))
    if not targets:
        return
    if g.current_event_key == key and sorted(g.current_targets) == targets:
        return
    rebalance_to_targets(context, targets)
    g.current_event_key = key
    g.current_targets = targets
    log.info("[NBS ETF] buy event=%s offset=%s targets=%s" % (key, str(offset), ",".join(targets)))


def check_event_exit(context):
    payload = load_signal_payload()
    if not payload:
        return
    today = today_str(context)
    event = active_event_by_key(payload.get("events", []), g.current_event_key)
    if event is None:
        if managed_positions(context):
            log.warn("[NBS ETF] current event missing, close managed positions")
            close_managed_positions(context)
        g.current_event_key = None
        g.current_targets = []
        return

    offset = event_offset(event, today)
    sell_offset = int(event.get("sell_offset", 24))
    if offset is not None and offset >= sell_offset:
        close_managed_positions(context)
        log.info("[NBS ETF] sell event=%s offset=%s" % (g.current_event_key, str(offset)))
        g.current_event_key = None
        g.current_targets = []
