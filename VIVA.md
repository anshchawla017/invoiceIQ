# InvoiceIQ: 30 likely viva questions and answers

Answers are written to match what the code actually does. Where the honest
answer is "this is a limitation", it says so, because examiners respect that more
than a bluff.

---

## A. The project in general

**1. What problem does InvoiceIQ solve?**
Finance teams pay thousands of invoices and cannot read each one closely. Errors
(a double entry, a mistyped amount) and problems (a vendor that is always late)
hide in the volume. InvoiceIQ scores every invoice for warning signs and explains
each score, so a person can spend their time on the few invoices that matter.

**2. Does it detect fraud?**
No. It flags invoices that are *worth a human look*. An unusual invoice can be
perfectly legitimate (a one-off large purchase). We have no confirmed-fraud
labels, so claiming fraud detection would be dishonest.

**3. Walk me through the architecture.**
CSV/Excel is validated and cleaned, then stored in SQLite through SQLAlchemy.
`features.py` turns invoices into 5 numbers. An Isolation Forest scores how
unusual each one is; `duplicate_detection.py` finds possible double entries;
`risk_engine.py` combines six factors into a 0-100 score with reasons. Results are
written back to SQL and the models saved with joblib. `dashboard_data.py` loads
everything for the Streamlit pages in `views/`.

**4. Why Python and Streamlit?**
Python has the data and ML libraries (pandas, scikit-learn). Streamlit builds an
interactive multi-page dashboard in pure Python, so the whole project is one
language and easy to run and explain.

**5. Why is the data synthetic?**
Real invoices are confidential and unlabelled. I generated 1,167 invoices with
known patterns planted (large invoices, extreme amounts, late-paying vendors,
duplicates) so I could check the system finds what I know is there. The
consequence is that results on this data are a sanity check, not proof of
real-world performance.

---

## B. Database and data quality

**6. Why a real database instead of a DataFrame?**
Data survives restarts, relationships are enforced by foreign keys, SQL does
aggregation efficiently, and imports can be transactional. It is also how a real
system would be built.

**7. Describe the tables.**
`vendors`, `invoices` (FK to vendors), `payments` (FK to invoices, only for
invoices with payment info), `risk_predictions` and `anomaly_results` (both FK to
invoices, one row per invoice, refilled each time the analysis runs).

**8. What happens with bad data in an upload?**
Nothing crashes. Rows with no ID, an unreadable date, or amount <= 0 are dropped
and counted; repeated invoice IDs keep the first; inconsistencies like "Paid" with
no payment date are kept but reported as warnings. The user sees a report before
anything is saved.

**9. What if the same file is imported twice?**
The import skips any `invoice_id` already stored, so nothing is duplicated. The
whole import runs in a transaction and rolls back if anything fails.

---

## C. Machine learning

**10. Why Isolation Forest?**
We have no labels, so we need an unsupervised method. Isolation Forest is built
for finding outliers: unusual points are easy to separate with random splits, so
they get short paths in the trees. It is fast, needs no scaling, and handles
several features at once.

**11. Explain how Isolation Forest works in one minute.**
Build many random trees. Each tree repeatedly picks a random feature and a random
split value until each point is alone. Points far from the crowd need only a few
splits; typical points need many. The average path length over 200 trees becomes
the anomaly score: shorter path, more anomalous.

**12. What does `contamination = 0.03` mean? Is it learned?**
It tells the model roughly what share of data to label anomalous, so it sets the
flagging threshold. It is an **assumption** I chose, not something learned. That
is why exactly about 3% of invoices are flagged (35 of 1,167) regardless of how
many are truly odd. Changing it changes how many are flagged.

