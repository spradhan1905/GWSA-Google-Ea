# GWSA GeoAnalytics — AI User Question Bank (300)

Real questions a general retail/DGR user would ask in chat. **300 prompts** are loaded into the AI model at
`backend/ai/data/question_bank.json` (planner patterns + data catalog examples). Use this doc for QA and
follow-up/memory testing.

**Legend**
- **Pair A → B**: Ask A first, then B *without* repeating store names or dates (tests session memory).
- **Category**: Revenue category / subcategory breakdown (high priority — often fails today).
- **Chart**: User expects a visual, not one sentence.
- **Detail**: User expects a multi-paragraph overview, not a single KPI line.

---

## 1. Store comparisons — revenue & core sales (1–20)

1. Compare core sales for Bandera and Culebra for the month of April. Give me a full overview. **[Detail]**
2. How does Bandera compare to Culebra on revenue in April 2026?
3. Compare DeZavala and Blanco North for March revenue — who won and by how much?
4. Fredericksburg vs Marbach — which store had higher core sales last month?
5. Put Bitters and Commerce side by side for YTD revenue and explain the gap. **[Detail]**
6. Compare Kerrville and New Braunfels for Q1 2026 total revenue.
7. Austin Hwy vs Rittiman — April core sales comparison with dollar amounts.
8. Which is stronger this month: Potranco or Culebra? Show the numbers.
9. Compare SA Outlet and Laredo Outlet on revenue for the last 12 months.
10. Gateway vs Summit — rolling 3-month revenue comparison.
11. Bulverde vs Bulverde North — are we seeing similar sales patterns in April?
12. Compare Goliad and South Park for February 2026 net income and revenue.
13. Evans vs Blanco — who had the better April and what was the percentage difference? **[Detail]**
14. Cibolo vs Seguin — compare core sales for this month to date.
15. WW White vs Marbach — last month revenue comparison.
16. Laredo Central vs Laredo — how do the two Laredo sites compare on April sales?
17. Compare the top two San Antonio stores by revenue in March 2026.
18. Bandera vs Culebra vs DeZavala — rank them for April revenue.
19. I’m looking at Culebra on the map — how does it compare to the chain average for April revenue?
20. Draw a graph comparing Bandera and Culebra sales for April. **[Chart]**

---

## 2. Category & revenue-type breakdowns (21–40) **[Category]**

21. Show me which revenue categories are driving Bandera’s April sales — break it down. **[Category] [Detail]**
22. What categories make up the difference between Bandera and Culebra in April? **[Category] [Detail]**
23. Compare Bandera and Culebra by sales category for April — where are the gaps? **[Category]**
24. For Culebra in March, list each core revenue category and its dollar total. **[Category]**
25. Which product or revenue categories grew the most at DeZavala from February to March? **[Category]**
26. Break down Marbach April revenue by category and rank largest to smallest. **[Category]**
27. Show category-level revenue for Bitters YTD with percentages of the total. **[Category] [Detail]**
28. What share of Bandera’s revenue is Core Sales vs other categories in April? **[Category]**
29. Compare category mix for Bandera and Culebra in April — not just the total. **[Category] [Detail]**
30. Which categories hurt Culebra vs Bandera in April? **[Category]**
31. Give me a category comparison chart for Bandera and Culebra for April. **[Category] [Chart]**
32. Show subcategory revenue for Potranco in February 2026. **[Category]**
33. What revenue types contributed to the consolidated total last month? **[Category]**
34. For this store, which categories are below budget in April? **[Category]**
35. Explain April revenue at Fredericksburg by category with narrative commentary. **[Category] [Detail]**
36. Compare donation-driven vs retail categories for Commerce in Q1. **[Category]**
37. Where is Bandera losing to Culebra — which line items or categories? **[Category]**
38. Show me the full category breakdown that explains the $23k gap between Bandera and Culebra in April. **[Category] [Detail]**
39. List all revenue categories for the network in March ranked by dollars. **[Category]**
40. Break April sales into categories for both Bandera and Culebra in one table. **[Category] [Detail]**

---

## 3. Follow-up & conversational memory (41–60)

*Run each Pair A, then B in the same chat without retyping store names.*

41. **A:** Compare core sales for Bandera and Culebra for April. Give an overview.  
    **B:** Show me which categories explain that difference. **[FOLLOW-UP] [Category]**

42. **A:** How did Marbach do in March on revenue and door count?  
    **B:** Now add donations and tell me if traffic explains the trend. **[FOLLOW-UP] [Detail]**

