# Clone from JoinQuant
# postId: 80da895c195c5002d993a12a8cd7f240
# backtestId: cc5c61ade43d7eb333d17273829b28aa
# title: 基于财务数据选股的简单尝试（作者：胖胖兵）

import pandas as pd

def get_stock_name(stock_code):
    stocks_df = get_all_securities()
    stock_name = [stocks_df.loc[c, 'display_name'] for c in stock_code]
    return stock_name

pd.set_option('display.max_columns', 100)
pd.set_option('display.max_rows', 100)

init_filter_query = query(
                            valuation.pe_ratio, indicator.code, indicator.roe, indicator.roa,
                        ).filter(
                            indicator.roa > 5,
                            indicator.roe > 10,
                            valuation.pe_ratio > 0,
                            income.total_operating_revenue <= 2e10,
                            income.total_operating_revenue > 1e10
                        ).order_by(
                            indicator.roe.desc()
                        ).limit(
                            100
                        )

df = get_fundamentals(init_filter_query, statDate='2018')
stocks = df['code']

multi_stock_data_query = query(
                                valuation.pe_ratio, indicator.code, indicator.roe, indicator.roa,
                            ).filter(
                                indicator.code.in_(stocks)                                
                            )
roe_dict = {}
roa_dict = {}
year_list = ['2012', '2013', '2014', '2015', '2016', '2017', '2018']
for year in year_list:
    df = get_fundamentals(multi_stock_data_query, statDate=year)
    df = df.set_index('code')
    roe_dict[year] = df['roe']
    roa_dict[year] = df['roa']

roe_df = pd.DataFrame(roe_dict)
roe_df.index = get_stock_name(roe_df.index)
print(roe_df)

roa_df = pd.DataFrame(roa_dict)
roa_df.index = get_stock_name(roa_df.index)
print(roa_df)