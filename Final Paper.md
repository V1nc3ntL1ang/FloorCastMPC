# Load-Aware Elevator Scheduling Optimization: Integrated Models for Time and Energy Optimization

## Group Members

| Name   | Student ID   | Major        | Class             |
| ------ | ------------ | ------------ | ----------------- |
| 梁乐天 | 202330420951 | Data Science | Grade 23, Class 2 |
| 林贝泽 | 202330381001 | Data Science | Grade 23, Class 2 |
| 吕铭浩 | 202264700058 | Data Science | Grade 22, Class 2 |

## Abstract

We investigate load-aware scheduling and energy optimization for a multi-elevator system that serves mixed passenger–goods traffic. Our framework couples stochastic demand generation, kinematic profiling, temporal door operations, and load-sensitive energy estimation. Passenger and freight masses follow truncated normal distributions, requests arrive through non-homogeneous Poisson processes that capture peak and off-peak periods, and elevator queues are processed with capacity-aware first-come–first-served logic. Travel time and energy models incorporate triangular and trapezoidal motion regimes whose velocity and acceleration envelopes decay with payload, while congestion-induced dwell extensions respond to dynamic car loading. The resulting objective minimizes a weighted sum of aggregate service time and traction energy....

**Keywords**:Elevator scheduling, Energy optimization, Temporal modeling

## Introduction

**Background**
Elevator group control scheduling (EGCS) plays a vital role in high-rise buildings, where vertical transportation efficiency directly affects passenger satisfaction and overall building performance. As the number of floors and passenger demand increase, elevators are required to coordinate in real time to deliver safe, fast, and energy-efficient services. Traditional one-size-fits-all elevator dispatching strategies are insufficient in such complex environments, making optimization-based methods increasingly necessary.

**Problem Statement**
The scheduling problem is inherently multi-objective and constrained. On the one hand, passengers expect reduced waiting and travel times; on the other hand, building managers are concerned with energy efficiency and operational costs. Moreover, the system must deal with varying traffic patterns—such as morning down-peak and evening up-peak while respecting constraints like elevator capacity, safety standards, and fairness across passengers. These challenges make EGCS a complex combinatorial optimization problem.

**Research Objective**
This study aims to develop an optimization framework based on MPC (Model Predictive Control) for elevator scheduling, balancing the conflicting goals of passenger experience and energy efficiency....

### Literature Review

### Contribution of this Article

## Methodology

### Model Formation

#### Problem Description & Assumptions

The elevator dispatching problem aims to minimize passenger waiting time, riding time, and system energy consumption while ensuring service quality and safety. In a multi-floor building, multiple elevators operate simultaneously to serve passenger requests that arise dynamically over time. Each request specifies an origin floor and a destination floor. The control system must decide which elevator responds to which request and in what sequence, subject to mechanical and safety constraints. The problem is inherently multi-objective: improving service time often increases energy consumption, while reducing energy use may prolong waiting time.

---

##### Load-related Assumptions

-   **Entity definition.**  
    Each boarding entity is treated as an indivisible unit consisting of a passenger and any carried goods. This abstraction avoids double-counting and ensures that all boarding and alighting operations are based on indivisible loads rather than separating persons from their belongings.

-   **Individual load distribution.**  
    The random entity weight $X$ follows a **bounded uniform law** whose support depends on the traffic segment:

    $$
    X \sim
    \begin{cases}
    \mathcal U\big[w_{\min}^{\text{off}}, w_{\max}^{\text{off}}\big], & t \in T_{\text{off-peak}}, \\
    \mathcal U\big[w_{\min}^{\text{peak}}, w_{\max}^{\text{peak}}\big], & t \in T_{\text{peak}}.
    \end{cases}
    $$

    Segment-specific bounds $(w_{\min}^{\text{off}}, w_{\max}^{\text{off}})$ and $(w_{\min}^{\text{peak}}, w_{\max}^{\text{peak}})$ are configurable to reflect lighter daytime goods traffic versus heavier peak-hour flows.