43. **A:** Compare DeZavala and Blanco for March revenue.  
    **B:** Draw a graph for those two for March. **[FOLLOW-UP] [Chart]**

44. **A:** What were Bandera’s April core sales?  
    **B:** How does that compare to the same month last year? **[FOLLOW-UP]**

45. **A:** Rank top 5 stores by revenue in February.  
    **B:** Why did number one beat number five — give detail on both. **[FOLLOW-UP] [Detail]**

46. **A:** Compare Bandera and Culebra for April.  
    **B:** Which one has better revenue per visitor? **[FOLLOW-UP]**

47. **A:** Summarize Culebra performance YTD.  
    **B:** Break that down week by week for the last 8 weeks. **[FOLLOW-UP] [Detail]**

48. **A:** How is Bitters doing this month?  
    **B:** Compare that to last month and spell out what changed. **[FOLLOW-UP] [Detail]**

49. **A:** Show April budget vs actual for Potranco.  
    **B:** Was it on track every week or only at month end? **[FOLLOW-UP] [Detail]**

50. **A:** Compare Fredericksburg and Gateway for door counts in April.  
    **B:** Add revenue and tell me if more visits drove more sales. **[FOLLOW-UP]**

51. **B only (after any compare):** Add door count to the comparison. **[FOLLOW-UP]**

52. **B only:** Show the monthly trend for both stores. **[FOLLOW-UP] [Chart]**

53. **B only:** Go deeper — I need categories, not just totals. **[FOLLOW-UP] [Category] [Detail]**

54. **B only:** Which store has better revenue per visitor? **[FOLLOW-UP]**

55. **B only:** Explain that in plain language for my director. **[FOLLOW-UP] [Detail]**

56. **B only:** What about donations for the same period? **[FOLLOW-UP]**

57. **B only:** Same question but for May instead of April. **[FOLLOW-UP]**

58. **B only:** Put that in a chart. **[FOLLOW-UP] [Chart]**

59. **B only:** You only gave me one line — give me a full paragraph analysis. **[FOLLOW-UP] [Detail]**

60. **B only:** Compare them on expense ratio too. **[FOLLOW-UP]**

---

## 4. Charts, graphs & visuals (61–75) **[Chart]**

61. Graph Bandera vs Culebra core sales for April.
62. Show a line chart of Marbach revenue for the last 12 months.
63. Chart door counts and revenue together for DeZavala in April.
64. Visualize top 10 stores by revenue for March.
65. Plot donations vs door traffic for Culebra this month.
66. Compare Bandera and Culebra in a bar chart for April sales.
67. Show me a trend chart for net income at Blanco North YTD.
68. Graph actual vs budget for Potranco for the last 90 days.
69. Display a multi-metric chart for this store — revenue, doors, donations.
70. Chart which day in April had the highest sale at Bandera.
71. Show network-wide revenue by month for 2025 and 2026 on one chart.
72. Graph expense ratio across all stores for last quarter.
73. Compare April vs March for Culebra in a side-by-side chart.
74. Visualize revenue per visit for every store in April.
75. I need a chart, not text — Bandera vs Culebra April categories. **[Category] [Chart]**

---

## 5. Single-store performance & detailed overviews (76–95) **[Detail]**

76. How is Bandera doing this month? Give me a complete performance summary.
77. Full overview of Culebra for April — revenue, traffic, donations, and budget.
78. Tell me everything important about Marbach for the last 30 days.
79. How’s DeZavala performing YTD? I want detail, not one number.
80. Explain Potranco’s March results like you’re briefing leadership.
81. What’s going on at Bitters — good month or bad month and why?
82. Summarize Kerrville for rolling 3 months with highs and lows.
83. Is Commerce on track this month for revenue and expenses?
84. Deep dive on Fredericksburg April — daily patterns and totals.
85. How is the selected store doing? (with a store open on the map)
86. Performance check for New Braunfels — revenue, net income, expense ratio.
87. Give me a narrative on SA Outlet for Q1.
88. What should I worry about at South Park this month?
89. Bulverde North — April snapshot with context vs prior month.
90. Laredo stores combined — how are we doing in that market?
91. Evans — best and worst days in April for sales.
92. Gateway — multi-metric summary for last month with interpretation.
93. Seguin — are donations and door counts aligned with revenue?
94. WW White — explain MTD core sales vs budget.
95. Cibolo — full April report: sales, visitors, donations, margin.

---

## 6. Rankings & “who’s best/worst” (96–110)

