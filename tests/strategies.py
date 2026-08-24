"""
Hypothesis strategies shared across all property tests.
"""

import hypothesis.strategies as st

from pgtrigger.consts import MAX_NAME_LENGTH
from pgtrigger.core.clauses import Event, Execution, ForEach, Time

########################################################################################

events = st.sampled_from(list(Event))
"""
Any single trigger event.
"""

executions = st.sampled_from(list(Execution))
"""
Any deferrability setting.
"""

for_each = st.sampled_from(list(ForEach))
"""
Row or statement level.
"""

identifiers = st.from_regex(r"\A[a-z][a-z0-9_]{0,20}\Z")
"""
Lower-case identifiers, which PostgreSQL reads without quoting.
"""

invalid_names = st.text(min_size=1).filter(
    lambda name: not name.replace("-", "").replace("_", "").isalnum()
)
"""
Names the validator rejects, by containing something outside the allowed set.
"""

row_events = st.sampled_from([Event.DELETE, Event.INSERT, Event.UPDATE])
"""
Events that are legal on a row-level trigger, so `TRUNCATE` is excluded.
"""

sql_text = st.text(max_size=200)
"""
Arbitrary text standing in for SQL, including whatever the tokenizer dislikes.
"""

statements = st.lists(
    st.from_regex(r"\A[A-Za-z0-9 _]+\Z").filter(str.strip),
    min_size=0,
    max_size=6,
)
"""
Statement bodies with no quoting, comments, or semicolons of their own.
"""

times = st.sampled_from(list(Time))
"""
Any `BEFORE`, `AFTER`, or `INSTEAD OF`.
"""

trigger_names = st.from_regex(rf"\A[A-Za-z0-9_-]{{1,{MAX_NAME_LENGTH}}}\Z")
"""
Names the validator accepts: the full character set, up to the length limit.
"""
