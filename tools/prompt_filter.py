"""Whack-a-mole regex isn't converging. Switch strategy:

Goose summaries are RELIABLY third-person PAST TENSE ("was created",
"was made", "was executed", "were saved", etc.).
Real user instructions are written TO the agent (imperatives, questions,
first person). So: reject any line containing passive-agent phrases
unless it contains strong first-person markers.
"""
import re

PASSIVE = re.compile(
    r"\b(was|were) (created|made|executed|saved|performed|called|run|ran|"
    r"updated|written|opened|checked|tested|installed|deleted|found|listed|"
    r"generated|analyzed|scanned|fixed|added|implemented|refactored|"
    r"inspected|written|stored|captured|blocked|truncated|parsed|used)\b|"
    r"\bhas been (created|made|saved|updated)|"
    r"\bcall was made\b|\btool call was\b|\bcommand (was|failed)|"
    r"\bfile was\b|\bmodule was\b|\bscript was\b|\bclass was\b|"
    r"^Screenshots were|^A (shell|tool|write|file|browser|directory"
    r"|background task|copy operation|SupervisorAgent|batch rename"
    r"|call to|tool call|directory structure)|"
    r"^The (assistant|copy operation|command|delegation|edit|contents"
    r"|Windows shell)"
    r"|^(A|An|The) .*(was created|was made|was executed|was initiated|"
    r"was performed|were created|were saved|was run|was attempted|"
    r"were read|was read|failed because|returned no)"
    r"|^Created "
    r"|^Listed "
    r"|^A robocopy"
    r"|^The (command|script|copy|user) (failed|needs|ran)")

# user QUOTING errors back at the agent ("hey again: A tool call could not...")
QUOTED_ERROR = re.compile(
    r"(a tool call (could not|was not)|an error|this error|the error|"
    r"no errors|same error|don'?t make errors|no tool call issues|"
    r"tool call could not)", re.IGNORECASE)

FIRST_PERSON = re.compile(
    r"^(hey|hi|ok|okay|please|pls|can you|could you|i want|i need|i also|"
    r"i don't|i dont|do (this|it|not)|make (sure|it)|continue|try|fix|"
    r"add|build|create|write|run|test|push|pull|delete|remove|check|"
    r"find|scan|search|give|show|tell|explain|why|what|how|when|where|"
    r"now |then |next |also |and |but |yes |no |so |my |we |you )",
    re.IGNORECASE)


def is_real_prompt(text: str) -> bool:
    t = text.strip()
    if len(t) < 8:
        return False
    if t.startswith((
            "[System:", "[CONTEXT COMPACTION", "[OUT-OF-BAND",
            "[PRIOR CONTEXT", "[Context from", "[IMPORTANT",
            "[Continuing toward", "[Response", "System Instruction:",
            "[response interrupted", "<think>", "<command-message>",
            "<command-name>", "<local-command", "[TOOL_CALL]",
            "[tool_call]")):
        return False
    if "maximum number of tool-calling iterations" in t[:200]:
        return False
    if "<command-message>" in t[:100] or "<command-name>" in t[:100]:
        return False
    if t.count("\n") > 10 and t.count("#") > 5 and "##" in t[:300]:
        return False
    # THE KEY RULE: passive agent-summary voice = not a user instruction
    if PASSIVE.search(t[:250]) and not FIRST_PERSON.match(t):
        # ...unless the user is quoting/complaining about an error
        if not QUOTED_ERROR.search(t):
            return False
    return True


if __name__ == "__main__":
    tests = [
        ("hey I want you to login into my Udemy", True),
        ("A `mkdir -p` command failed on Windows", False),
        ("have you opened chrome in the browser and tried it yourself ?", True),
        ("A SupervisorAgent class was created in `src/agents/supervisor.py`",
         False),
        ("A tool call could not be parsed", True),  # user quoting an error
        ("The `__init__.py` file for the `browser` module was created",
         False),
        ("continue and don't mke tool call errors", True),
        ("Screenshots were successfully saved to C:\\Users", False),
        ("but you didn't logged in at all", True),
        ("hs8326467@gmail.com/Qwerty@123", True),
        ("A todo list was created/updated with a comprehensive 5-phase plan",
         False),
        ("Create the todo list for the super app", True),
    ]
    for text, expected in tests:
        got = is_real_prompt(text)
        mark = "OK " if got == expected else "FAIL"
        print(f"{mark} expected={expected} got={got}: {text[:60]}")
