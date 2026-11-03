# Clone from JoinQuant
# postId: d0d306bfd572a75739d980c5e836bc2a
# backtestId: ca5fc9357bc728a17d9824f49c0c2dfc
# title: 复刻选取市值最小的10家公司，代码有个小问题。

def initialize(context):
      run_daily(market_open,time='every_bar')
      g.stocksnum = 3
def market_open(context):
      scu = get_index_stocks('000001.XSHG')+get_index_stocks('399106.XSHE')
      q=query(valuation.code).filter(valuation.code.in_(scu)).order_by(valuation.market_cap.asc()).limit(g.stocksnum)
      log.info(q)