-   **Aggregate boarding/alighting load.**
    If $n_f^{(u)}$ entities board at floor $f$, the total boarding weight is

    $$
    W_f^{(u)}=\sum_{i=1}^{n_f^{(u)}} X_i,\qquad X_i \stackrel{iid}{\sim} X,
    $$

    and by the central limit theorem,

    $$
    W_f^{(u)} \approx \mathcal N\!\Big(n_f^{(u)}\,\mathbb E[X],\; n_f^{(u)}\,\operatorname{Var}(X)\Big).
    $$

    Similarly, the alighting load $W_f^{(d)}$ can be obtained.

-   **Stochastic number of entities.**  
    Each segment $T_j$ contributes a predetermined number of requests according to its weight in the daily schedule. Aggregating entity weights within a segment therefore yields deterministic first moments, e.g.

    $$
    \mathbb E[W_f^{(u)}] = n_{f,j}^{(u)}\,\mathbb E[X \mid T_j],
    \quad
    \operatorname{Var}(W_f^{(u)}) = n_{f,j}^{(u)}\,\operatorname{Var}(X \mid T_j),
    $$

    where $n_{f,j}^{(u)}$ is the count of boarding entities allocated to floor $f$ in segment $T_j$.

-   **Capacity constraint.**  
    For elevator $k$, the instantaneous load at time $t$ is

    $$
    L_k(t)\;:=\;\sum_{f} W_{k,f}^{(u)}(t)\;-\;\sum_{f} W_{k,f}^{(d)}(t),
    \qquad
    L_k(t)\;\le\;L*{\max},\ \forall t,\ \forall k\in\mathcal K.
    $$

    If boarding would exceed Lmax, the excess entities remain in the queue and are deferred to subsequent service cycles.

---

##### Temporal Assumptions

-   **Non-uniform passenger flow.**  
    Passenger arrivals vary across the day, exhibiting peak (e.g., morning and evening rush hours) and off-peak periods (e.g., mid-day, late night).

-   **Segment-wise sampling.**  
    For each period $p \in \{\text{peak},\text{off}\}$ we first allocate a fixed number of requests using the segment weights, then sample their arrival times from a continuous distribution: **uniform** over the interval during off-peak periods and **truncated Gaussian** centered on the rush-hour mean during peak periods.

-   **Time-of-day segmentation.**  
    The day is divided into segments $T=\{T_1, T_2, \ldots, T_m\}$, with piecewise-constant arrival rates:

    $$
    \lambda_f(t) = \lambda_f^{(j)}, \quad t \in T_j.
    $$

-   **Event-driven time representation.**  
    We adopt an **event-driven (continuous-time)** representation. All timestamps $T_c^{\mathrm{arrival}},\; T_c^{\mathrm{pickup}},\; T_c^{\mathrm{dropoff}}$ are real-valued and measured in seconds; no discrete time grid is used.

---

##### Floor-traffic Assumptions

-   **Asymmetric floor demand.** Ground floor/lobby acts as a major source/sink.
-   **Origin–destination distribution.**
    $$
    P(\text{origin}=f)=p_f^{(o)},\ P(\text{destination}=f)=p_f^{(d)},
    $$
    with
    $$
    \sum_{f \in \mathcal{F}}p_f^{(o)}=\sum_{f \in \mathcal{F}}p_f^{(d)}=1.
    $$
-   **Time-dependent floor traffic.**  
    Distributions may vary by segment $T_j$.

---

##### Queueing and Service Assumptions

-   **Queueing discipline.**  
    At each floor $f$, entities form a **first come first served (FCFS)** queue across elevators:

    -   if two requests arrive at the same floor $f$ with $T_{c_1}^{\mathrm{arrival}} < T_{c_2}^{\mathrm{arrival}}$, then $T_{c_1}^{\mathrm{pickup}} \le T_{c_2}^{\mathrm{pickup}}$.
    -   Each entity is indivisible: it either boards fully or waits; splitting is not allowed.

