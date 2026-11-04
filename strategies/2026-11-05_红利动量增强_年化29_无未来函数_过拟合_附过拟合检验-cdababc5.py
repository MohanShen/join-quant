# Clone from JoinQuant
# postId: cdababc58681fcb2380244da37ca8bfc
# backtestId: 87a7e4dd95c7ae9e95e369259dd3e75d
# title: 红利动量增强，年化29%，无未来函数，过拟合，附过拟合检验

from jqdata import *
import datetime
import pandas as pd


class DividendYield(object) :
    
    '''
    转换交易日期
    遇到节假日取最近的一个交易日
    '''
    @staticmethod
    def convert_trade_date(query_date: datetime.date) -> datetime.date:
        if query_date is None :
            return None
        
        if type(query_date) is str :
            query_date = datetime.datetime.strptime(query_date, "%Y-%m-%d").date()

        trade_days = get_trade_days(start_date=None, end_date=query_date, count=1)
        return trade_days[0] if len(trade_days) > 0 else None
    
    '''
    单个股票在查询日期对应的去年分红（每10股分红）
    增加防御：如果目标年度无分红记录，向下顺延查找前一年
    '''
    @staticmethod
    def get_bonus_ratio_rmb(item:pd.DataFrame, query_date:datetime.date) -> float :
        max_report_date = item[item['board_plan_pub_date']<query_date]['report_date'].max()
        if not type(max_report_date) is datetime.date :
            return 0
        
        last_year = datetime.datetime.strptime(str(query_date.year-1)+'-12-31', "%Y-%m-%d").date()
        
        if max_report_date >= last_year:
            bonus_year = query_date.year-1
        else :
            bonus_year = query_date.year-2

        bonus_sum = item.groupby('bonus_year').sum().sort_values(by='bonus_year', ascending=False)

        bonus_ratio_rmb = 0
        if bonus_year in bonus_sum.index :
            bonus_ratio_rmb = bonus_sum['bonus_ratio_rmb'][bonus_year]
        else:
            for fallback_year in [bonus_year - 1, bonus_year - 2]:
                if fallback_year in bonus_sum.index:
                    bonus_ratio_rmb = bonus_sum['bonus_ratio_rmb'][fallback_year]
                    break

        return bonus_ratio_rmb
    
    '''
    批量查询一组股票的每10股分红数据
    '''
    @staticmethod
    def get_bonus_ratio(code_list:list, query_date:datetime.date) -> pd.DataFrame:
        if len(code_list) == 0 or query_date is None:
            return None
        
        tb=finance.STK_XR_XD
        q=query(tb.code, tb.report_date, tb.bonus_ratio_rmb, tb.board_plan_pub_date)\
            .filter(tb.code.in_(code_list))\
            .order_by(tb.report_date.desc())
        df = finance.run_query(q)
        df=df.dropna()
    
        df['bonus_year'] = df['report_date'].map(lambda x : x.year)

        tmp = []
        for code in code_list:
            tmp.append({
                'code':code, \
                'query_date':query_date, \
                'bonus_ratio_rmb':DividendYield.get_bonus_ratio_rmb(df[df['code']==code], query_date)
            })

        return pd.DataFrame(tmp)
    
    '''
    股息率(%) = 每10股分红（元） / (10 * 股价（元）)
    '''
    @staticmethod
    def calc_dividend_yield(code_list:list, query_date:datetime.date) -> pd.DataFrame:
        bonus_df = DividendYield.get_bonus_ratio(code_list, query_date) 
        if bonus_df is None :
            return None
        
        price_df = get_price(code_list, start_date=query_date, end_date=query_date, frequency='daily', fields=['close'], skip_paused=False, fq='pre', count=None, panel=False, fill_paused=False)
        price_df = price_df.drop(['time'], axis=1)
        df = pd.merge(price_df, bonus_df, on='code')
        
        df['dividend_yield'] = df.bonus_ratio_rmb / (10 * df.close)
        df = df.drop(['close', 'bonus_ratio_rmb'], axis=1)
        return df


# ==================== 策略主体 ====================

