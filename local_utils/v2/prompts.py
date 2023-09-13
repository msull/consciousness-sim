from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_utils.v2.thoughts import Thought

AVAILALBLE_TOOLS = """
CreateArt - Generate a piece of art -- you can use this to photograph things, 
    paint pictures, and produce digital art of all kinds

WriteInJournal - Record information in a journal; use this whenever you need a step to "Think" about something, 
    for example after QueryForInfo you could journal and then create a piece of art or take a photograph.

ReadFromJournal - Returns the contents of your latest 3 journal entries.

WriteBlogPost - Write a new blog post using text and and a single image.

ReadLatestBlogs - Returns the contents of your latest 3 blog posts, useful to ensure continuity.

QueryForInfo - your main interface for asking questions / learning things, you can query for any piece 
    of information and receive a response; information learned in this 
    manner is the only thing you can utilize when writing blog entries.
"""

GET_NEW_THOUGHT = """
## TAKE ON THE FOLLOWING PERSONA

{persona}

## YOUR JOB

Your job now is to come up with a specific task that can be completed utilizing the available tools. 
It is important to choose a task that is in-line with your persona and that can be accomplished with your tools. 
You can build upon a previous task, for example if you have previously created a piece of Art you could choose 
to write a blog post about it. 

Don't try to do too much in a single thought

## AVAILABLE TOOLS

{tools}

## RECENT ACTIONS

{recent_actions}

------

NOW CHOOSE A TASK
Now is the time to define the specific task you will do, ensuring the use of at least one OUTPUT tool. 
Define a plan on how to achieve this utilizing the available tools, 
laying out the decisions you may need to make at each step using the following format:

## RATIONALE

Why you choose this task

## Plan

A brief plan on how to accomplish the task with the available tools

For example, if I were planning to write in my blog, I might:

1. Use ReadLatestBlogs to see what I have blogged about recently
2) Use QueryForInfo to gather some new information
3) Use WriteInJournal to plan how the new entry based on what I've gathered
4) Use WriteBlogPost to write the new piece

## Task
I will...
""".strip()


def get_new_thought(persona: str, goals: str, recent_actions: str):
    return GET_NEW_THOUGHT.format(persona=persona, goals=goals, recent_actions=recent_actions, tools=AVAILALBLE_TOOLS)


PLAN_TASK = """
# CONTEXT
Given the following rationale, plan, and task, and the listing of available tools, 
reformat the plan into a json listing.

# TASK

{task_plan}

# AVAILABLE TOOLS

{tools}

------

NOW OUTPUT THE PLAN IN JSON; do not output any additional text other than the raw JSON output.
Example:

[{{'tool_name': "ReadLatestBlogs", "purpose": "Review recent blog topics before picking a new one"}},...]
""".strip()


def plan_for_task(thought: "Thought"):
    return PLAN_TASK.format(task_plan=thought.it_rationale, tools=AVAILALBLE_TOOLS)
