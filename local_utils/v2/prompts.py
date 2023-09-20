# ruff: noqa: E501
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from local_utils.brainv2 import PieceOfArt
    from local_utils.v2.personas import Persona
    from local_utils.v2.thoughts import PlanStep, Thought


class ToolNames(str, Enum):
    CreateArt = "CreateArt"
    WriteInJournal = "WriteInJournal"
    ReadFromJournal = "ReadFromJournal"
    WriteBlogPost = "WriteBlogPost"
    PostOnSocial = "PostOnSocial"
    ReadLatestBlogs = "ReadLatestBlogs"
    QueryForInfo = "QueryForInfo"


AVAILALBLE_TOOLS = """
ReadLatestBlogs - Returns the contents of your latest 3 blog posts, useful to ensure continuity.

ReadFromJournal - Returns the contents of your latest 3 journal entries.

CreateArt - Generate a piece of art -- you can use this to photograph things, 
    paint pictures, and produce digital art of all kinds

WriteInJournal - Record information in a journal; use this whenever you need a step to "Think" about something, 
    for example after QueryForInfo you could journal and then create a piece of art or take a photograph.

PostOnSocial - Send a short message out to the social media sphere. If you use this immediately after using CreateArt,
    an image of the art will be included in the post.

WriteBlogPost - Write a long format blog post; ensure you are ready to publish before using this action, as there is no editing or drafts.

QueryForInfo - your main interface for asking questions / learning things, you can query for any piece 
    of information and receive a response; information learned in this manner is the only thing you can utilize 
    when writing blog entries.
"""

GET_NEW_THOUGHT = """
## TAKE ON THE FOLLOWING PERSONA

{persona}

## YOUR JOB

Your job now is to come up with a specific task that can be completed utilizing the available tools. 
It is important to choose a task that is in-line with your persona and that can be accomplished with your tools. 
You can build upon a previous task, for example if you have previously created a piece of Art you could choose 
to write a blog post about it. 

Don't try to do too much in a single thought, ideally keep it to 6 or fewer steps.

## AVAILABLE TOOLS

{tools}

## RECENTLY COMPLETED ACTIONS

Tasks you have recently completed, most recent first:

{recent_actions}

------

NOW CHOOSE A TASK
Now is the time to define the specific task you will do, ensuring the use of at least one output tool. 
Consider your recently completed actions, try not to repeat the exact action over and over.

Define a plan on how to achieve this utilizing the available tools, 
laying out the decisions you may need to make at each step using the following format:
{user_nudge}

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

----

Respond now, ensuring your Task begins with "I will"
""".strip()


def get_new_thought(persona: "Persona", recent_actions: str, user_nudge: Optional[str] = None):
    if user_nudge:
        user_nudge = user_nudge.replace("\n", "")
        user_nudge = (
            f"\n\nA SYSTEM USER REQUESTED YOU INCORPORATE THE FOLLOWING INTO YOUR CHOSEN TASK; "
            f"DO SO IF THE SUGGESTION IS IN-LINE WITH YOUR CHARACTER:\n\n\t^^^{user_nudge}^^^"
        )
    return GET_NEW_THOUGHT.format(
        persona=persona.format(include_physical=False, include_blogging_voice=True),
        recent_actions=recent_actions,
        tools=AVAILALBLE_TOOLS,
        user_nudge=user_nudge or "",
    )


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


# prompt to take some info, more than I want to keep, and combine it with the existing AI managed "Context"
SUMMARIZE_FOR_CONTEXT = """
# SETUP

You are acting as the following persona:

* {persona_name}
* {short_persona}

You are currently working to accomplish the following task:

{task_plan}

You have just executed this action: "{current_action}"

The output from this action will follow. 

# JOB

Your job now is to consider the output of the action and add information relevant to your task plan
from this output into your context window. This context window is the only part of the output that 
will be carried forward to the future actions. Capture whatever may be useful in your future actions,
including specific quotes when appropriate to the task at hand.

Here is your current context window -- you must retain or rewrite this information, along with whatever
additional information you want to add based on the output you receive



## CURRENT CONTEXT WINDOW

{current_context}

~~~

OUTPUT ONLY THE NEW CONTEXT WINDOW WITH NO ADDITIONAL TEXT. DO NOT UTILIZE MARKDOWN FORMATTING IN THIS RESPONSE

ACTION OUTPUT BEGINS NOW:

{summarize_this}

"""


def summarize_for_context(thought: "Thought", persona: "Persona", current_task: "PlanStep", data: str) -> str:
    return SUMMARIZE_FOR_CONTEXT.format(
        persona_name=persona.name,
        short_persona=persona.short_description,
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context or "Your context is currently blank",
        summarize_this=data,
    )


GENERATE_ANSWER_TO_QUESTION = """
Write an answer to the following question or questions as if you were writing a wikipedia article

* Be sure to restate the question. If there are multiple questions, address each separately
* Do not generate more than a few paragraphs for each question..
* You may utilize markdown formatting in your response
* Do not output anything other than the restated questions and answers

Questions:
{question}
"""


def general_question_answer(question: str) -> str:
    return GENERATE_ANSWER_TO_QUESTION.format(question=question)