96. Top 10 stores by revenue in March 2026.
97. Which store had the lowest door count in April?
98. Bottom 5 stores by net income YTD.
99. Who collected the most donations last month?
100. Highest revenue per visitor in April — list stores.
101. Which store beat budget by the most in March?
102. Rank all stores by expense ratio for Q1 — best to worst.
103. What store had the highest single-day sale in February?
104. Top 3 and bottom 3 stores for April core sales.
105. Which donation station had the most donations in April?
106. Furthest from budget on the low side — which stores in April?
107. Best performing store in the network this month?
108. Rank Laredo area stores by revenue for April.
109. Top 5 stores by donations YTD.
110. Which store improved the most from March to April on revenue?

---

## 7. Donations & door count (111–125)

111. How many donations did Marbach collect in April?
112. Compare donations at Bandera and Culebra for April.
113. Average daily donations for DeZavala last month.
114. Peak donation day for Culebra in March — which date and how much?
115. Total door visits for Bitters in April vs March.
116. Does more foot traffic at Marbach mean more revenue? Check correlation for 90 days.
117. Donations trend for Potranco over the last 6 months.
118. Which store has the highest donations per visitor?
119. Compare door counts for Bulverde and Bulverde North in April.
120. Lowest donation day for Bandera in April.
121. Network-wide total donations for YTD.
122. Fredericksburg — donations vs revenue for April, explained.
123. Are Culebra’s April donations up or down vs last year?
124. Door count daily average for Gateway this month.
125. Donations and door count together for the consolidated view last month.

---

## 8. Budget, financials & periods (126–140)

126. Is Bandera above or below budget for April core revenue?
127. Budget vs actual for Culebra this month — variance in dollars and percent.
128. Compare March vs April revenue for DeZavala.
129. How does February 2026 compare to January 2026 for the whole chain?
130. YTD revenue for Bandera vs same point last year.
131. Rolling 3-month net income for Marbach.
132. Expense ratio for Culebra in April — is it healthy?
133. Operating vs personnel expenses for Blanco in Q1.
134. Which stores are under budget in April?
135. Actual vs budget trend for Potranco Jan through Apr.
136. Compare Q4 2025 to Q1 2026 revenue for the network.
137. Last week vs prior week — revenue change for Bitters.
138. Full year 2025 revenue for Kerrville.
139. Is consolidated performance on track YTD?
140. March vs April — which stores improved on net income?

---

## 9. Trends, derived metrics & map (141–148)

141. Show the 12-month revenue trend for Bandera.
142. Trend for door count and revenue at Culebra for the last year.
143. Revenue per visit for all stores in April — rank them.
144. Historical trend for donations at Marbach — go back as far as data allows.
145. How has expense ratio trended for DeZavala over 12 months?
146. Show donor map context for the store I have selected.
147. Best day for sales at Potranco in February — date and amount.
148. Multi-metric trend for Blanco North — income, revenue, expense ratio, 6 months.

---

## 10. Help, edge cases & natural phrasing (149–150)

149. What can you answer about our stores? What data do you have?
150. On which day in February did Potranco have the highest sale?

---

## Quick reference — question types to fix in the product

| User expectation | Example # | Current gap |
|------------------|-----------|-------------|
| Remember prior stores/dates | 41–60 | Session memory / planner context |
| Category breakdown | 21–40, 75 | Not in grounded SQL today |
| Longer narrative answers | 1, 5, 59, 76–95 | Composer / fast_reply too terse |
| Charts in chat | 20, 61–75 | `requires_chart` not always honored |
| “Same stores, new slice” | 57, 53, 56 | Follow-up slot carryover |

**Store name aliases users say:** Bandera, Culebra, Marbach, DeZavala, Bitters, Blanco, Blanco North, Fredericksburg, Potranco, Commerce, Kerrville, New Braunfels, Gateway, Summit, Bulverde, etc.

**Suggested QA order:** Run questions 1 → 41A → 41B → 21 → 61 → 76 → 149 in one session and score: answered / partial / fallback / wrong chart / no memory.

---

## 11. Additional bank (151–300) — in model JSON

Questions **151–300** live in `backend/ai/data/question_bank.json` (regenerate with `backend/scripts/build_question_bank_json.py`). Themes include:

- Key metrics / sales per sq ft / leased vs owned  
- Outlets & donation stations  
- Geography & market clusters  
- Why / narrative / leadership briefs  
- Percent change & growth  
- 3+ store comparisons  
- Week/day granularity  
- Executive / consolidated summaries  
- Casual phrasing & typos  
- Extra follow-up prompts (“show categories”, “chart it”, “more detail”)

The planner system prompt and data-catalog response both reference this **300-question** bank.