**13. Which features do you use and why?**
Five, all "how unusual is this invoice": `log_amount`, `log_amount_ratio` (amount
vs the vendor's median), `effective_delay`, `delay_deviation` (vs the vendor's
usual delay), and `vendor_burst_7d` (vendor's invoices within +/-7 days). A raw
amount means little on its own; $9,000 is normal for one vendor and alarming for
another, so features are relative to the vendor.

**14. Why the log scale?**
Dollar amounts are extremely skewed. One $406K invoice stretched the raw range so
much that random splits never landed near a $3.70 invoice, and it was missed. On a
log scale, $3 and $400K are both far from typical.

**15. Why the median, not the mean, for vendor "typical" values?**
A mean is pulled toward the very outliers we are trying to find, hiding them. The
median is not.

**16. How did you choose the features?**
By experiment. My first version (raw dollars, tax, discount, vendor averages)
missed the $3.70 invoice and flagged 12 normal invoices from vendor V112, whose
usual invoice is about $14K. I compared four feature sets on the same data and
picked the one that caught the most planted anomalies with no false flags. The
comparison table is in the README.

**17. Isn't that circular, tuning on data you planted?**
Partly, yes, and I say so in the README. It shows the design handles known cases
and fixed two real bugs, but it does not prove the same performance on real
invoices. Real validation needs real labelled outcomes.

**18. Why don't you report accuracy, precision, recall or F1?**
Those compare predictions with confirmed correct answers, and we have none. Any
number would be made up. The Model Center shows real statistics instead (settings,
feature averages for flagged vs normal invoices, score distribution) and explains
this.

**19. Do you scale the features?**
No. Tree-based models split on thresholds, so scaling makes no difference.

**20. Why are 11 of 35 flagged invoices Low risk?**
The flag means "statistically unusual". The risk score also weighs lateness,
vendor history and duplicates. An invoice can be an oddity yet paid on time and
not repeated. The dashboard shows both instead of hiding the difference.

---

## D. Risk score and duplicates

**21. How is the risk score calculated?**
Six factors, each scaled to 0-1, multiplied by a weight, summed and times 100:
unusual amount 25, payment delay 20, anomaly score 20, possible duplicate 15,
vendor payment history 10, unusual frequency 10. The weights sum to 1, so the
maximum is exactly 100. Levels: 0-29 Low, 30-59 Medium, 60-79 High, 80+ Critical.

**22. Why a rule-based score and not a trained classifier?**
A classifier needs labels, and we have none. A weighted score is also fully
transparent: every point can be traced to a named factor, which is what the "Why
was this flagged?" panel shows. The trade-off is that the weights are my judgement,
not learned.

**23. How did you pick the weights?**
By judgement: amount and delay are the strongest direct signals, the model score
adds statistical evidence, and vendor-level signals are context. They are not
optimised. With labelled outcomes they could be fitted, for example with logistic
regression.

**24. Why are there no Critical invoices on the demo data?**
Reaching 80 needs near-maximum on several factors at once. The top demo score is
about 72. I did not bend the thresholds to force a Critical result.

**25. How does duplicate detection work?**
Only invoices from the same vendor are compared. Exact = same amount to the cent
and same date; Strong = amount within 0.1% and within 7 days; Weak = amount within
1% and within 3 days. Both invoices of a pair are marked because we cannot know
which is the original. On the demo data it found all 17 planted pairs.

**26. What are its weaknesses?**
It looks only at amount and date, so a genuinely repeating bill can be flagged.
The Weak tier produced 12 extra matches that look like chance near-matches for
vendors with many invoices, which is why the UI labels the strength. It would be
improved by comparing invoice numbers or line items.

---

## E. Testing, limitations, future

**27. How did you test it?**
31 pytest tests: validation counts on a deliberately messy CSV, feature maths,
risk-score bounds and level boundaries, duplicate rules, the full pipeline on the
demo data, analytics, and end-to-end database tests on a throw-away SQLite file. I
also broke the code on purpose (changed a weight, removed the same-vendor rule,
allowed negative amounts) to confirm the tests fail when they should.

**28. What are the main limitations?**
No labels, so no accuracy figures; synthetic data with features tuned on planted
patterns; 3% contamination is an assumption; duplicate matching is simple; weights
and vendor rules are judgement, not tuned; single-user local SQLite with no login;
the app re-reads the database on each click, which would need caching at scale.

**29. How would you improve it with more time or real data?**
Collect reviewer decisions (confirmed problem or not) as labels, then train a
supervised model and report real precision and recall, and fit the risk weights.
Add fuzzy invoice-number matching, PDF extraction, multi-currency, user login with
an audit log, and caching for large datasets.

**30. What is the single most important design decision?**
Being honest about what the system can and cannot claim. Relative-to-vendor
features and log scaling made the model work; explainable factor-by-factor scores
make it usable; and refusing to invent accuracy numbers keeps it defensible.