-   **Service capacity constraint.**  
    Boarding at time $t$ for elevator $k$ is permitted only if $L_k(t) + W_f^{(u)} \le L_{\max}$.

-   **Event-driven queue evolution.**  
    Let $\{t_i\}$ be the event times at floor $f$, including **arrivals** of new entities and **boarding completions**. The queue evolves as

    $$
    Q_f(t_i^+) \;=\; Q_f(t_i^-) \;\cup\; \mathrm{arrivals}(t_i) \;-\; \mathrm{boarded}(t_i),
    $$

    where $t_i^-$ and $t_i^+$ denote instants immediately before and after the event $t_i$.

    -   $\mathrm{arrivals}(t_i)$: set of entities that arrive at floor $f$ at event time $t_i$.
    -   $\mathrm{boarded}(t_i)$: set of entities that successfully board at $t_i$ given available capacity.

---

##### Other Assumptions

1. **Building layout.**  
   Floors are equally spaced with height $h$.

2. **Elevator capacity.**  
   Each elevator has maximum admissible load $L_{\max}$.

3. **Kinematic profile.**  
   Motion follows triangular or trapezoidal velocity profiles determined by load-dependent $V_{\max,\mathrm{dir}}(L)$ and $a_{\mathrm{dir}}^{\text{acc/dec}}(L)$.

4. **Service (holding) time.**  
   The only stop-time component is the **holding time**, which depends on boarding and alighting mass at that floor. Door opening/closing and leveling are ignored. At the destination floor, passengers are assumed to **leave immediately** upon arrival, without additional holding time.

5. **Service rule under low demand.**  
   In off-peak hours, cars may depart with partial loads.

6. **Energy model.**  
   Energy consists of a base auxiliary component and motion energy with no regeneration.

7. **Homogeneity of elevators.**  
   Unless stated otherwise, all elevators are **homogeneous** and share the same kinematic parameters $V_{\max,\mathrm{dir}}(\cdot)$ and $a_{\mathrm{dir}}^{m}(\cdot)$.

---

#### Model Design

##### Sets

-   $\mathcal{F}$: set of floors, indexed by $f$
-   $\mathcal{K}$: set of elevators, indexed by $k$
-   $\mathcal{C}$: set of service requests (calls), indexed by $c$. Each request is
    $$
    c = (o_c, d_c, L_c, T_c^{\text{arrival}}),
    $$
    where
    -   $o_c,d_c\in\mathcal F$ are origin and destination floors,
    -   $L_c$ is entity load, and
    -   $T_c^{\text{arrival}}$ is arrival time at floor $o_c$.
-   $\mathcal{D}:=\{\uparrow,\downarrow\}$: set of travel directions
-   $\mathcal{M}:=\{\text{acc},\text{dec}\}$: motion modes (acceleration, deceleration)

---

##### Kinematics Model

**Maximum speed (general form)**  
For direction $ \mathrm{dir}\in\mathcal D $ and load $ L\in[0,L_{\text{max}}] $,

$$
V_{\text{max},\mathrm{dir}}(L)
= V_{\text{max},\mathrm{dir}}(L_{\text{max}})
+\bigl( V_{\text{max},\mathrm{dir}}(0)-V_{\text{max},\mathrm{dir}}(L_{\text{max}}) \bigr)
\, e^{-\rho_{\mathrm{dir}}\, L / L_{\text{max}} } .
$$

where

-   $L_{\text{max}}$ : maximum payload of the lift,
-   $V_{\text{max},\mathrm{dir}}(0)$ : maximum speed at no load ($L = 0$, maximum value),
-   $V_{\text{max},\mathrm{dir}}(L_{\text{max}})$ : maximum speed at full load ($L = L_{\text{max}}$, minimum value),
-   $\rho_{\mathrm{dir}} \gt 0$ : shape parameter controlling how fast the value decays with load.