def initialize(context):
    set_option("avoid_future_data", True)
    set_option('use_real_price', True)
    set_benchmark('000015.XSHG')
    set_slippage(PriceRelatedSlippage(0.001))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type='stock',
    )

    log.set_level('order', 'error')
    log.set_level('history', 'error')
    log.set_level('system', 'error')

    g.sell_list = []
    g.buy_df = pd.DataFrame(columns=['name', 'price', 'amount', 'value'])
    g.stock_num = 5
    g.high_limit_list = []
    g.strategy = 'hongli_momentum'
    g.filename = '红利动量增强.csv'

    g.first = 1
    g.out_cash = 0

    # ========== 核心参数配置区 ==========
    g.use_momentum = True         # 动量开关：True开启动量增强，False关闭(纯红利策略)
    g.momentum_days = 25       # 动量计算天数
    g.dividend_weight = 0.7      # 股息率权重
    g.momentum_weight = 0.3    # 动量权重
    g.min_select = 1
    # ==================================

    g.score_df = None
    g.candidate_rank = []
    g.pending_replenish = False
    g.recently_sold = set()
    g.rebalance_date = None

    run_daily(prepare_stock_list, '09:00')
    run_monthly(get_stock_list, 1, '09:01')
    run_monthly(my_trade, 1, '09:30')
    run_daily(check_limit_up, '10:00')
    run_daily(replenish_positions, '09:35')
    run_daily(replenish_positions, '14:50')


def get_min_lot(stock_code):
    if stock_code[:3] == '688':
        return 200
    return 100


def get_limit_ratio(stock_code, current_dt):
    date_str = str(current_dt)[:10]
    if stock_code[:3] == '688':
        return 0.20
    if stock_code[0] == '3' and date_str >= '2020-08-24':
        return 0.20
    return 0.10


def get_buy_limit_price(stock_code, close_price, current_dt):
    ratio = get_limit_ratio(stock_code, current_dt)
    return round(close_price * (1 + ratio), 2)


def calc_affordable_amount(stock_code, budget, limit_price):
    min_lot = get_min_lot(stock_code)
    if limit_price <= 0 or budget < limit_price * min_lot:
        return 0
    return min_lot * int(budget / limit_price / min_lot)


def is_unbuyable(current_data, stock_code):
    cd = current_data[stock_code]
    if cd.paused:
        return True
    if cd.last_price <= 0:
        return True
    if cd.high_limit > 0 and cd.last_price >= cd.high_limit * 0.998:
        return True
    return False


def get_current_slots_needed(context):
    hold_count = len(context.portfolio.positions)
    return max(0, g.stock_num - hold_count)


def pick_replenish_targets(context, hold_list, slots_needed):
    if slots_needed <= 0 or not g.candidate_rank:
        return []

    current_data = get_current_data()
    per_stock_value = context.portfolio.total_value / g.stock_num
    targets = []

    for code in g.candidate_rank:
        if len(targets) >= slots_needed:
            break
        if code in hold_list:
            continue
        if code in g.recently_sold:
            continue
        if is_unbuyable(current_data, code):
            continue

        price = current_data[code].last_price
        if calc_affordable_amount(code, per_stock_value, price) <= 0:
            continue
        targets.append(code)

    return targets


def select_target_stocks(context, score_df, hold_list, stock_num):
    per_stock_budget = context.portfolio.total_value / stock_num
    target_list = []
    skipped = []

    for code in score_df.index:
        if len(target_list) >= stock_num:
            break

        if code in hold_list:
            target_list.append(code)
            continue

        close_df = get_price(
            code,
            end_date=context.previous_date,
            frequency='1d',
            count=1,
            fields=['close'],
            fq='pre',
            panel=False,
            skip_paused=False,
            fill_paused=True,
        )
        if close_df.empty:
            skipped.append((code, '无有效收盘价'))
            continue

        limit_price = get_buy_limit_price(code, close_df['close'].iloc[-1], context.current_dt)
        amount = calc_affordable_amount(code, per_stock_budget, limit_price)
        if amount > 0:
            target_list.append(code)
        else:
            skipped.append((code, '单价 %.2f，预算 %.2f 不足买 %d 股' % (
                limit_price, per_stock_budget, get_min_lot(code))))

    if skipped:
        print('========== 买不起/跳过标的 ==========')
        for code, reason in skipped:
            print('%s: %s' % (code, reason))
        print('====================================')

    return target_list


def prepare_stock_list(context):
    g.high_limit_list = []
    g.hold_list = list(context.portfolio.positions)
    if len(g.hold_list) != 0:
        df = get_price(
            g.hold_list,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False,
            fill_paused=False,
            skip_paused=False,
        ).dropna()
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)


