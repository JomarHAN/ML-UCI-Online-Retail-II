# Customer Recommendation Examples

Generated from the UCI Online Retail II dataset. One representative customer per strategy quadrant.


## 2. Urgent Win-back

### Customer 12458.0 — Loyal Customers
**Strategy:** 2. Urgent Win-back  |  **Priority:** 0.999

**Metrics**
- Historical revenue: £1,077.01
- Predicted 90-day CLV: £15.68
- Churn risk: 53%
- Last purchased: 194 days ago
- Order history: 3 orders

**Recommended action**
- *Urgent personalized win-back* (high urgency)
- Tactic: Personal email + meaningful discount on a previously-loved category
- Suggested discount: 15%
- Estimated intervention cost: £20

**Why this customer is at risk (top SHAP drivers)**
- monetary = 1077.01
- frequency = 3.0

**Their favorite product:** LUNCH BAG CARS BLUE (20728)

**Product recommendations** (frequently bought with their favorite)
- LUNCH BAG PINK POLKADOT — 8.63× lift
- LUNCH BAG SUKI  DESIGN — 7.95× lift
- LUNCH BAG RED RETROSPOT — 6.85× lift

---

## 1. VIP Retention

### Customer 12370.0 — Loyal Customers
**Strategy:** 1. VIP Retention  |  **Priority:** 0.667

**Metrics**
- Historical revenue: £3,221.03
- Predicted 90-day CLV: £31.27
- Churn risk: 43%
- Last purchased: 184 days ago
- Order history: 6 orders

**Recommended action**
- *Reward & retain* (low urgency)
- Tactic: Invite to loyally programl early access to new arrivals
- Estimated intervention cost: £5

**Why this customer is at risk (top SHAP drivers)**
- frequency = 6.0

**Their favorite product:** WHITE HANGING HEART T-LIGHT HOLDER (85123A)

**Product recommendations** (frequently bought with their favorite)
- RED HANGING HEART T-LIGHT HOLDER — 5.07× lift

---

## 3. Upsell Opportunity

### Customer 12897.0 — Need Attention
**Strategy:** 3. Upsell Opportunity  |  **Priority:** 0.333

**Metrics**
- Historical revenue: £514.25
- Predicted 90-day CLV: £6.37
- Churn risk: 46%
- Last purchased: 114 days ago
- Order history: 4 orders

**Recommended action**
- *Cross-sell to grow basket* (medium urgency)
- Tactic: Recommend comlementary products at check/email
- Suggested discount: 5%
- Estimated intervention cost: £3

**Why this customer is at risk (top SHAP drivers)**
- frequency = 4.0
- total_units = 249.0

**Their favorite product:** HEART OF WICKER SMALL (22469)

**Product recommendations** (frequently bought with their favorite)
- HEART OF WICKER LARGE — 9.82× lift

---

## 4. Low Priority

### Customer 12361.0 — Need Attention
**Strategy:** 4. Low Priority  |  **Priority:** 0.000

**Metrics**
- Historical revenue: £451.25
- Predicted 90-day CLV: £2.79
- Churn risk: 68%
- Last purchased: 196 days ago
- Order history: 4 orders

**Recommended action**
- *Minimal investment* (low urgency)
- Tactic: Generic newsletter only
- Estimated intervention cost: £0.5

**Why this customer is at risk (top SHAP drivers)**
- total_units = 231.0
- frequency = 4.0
- monetary = 451.25

**Their favorite product:** LUNCH BAG RED RETROSPOT (20725)

**Product recommendations** (frequently bought with their favorite)
- LUNCH BAG PINK POLKADOT — 7.46× lift
- LUNCH BAG WOODLAND — 7.11× lift
- LUNCH BAG CARS BLUE — 6.85× lift

---