**Acceleration and deceleration**  
For $ \mathrm{dir}\in\mathcal D$, $ m\in\mathcal M $,

$$
a_{\mathrm{dir}}^{m}(L)
= a_{\mathrm{dir}}^{m}(L_{\text{max}})
+\bigl( a_{\mathrm{dir}}^{m}(0)-a_{\mathrm{dir}}^{m}(L_{\text{max}}) \bigr)
\, e^{-\rho_{\mathrm{dir}}^{m}\, L / L_{\text{max}} } .
$$

where

-   $a_{\mathrm{dir}}^{m}(0)$ : acceleration (if $m=\text{acc}$) or deceleration (if $m=\text{dec}$) at no load $L=0$, representing the **upper bound** of elevator performance,
-   $a_{\mathrm{dir}}^{m}(L_{\text{max}})$ : acceleration/deceleration at full load $L=L_{\text{max}}$, representing the **minimum achievable** performance,
-   $\rho_{\mathrm{dir}}^{m} \gt 0$ : shape parameter controlling how quickly acceleration/deceleration decays as the load increases.

**Segment-specific direction and load**

For a served path segment $(f_{j} \to f_{j+1})$ by elevator $k$, define the distance $H_{j} := |f_{j+1}-f_{j}|\,h$, direction $\mathrm{dir}_j\in\mathcal D$, and the **segment load** $L_{k,j}$ (realized after holding at $f_{j}$). Then

$$
v_{\text{peak},j}^{\ast}=\sqrt{ \frac{ 2 H_{j}\, a_{\mathrm{dir}_j}^{\text{acc}}(L_{k,j})\, a_{\mathrm{dir}_j}^{\text{dec}}(L_{k,j}) }
{ a_{\mathrm{dir}_j}^{\text{acc}}(L_{k,j}) + a_{\mathrm{dir}_j}^{\text{dec}}(L_{k,j}) } } .
$$

If $v_{\text{peak},j}^{\ast} \le V_{\text{max},\mathrm{dir}_{j}}(L_{k,j})$, the profile is **triangular**; otherwise **trapezoidal**, with distances/times computed using $(L_{k,j}, \mathrm{dir}_{j}, H_{j})$.

**Kinematic feasibility**

For each segment $j$,

$$
0 \le v_{k,j}(t) \le V_{\text{max},\mathrm{dir}_j}(L_{k,j}), \qquad
|a_{k,j}(t)| \le \max\!\bigl\{ a_{\mathrm{dir}_j}^{\text{acc}}(L_{k,j}), \; a_{\mathrm{dir}_j}^{\text{dec}}(L_{k,j}) \bigr\}.
$$

---

##### Temporal Model

**Holding time (piecewise congestion):**

The holding/boarding time at floor $f$ with boarding weight $W_f^{(u)}$ and alighting weight $W_f^{(d)}$ is defined as:

$$
t_{\text{hold}}\!\left(W_f^{(u)}, W_f^{(d)}\right) =
\begin{cases}
\gamma_0 + \eta_1 \big(W_f^{(u)} + W_f^{(d)}\big), & W_f^{(u)} + W_f^{(d)} \le \Theta, \\[6pt]
\gamma_0 + \eta_1 \Theta + \eta_2 \big[ (W_f^{(u)} + W_f^{(d)}) - \Theta \big], & W_f^{(u)} + W_f^{(d)} > \Theta .
\end{cases}
$$

where

-   $\gamma_0$: base time (minimum reaction after door open),
-   $\eta_1$: boarding/alighting efficiency in the **normal range**,
-   $\eta_2$: efficiency in the **congested range** ($\eta_2 > \eta_1$),
-   $\Theta$: threshold load (kg) beyond which congestion effects appear.