def get_momentum_factor(context, stock_list, days=20):
    if not stock_list:
        return pd.DataFrame(columns=['momentum'])

    yesterday = context.previous_date
    df = get_price(
        stock_list,
        end_date=yesterday,
        frequency='daily',
        fields=['close'],
        count=days + 5,
        panel=False,
        skip_paused=False,
        fill_paused=True,
    )

    if df.empty:
        return pd.DataFrame(columns=['momentum'])

    momentum_list = []
    for code in stock_list:
        code_df = df[df['code'] == code].dropna()
        if len(code_df) >= days:
            start_price = code_df['close'].iloc[-days]
            end_price = code_df['close'].iloc[-1]
            momentum = (end_price / start_price - 1) * 100
        else:
            momentum = -999
        momentum_list.append({'code': code, 'momentum': momentum})

    return pd.DataFrame(momentum_list).set_index('code')


def get_stock_list(context):
    g.buy_df = pd.DataFrame(columns=['name', 'price', 'amount', 'value'])
    yesterday = str(context.previous_date)
    today = context.current_dt

    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcb_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)

    stock_list = initial_list
    df = get_fundamentals(query(valuation.code).filter(
        valuation.code.in_(stock_list),
        valuation.pe_ratio.between(5, 50),
        indicator.inc_return.between(5, 100),
        indicator.inc_total_revenue_year_on_year.between(5, 100),
        indicator.inc_net_profit_year_on_year.between(10, 100),
    ))
    stock_list = list(df.code)

    query_date = context.previous_date
    div_df = DividendYield.calc_dividend_yield(stock_list, query_date)
    
    if div_df is None or div_df.empty:
        print("警告：无满足股息计算条件的股票，本次不交易")
        g.sell_list = [s for s in g.hold_list if s not in g.high_limit_list]
        return
    
    div_df = div_df.dropna(subset=['dividend_yield'])
    div_df = div_df[div_df['dividend_yield'] > 0]
    div_df = div_df[div_df['dividend_yield'] > 0.03]
    
    dividend_list = list(div_df['code'])
    if not dividend_list:
        print("警告：股息率低于3%%，本次不交易")
        g.sell_list = [s for s in g.hold_list if s not in g.high_limit_list]
        return

    # 根据开关决定是否计算动量
    if g.use_momentum:
        momentum_df = get_momentum_factor(context, dividend_list, days=g.momentum_days)
        score_df = div_df.set_index('code').join(momentum_df, how='left')
        # 如果某些股票动量数据缺失，填充为极低值
        score_df['momentum'] = score_df['momentum'].fillna(-999)
        
        score_df['dividend_rank'] = score_df['dividend_yield'].rank(pct=True, ascending=True)
        score_df['momentum_rank'] = score_df['momentum'].rank(pct=True, ascending=True)
        
        score_df['total_score'] = (
            g.dividend_weight * score_df['dividend_rank'] +
            g.momentum_weight * score_df['momentum_rank']
        )
    else:
        # 纯红利模式：直接按股息率打分
        score_df = div_df.set_index('code')
        score_df['total_score'] = score_df['dividend_yield']

    score_df = score_df.sort_values('total_score', ascending=False)

    hold_list = getattr(g, 'hold_list', list(context.portfolio.positions))
    target_list = select_target_stocks(context, score_df, hold_list, g.stock_num)
    select_count = max(g.min_select, min(g.stock_num, len(target_list)))
    target_list = target_list[:select_count]

    g.score_df = score_df
    g.candidate_rank = list(score_df.index)
    g.rebalance_date = context.current_dt.date()

    print('========== 综合打分详情 (Top 15) ==========')
    display_df = score_df[['dividend_yield', 'total_score']].head(15).copy()
    if g.use_momentum and 'momentum' in score_df.columns:
        display_df = score_df[['dividend_yield', 'momentum', 'total_score']].head(15).copy()
    
    names = []
    for code in display_df.index:
        try:
            info = get_security_info(code, yesterday)
            names.append(info.display_name if info else '未知')
        except:
            names.append('未知')
    
    display_df.insert(0, 'name', names)
    
    display_df['dividend_yield'] = (display_df['dividend_yield'] * 100).round(2).astype(str) + '%'
    if g.use_momentum and 'momentum' in display_df.columns:
        display_df['momentum'] = display_df['momentum'].round(2).astype(str) + '%'
    display_df['total_score'] = (display_df['total_score'] * 100).round(2).astype(str) + '%'
    
    print(display_df)
    print('==========================================')
    print('选中标的:', target_list)

    g.sell_list = [s for s in hold_list if s not in target_list and s not in g.high_limit_list]
    buy_list = [s for s in target_list if s not in hold_list]

    value = context.portfolio.available_cash
    for s in g.sell_list:
        value += context.portfolio.positions[s].value

    if buy_list:
        value = value / len(buy_list)
        price_df = get_price(
            buy_list,
            end_date=yesterday,
            frequency='1d',
            count=1,
            fields=['close'],
            fq='pre',
            panel=False,
            skip_paused=False,
            fill_paused=True,
        ).set_index('code')

        rows = []
        for s in buy_list:
            limit_price = get_buy_limit_price(s, price_df.loc[s, 'close'], context.current_dt)
            amount = calc_affordable_amount(s, value * 1.05, limit_price)
            if amount <= 0:
                print('警告：%s 预算不足，跳过买入' % s)
                continue
            rows.append({
                'code': s,
                'name': get_security_info(s, yesterday).display_name,
                'price': limit_price,
                'amount': amount,
                'value': limit_price * amount,
            })

        if rows:
            g.buy_df = pd.DataFrame(rows).set_index('code')

    print('卖出', g.sell_list)
    print('———————————————————————————————————')
    print('红利动量' if g.use_momentum else '纯红利', g.buy_df)
    print('———————————————————————————————————')


