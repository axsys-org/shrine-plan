# Task: a contractor's trades

The owner is a general contractor who keeps a bench of subcontractors:
electricians, plumbers, framers. Jobs come and go; what must stay true is
that for each trade in `/needs/*` there are `want` subcontractors who are
licensed, insured, available within the lead time the need states, and
whose day rate is under the ceiling.

Evidence is a statement from the subcontractor (any channel, or
`/her/<peer>` when they run Shrine) about availability, rate and the dates
their license and insurance run to. A license or insurance date that
passed is not ok until a new statement says otherwise; write the expiry as
`expires` on the observation so the judgment goes stale on its own.

Ask each subcontractor only when the need's cadence or an expiry says so.
Tell the owner through `/attention/<n>` when a trade falls below `want`, when
a rate changes above the ceiling, or when a job's start date in the need is
within the lead time and the bench is short.
