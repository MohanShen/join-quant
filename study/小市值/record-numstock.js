// Recorder helper for q-e9-champ-numstock (2026-11-04). Records the finding (stamps measuredEpoch)
// and marks the queue entry answered. Refuses to write twice.
const rq = require('../../utils/research-queue');
const FAM = '小市值';
const QID = 'q-e9-champ-numstock';

if (rq.findings(FAM).some(f => f.qId === QID)) throw new Error(`${QID} already recorded`);

rq.recordFinding(FAM, {
  qId: QID,
  type: 'ablation',
  component_or_param: '反向消融：打开 champion 02fdafaa 自带却 0 处调用的 adjust_stock_num（L576–590；399101 close−MA10 点差，previous_date 取数：diff ≥ 200 → 3，[−200,200) → 4，[−500,−200) → 5，其余 → 6）。唯一逻辑改动 = L145 weekly_adjustment 交易信号分支内第一行插入 g.stock_num = adjust_stock_num(context)，另加 NUMSTOCK/NUMHELD 日志。builder study/小市值/build-numstock-02fdafaa.js → 变体 study/小市值/variants/02fdafaa-numstock.py。CONTROL = 02fdafaa 自身 epoch-9 台账行 3.0172 / 8.22 / 320.35 / 18.63，不是 base 7a1c225f，也不是前 champion 0a7de9fa',
  metric_delta: 'objective 3.0172 → 3.8960（Δ +0.8788）/ sharpe 8.22 → 10.64（+2.42）/ annual 320.35 → 407.90（+87.55pp）/ maxDD 18.63 → 18.30（−0.33pp；窗口 2024-05-07→06-24 变为 2024-05-17→06-24，同一谷底、峰更晚）。recorder 由两条存盘曲线（各 242 点）独立复算 objective / total / maxDD / 窗口',
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding: '预注册落 (c)「有益」，但效应集中在一个事件上。有效性闸门通过：42 NUMSTOCK = 42 NUMHELD（一月与四月被本书自身闸门挡住），0 MISMATCH、0 失败、0 traceback；一月恰 0.00%，二月 +35.34% 与对照逐位相同（三次二月调仓均为 n=6），底部再入场形状原样存活。n 分布：3 ×10（指数高于 MA10 +2.19%…+20.65%）、4 ×24、5 ×4、6 ×4（2 次市场决定，2 次春节 NaN 落空：2024-02-20 与 2024-02-27，gatekeeper 只预测了前者；均未修补）。实际持仓与 n 不同 5/42 次；7 次下调里只有 3 次被卖出规则多留名字，「卖出规则吸收旋钮」分支不触发。按月对数增长差（recorder 复算）总计 +0.1892：四月份额 4.0% 且自身为负 ⇒ 现金比例通道排除、集中度主导；2024-09-24 至年末 +0.2079 = 总量的 110%（10 月 +0.127、11 月 +0.076，8 次调仓中 5 次 n=3），09-24 之前净 −0.019（3 月 −0.013、5 月 −0.011、7 月 −0.072，6 月 +0.033、8 月 +0.037 部分抵消）',
  confidence: 'high',
  flags: '⚠零滑点高估; regime-specific（2024-09-24 政策行情贡献 110%）; 阈值为 399101 绝对点数，2024 年 ±200 点 ≈ ±1.7%–2.4%，跨窗口即另一条规则; 单书，未消融任何兄弟成员; 非 realizability 陈述（n=3 时可行性地板约 ¥6.67e6/日，未测）',
  description: '新成员 7e59016c（0.7751）以 adjust_num = True 入族，champion 02fdafaa 逐行携带同一规则但处于休眠；gatekeeper 查得 4 本已测成员（aaba7575 1.1403 / 17c95d16 1.3571 / 76593fb6 0.6923 / 7e59016c 0.7751，另 55458717 未测）均打开此规则，0 本有开/关对照。单书 TRAIN 一次、105 秒。champion postedAt 2025-06-06（2026-10-30 为抓取日）',
  implication: '决定：不采纳，也不在本台开 improve 条目。+0.88 是一次行情事件而不是稳定效应——该规则在 TRAIN 2024 的全部贡献来自把仓位集中到 3 只、正好赶上 2024-09-24 的政策行情，其余八个月是轻微拖累；单年 TRAIN 无法区分「规则会择时行情」与「规则恰好在全年最大的小盘行情里处于 n=3」，所以没有 2024 之外的证据就不得作为候选。本族 VAL 已用且失败（owner: human），这里的任何结果都不能移动 exit gate。其二：重读四本兄弟书——aaba7575 / 17c95d16 / 76593fb6 / 7e59016c 都运行此规则，它们的 epoch-9 水平可能含同一笔 Q4 集中度红利；这只是对它们 §3 数字的 caveat，不是测量（四本均未消融，证据只是一本书）。其三：不是 realizability 陈述——n=3 时单仓翻倍，q-e9-champ-liq-02fdafaa 的 ¥3.33e6/日 地板对变体不再覆盖（起始资本下约 ¥6.67e6/日，随复利上升），realizability: 与 realizabilityScope: 不动。其四：尺度依赖——阈值是绝对点数，399101 在 2024 年约 8,200–11,900，±200 点 ≈ ±1.7%–2.4%，带宽只属于这一年，本结果对任何别的窗口不作陈述',
  spawned: 'none',
  edgeRef: '',
});

const e = rq.load(FAM).find(x => x.id === QID);
const last = rq.findings(FAM).slice(-1)[0];
console.log(`status=${e.status} qId=${last.qId} measuredEpoch=${last.measuredEpoch}`);