GENERATE_QUESTIONS = """
# SETUP

You are acting as the following persona:

* {persona_name}
* {short_persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"


## CURRENT CONTEXT WINDOW

{current_context}

# JOB

Your job now is to consider the action you are performing, your overall task, and your current context and come
up with one or more appropriate questions or queries. You will then receive responses to those queries to update
your context window. 

You may ask 1, 2, or 3 questions. The more detailed and specific the better quality the response will be.
One detailed question is better than 3 lackluster questions.

OUTPUT YOUR QUESTIONS NOW, EACH ON A SEPARATE LINE. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE QUESTIONS.
"""


def generate_questions(thought: "Thought", persona: "Persona", current_task: "PlanStep") -> str:
    return GENERATE_QUESTIONS.format(
        persona_name=persona.name,
        short_persona=persona.short_description,
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context or "Your context is currently blank",
    )


WRITE_JOURNAL_ENTRY = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

## CURRENT CONTEXT WINDOW

{current_context}

# JOB

Your job now is to write the journal entry, taking into account your personality, context window, and purpose.

You may use markdown formatting in your response.

OUTPUT THE JOURNAL ENTRY NOW. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE ENTRY.
"""


def write_journal_entry(thought: "Thought", persona: "Persona", current_task: "PlanStep") -> str:
    return WRITE_JOURNAL_ENTRY.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=False, include_blogging_voice=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context or "Your context is currently blank",
    )


CREATE_ARTWORK = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

## CURRENT CONTEXT WINDOW

{current_context}

# JOB

Your job now is to create art!

You create art by providing a detailed description of the piece-- taking into account your personality, 
context window, and purpose. You can create artwork of nearly any type, be it a painting, 
photograph, statue, computer program, or anything else. Avoid mentioning most proper nouns, 
rather describe what can be seen, and limit the output to a single paragraph.

DO NOT NAME THE ARTWORK NOW, YOU WILL NAME IT AT A LATER TIME. 

DO NOT OUTPUT MORE THAN ONE PARAGRAPH.

OUTPUT THE DESCRIPTION OF THE NEW ARTWORK NOW. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE DESCRIPTION.

ALWAYS BEGIN BY STATING WHAT TYPE OF ARTWORK YOU ARE CREATING, E.G. "An oil painting of...", "A photograph of..."
"""


def create_artwork(thought: "Thought", persona: "Persona", current_task: "PlanStep") -> str:
    return CREATE_ARTWORK.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context or "Your context is currently blank",
    )


TITLE_ARTWORK = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

# JOB

You've just created a new piece of art. Now you must give it a title

Here is the description of the art you've created:

{artwork_descr}

OUTPUT THE NAME OF THE NEW ARTWORK NOW. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE NAME
"""


def title_artwork(thought: "Thought", persona: "Persona", current_task: "PlanStep", artwork_descr: str) -> str:
    return TITLE_ARTWORK.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        artwork_descr=artwork_descr,
    )


TITLE_BLOG = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

## CURRENT CONTEXT WINDOW

{current_context}

# JOB

You are ready to create a new blog entry. The first step is to come up with a title -- taking into account your 
personality, context window, and purpose.

OUTPUT THE TITLE OF THE UPCOMING BLOG POST. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE TITLE
"""


def create_blog_title(thought: "Thought", persona: "Persona", current_task: "PlanStep") -> str:
    return TITLE_BLOG.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context,
    )


WRITE_BLOG_ENTRY = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

## CURRENT CONTEXT WINDOW

{current_context}

# JOB


You are ready to create a new blog entry. You've just come up with a title:

"{blog_title}"

Your writing style:
{writing_style}

To create the blog post, simply output the markdown contents of the post.

{include_artwork}

DO NOT INCLUDE THE TITLE OF THE BLOG POST, OR A BYLINE -- THESE WILL BE ADDED AS WELL.

OUTPUT THE CONTENT OF THE BLOG POST. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE CONTENTS.
"""


def write_blog_entry(
    thought: "Thought",
    persona: "Persona",
    current_task: "PlanStep",
    blog_title: str,
    generated_artwork: list["PieceOfArt"],
) -> str:
    assert current_task in thought.plan
    include_artwork = ""
    _ = generated_artwork

    return WRITE_BLOG_ENTRY.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context,
        blog_title=blog_title,
        writing_style=persona.blogging_voice,
        include_artwork=include_artwork,
    )


POST_ON_SOCIAL = """
# SETUP

Today's date is: {now}

You are acting as the following persona:

{persona}

You are currently working to accomplish the following task:

{task_plan}

You are currently performing this action: "{current_action}"

## CURRENT CONTEXT WINDOW

{current_context}

# JOB

You are ready to create a social media post -- this is a short message, generally a single sentence.
If you've just finished creating a piece of art, it will be included in your post.

Your writing style:
{writing_style}

Your job now is to simply output the contents of the social media post.

OUTPUT THE CONTENT OF THE POST. DO NOT INCLUDE ANY ADDITIONAL TEXT OTHER THAN THE POST CONTENTS.
"""


def post_on_social(
    thought: "Thought", persona: "Persona", current_task: "PlanStep", linked_art: Optional["PieceOfArt"] = None
) -> str:
    _ = linked_art

    return POST_ON_SOCIAL.format(
        now=datetime.utcnow().isoformat(),
        persona=persona.format(include_physical=True),
        task_plan=thought.it_rationale,
        current_action=current_task.format(),
        current_context=thought.context,
        writing_style=persona.blogging_voice,
    )
