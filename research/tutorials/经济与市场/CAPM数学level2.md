---
title: "【量化课堂】CAPM 模型和公式"
category: 经济与市场
learners: 9711
postedAt: 2016-08-18 15:05:11
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:29:34.042Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【量化课堂】CAPM 模型和公式

**导语**：$\alpha$ 和 $\beta$ 你肯定都听说过吧。那么 $\gamma$ 呢？$\delta$？$\varepsilon$？$\zeta$，$\eta$，$\theta$，$\iota$，... $\omega$？？？那好！我们今天就来告诉你...... $\beta$ 是什么。
$ $
```
作者：肖睿
编辑：宏观经济算命师

本文由JoinQuant量化课堂推出，难度为进阶上，深度为 level-2。
```
阅读本文需要掌握 [MPT 模型（**level-1**）](https://www.joinquant.com/post/1991?f=study&m=financial)和微积分（**level-0**）的知识。
$ $
本文是一系列文章中的第三篇。本系列从基础概念入手，推导出 CAPM 模型。系列中共有四篇：
1. [效用模型](https://www.joinquant.com/post/1772?f=study&m=financial)
2. [风险模型](https://www.joinquant.com/post/1774?f=study&m=financial)
3. [MPT 模型](https://www.joinquant.com/post/1991?f=study&m=financial)
4. **CAPM 模型**
$ $

#### **概述**

CAPM，全称 Capital Asset Pricing Model，译为资本资产定价模型，是由 Treynor, Sharpe, Lintner, Mossin 几人分别提出。搭建于 Markowitz 的现代资产配置理论（MPT）之上，该模型用简单的数学公式表述了资产的收益率与风险系数 $\beta$ 以及系统性风险之间的关系。尽管 CAPM 的假设偏于牵强，结论也常与实验证据相悖，但它一直是金融经济学中重要的理论，为更多先进的模型打好了基础。
$ $
#### **模型假设**

CAPM 是一个理论性很强的模型，它所假设的金融市场有一个非常简单的框架，这样不仅简化了分析的难度，也用非常简练的数学公式表达出结论。

CAPM 假设，市场上所有的投资者对于风险和收益的评估仅限于对于收益变量的预期值和标准差的分析，而且所有投资者都是完全理智的。并且，市场是完全公开的，所有投资者的信息和机会完全平等，任何人都可以以唯一的无风险利率无限制地贷款或借出。

因此，所有投资者必定在进行资产分配时计算同样的优化问题，并且得到同样的有效前沿和资本市场线（见 [MPT 模型](https://www.joinquant.com/post/1991?f=study&m=financial)）。
![MPT.jpg][1]

为了最大化预期收益并最小化标准差，所有投资者必定选择资本市场线上的一点作为资产配置。也就是说，所有投资者都按一定比例持有现金和市场组合 $M$。因此， $M$ 是名副其实的“市场组合”，因为整个市场都是按照这个组合来分配资产的。所以 $M$ 的波动性和不确定性不单单是市场组合的风险，也是整个市场的风险，叫做*系统性风险(systematic risk)*。
$ $
#### **CAPM 公式**

CAPM 公式是从以上模型框架推导出的数学表达式，它表达了任何风险资产的收益率和市场组合的收益率之间关系。在这个公式中，任何风险资产的收益率都可以被分为两个部分：无风险收益（利率）和风险收益（$\beta$ 收益）。我们先看公式。
$ $
**定理（CAPM 公式）.** *对于某一风险资产 $S$（可以把 $S$ 想象为一种证券），有
\[ E[r_S] = r_f + {\beta_S} \cdot ({E[r_M] - r_f}). \]其中：
$-\ r_S$ 是组合 $S$ 的收益变量；
$-\ r_M$ 是市场组合的收益变量;
$-\ r_f  $ 是市场的无风险利率;
$-\ \beta_S$ 是组合 $S$ 对于市场风险的敏感度，计算公式为*
\[\beta_S = \frac{\text{Cov}(r_S, r_M)}{\text{Var} (r_M)} . \]
$ $
在公式中，$r_f$ 是资产的时间价值，是按照无风险利率产生的收益。右边的 $\beta_S \cdot (E[r_M] - r_f)$ 是资产的风险收益，是对投资者所承担的风险的补偿。这里面，$E[r_M] - r_f$ 是市场组合的风险收益，还有 $\beta_S$ 是组合 $S$ 对系统性风险的敏感系数。可以理解为，资产 $S$ 承担了 $\beta _S$ 倍的系统性风险，所以将会得到相应倍数的风险补偿。

这里应该指出，风险组合 $S$ 的预期收益是完全由它的 $\beta _S$ 决定的，与这个资产自己的风险 $\sigma _S$ 是没有关系的。也就是说，假设风险资产 $S$ 有巨大的风险 $\sigma _S$，但是它和市场组合的相关性 $\beta _S$ 很小，那么 $S$ 预期的收益率其实是很小的。

通过 CAPM 公式，我们还可以推算出资产 $S$ 的夏普比率 $\text{Sharpe}(S)$ 和市场组合 $M$ 的夏普比率 $\text{Sharpe}(M)$ 的关系，如下。
\begin{align*}
\text{Sharpe}(S) &= \frac{E[r_S] - r_f}{ \sigma _S }\\
& = \frac{ \beta_S \cdot (E[r_M] - r_f)  }{ \sigma _S }\\
& = \frac{\text{Cov} (r_M, r_S)}{ \sigma _M  \sigma _S } \cdot \frac{E[r_M] - r_f}{\sigma _M}\\
& = \text{Corr}(r_M, r_S) \cdot \text{Sharpe}(M).
\end{align*}
也就是说，组合 $S$ 的夏普比率等于 $M$ 的夏普比率乘以 $M$ 与 $S$ 的相关系数。在 MPT 模型中，$M$ 是所有风险组合中夏普比率最高的，也就是最有效的。这个公式告诉我们， $S$ 和 $M$ 的相关性越高，$S$ 的夏普比率就越高，收益比风险的比例也就越大。
$ $
#### **CAPM 公式的证明**

***证明***. 对于 $\alpha \in \mathbb R$，我们定义 $A_\alpha$ 为按照 $\alpha$ 份 $S$ 比 $1-\alpha$ 份 $M$ 所构成的资产配置。定义 $\overline r(\alpha)$ 和 $\sigma(\alpha)$ 分别为组合 $A_\alpha$ 的预期收益和波动率。定义函数 $f(\alpha) = (\sigma(\alpha) , \overline r (\alpha))$，那么 $f$ 是一条在可行资产配置区域内的平滑曲线，并且 $f(1) = (\sigma _S, E[r_S])$， $f(0) = (\sigma _M , E[r_M])$。该曲线在 $\alpha = 0$ 时和资本配置线重叠在市场组合之上；并且，由于所有风险资产配置得位置都在资本配置线的下方，所以曲线 $f$ 不会和资本配置线相交。因此，可以肯定资本配置线和 $f(\alpha)$ 在 $(\sigma _M, E[r_M])$ 处构成切线关系。如下图所示：
![CAPM_proof2.jpg][2]

我们知道资本配置线的坡度是 $M$ 的夏普比率 
\begin{align}
\text{Sharpe}(M) = \frac{E[r_M] - r_f}{\sigma_M}. 
\end{align}
那么，曲线 $f$ 的 $\overline r$ 坐标相对于 $\sigma$  坐标在 $\alpha = 0$ 的导数也等于这个坡度,
\begin{align}
\left. \frac{d \overline r}{d \sigma } \right|_{\alpha = 0} = \frac{ E[r_M] - r_f }{\sigma _M}.\ \ (1)
\end{align}
$A_\alpha$ 的收益变量是 
\begin{align}
r_{A_\alpha} = \alpha r_S+(1-\alpha) r_M,
\end{align} 
因此有
\begin{align}
\overline r(\alpha) & = E[r_{A_\alpha}] = \alpha E[r_S] + (1-\alpha) E[r_M], & (2)\\
\sigma(\alpha) & = \sigma (r_{A_{\alpha}}) = \sqrt{\alpha^2\sigma _{r_S}^2 + (1-\alpha)^2 \sigma _{r_M}^2 + 2\alpha(1-\alpha) \text{Cov}(r_M, r_S) }. & (3)
\end{align}
代入等式 (2) 和 (3) 并使用初等微积分技能，我们亲手肢解等式 (1) 左侧的表达式，
\begin{align}
\left. \frac{d\overline r }{d \sigma} \right|_{\alpha = 0} & = \left[ \left. \frac{d \overline r }{d \alpha} \right/  \frac{d \sigma }{d \alpha} \right]_{\alpha = 0}\\
& = \left. \frac {E[r_S] - E[r_M]}{ { \frac{1}{2} \cdot \left( \alpha\sigma _{S}^2 + (1-\alpha)^2 \sigma _{M}^2 + 2\alpha(1-\alpha) \text{Cov}(r_M, r_S)\right)^{-\frac{1}{2} } }{\cdot \left(2 \alpha \sigma _{S}^2 - 2(1-\alpha) \sigma _{M} ^2 + (2-4\alpha)\text{Cov}(r_M,r_S) \right)  } } \right|_{\alpha = 0}\\
& = \frac{E[r_S] - E[r_M]}{ \frac{1}{2} \cdot \sigma _M^{-1} \cdot \left(2\, \text{Cov}(r_M, r_S) - 2\, \text{Var}(r_M) \right) }\\
& = \frac{\left( E[r_S] - E[r_M] \right) \cdot \sigma _M}{\text{Cov}(r_S, r_M) - \text{Var}(r_M)}.
\end{align}
再代入等式 (1) 得到
\begin{align}
\frac{\left( E[r_S] - E[r_M] \right) \cdot \sigma _M}{\text{Cov}(r_S, r_M) - \text{Var}(r_M)} & = \frac{E[r_M] - r_f}{ \sigma _M }\\
E[r_S] - E[r_M]  & = \frac{\text{Cov}(r_S, r_M) - \text{Var}(r_M)}{\text{Var}(r_M)} \cdot \left( E[r_M] - r_f \right) \\
E[r_S] - E[r_M] & = \left( \beta_S - 1 \right) \cdot \left( E[r_M] - r_f \right)\\
E[r_S] & = r_f + \beta_S \cdot (E[r_M] - r_f).
\end{align}
擦干净双手，完成了证明。$\blacksquare$
$ $
#### **CAPM 的应用**

CAPM 公式的应用在理论上是一个悖论，那是因为在 CAPM 的假设下所有投资者都持有市场组合 $M$，那么投资者也没有必要去单独计算每一个风险资产的收益率 --- 因为他所持有的资产配置已经是最优的了。但实际上，投资者的效用标准都不一样，资产配置也大相庭径，并不存在一个一致认同的市场组合，这时 CAPM 公式就可以派上用场。

在现实环境里，我们可以将一个概括市场整体的组合（比如大盘指数）作为市场组合，并以其为基准计算每个风险资产的系统性风险 $\beta$。这样，我们根据对市场整体趋势的判断以及对风险控制的需要，选择适当的 $\beta$ 进行资产配置。
$ $
举个例子，假设我们以沪深300指数作为市场组合，取过去 $500$ 天的年化日均收益率为 $(r_M(t))_{t=1} ^{500}$，并且取一只股票 $S$ 过去 $500$ 天的年化日均收益率为 $(r_S(t))_{t=1}^{500}$。记它们的均值为
\[ \mu _M = \frac{1}{500} \sum _{t=1} ^{500} r_M(t),\ \mu _S = \frac{1}{500} \sum _{t=1} ^{500} r_S(t). \]
可以估测出 $S$ 的 $\beta$ 为
\[ \beta_S = \frac{\text{Cov}(r_S, r_M)}{ \text{Var}(r_M) } = \frac{ \sum _{t=1}^{500} (r_M(t)- \mu _M)(r_S(t) - \mu _S) }{ \sum _{t=1} ^{500} (r_M(t) - \mu _M )^2 }. \]

假设我们选出三支股票，并且计算发现它们的 $\beta$ 分别为 $\beta_1 = 0.5$， $\beta_2 = 1$ 和 $\beta_3 = 2$，也就是说它们对市场风险的敏感度依次为低、中、高。如果我们通过分析预测大盘在近期会整体趋势向上，那么应该持仓股票3，赚取大盘 $2$ 倍的收益；如果我们认为大盘近期的走势不可判断，那么可以持有股票2，这样收益基本与大盘持平；如果我们认为大盘在近期会整体下跌，那么可以持有股票1，这样损失只有大盘的一半，或者干脆直接空仓。
$ $
#### **结语**

量化课堂的“从效用到CAPM”系列文章从效用模型开始，介绍了风险分散的原则，再到 MPT 资产配置理论的有效前沿和市场组合，最后本篇讲解了 CAPM 中风险资产的定价公式，这些内容都是金融经济学的核心基础。在以上基础上建立的有 APT 套利定价模型、Fama-French 三因子模型以及其他的诸多理论和模型。读者可以在量化课堂的“策略与应用”栏找到基于这些模型的交易策略，也敬请期待量化课堂未来的经济学文章。
\[ \]
```
本文由JoinQuant量化课堂推出，版权归JoinQuant所有，商业转载请联系我们获得授权，非商业转载请注明出处。

文章更迭记录：
v1.1，2016-09-01，修改公式，感谢 jiziwei 指出
v1.0，2016-08-18，文章上线
```

  [1]: https://image.joinquant.com/484b0dfd9f005f9fccfdc62474ace055
  [2]: https://image.joinquant.com/645342ba3e676d398d7d19b08f05fc6c