**Overall travel time model:**  
For segment $(f_j \!\to f_{j+1})$ with $H_j$, $(L_{k,j},\mathrm{dir}_j)$, the triangular/trapezoidal formulas determine $t_{\text{acc},j}$, $t*{\text{const},j}$, $t*{\text{dec},j}$.  
The **motion-only** travel time is

$$
\tau_{f_j \to f_{j+1}}
:= t_{\text{acc},j}+t_{\text{const},j}+t_{\text{dec},j}.
$$

For a realized stop sequence $\text{Path}(c): f_0=o_c,\dots,f_m=d_c$,

$$
\tau_{o_c \to d_c}
:= \sum_{\ell=0}^{m-1}\tau_{f_\ell \to f_{\ell+1}}
\quad \text{(motion only)}.
$$

**Overall temporal cost (per call):**  
The total service time for $c=(o_c,d_c,L_c,T_c^{\text{arrival}})$ is

$$
T_c^{\text{total}}=\underbrace{\big(T_c^{\text{pickup}}-T_c^{\text{arrival}}\big)\;+\;t_{\mathrm{hold}}\!\big(W_{o_c}^{(u)},W_{o_c}^{(d)}\big)}_{\text{waiting at origin (incl.\ origin holding)}}
\;+\;
\underbrace{\tau_{o_c \to d_c}}_{\text{motion}}
\;+\;
\underbrace{\sum_{j=1}^{m-1} t_{\mathrm{hold}}\!\big(W_{f_j}^{(u)},W_{f_j}^{(d)}\big)}_{\text{intermediate holdings only}}.
$$

Dropoff is instantaneous at $d_c$ per assumption.

##### Energy Model

Assume a segment with direction $\mathrm{dir}_j$, load $L_{k,j}$, and distances $d_{\text{acc}}, d_{\text{const}}, d_{\text{dec}}$. Define:

-   Counterweight mass: $M_{\mathrm{bal}}$
-   Car mass: $M_{\mathrm{cab}}$
-   Effective mass difference: $\Delta M := (M_{\mathrm{cab}} + L_{k,j}) - M_{\mathrm{bal}}$
-   Direction sign: $s_{\mathrm{dir}_j} = +1$ (up), $-1$ (down)
-   Equivalent moving mass: $M_{\mathrm{eq}}(L) = M_0 + \gamma L$
-   Frictional/drag energy per meter: $e_{\mathrm{fric}}$ (J/m)
-   Motor efficiency: $\eta_{\mathrm{mot}} \in (0,1]$
-   Gravitational acceleration: $g := 9.81\ \mathrm{m/s^2}$

**Segment-wise motion energy (positive work only)**  
Let $v_{\text{peak}}$ be the segment peak speed. Then

$$
\begin{aligned}
E_{\text{acc}} &=
\frac{\bigl[\tfrac12 M_{\mathrm{eq}}(L_{k,j})\,v_{\text{peak}}^2
+s_{\mathrm{dir}_j}\,g\,\Delta M\,d_{\text{acc}}
+e_{\mathrm{fric}}\,d_{\text{acc}}\bigr]_{+}}{\eta_{\mathrm{mot}}} \\[6pt]
E_{\text{const}} &=
\frac{\bigl[s_{\mathrm{dir}_j}\,g\,\Delta M\,d_{\text{const}}
+e_{\mathrm{fric}}\,d_{\text{const}}\bigr]_{+}}{\eta_{\mathrm{mot}}} \\[6pt]
E_{\text{dec}} &=
\frac{\bigl[-\tfrac12 M_{\mathrm{eq}}(L_{k,j})\,v_{\text{peak}}^2
+s_{\mathrm{dir}_j}\,g\,\Delta M\,d_{\text{dec}}
+e_{\mathrm{fric}}\,d_{\text{dec}}\bigr]_{+}}{\eta_{\mathrm{mot}}}
\end{aligned}
$$

