# Clone from JoinQuant
# postId: 688c1db27a595b326510264370e04e9d
# backtestId: aa626cd52898d3e79bc636898f755201
# title: 为什么不能回测？

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 读取数据
data = pd.read_csv('hs300.csv') # 假设数据文件名为 hs300.csv
close = data['close'] # 收盘价序列

# 计算移动平均线
ma5 = close.rolling(window=5).mean()
ma10 = close.rolling(window=10).mean()
ma22 = close.rolling(window=22).mean()
ma30 = close.rolling(window=30).mean()
ma60 = close.rolling(window=60).mean()

# 生成买卖点序列
buy_signals = (ma5 > ma10) & (ma10 > ma22) & (ma22 > ma30) & (ma30 > ma60)
sell_signals = (ma5 < ma10) & (ma10 < ma22) & (ma22 < ma30) & (ma30 < ma60)

# 生成交易信号序列
signals = pd.Series(np.zeros(len(close)), index=close.index)
signals[buy_signals] = 1
signals[sell_signals] = -1

# 计算持仓和资金曲线
positions = signals.diff()
holdings = close * positions.cumsum()
cash = 1000000 - (positions.shift(1) * close * 0.0003).cumsum() # 假设交易费用为0.03%

# 计算累积收益率
returns = (holdings + cash) / 1000000 - 1

# 统计分析
accuracy = (signals == positions.shift(1)).mean()
total_returns = returns[-1]
annual_returns = (1 + total_returns) ** (250 / len(close)) - 1
sharpe_ratio = np.sqrt(250) * returns.mean() / returns.std()

# 画图展示
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(returns)
ax.set_title('Cumulative Returns')
ax.set_xlabel('Date')
ax.set_ylabel('Cumulative Returns')
plt.show()
