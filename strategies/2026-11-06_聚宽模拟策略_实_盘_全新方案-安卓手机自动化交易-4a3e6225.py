# Clone from JoinQuant
# postId: 4a3e62256deb55668d319f8a5ba28ac8
# backtestId: b23ff3f22b391bc565415af00921c87b
# title: 聚宽模拟策略.实.盘.全新方案-安卓手机自动化交易

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    # 获取股票的收盘价
    close_data = get_bars(security, count=5, unit='1d', fields=['close'])
    # 取得过去五天的平均价格
    MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    current_price = close_data['close'][-1]
    # 取得当前的现金
    cash = context.portfolio.available_cash

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if (current_price > 1.01*MA5) and (cash > 0):
        # 记录这次买入
        log.info("价格高于均价 1%%, 买入 %s" % (security))
        # 用所有 cash 买入股票
        order_value(security, cash)
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif current_price < MA5 and context.portfolio.positions[security].closeable_amount > 0:
        # 记录这次卖出
        log.info("价格低于均价, 卖出 %s" % (security))
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    
'''
# -*- coding: utf-8 -*-
#项目名称：聚宽策略实盘安卓同花顺自动交易
#作者: flyaga li
#项目主页：https://github.com/flyaga/jq-strategy-android-ths-auto-trader

#开发历史：
#2026-10-21 v1.0 实现跟踪聚宽模拟策略，自动在同花顺安卓手机端交易

from ascript.android.action import click, Touch, Key
from ascript.android.node import Selector
from ascript.android import action
from airscript.intent import Intent
from ascript.android.system import R,Device
from ascript.android import system

import requests
import json
import time
import threading
import pickle
import os
import logging
import urllib3
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================== 配置区域 ========================
isMn = True  # 是否模拟交易（类变量，可通过 self.isMn 访问）
isTest = False

# 手机屏幕PW，根据实际修改
MOBILE_SCREEN_PW = "999999"

JOINQUANT_USER = "聚宽用户名，根据实际修改"          # 聚宽用户名，根据实际修改
JOINQUANT_PWD = "聚宽密码，根据实际修改"           # 聚宽密码，根据实际修改
STRATEGY_URLS = [                         # 策略URL列表，根据实际修改
    "https://www.joinquant.com/algorithm/live/index?backtestId=62afb0756674af22524140a69d68a5ef"
]
TRACK_INTERVAL = 5                        # 轮询间隔（秒）
CMD_EXPIRE_SECONDS = 120                  # 指令超时时间（秒）
CMD_CACHE_FILE = "jq_cmd_cache.pk"        # 缓存文件
USE_TRADE_RATIO = True                   # 是否按比例交易

class JoinQuantFollower:
    """聚宽策略跟踪器（手机版）"""
    
    LOGIN_PAGE = "https://www.joinquant.com"
    LOGIN_API = "https://www.joinquant.com/user/login/doLogin?ajax=1"
    TRANSACTION_API = "https://www.joinquant.com/algorithm/live/transactionDetail"
    POSITION_API = "https://www.joinquant.com/algorithm/live/position"
    
    def __init__(self):
        urllib3.disable_warnings()
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.joinquant.com/user/login/index",
            "Origin": "https://www.joinquant.com",
            "X-Requested-With": "XMLHttpRequest"
        })
        self.expired_cmds = set()
        self.load_expired_cache()
    
    def login(self, username, password):
        """登录聚宽"""
        logger.info("登录聚宽...")
        self.s.get(self.LOGIN_PAGE)  # 初始化cookie
        params = {
            "CyLoginForm[username]": username,
            "CyLoginForm[pwd]": password,
            "ajax": 1
        }
        resp = self.s.post(self.LOGIN_API, data=params)
        if "set-cookie" in resp.headers and len(resp.headers["set-cookie"]) > 50:
            logger.info("聚宽登录成功")
            self.s.headers.update({"cookie": resp.headers["set-cookie"]})
        else:
            raise Exception("聚宽登录失败，请检查用户名密码")
    
    def extract_strategy_id(self, url):
        """从URL提取策略ID"""
        match = re.search(r"backtestId=([a-f0-9]+)", url)
        if match:
            return match.group(1)
        raise ValueError(f"无法提取策略ID: {url}")

    def re_search(self, pattern, string, dtype=str):
        return dtype(re.search(pattern,string).group(1))

    def extract_strategy_name(self, url):
        rep = self.s.get(url)
        return self.re_search(r'class="backtest_name".+?>(.*?)</span>', rep.content.decode("utf8"))
    
    def query_transaction(self, strategy_id):
        """查询策略调仓记录"""
        today = datetime.today().strftime("%Y-%m-%d")
        params = {"backtestId": strategy_id, "date": today, "ajax": 1}
        resp = self.s.get(self.TRANSACTION_API, params=params)
        if resp.status_code != 200:
            raise Exception(f"查询调仓失败: {resp.text}")
        data = resp.json()
        transactions = data.get("data", {}).get("transaction", [])
        return self._format_transactions(transactions)
    
    def _format_transactions(self, raw_list):     
        """标准化调仓数据"""
        formatted = []
        for t in raw_list:
            # 解析数量
            amount_str = t.get("amount", "0")
            match = re.search(r'[\d,]+(?:\.\d+)?', amount_str)
            amount = 0
            if match:
                amount = int(float(match.group().replace(',', '')))
            logger.info(f"amount={amount}")

            # 解析价格
            price = float(t.get("price", 0))
            
            stock_code = ''
            stock = t.get("stock", "")
            match = re.search(r'[（(]\s*(\d+)', stock)
            if match:
                stock_code = match.group(1)
            if stock_code == '':
                raise Exception("得到聚宽股票代码失败")
            logger.info(f"stock_code={stock_code}")

            # 动作
            action = "buy" if t.get("transaction") == "买" else "sell"
            # 时间
            dt_str = f"{t.get('date')} {t.get('time')}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            formatted.append({
                "action": action,
                "stock_code": stock_code,
                "amount": amount,
                "price": price,
                "datetime": dt
            })
        return formatted
    
    def query_position(self, strategy_id):
        """查询策略持仓（用于获取总资产）"""
        today = datetime.today().strftime("%Y-%m-%d")
        params = {"backtestId": strategy_id, "date": today, "ajax": 1}
        resp = self.s.get(self.POSITION_API, params=params)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {})
        return {}
    
    def get_strategy_total_assets(self, strategy_id):
        """获取策略总资产"""
        pos = self.query_position(strategy_id)
        return pos.get("totalValue", 1)  # 防止除零
    
    def is_cmd_expired(self, cmd):
        key = self._cmd_key(cmd)
        return key in self.expired_cmds

    def _cmd_key(self, cmd):
        return f"{cmd['stock_code']}_{cmd['action']}_{cmd['amount']}_{cmd['price']}_{cmd['datetime']}"

    def mark_cmd_executed(self, cmd):
        key = self._cmd_key(cmd)
        if key not in self.expired_cmds:
            self.expired_cmds.add(key)
            self._save_cache()

    def get_cmd_cache_file(self):
        return f'{os.path.dirname(os.path.abspath(__file__))}/{CMD_CACHE_FILE}'

    def load_expired_cache(self):
        file_path = self.get_cmd_cache_file()
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                self.expired_cmds = pickle.load(f)
                logger.debug(f'expired_cmds={self.expired_cmds}')

    def _save_cache(self):
        file_path = self.get_cmd_cache_file()
        mode = 'wb'
        with open(file_path, mode) as f:
            pickle.dump(self.expired_cmds, f)


# ======================== 同花顺手机端交易执行器 ========================
class ThsMobileTrader:
    """同花顺手机端自动化交易。

    封装了屏幕解锁、同花顺 APP 操作、买卖委托全流程。
    ``isMn`` 控制模拟盘 / 实盘切换。
    """

    def __init__(self, is_mn=isMn):
        """
        Args:
            is_mn: 是否模拟交易（True=模拟盘, False=实盘）
        """
        self.is_mn = is_mn

    # ========================================================
    # 屏幕解锁
    # ========================================================
    def get_lock_key_coords(
        self,
        keyboard_left_margin=0.05,
        keyboard_right_margin=0.05,
        keyboard_top_ratio=0.50,
        keyboard_bottom_ratio=0.85
    ):
        """针对 vivo X70（OriginOS）锁屏数字键盘（3列×5行）返回所有按键中心坐标。

        Returns:
            dict: {'digits': [(x,y)]*10, 'confirm': (x,y)}
        """
        display = Device.display()
        screen_w = display.widthPixels
        screen_h = display.heightPixels

        x_start = int(screen_w * keyboard_left_margin)
        x_end   = int(screen_w * (1 - keyboard_right_margin))
        y_start = int(screen_h * keyboard_top_ratio)
        y_end   = int(screen_h * keyboard_bottom_ratio)

        col_count = 3
        row_count = 5
        cell_w = (x_end - x_start) / col_count
        cell_h = (y_end - y_start) / row_count

        def _center(row, col):
            cx = int(x_start + cell_w * (col + 0.5))
            cy = int(y_start + cell_h * (row + 0.5))
            return (cx, cy)

        digit_positions = {
            0: (4, 1),
            1: (1, 0),
            2: (1, 1),
            3: (1, 2),
            4: (2, 0),
            5: (2, 1),
            6: (2, 2),
            7: (3, 0),
            8: (3, 1),
            9: (3, 2),
        }

        digit_coords = [None] * 10
        for digit, pos in digit_positions.items():
            digit_coords[digit] = _center(*pos)

        confirm_coord = _center(0, 2)

        return {
            'digits': digit_coords,
            'confirm': confirm_coord
        }

    def screenUnlock(self):
        """锁定屏幕再解锁（确保屏幕亮起并进入主界面）。

        支持 vivo X70 (vivoV2133A) 和华为 (HUAWEIMRD-AL00) 两款设备，根据实际修改
        """
        logger.info("任务开始，先锁定屏幕...")
        action.Key.lockscreen()
        time.sleep(0.3)

        name = Device.name()
        logger.info("唤醒屏幕")
        Device.wake_up()
        time.sleep(0.5)

        if name in ['vivoV2133A', 'HUAWEIMRD-AL00']:
            # vivo X70 上滑解锁，根据实际修改
            action.Touch.down(440, 1345)
            action.Touch.move(445, 852, 1000)
            action.Touch.up(445, 852)
            time.sleep(1)

        # 输入密码（请根据实际修改）
        password = MOBILE_SCREEN_PW
        if name in ['vivoV2133A']:
            coords = self.get_lock_key_coords(0.05, 0.05, 0.5, 0.9)

        if name in ['HUAWEIMRD-AL00']:
            coords = self.get_lock_key_coords(0.01, 0.01, 0.55, 0.95)

        for digit in password:
            x, y = coords['digits'][int(digit)]
            action.click(x, y)
            time.sleep(0.1)

        # 点击确认
        if name in ['vivoV2133A']:
            x, y = coords['confirm']
            action.click(x, y)

        logger.info('屏幕解锁完成')
        time.sleep(1)

    # ========================================================
    # 动作序列辅助
    # ========================================================
    @staticmethod
    def getNextAction(myActions, myAction):
        """获取动作列表中的下一个动作。"""
        index = myActions.index(myAction)
        if index < 0 or index >= len(myActions) - 1:
            return ''
        return myActions[index + 1]

    def logger_info(self, info):
        logger.info(info)
        self.info_per_no = f'{self.info_per_no},{info}'

    # ========================================================
    # 买卖交易执行
    # ========================================================
    def execute_order(self, trade_action, stock_code, amount,
                      price=None, strategy_total_assets=0, stock_name=""):
        """执行买卖交易（完整自动化流程）。

        流程：解锁屏幕 -> 打开同花顺 -> 登录 -> 买/卖 -> 确认委托 -> 退出 -> 锁屏。

        Args:
            trade_action:          'buy' 或 'sell'
            stock_code:            股票代码，如 '159985'
            amount:                股数
            price:                 限价（可选，预留）
            strategy_total_assets: 策略总资产（用于按比例交易计算）
            stock_name:            股票名称（可选，仅用于日志显示）

        Returns:
            bool: 交易是否成功（委托已提交）
        """
        logger.info(f"执行{trade_action}指令: {stock_code}{stock_name}, 数量{amount}, 价格{price}")         

        # 3. 定义动作序列
        myActions = ['login', trade_action, 'exit']
        buy_code = stock_code
        buy_amount = amount
        sell_code = stock_code
        sell_amount = amount
        myAction = myActions[0]

        no = 0
        # no_found = True
        is_success = False
        user_total_assets = 0
        is_less_money = False       # 可用余额不足标志
        self.last_info_per_no = ''
        repeat_no = 0

        while True:
            if len(myAction) < 1:
                logger.info(f'完成所有动作{myActions}')
                logger.info("任务完成，锁定屏幕...")
                action.Key.lockscreen()
                break

            time.sleep(1)
            no += 1
            logger.info(f'no={no}')

            self.info_per_no = ''

            node = Selector().packageName('com.hexin.plat.android').find()
            if node:
                self.logger_info('发现packageName为com.hexin.plat.android')
            else:
                self.logger_info("桌面没有packageName为com.hexin.plat.android，打开同花顺")
                if not Device.is_screen_on():
                    self.screenUnlock()
                else:
                    system.open("com.hexin.plat.android")
                    # 等待同花顺出现在前台,最多等10秒
                    if system.wait_for_package("com.hexin.plat.android", 10000):
                        self.logger_info("同花顺已打开")
                    else:
                        self.logger_info("同花顺打开超时")    
                        action.Key.back()

            # ---- 发现"交易"入口 ----
            node = Selector().path("/FrameLayout/RelativeLayout/LinearLayout/RelativeLayout/TextView").text('交易').find()
            if node:
                self.logger_info('发现交易')
                action.click(node.rect.centerX(), node.rect.centerY())
                self.logger_info('点击交易')

            # ---- 发现未登录（添加账户） ----
            node = Selector().type("TextView").text('添加账户').find()
            if node:
                self.logger_info('发现未登录')
                if myAction in ['exit']:
                    self.logger_info('已经退出')
                    break
                if myAction in ['login']:
                    # 实盘账号名称，可根据实际调整
                    node1 = Selector().type("TextView").text('国金证券').find()
                    if node1:
                        action.click(node1.rect.centerX(), node1.rect.centerY())

            # ---- 发现输入密码界面 ----
            node = Selector().id('checked_tv').find()
            if node and myAction in ['login']:
                self.logger_info('发现输入密码')
                # 输入6位密码（固定坐标，可根据实际调整）
                action.click(90, 1091)
                action.click(90, 1091)
                action.click(90, 1091)
                action.click(90, 1091)
                action.click(90, 1091)
                action.click(90, 1091)
                action.click(630, 1356)
                time.sleep(5)
                node = Selector().type("TextView").text('总资产').find()
                if node:
                    self.logger_info('发现总资产')
                    myAction = self.getNextAction(myActions, 'login')

            # ---- 发现退出按钮 ----
            node = Selector().id('exit_btn').find()
            if node and myAction in ['exit']:
                self.logger_info('发现退出按钮')
                node.click()
                self.logger_info('点击退出按钮')
                myAction = self.getNextAction(myActions, 'exit')
                time.sleep(3)

            # ---- 切换模拟/实盘 ----
            if not self.is_mn:
                node = Selector().id('com.hexin.plat.android:id/tab_a').find()
                if node:
                    self.logger_info('发现A股')
                    node.click()
                    self.logger_info('点击A股')
            else:
                node = Selector().id('com.hexin.plat.android:id/tab_mn').find()
                if node:
                    self.logger_info('发现模拟')
                    node.click()
                    self.logger_info('点击模拟')

            # ---- 获取用户总资产 ----
            node = Selector().id("com.hexin.plat.android:id/capital_value_text").find()
            if node:
                self.logger_info('发现总资产')
                user_total_assets = float(node.text.replace(',', ''))
                self.logger_info(f'得到总资产={user_total_assets}')

            # ---- 卖出按钮 ----
            node = Selector().id('com.hexin.plat.android:id/menu_sale').find()
            if node and 'sell' in myActions:
                self.logger_info('发现卖出按钮')
                if user_total_assets == 0:
                    self.logger_info('还没有得到总资产，回退')
                    action.Key.back()
                    continue
                action.click(node.rect.centerX(), node.rect.centerY())
                self.logger_info('点击卖出按钮')

            # ---- 买入按钮 ----
            node = Selector().id('com.hexin.plat.android:id/menu_buy').find()
            if node and 'buy' in myActions:
                self.logger_info('发现买入按钮')
                if user_total_assets == 0:
                    self.logger_info('还没有得到总资产，回退')
                    action.Key.back()
                    continue
                action.click(node.rect.centerX(), node.rect.centerY())
                self.logger_info('点击买入按钮')

            # ---- 股票代码输入框（列表页） ----
            node = Selector().id('com.hexin.plat.android:id/auto_stockcode').path(
                '/FrameLayout/RelativeLayout/RelativeLayout/LinearLayout/EditText').find()
            if node and ('buy' in myActions or 'sell' in myActions):
                self.logger_info('发现买入/卖出窗口')
                if user_total_assets == 0:
                    self.logger_info('还没有得到总资产，回退')
                    action.Key.back()
                    continue
                node.click()

            # ---- 股票代码输入框（交易页） ----
            node = Selector().id('com.hexin.plat.android:id/auto_stockcode').path(
                '/FrameLayout/FrameLayout/RelativeLayout/EditText').find()
            if node and ('buy' in myActions or 'sell' in myActions):
                node1 = Selector().path(
                    '/FrameLayout/RelativeLayout/RelativeLayout/RelativeLayout/ViewPager/TextView').find()
                isBuy = '买 入' in node1.text

                # 界面与动作不一致时切换买/卖
                if isBuy and 'sell' in myActions:
                    self.logger_info('界面为买入，但动作列表有sell，切换到卖出')
                    btn = Selector().id('com.hexin.plat.android:id/btn').text('卖出').find()
                    if btn:
                        btn.click()
                        continue

                if not isBuy and 'buy' in myActions:
                    self.logger_info('界面为卖出，但动作列表有buy，切换到买入')
                    btn = Selector().id('com.hexin.plat.android:id/btn').text('买入').find()
                    if btn:
                        btn.click()
                        continue

                # 输入股票代码
                if isBuy:
                    node.input(buy_code)
                else:
                    node.input(sell_code)
                self.logger_info('输入了股票代码')
                time.sleep(2)

                # ---- 输入数量 ----
                node = Selector().type('EditText').hintText('数量').find()
                if node:
                    self.logger_info('输入数量')
                    if user_total_assets == 0:
                        self.logger_info('还没有得到总资产，回退')
                        action.Key.back()
                        continue
                    # 交易比例默认为1
                    trade_ratio = 1
                    if strategy_total_assets != 0:
                        trade_ratio = user_total_assets / strategy_total_assets
                        self.logger_info(f'trade_ratio={trade_ratio}')

                    if isBuy:
                        if is_less_money:
                            # 可用余额不足时点击全仓按钮
                            node = Selector().id('com.hexin.plat.android:id/tv_flashorder_cangwei').find()
                            if node:
                                action.click(node.rect.centerX(), node.rect.centerY())
                                self.logger_info('指定金额不足，点击全仓按钮')
                        else:
                            node.input(str(int(buy_amount * trade_ratio // 100 * 100)))
                    else:
                        node.input(str(int(sell_amount * trade_ratio // 100 * 100)))

                    # 点击买入/卖出按钮
                    node = Selector().path(
                        '/FrameLayout/RelativeLayout/RelativeLayout/RelativeLayout/ViewPager/TextView').find()
                    if node:
                        self.logger_info('发现买入/卖出按钮')
                        action.click(node.rect.centerX(), node.rect.centerY())
                        self.logger_info('点击买入/卖出按钮')
                        time.sleep(3)

            # ---- 确认委托 ----
            node = Selector().id('com.hexin.plat.android:id/ok_btn').find()
            if node and ('buy' in myActions or 'sell' in myActions):
                self.logger_info('发现委托确认窗口')
                action.click(node.rect.centerX(), node.rect.centerY())
                self.logger_info('点击确认')
                time.sleep(3)

            # ---- 处理错误/提示弹窗 ----
            node = Selector().id('com.hexin.plat.android:id/prompt_content').find()
            node1 = Selector().id('com.hexin.plat.android:id/dialog_title').find()
            if (node or node1) and ('buy' in myActions or 'sell' in myActions):
                if node:
                    self.logger_info(f'发现系统信息={node.text}')
                    is_success = '委托已提交，合同号为' in node.text
                    # 可用余额不够
                    is_less_money = '可用余额不够' in node.text
                if node1:
                    self.logger_info(f'发现提示={node1.text}')

                action.Key.back()
                time.sleep(3)
                action.Key.back()

                if is_success:
                    if 'buy' in myActions:
                        myAction = self.getNextAction(myActions, 'buy')
                    else:
                        myAction = self.getNextAction(myActions, 'sell')
                    self.logger_info(f'设置当前action为{myAction}')
                    if self.is_mn:
                        myAction = self.getNextAction(myActions, myAction)
                        self.logger_info(f'设置当前action为{myAction}')

            if self.last_info_per_no == self.info_per_no:
                logger.info('发现有重复操作，回退')
                action.Key.back()
                repeat_no = repeat_no + 1
                if repeat_no>2:
                    logger.error('发现有多次重复操作，回退没有效果')
                    break
            else:
                repeat_no = 0        

            self.last_info_per_no = self.info_per_no

        return is_success

def is_a_stock_trading_time() -> bool:
    """
    判断当前时间是否为 A 股开盘时间（工作日 + 连续竞价时段）。
    使用本地时间，假设设备时间为北京时间（中国时区）。
    返回 True 表示正在交易，False 表示非交易时间。
    """
    now = datetime.now()
    
    # 检查是否为工作日（周一=0，周日=6）
    if now.weekday() >= 5:  # 周六、周日休市
        return False
    
    hour = now.hour
    minute = now.minute
    
    # 上午交易时段：9:25（含）~ 11:30（不含）
    if (hour == 9 and minute >= 25) or (hour == 10) or (hour == 11 and minute < 30):
        return True
    
    # 下午交易时段：13:00（含）~ 15:00（不含）
    if 13 <= hour < 15:
        return True
    
    return False

# ======================== 主控逻辑 ========================
# 主轮询循环
last_time = time.time()
last_is_a_stock_trading_time = False
while True:
    try:        
        if isTest:
            now_is_a_stock_trading_time=True
        else:
            now_is_a_stock_trading_time=is_a_stock_trading_time()
        if now_is_a_stock_trading_time:
            if last_is_a_stock_trading_time != now_is_a_stock_trading_time:
                # 初始化聚宽跟踪器
                jq = JoinQuantFollower()
                jq.login(JOINQUANT_USER, JOINQUANT_PWD)

                # 提取策略ID
                strategies = []
                for url in STRATEGY_URLS:
                    sid = jq.extract_strategy_id(url)
                    name = jq.extract_strategy_name(url)
                    strategies.append({"id": sid, "url": url, "name": name})
                    
                last_is_a_stock_trading_time = now_is_a_stock_trading_time

            for strategy in strategies:
                sid = strategy["id"]
                name = strategy["name"]
                logger.info(f"查询策略 {name} 调仓...")
                transactions = jq.query_transaction(sid)
                if isTest:
                    transactions = [
                            {
                                "action": 'buy',
                                "stock_code": '159985',
                                "amount": 1000,
                                "price": 2.4525,
                                "datetime": datetime.now().replace(hour=10, minute=30, second=0, microsecond=0),
                            }
                        ]
                logger.info(transactions)

                if not transactions:
                    logger.info("无新调仓")
                    continue
                
                # 处理每个指令
                for cmd in transactions:
                    # 检查是否过期（时间超时）
                    now = datetime.now()
                    if (now - cmd["datetime"]).total_seconds() > CMD_EXPIRE_SECONDS:
                        logger.warning(f"指令超时，丢弃: {cmd}")
                        continue
                    
                    # 检查是否已执行
                    if jq.is_cmd_expired(cmd):
                        logger.info(f"指令已执行过: {cmd}")
                        continue
                    
                    # 执行交易
                    trader = ThsMobileTrader()

                    # 若启用比例交易，可在此计算调整数量（需获取用户总资产）
                    strategy_total_assets = 0
                    if USE_TRADE_RATIO:
                        #计算策略总资产
                        strategy_total_assets=jq.get_strategy_total_assets(sid)
                        logger.info(f"策略总资产: {strategy_total_assets}")

                    success = trader.execute_order(
                        trade_action=cmd["action"],
                        stock_code=cmd["stock_code"],
                        amount=cmd["amount"],
                        price=cmd["price"],
                        strategy_total_assets=strategy_total_assets,
                    )
                    if success:
                        jq.mark_cmd_executed(cmd)
                        logger.info(f"指令执行成功: {cmd}")
                    else:
                        logger.error(f"指令执行失败: {cmd}")
                        # 可发邮件告警，根据实际修改
                        # send_email(...)
                    
                    # 指令间间隔
                    time.sleep(2)
        else:
            logger.info('现在是非交易时间，不操作')

        # 等待下一次轮询
        elapsed = time.time() - last_time
        if elapsed < TRACK_INTERVAL:
            time.sleep(TRACK_INTERVAL - elapsed)
        last_time = time.time()
        
    except Exception as e:
        logger.exception("轮询异常: %s", e)
        time.sleep(TRACK_INTERVAL)
'''