Only the positive part contributes; negative work is dissipated (no regeneration).

**Total energy (including auxiliary systems)**  
Let the planning horizon be $[0,T_{\mathrm{hor}}]$. Base energy:

$$
E_{\mathrm{base}} := \sum_{k \in \mathcal K}\ \int_{0}^{T_{\mathrm{hor}}} P_{\mathrm{base}}\,\mathrm{d}t
= |\mathcal K|\,P_{\mathrm{base}}\,T_{\mathrm{hor}}.
$$

Motion energy over all segments:

$$
E_{\mathrm{move}} := \sum_{k \in \mathcal K}\ \sum_{\text{segments } j \text{ of } k}\
\Big(E_{\text{acc},k,j} + E_{\text{const},k,j} + E_{\text{dec},k,j}\Big).
$$

Total:

$$
E_{\mathrm{total}} := E_{\mathrm{base}} + E_{\mathrm{move}}.
$$

##### Decision Variables

-   $x_{k,c} \in \{0,1\}$: whether elevator $k$ serves request $c$.
-   $u_{c_1,c_2}^k \in \{0,1\}$: ordering variable, equals 1 if $c_1$ is served before $c_2$ by elevator $k$.
-   $T_c^{\text{arrival}},\; T_c^{\text{pickup}},\; T_c^{\text{dropoff}}$: arrival, pickup, and dropoff timestamps.
-   $\tau_{A \to B}^k$: motion-only travel time of elevator $k$ between floors $A,B \in \mathcal F$.
-   $L_k(t)$: instantaneous load of elevator $k$ at time $t$.
-   $Q_f(t)$: queue at floor $f$ at time $t$ (event-driven updates).

---

##### Objective Function

We minimize a weighted sum of total time and energy using a **single time weight** $w_t$:

##### Objective Function

**Time cost (total across requests):**

$$
T_{\mathrm{total}} := \sum_{c \in \mathcal C}
\Big[(T_c^{\mathrm{pickup}} - T_c^{\mathrm{arrival}})
+\tau_{o_c \to d_c}
+\sum_{f_j \in \mathrm{IntStops}(c)} t_{\mathrm{hold}}\!\big(W_{f_j}^{(u)}, W_{f_j}^{(d)}\big)\Big].
$$

> where $\mathrm{IntStops}(c)$ denotes the **intermediate** stops on $\text{Path}(c)$  
> c(origin holding is included in the waiting term; destination has no holding by assumption).

**Energy cost:**

$$
E_{\mathrm{total}} := E_{\mathrm{base}} + E_{\mathrm{move}}.
$$

**Overall weighted objective:**

$$
\min Z \;=\; w_t \, T_{\mathrm{total}} \;+\; w_e \, E_{\mathrm{total}}.
$$

where $\mathrm{IntStops}(c)$ denotes the **intermediate** stops on $\text{Path}(c)$  
(origin holding is included in the waiting term; destination has no holding by assumption).

##### Constraints

1. **Capacity constraint**

$$
L_k(t) \le L_{\max}, \quad \forall k \in \mathcal K,\ \forall t.
$$

2. **Kinematic feasibility (induced)**  
   For each segment, the constructed profile satisfies

$$
0 \le v_{k,j}(t) \le V_{\max,\mathrm{dir}_j}(L_{k,j}), \quad
|a_{k,j}(t)| \le \max\!\bigl\{ a_{\mathrm{dir}_j}^{\text{acc}}(L_{k,j}),\; a_{\mathrm{dir}_j}^{\text{dec}}(L_{k,j}) \bigr\}.
$$

3. **Time propagation**

-   **Motion time (between floors):**

    $$
    \tau_{f_j \to f_{j+1}} = t_{\text{acc},j} + t_{\text{const},j} + t_{\text{dec},j}.
    $$

