# Clone from JoinQuant
# postId: c6126cc2044ad1461ce4a9edc047f7d6
# backtestId: 2a525a07722d9391f96632512ba1eca5
# title: 一创聚宽无法使用requests 爬虫

from jqdata import *
import numpy as np
import pandas as pd
import talib


import requests

url = "https://www.baidu.com/"

resp = requests.get(url)
resp.encoding='utf-8'
data=resp.text
print(data)