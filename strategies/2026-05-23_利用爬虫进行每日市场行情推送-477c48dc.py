# Clone from JoinQuant
# postId: 477c48dc8b6287bf528169c20cc0d29d
# backtestId: 7fb1b9d0693e8f505958e820d020cc49
# title: 利用爬虫进行每日市场行情推送

from bs4 import BeautifulSoup
import requests

def initialize(context):
    run_daily(morning, time='9:30', reference_security='000300.XSHG') 
    run_daily(afternoon, time='15:00', reference_security='000300.XSHG')

def morning(context):
    get_market_info()

def afternoon(context):
    get_market_info()

def get_market_info():
    """爬虫抓取华尔街见闻市场行情"""
    url = 'https://wallstreetcn.com/'
    soup = BeautifulSoup(requests.get(url).text, 'lxml')
    item_list = soup.select('a.quotation-bar__item')
    msg = ''
    for item in item_list:
        name = item.select_one('.name').get_text()
        price = item.select_one('.price').get_text()
        chg = item.select_one('.px_change_rate').get_text().strip()
        chg_pct = item.select_one('.px_change_percentage').get_text().strip()
        msg += f'{name}\n{price} {chg} {chg_pct}\n'
    url = 'https://wallstreetcn.com/markets/codes/CN10YR.OTC'
    soup = BeautifulSoup(requests.get(url).text, 'lxml')
    name = soup.select_one('.cn').get_text().strip()
    price = soup.select_one('.price-lastpx').get_text().strip()
    chg = soup.select_one('.price-precision').get_text().strip()
    chg_pct = soup.select_one('.price-rate').get_text().strip().replace(' ', '').replace('\n', '')
    msg += f'{name}\n{price} {chg} {chg_pct}\n'
    send_message(msg)
    print(msg)
    
    