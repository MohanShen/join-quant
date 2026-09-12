---
title: "【量化课堂】MPT 模型的解析解（上）"
category: 经济与市场
learners: 6815
postedAt: 2017-01-19 19:24:31
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:29:55.743Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【量化课堂】MPT 模型的解析解（上）

**导语**：本篇文章将用拉格朗日乘子法来计算马科维兹的方差最小化问题。
$ $
```
作者：肖睿
编辑：宏观经济算命师

本文由JoinQuant量化课堂推出，难度为进阶（上），深度为 level-1。
```
阅读本文前需要掌握线性代数、多元微积分、[MPT 模型](https://www.joinquant.com/post/1991?f=study&m=financial)以及[拉格朗日乘子法](https://www.joinquant.com/post/3796?f=study&m=math)的基础知识。
$ $
### **前言**

量化课堂的 [MPT 模型](https://www.joinquant.com/post/1991?f=study&m=financial)文章介绍了马科维兹的现代资产配置理论 (MPT, modern portfolio theory) 的模型和理论，其中讲解了重要的有效前沿和资本市场线的重要概念，但并没有解释有效前沿的计算方法。在[拉格朗日乘子](https://www.joinquant.com/post/3796?f=study&m=math)文章中我们介绍了使用拉格朗日乘子 (Lagrange multiplier) 来解决非线性规划问题的方法，并提到了该方法可以用来解决现代资产配置理论中的优化问题，这便是本篇文章探讨的主题。

MPT 模型可以分没有无风险资产和有无风险资产两个版本，这两个版本的解决思路相似但在细节上有一些差异，故本系列文章分为上下两篇，上篇主要探讨没有无风险资产的情况，而下篇解决有无风险资产的情况。本篇为上篇。
$ $
### **回顾**
#### **MPT 模型**

在 MPT 模型中，我们假设金融市场上有风险资产 $i\in \{ 1,2, \dots, n\}$，其中的每个资产的收益率都随机变量 $r_i$ 表示，有数学期望值 $\overline {r_i} = \mathbb E[r_i]$ 以及标准差 $\sigma _i  = \sqrt{\text{Var}[r_i]}$。这些资产之所以称为风险资产，因为它们的标准差 $\sigma _i$ 都大于零。在没有无风险资产的 MPT 模型中，我们想要按照一定权重将资金配置于风险资产，如果分配于资产 $i$ 的权重是 $w_i$，那么 $\textbf w = (w_1,\dots , w_n)$ 代表整个资产组合的配置比重。注意这里必须满足 $\sum _{i=1} ^n w_i = 1$；当 $w_i<0$ 时意味着要卖空第 $i$ 种金融资产。

我们用 $r_w$ 表示按照 $w$ 配置资产得出的资产组合的收益率变量。经过计算，发现 $r_w$ 的期望值和方差分别满足以下等式
\begin{align*}
\mathbb E [r_w] & = \sum_{i=1} ^n w_i \overline{r_i}\\
\text{Var}[r_w] & = \sum_{i=1}^n \sum_{j=1}^n w_i w_j \text{Cov}(r_i, r_j).
\end{align*}

根据分散风险的方针，资产配置的一个目标是在固定预期收益的前提条件下把收益率的方差最小化，也就是对于一个固定的期望收益 $\mu$ 解决下面的最小化问题
\begin{align*}
\text{最小化} & \qquad \sum_{i=1}^n \sum_{j=1}^n w_i w_j \text{Cov}(r_i, r_j)\\
\text{满足} & \qquad \sum_{i=1}^n w_i \overline{r_i} = \mu\\
  & \qquad \sum_{i=1} ^n w_i = 1.
\end{align*}
得到一个最小的方差 $V(\mu)$，对应着标准差 $\sigma(\mu) = \sqrt{V(\mu)}$。所有的期望和最小标准差的二元组 $(\mu, \sigma(\mu))$ 组成一条曲线，叫做有效前沿 (efficient frontier)。本文将致力于解决上述的方差最小化问题，并计算出有效前沿的闭合式公式。
$ $
#### **拉格朗日乘子法**

在拉格朗日乘子的文章中，我们提到了一个重要的定理：
$ $
**定理.** 设 $n,m \in \mathbb N$。对于 $i \in \{ 1,2,\dots,m\}$，$g_i$ 和 $f$ 都是 $\mathbb R^n \to \mathbb R$ 的 $\mathcal C^1$ 函数。并且设 $c_i \in \mathbb R$。考虑规划问题
\begin{align*}
\text{最小化} & \qquad f(x)\\
\text{满足} & \qquad g_i( x)=c_i, \ \forall i=1,2,\dots, m\\
& \qquad x \in \mathbb R^n.
\end{align*}

定义函数

\[ \mathcal L(x,\lambda) = f(x) - \lambda _1(g_1(x)- c_1) - \dots - \lambda_m (g_m(x)- c_m), \]

这里 $\lambda = (\lambda_1, \lambda_2, \dots , \lambda_m) \in \mathbb R^m$。如果 $\widetilde x \in \mathbb R^n$ 是上述规划问题的极值点，那么必定存在某个 $\widetilde \lambda \in \mathbb R^m$ 满足

\[  \nabla\mathcal L (x, \lambda) = 0. \]

我们就将使用这个定理来解决 MPT 模型的方差最小化问题。
$ $

### **解决马科维兹最优化问题**
我们稍微更改原本的问题：

\begin{align*}
\text{最小化} & \qquad \frac{1}{2}\text{Var}[r_w] = \frac{1}{2} \sum_{i=1}^n \sum_{j=1}^n w_i w_j \text{Cov}(r_i, r_j)\\
\text{满足} & \qquad \sum_{i=1}^n w_i \overline{r_i} = \mu\\
  & \qquad \sum_{i=1} ^n w_i = 1.
\end{align*}

目标函数中的 $\frac{1}{2}$ 不改变问题的本质，但它可以让后边的计算过程更干净。上边的问题也可以改写成矩阵的形式

\begin{align*}
\text{最小化} &\qquad \frac{1}{2} \mathbf w ^{\mathsf T} \mathbf \Sigma \mathbf w\\
\text{满足} &\qquad \mathbf w ^{\mathsf T} \mathbf r = \mu\\
& \qquad \mathbf w ^{\mathsf T} \mathbf 1 _{n} = 1
\end{align*}

在这些符号中，

\[ \mathbf{\Sigma} = \begin{bmatrix} \text{Cov}(r_1 ,r_1) & \dots & \text{Cov}(r_1, r_n) \\ \vdots & \ddots & \vdots \\ \text{Cov}(r_n, r_1) & \dots & \text{Cov}(r_n, r_n) \end{bmatrix};\ \mathbf w = \begin{bmatrix} w_1 \\ \vdots \\ w_n \end{bmatrix}; \ \mathbf{r} = \begin{bmatrix} \overline{r_1} \\ \vdots \\ \overline{r_n} \end{bmatrix}; \ \mathbf{1}_n = \begin{bmatrix} 1 \\ \vdots \\ 1 \end{bmatrix}.\]

当然，我们知道 $\text{Cov}(r_i, r_i) = \text{Var}[r_i]$。
$ $
在解题之前我们确认这个规划问题的极小点是存在的。首先，目标函数（也就是方差）是一个凸函数：对于任何两个随机变量 $X$ 和 $Y$ 有

\begin{align*}
\text{Var}\left[\frac{1}{2}X + \frac{1}{2}Y\right] & = \frac{1}{4} \text{Var} [X] + \frac{1}{4} \text{Var}[Y] + \frac{1}{2} \text{Cov} (X,Y)\\
 & \leq \frac{1}{4} \text{Var}[X] + \frac{1}{4} \text{Var} [Y] + \frac{1}{2} \sigma_X \sigma_Y \\
 & \overset{(*)}\leq \frac{1}{2}\text{Var}[X] + \frac{1}{2} \text{Var}[Y]
\end{align*}

步骤 $(*)$ 是因为

\begin{align*}
&\frac{1}{4} \text{Var}[X] + \frac{1}{4} \text{Var} [Y] - \frac{1}{2} \sigma_X \sigma_Y = \left(\frac{1}{2} \sigma _X - \frac{1}{2} \sigma_Y \right)^2 \geq 0 \\ 
\implies &\frac{1}{4} \text{Var}[X] + \frac{1}{4} \text{Var} [Y] \geq \frac{1}{2} \sigma_X \sigma_Y
\end{align*}

在此之上，规划问题的可行集 $\Delta =\left\{ w_1, \dots, w_n \in \mathbb R: \sum _{i=1} ^n w_i \overline{r_i} = \mu , \sum_{i=1} ^n w_i = 1 \right\} $ 是由两个线性约束决定的，因此它是一个凸集。根据[数学规划简介](https://www.joinquant.com/post/3293?f=study&m=math)所述，一个凸函数在一个凸集上必定有极小点，即 $\min_{\mathbf w \in \Delta} \frac{1}{2}\text{Var} (r_{\textbf w})$ 是有解的。*以上逻辑所涉及到的理论会在以后的凸优化文章中更详细地解释。*
$ $
下面我们着手解决上述规划问题。根据拉格朗日乘子定理，我们定义函数

\[ \mathcal L(\mathbf w, \lambda _1, \lambda_2):= \sum_{i=1}^n \sum_{j=1}^n w_i w_j \text{Cov}(r_i, r_j) - \lambda_1\left(\sum_{i=1}^n w_i \overline{r_i}-\mu\right) - \lambda_2\left(\sum_{i=1}^n w_i-1\right).\]

并计算它的各个偏导，

\begin{align*}
\frac{\partial \mathcal L}{\partial w_i}&= \sum_{j=1}^n w_j \text{Cov}(r_i, r_j) - \lambda_1 r_i - \lambda_2,\ i=1,2,\dots,m\\
\frac{\partial \mathcal L}{\partial \lambda_1} & = \sum_{i=1} ^n w_i \overline{r_i} - \mu\\
\frac{\partial \mathcal L}{\partial \lambda_2} & = \sum_{i=1} ^n w_i -1.
\end{align*}

上面的第一条可以改写成矩阵的形式，表示为

\begin{align*}
\frac{\partial \mathcal L}{\partial \mathbf{w}} & = \mathbf{\Sigma} \mathbf{r} - \lambda_1 \mathbf{r} - \lambda_2 \mathbf{1}_n\\
\frac{\partial \mathcal L}{\partial \lambda_1} & = \mathbf{w}^\mathsf{T} \mathbf{r} - \mu\\
\frac{\partial \mathcal L}{\partial \lambda_2} & = \mathbf{w}^\mathsf{T} \mathbf{1}_n -1.
\end{align*}


将梯度 $\nabla \mathcal L$ 设为 $0$，即

\begin{align*}
\mathbf{0}_n & = \mathbf{\Sigma} \mathbf{w} - \lambda_1 \mathbf{r} - \lambda_2 \mathbf{1}_n & \text{(1)}\\
0 & = \mathbf{w}^\mathsf{T} \mathbf{r} - \mu & \text{(2)}\\
0 & = \mathbf{w}^\mathsf{T} \mathbf{1}_n -1 & \text{(3)}
\end{align*}

假设 $\mathbf{\Sigma}$ 是可逆的，由 (1) 可以得出 $\mathbf w$ 与 $\lambda _1$ 和 $\lambda_2$ 的关系

\[ \mathbf{w} = \lambda _1 \mathbf{\Sigma} ^{-1} \mathbf r + \lambda_2 \mathbf{\Sigma}^{-1} \mathbf{1}_n\qquad (\dagger)\]

下面还需要解出 $\lambda_1$ 和 $\lambda_2$ 根据 (2) 和 (3) 两个等式，又有

\begin{align*}
\mu = &\mathbf{w}^\mathsf{T}\mathbf r\\
1 = & \mathbf{w}^\mathsf{T}\mathbf{1}_n
\end{align*}

代入 ($\dagger$)，有

\begin{align*}
\mu & = [\lambda_1 (\mathbf{\Sigma}^{-1} \mathbf r)+ \lambda_2(\mathbf{\Sigma}^{-1} \mathbf 1_n)]^{\mathsf T}  \mathsf r = \lambda _1 \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r + \lambda _2 \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r \\
1 & = [\lambda_1 (\mathbf{\Sigma}^{-1} \mathbf r)+ \lambda_2(\mathbf{\Sigma}^{-1} \mathbf 1_n)]^{\mathsf T} \mathsf 1_n = \lambda _1 \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n + \lambda _2 \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n
\end{align*}

这里注意因为协方差矩阵 $\mathbf \Sigma$ 是对称的，根据线性代数和对称矩阵的一些基本性质，有 $(\mathbf \Sigma ^{-1})^{\mathsf T} = \mathbf \Sigma ^{-1}$.

上面的两个等式可以写为矩阵形式，即

\[ \begin{bmatrix} \mu \\ 1  \end{bmatrix} = \begin{bmatrix} \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r & \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r \\ \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n & \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n \end{bmatrix} \begin{bmatrix} \lambda_1 \\ \lambda_2 \end{bmatrix}. \]

那么，如果我们设 $a = \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r, b = \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r, c = \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n$，可以解出

\[\begin{bmatrix} \lambda _1 \\ \lambda_2\end{bmatrix} = \begin{bmatrix} a & b \\ b & c \end{bmatrix}^{-1} \begin{bmatrix} \mu \\ 1 \end{bmatrix}, \qquad (\dagger \dagger) \]

然后利用 ($\dagger$) 的等式

\[ \mathbf w = \lambda_1 \mathbf \Sigma ^{-1} \mathbf r + \lambda_2 \mathbf \Sigma^{-1} \mathbf 1_n \]

就可解出梯度函数 $\nabla \mathcal L$ 的一个零点 $\mathbf w^*$；如果矩阵 $\begin{bmatrix} a & b\\ b& c \end{bmatrix}$ 和 $\mathbf \Sigma$ 都是可逆的话，根据矩阵的列秩的性质，$\mathbf w^*$ 便是 $\nabla \mathcal L (\mathbf w, \lambda_1, \lambda_2) = 0$ 的唯一解。我们知道原规划问题是有极小点的，根据拉格朗日乘子定理那些极小点都是 $\nabla \mathcal L$ 的零点，然而如果 $\nabla \mathcal L $ 只有一个零点 $\mathbf w^*$，那么 $\mathbf w^* $ 必定是规划问题的唯一极小点。接下来我们需要确认 $\begin{bmatrix} a & b \\ b & c \end{bmatrix}$ 和 $\mathbf \Sigma$ 在什么情况下是可逆的，并且对于不可逆的情况给出解决方法。
$ $
### **两个矩阵的可逆性**
在这一节中我们将发现有两个假设可以保证矩阵 $\Sigma$ 和 $\begin{bmatrix} a & b \\ b & c\end{bmatrix}$ 的可逆性。它们是：

1. 如果任何一组风险资产都不能配置出无风险资产，那么 $\Sigma$ 是可逆的，即公式 $(\dagger)$ 成立；
2. 如果不是所有风险资产的收益率期望都是相等的，那么 $\begin{bmatrix} a& b \\ b & c \end{bmatrix}$ 是可逆的，即公式 $(\dagger \dagger)$ 成立。

接下来将展示上述结论的推导，这需要使用正定矩阵和半正定矩阵的相关理论。在[线搜索方法](https://www.joinquant.com/post/3361?f=study&m=math)的文章中我们介绍过正定矩阵和半正定矩阵的定义，这里重温一下：
$ $
**定义.** 设 $A \in \mathbb R^{n \times n}$ 是一个对称矩阵，即 $A^{\mathsf T} = A$。如果对于任何一个 $x \in \mathbb R^n$ 都有 $x ^{\mathsf T} A x \geq 0$，那么 $A$ 是一个*半正定矩阵 (positive semidefinite matrix)*。如果对于任何一个 $x \in \mathbb R^n \backslash \{\mathbf 0_n \}$ 都有 $x^{\mathsf T} A x >0$，那么 $A$ 是一个*正定矩阵 (positive definite matrix)*。
$ $
首先我们考虑协方差矩阵 $\mathbf \Sigma$。根据概率论的基础理论，任何的协方差矩阵都是一个半正定矩阵。我们需要用到线性代数的理论中关于半正定矩阵可逆性的命题：
$ $
**定理.** 设 $A \in \mathbb R^{n \times n}$ 是一个半正定矩阵，那么下面两个陈述是等价的：
1. $A^{-1} $ 存在；
2. 对于每一个 $ x \in \mathbb R^n \backslash \{\mathbf 0_n \}$，都有 $x^\mathsf{T} A x > 0$。

$ $
假设半正定矩阵 $\mathbf \Sigma$ 不是可逆的，根据以上定理，可以找出某个非零的 $\mathbf w \in \mathbb R^n$ 以满足 $\mathbf w ^{\mathsf T} \mathbf \Sigma \mathbf w=0$。那么有
\begin{align*}
0 &= \mathbf w ^\mathsf{T} \mathbf \Sigma \mathbf w\\
& = \sum_{i=1}^n \sum_{j=1} ^n w_i w_j \text{Cov}(r_i, r_j)\\
& = \text{Var}\left[\sum_{i=1} ^n w_i r_i\right].
\end{align*} 
那么，按照 $w_1, \dots, w_n$ 的比例配置 $(r_1, \dots, r_n)$，会得到一个零方差的随机变量，对应着一个无风险的投资组合。这种情况可以在下一篇的有无风险资产的 MPT 模型中解决；本篇中不妨假设无风险资产不能由风险资产配置得来，这样 $\Sigma$ 必定是可逆的。
$ $
接下来我们需要保证矩阵 $\begin{bmatrix}a & b \\ b & c \end{bmatrix} = \begin{bmatrix} \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r & \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r \\ \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n & \mathbf 1_n^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n \end{bmatrix}$ 是可逆的。根据行列式的定理，只需要证明 $b^2 - ac \ne 0$ 即可。

首先，我们需要假设 $a\mathbf 1_n - b\mathbf r \ne \mathbf 0_n$。这是一个合理的假设，因为如果上述的差等于零，那么所有的 $\overline{r_i}$ 都是相等的，也就是说所有的风险资产的收益率都是相同的，很显然这在现实中是几乎不可能发生的，这种情况也会导致有效前沿变成一条横向直线而不是一条曲线。

根据前一段的结论，我们知道 $\mathbf \Sigma$ 是一个正定矩阵，并且根据下面的定理，
$ $
**定理.** 如果 $A \in \mathbb R^{n \times n}$ 是一个正定矩阵，那么 $A^{-1}$ 也是一个正定矩阵。
$ $
可以得知 $\mathbf \Sigma ^{-1}$ 也是正定矩阵。

那么根据正定矩阵的性质和 $a \mathbf 1_n - b \mathbf r \ne \mathbf 0_n$ 的性质，有

\begin{align*}
0 & < (a \mathbf 1_n - b \mathbf r)^{\mathsf T} \mathbf \Sigma^{-1} (a \mathbf 1_n - b \mathbf r)\\
 & = a^{2} \mathbf 1_n ^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf 1_n - ab \mathbf 1_n \mathbf \Sigma ^{-1} \mathbf r - ba \mathbf r \mathbf \Sigma ^{-1} \mathbf 1_n + b^2 \mathbf r \mathbf \Sigma ^{-1} \mathbf r\\
 & = a^2c - ab^2 - ab^2 + ab^2\\
 & = a(ac-b^2).
\end{align*}

由此可见 $ac-b^2 \ne 0$，得知 $\begin{bmatrix} a & b \\ b & c \end{bmatrix}$ 是可逆的。
$ $

###**有效前沿和资本市场线**
#### **有效前沿**

在马科维兹优化问题中，给定每一个期望收益率 $\mu$ 都有一个对应的最小标准差 $\sigma (\mu)$，所有这些 $(\mu ,  \sigma(\mu))$ 的二元组构成了一条曲线，叫做有效前沿。接下来我们将计算出这条曲线的公式。 

根据第二节中的拉格朗日乘子方法，标准差最小的配置权重向量满足

\[ \mathbf w = \lambda _1 \mathbf \Sigma ^{-1} \mathbf r + \lambda _2 \mathbf \Sigma ^{-1} \mathbf 1_n \]

于是有

\begin{align*}
\text{Var} [r_{\mathbf w}] &= \mathbf w ^{\mathsf T} \mathbf \Sigma \mathbf w \\
& = (\lambda_1 \mathbf r^{\mathsf T} \mathbf \Sigma ^{-1} + \lambda_2 \mathbf 1_n^{\mathsf T} \mathbf \Sigma ^{-1}) \mathbf \Sigma (\lambda_1 \mathbf \Sigma ^{-1} \mathbf r + \lambda_2 \mathbf \Sigma ^{-1} \mathbf 1_n)\\
& = \lambda_1^{2} \mathbf r^\mathsf{T} \mathbf \Sigma ^{-1} \mathbf r + 2\lambda_1 \lambda_2 \mathbf 1_n ^{\mathsf T} \mathbf \Sigma ^{-1} \mathbf r + \lambda_2 ^2 \mathbf 1 _n ^{\mathsf T} \mathbf \Sigma \mathbf 1 _n\\
& =  \lambda _1 ^2 a + 2\lambda_1 \lambda_2 b + \lambda_2 ^2 c \\
& = \begin{bmatrix} \lambda_1  & \lambda_2 \end{bmatrix} \begin{bmatrix} a & b \\ b & c \end{bmatrix} \begin{bmatrix} \lambda_1 \\ \lambda_2 \end{bmatrix}
\end{align*}

再代入

\[ \begin{bmatrix} \lambda_1 \\ \lambda_2 \end{bmatrix} = \begin{bmatrix} a & b \\ b & c \end{bmatrix} ^{-1}  \begin{bmatrix} \mu \\ 1 \end{bmatrix} \]

的结论，有

\begin{align*}
\text{Var} [r_\mathbf{w}] & = \begin{bmatrix} \mu & 1 \end{bmatrix}  \begin{bmatrix} a & b \\ b & c \end{bmatrix} ^{-1} \begin{bmatrix} a & b \\ b & c \end{bmatrix}  \begin{bmatrix} a & b \\ b & c \end{bmatrix} ^{-1} \begin{bmatrix} \mu \\ 1 \end{bmatrix}\\
& = \begin{bmatrix} \mu & 1 \end{bmatrix} \begin{bmatrix} a & b \\ b & c \end{bmatrix} ^{-1} \begin{bmatrix} \mu \\ 1 \end{bmatrix}\\
& = \frac{1}{ac - b^2} \begin{bmatrix} \mu & 1 \end{bmatrix} \begin{bmatrix} c & -b \\ -b & a \end{bmatrix} \begin{bmatrix} \mu \\ 1 \end{bmatrix}\\
& = \frac{1}{ac - b^2}(c\mu^2 - 2b\mu + a) 
\end{align*}

那么得出有效前沿的公式

\[ \sigma(\mu) = \sqrt{\frac{1}{ac-b^2} (c\mu^2 - 2b\mu + a)}. \]
$ $
#### **最小风险组合**

下面我们计算有效前沿上风险最小的组合。为了寻找函数 $\sigma (\mu)$ 的极小点，我们取其导数并将导数设为 $0$，

\[ 0 = \frac{d\sigma }{d \mu} = \frac{1}{2 \sigma(\mu)} (2c\mu - 2b). \]

由于 $\sigma(\mu)>0$，那么上面等式成立当且仅当 $c\mu = b$，也就是说最小的标准差存对应着收益期望 $\mu = b/c$，将这个数代进马科维兹优化问题就可以算出最小方差组合的权重了。
$ $
### **举例的时间到了**
为了举例的简便性，我们只选择五个风险资产进行计算。这五个资产是从沪深 300 成分股中随机选出的五支股票，使用两年的日收益率数据来计算收益率和标准差和协方差。这五支股票的日平均收益率和日收益率标准差分别是

\[ \mathbf r = \begin{bmatrix}1.063\\2.834\\4.133\\2.326\\2.788 \end{bmatrix}\cdot 10^{-3};\ 
\mathbf{\sigma} = \begin{bmatrix} 2.490\\2.700\\3.379\\3.511\\3.607 \end{bmatrix} \cdot 10^{-2}.\]

这些数据放到标准差-均值坐标图上如下图的蓝色三角所示，图中的粉点是同期其他的沪深 300 成分股作为参考对比。

![five.png][1]

并且，我们计算这五支股票收益率的协方差矩阵为

\[ \mathbf \Sigma = \begin{bmatrix} 6.202 & 4.047 & 1.069 & 1.843 & 3.826 \\
4.047 & 7.292 & 0.815 & 1.618 & 3.458 \\
1.069 & 0.815 & 11.428 & 2.028 & 4.055 \\
1.843 & 1.618 & 2.028 & 12.330 & 5.592 \\
3.826 & 3.458 & 4.055 & 5.592 & 13.011 \end{bmatrix} \cdot 10^{-4} \]

使用 Numpy 计算 $a,b,c$ 的值：

\begin{align*} 
a & = \mathbf r ^{\mathsf T} \mathbf \Sigma ^{-1} \mathbf r = 0.02651\\
b & = \mathbf r ^{\mathsf T} \mathbf \Sigma ^{-1} \mathbf 1_5 = 6.724 \\
c & = \mathbf 1_5 ^{\mathsf T} \mathbf \Sigma^{-1} \mathbf 1_5 = 2724
\end{align*}

那么计算出有效前沿曲线的公式为

\[ \sigma (\mu) = \sqrt{ \frac{1}{ac-b^2} (c \mu^2-2b\mu +a)} = \sqrt{99.41\mu^2 - 0.4865 \mu + 9.593\cdot 10^{-4} }, \]

在 $(\sigma, \mu)$ 坐标图上的曲线如下

![frontier.png][2]

同时，我们也可以通过穷举列出一些加和为 $1$ 的权重向量，让后计算按照这些权重配置出的资产组合的标准差和收益预期，并将这些数据也画在坐标图上，得到下面的图。图中的蓝线是之前算出的有效前沿，圆圈是穷举出的组合，五个蓝色三角形对应的是五个原生股票。

![frontier_with_samples.png][3]

可以看出，所有的组合都在有效前沿的右边，并且标准差最小的组合正好就在有效前沿上。
$ $
下面我们想计算整个有效前沿上风险最小的投资组合。根据之前的分析，我们知道最小标准差组合的收益期望是 

\[ \mu_{\text{min}} = \frac{b}{c} = 2.447 \cdot 10 ^{-3}. \]

那么建立马科维兹优化问题

\begin{align*}
\text{最小化} & \qquad \frac{1}{2}\mathbf w^{\mathsf T} \mathbf \Sigma \mathbf w\\
\text{满足} & \qquad \mathbf w ^{\mathsf T} \mathbf r = \mu_{\text{min}}\\
&\qquad \mathbf w ^{\mathsf T} \mathbf 1_5 = 1.
\end{align*}

我们用公式 ($\dagger\dagger$) 先计算出拉格朗日乘子的值

\begin{align*}
\begin{bmatrix} \lambda_1 \\ \lambda_2 \end{bmatrix} & = \begin{bmatrix} a & b \\ b & c \end{bmatrix} ^{-1} \begin{bmatrix} \mu_\text{min} \\ 1 \end{bmatrix}\\
 & =  \begin{bmatrix} 0.02651 & 6.724 \\ 6.724 & 2724 \end{bmatrix}^{-1} \begin{bmatrix} 0.002447 \\ 1 \end{bmatrix}\\
 & = \begin{bmatrix} -2.776 \cdot 10^{-17} \\ 3.640 \cdot 10^{-4} \end{bmatrix}
\end{align*}

然后再使用公式 ($\dagger$) 计算出权重向量

\begin{align*}
\mathbf w_{\text{min}} & = \lambda _1 \mathbf \Sigma ^{-1} \mathbf r + \lambda_2 \mathbf \Sigma ^{-1} \mathbf 1_5\\
& = -2.776 \times 10^{-17} \cdot \begin{bmatrix} 6.202 & 4.047 & 1.069 & 1.843 & 3.826 \\
4.047 & 7.292 & 0.815 & 1.618 & 3.458 \\
1.069 & 0.815 & 11.428 & 2.028 & 4.055 \\
1.843 & 1.618 & 2.028 & 12.330 & 5.592 \\
3.826 & 3.458 & 4.055 & 5.592 & 13.011 \end{bmatrix} ^{-1} \times 10^{4} \cdot \begin{bmatrix}1.063\\2.834\\4.133\\2.326\\2.788 \end{bmatrix}\times 10^{-3}\\
 & \qquad +3.640 \times 10^{-4} \cdot \begin{bmatrix} 6.202 & 4.047 & 1.069 & 1.843 & 3.826 \\
4.047 & 7.292 & 0.815 & 1.618 & 3.458 \\
1.069 & 0.815 & 11.428 & 2.028 & 4.055 \\
1.843 & 1.618 & 2.028 & 12.330 & 5.592 \\
3.826 & 3.458 & 4.055 & 5.592 & 13.011 \end{bmatrix} ^{-1} \times 10^{4} \cdot \begin{bmatrix} 1 \\ 1 \\ 1 \\ 1 \\ 1 \end{bmatrix}\\
& = \begin{bmatrix}0.3499 \\ 0.2594 \\ 0.2523 \\ 0.1914 \\ -0.05298 \end{bmatrix}
\end{align*}

这个向量代表着五支股票配置的权重比例，其中第五支股票的权重是负数，说明需要做空。

接下来计算这个组合的期望收益和标准差，有

\begin{align*}
\overline{r_{\mathbf w_{\text{min}}}} & = \mathbf w_{\text{min}}^{\mathsf T} \mathbf r\\
& = \begin{bmatrix}0.3499 & 0.2594 & 0.2523 & 0.1914 & -0.05298 \end{bmatrix} \begin{bmatrix}1.063\\2.834\\4.133\\2.326\\2.788 \end{bmatrix}\times 10^{-3}\\
& = 2.447 \times 10^{-3}
\end{align*}

以及

\begin{align*}
\sigma _{\mathbf w_{\text{min}}} & = \sqrt{\mathbf w_{\text{min}} ^\mathsf{T} \mathbf \Sigma \mathbf w _{\text{min}}}\\
& =\sqrt{ \begin{bmatrix}0.3499 \\ 0.2594 \\ 0.2523 \\ 0.1914 \\ -0.05298 \end{bmatrix}^{\mathsf T} \cdot \begin{bmatrix} 6.202 & 4.047 & 1.069 & 1.843 & 3.826 \\
4.047 & 7.292 & 0.815 & 1.618 & 3.458 \\
1.069 & 0.815 & 11.428 & 2.028 & 4.055 \\
1.843 & 1.618 & 2.028 & 12.330 & 5.592 \\
3.826 & 3.458 & 4.055 & 5.592 & 13.011 \end{bmatrix}\times 10^{-4} \cdot \begin{bmatrix}0.3499 \\ 0.2594 \\ 0.2523 \\ 0.1914 \\ -0.05298 \end{bmatrix}} \\
& = 1.908 \times 10^{-2}
\end{align*}

将 $(1.908\times 10^{-2} , 2.477 \times 10^{-3})$ 的点画在坐标图上，是下图中的红色猩猩，

![frontier_with_min.png][4]

它的确是在整个有效前沿曲线的最顶端，这就对了。
$ $
### **结语**
本文使用拉格朗日乘子法解决了没有无风险资产的 MPT 模型的优化问题，算出了最小方差组合以及有效前沿还有的闭合式公式，以此进行计算要比穷举和使用蒙特卡罗法更快也更准确。在本系列的下一篇文章中，我们将使用拉格朗日乘子法来解决有无风险资产情况，计算出资本市场线的闭合公式，分析它和有效前沿的关系，并得到市场组合的计算方法。

\[ \]
```
本文由JoinQuant量化课堂推出，版权归JoinQuant所有，商业转载清联系我们获得授权，非商业转载请注明出处。

v1.0，2017-01-19，文章上线
```

  [1]: https://image.joinquant.com/cb634802e426d6eed0d83735f0487567
  [2]: https://image.joinquant.com/3f86cbb111113826a33a744c7067d8c9
  [3]: https://image.joinquant.com/8cbd3f809c90a6e639567bce82cc7664
  [4]: https://image.joinquant.com/b0825ffd3a4da14fd70db4e4a43dc1d5
