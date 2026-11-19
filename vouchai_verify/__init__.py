"""Independent verifier of VouchAI episodes.

It never imports `vouchai` (import-graph test): it re-derives every amount of
the truth from the cited evidence records only, checks the accounting
invariants on the clean books and the declared discrepancies on the public
books, and writes the episode passport ("Given / Find / Solution / Answer").

Status: skeleton (phase 0). The checks land in phase 2 of the plan.
"""

__version__ = "0.1.0"