-   **Pickup feasibility:**

    $$
    T_c^{\text{pickup}} \;\ge\; T_c^{\text{arrival}}, \quad \forall c \in \mathcal C.
    $$

-   **Per-request propagation with intermediate holdings:**

    $$
    T_c^{\text{dropoff}}=
    T_c^{\text{pickup}}
    +\sum_{\ell=0}^{m-1} \tau_{f_\ell \to f_{\ell+1}}
    +\sum_{j=0}^{m-1} t_{\mathrm{hold}}\!\big(W_{f_j}^{(u)}, W_{f_j}^{(d)}\big),
    $$

    where the second sum includes the origin holding and excludes the destination.

4. **Queue dynamics (event-driven)**

$$
Q_f(t_i^+) = Q_f(t_i^-) \cup \mathrm{arrivals}(t_i) - \mathrm{boarded}(t_i).
$$

5. **First-Come-First-Served (FCFS)**  
   If two requests arrive at the same floor $f$ with  
   $T_{c_1}^{\mathrm{arrival}} < T_{c_2}^{\mathrm{arrival}}$, then

$$
T_{c_1}^{\mathrm{pickup}} \le T_{c_2}^{\mathrm{pickup}}.
$$

6. **Service uniqueness**

$$
\sum_{k \in \mathcal K} x_{k,c} = 1, \quad \forall c \in \mathcal C.
$$

7. **Ordering consistency (pairwise precedence within an elevator)**  
   For any $c_1 \ne c_2$ with $x_{k,c_1} = x_{k,c_2} = 1$,

    $$
      u_{c_1,c_2}^k \in \{0,1\}, \qquad
      u_{c_1,c_2}^k + u_{c_2,c_1}^k = 1,
    $$

    and with sufficiently large $M$,

    $$
      T_{c_2}^{\mathrm{pickup}}
      \ \ge\
      T_{c_1}^{\mathrm{dropoff}}
      +\tau^{k}\!\big(\mathrm{end}(c_1) \to o_{c_2}\big)
      -\big(1 - u_{c_1,c_2}^k\big)\,M,
    $$

    where $\mathrm{end}(c_1)$ is the last stop serving $c_1$.

8. **Initial state**  
   Each elevator $k$ starts from a known initial state $(S_k^0, t_k^0)$ (floor and time), anchoring the first motion segment.

### Model Optimization

## Conclusion

## Reference

# Optimization Method Course Assignment Template

Name, Student ID, Major and Class
Name, Student ID, Major and Class
Name, Student ID, Major and Class
Name, Student ID, Major and Class
Name, Student ID, Major and Class
Abstract: （不超过 250 个英文单词，提交时删除该提示内容）

Keywords: keyword1; keyword2; keyword3; (请选择 3-7 个关键词，提交时删除该提示内容)

1. Introduction

1.1 Literature review

1.2 Contribution of this article

1.3 Organization of this article

2. Methodology (including explanation of data and assumptions)
   （该部分内容按照写作需要可以分小点撰写，以使条例更清晰，即：2.1 2.2 2.3…，也可以不分。提交时删除该内容）
   2.1

2.2

3. Result and discussion
   （该部分内容按照写作需要可以分小点撰写，以使条例更清晰，即：3.1 3.2 3.3…，也可以不分。提交时删除该内容）
   3.1

3.2

4. Conclusion

Reference
[1] Author1, Author2. Title. Journal, year, volume: page (or id number).
[2] M. Waseem, M. Ahmad, A. Parveen, M. Suhaib. Battery technologies and functionality of battery management system for EVs: Current status, key challenges, and future prospectives. Journal Power Sources, 2023, 580: 233349.
[3] Z. Wei, K. Liu, X. Liu, et al. Multilevel Data-Driven Battery Management: From Internal Sensing to Big Data Utilization. IEEE Transactions on Transportation Electrification, 2023, 9: 4805–4823.