def my_trade(context):
    current_data = get_current_data()

    for s in g.sell_list:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)

    for s in list(g.buy_df.index):
        amount = int(g.buy_df.loc[s, 'amount'])
        if amount <= 0:
            print('跳过买入 %s：数量为 0' % s)
            g.pending_replenish = True
            continue
        if is_unbuyable(current_data, s):
            print('跳过买入 %s：开盘涨停/停牌，稍后补位' % s)
            g.pending_replenish = True
            continue
        print('买入', [s, g.buy_df.loc[s, 'name']])
        order(s, amount, LimitOrderStyle(g.buy_df.loc[s, 'price']))
        print('———————————————————————————————————')

    if get_current_slots_needed(context) > 0:
        g.pending_replenish = True


def check_limit_up(context):
    current_data = get_current_data()

    if g.high_limit_list:
        for s in g.high_limit_list:
            if current_data[s].last_price < current_data[s].high_limit:
                order_target_value(s, 0)
                g.recently_sold.add(s)
                g.pending_replenish = True
                print(s, '涨停打开，卖出（待补位）')
                print('———————————————————————————————————')
            else:
                print(s, '涨停，继续持有')
                print('———————————————————————————————————')


def replenish_positions(context):
    slots_needed = get_current_slots_needed(context)
    if slots_needed <= 0:
        g.pending_replenish = False
        g.recently_sold = set()
        return

    if g.rebalance_date == context.current_dt.date() and context.current_dt.hour < 10:
        return

    if not g.candidate_rank:
        print('补位跳过：无缓存候选排名')
        return

    hold_list = list(context.portfolio.positions.keys())
    buy_list = pick_replenish_targets(context, hold_list, slots_needed)
    if not buy_list:
        print('补位待定：暂无可买标的（可能均在涨停/停牌），稍后重试')
        g.pending_replenish = True
        return

    per_stock_value = context.portfolio.total_value / g.stock_num
    current_data = get_current_data()

    print('========== 持仓补位 ==========')
    print('需补 %d 只，尝试买入: %s' % (slots_needed, buy_list))

    for code in buy_list:
        if is_unbuyable(current_data, code):
            print('跳过 %s：当前涨停或停牌' % code)
            continue
        order_target_value(code, per_stock_value)
        print('补位买入 %s，目标市值 %.2f' % (code, per_stock_value))

    remaining = get_current_slots_needed(context)
    g.pending_replenish = remaining > 0
    if remaining == 0:
        g.recently_sold = set()
    else:
        print('补位后仍缺 %d 只，后续继续尝试' % remaining)
    print('==============================')


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [
        stock for stock in stock_list
        if not current_data[stock].is_st
        and 'ST' not in current_data[stock].name
        and '*' not in current_data[stock].name
        and '退' not in current_data[stock].name
    ]


def filter_kcb_stock(stock_list):
    return [
        stock for stock in stock_list
        if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68'
    ]


def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [
        stock for stock in stock_list
        if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)
    ]