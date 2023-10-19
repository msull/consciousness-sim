from pathlib import Path

import streamlit as st

from local_utils import deep_dive_text

IMAGE_DIR = Path(__file__).parent.parent / "images" / "thought-deep-dive"
assert IMAGE_DIR.exists() and IMAGE_DIR.is_dir()


class Images:
    persona_selection = IMAGE_DIR / "0-persona-selection.png"
    start_new_thought = IMAGE_DIR / "1-start-new-thought.png"
    thought_plan = IMAGE_DIR / "2-thought-plan.png"
    new_thought_ready = IMAGE_DIR / "3-new-thought-ready.png"
    research_start = IMAGE_DIR / "4-research-start.png"
    research_mock_results = IMAGE_DIR / "5-research-mock-results.png"
    research_evaluate = IMAGE_DIR / "6-research-evaluate.png"
    up_next_read = IMAGE_DIR / "7-up-next-read-from-journal.png"
    reading_from_journal = IMAGE_DIR / "8-reading-from-journal.png"
    up_next_write_journal = IMAGE_DIR / "9-up-next-write-in-journal.png"
    writing_in_journal = IMAGE_DIR / "10-writing-in-journal.png"
    up_next_create_art = IMAGE_DIR / "11-create-art.png"
    creating_art = IMAGE_DIR / "12-begin-crafting-art.png"
    rendering_image = IMAGE_DIR / "13-rendering-image.png"
    up_next_write_blog = IMAGE_DIR / "14-up-next-write-blog.png"
    writing_blog = IMAGE_DIR / "15-writing-blog.png"
    up_next_post_on_social = IMAGE_DIR / "16-up-next-post-on-social.png"
    posting_on_social = IMAGE_DIR / "17-posting-on-social.png"
    generated_art = IMAGE_DIR / "generated-art.png"
    sequence = IMAGE_DIR / "sequence.png"


def main():
    st.subheader('A deep dive into one "Thought"')

    with st.expander("Sequence of a Thought"):
        st.image(str(Images.sequence))
        st.write(
            "Main code that implement this process "
            "https://github.com/msull/consciousness-sim/blob/6ab239a5fc2125f"
            "3b7b7b60a846829cf55ccd6a9/local_utils/brainv2.py#L632-L707"
        )
    st.write(
        "Prompt Templates: [Link](https://github.com/msull/consciousness-sim/blob/"
        "6ab239a5fc2125f3b7b7b60a846829cf55ccd6a9/local_utils/v2/prompts.py)"
    )

    st.write(
        "Thought `20231012161723yjliiv` was undertaken by persona Lucas Blackthorn, "
        "and was the last thought performed by the system before the Hackathon access ended."
    )
    st.subheader("Initiating the thought...")
    render_thought_initiation()
    st.divider()
    st.subheader("A task is chosen...")
    render_new_thought()
    st.divider()
    st.subheader("Executing the plan...")
    render_plan_execution()


def render_thought_initiation():
    cols = iter(st.columns((2, 1)))
    with next(cols):
        st.write(
            "The process begins by selecting one of the defined Personas and triggering a thought. "
            'The user can provide a "nudge" to help focus the thought during task selection; in this case, no such'
            '"nudge" was provided.'
        )

    with next(cols):
        st.image(str(Images.persona_selection), caption="Selecting the persona")

    st.write(
        "Now the system generates a task as the persona. "
        "The prompt sent to GPT-4 gives the details of the persona, recently completed tasks, "
        "details on the available actions the system can take, and so on, and asks them to come up with "
        "a task they can complete using those actions, and a rationale for why they are doing it."
    )
    st.image(str(Images.start_new_thought), caption="Starting the new thought")
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.task_creation_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.task_creation_response)


def render_new_thought():
    st.write(
        '> "I will write a detailed blog post about Beholders, incorporating their history, abilities, '
        "characteristics, my personal experiences, and an original illustration. "
        'After publishing the blog post, I will share it on social media for my followers to read."'
    )
    st.write(
        "The system saw the recently completed action of a social media post teasing an upcoming Beholder "
        "blog entry, and decided to write that entry now."
    )
    st.write(
        "The response includes a plan on how to complete the task using the available actions, in Markdown format. This is now sent off to GPT-4 to be turned into a JSON plan, for easier processing."
    )

    _, c, _ = st.columns(3)
    with c:
        st.image(str(Images.thought_plan))
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.create_json_plan_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.create_json_plan_response)
    st.write("")
    st.write("")
    st.write("**With a plan in hand, the system is now ready to execute the steps to achieve the selected task:**")
    st.image(str(Images.new_thought_ready))


def render_plan_execution():
    st.write(
        "The system now proceeds through each of the defined steps of the plan. Each step involves doing some specific "
        'taskand ends by updating the Thought "Context." '
        'This "Context" begins as an empty string and is the only '
        "information carried forward between steps of the plan. "
        "Sometimes the LLM is responsible for updating it, other times the action "
        "will cause it to be updated in a specific way."
    )
    st.write("### QueryForInfo")
    st.write("> Gather detailed information about Beholders - their history, abilities, and characteristics")
    st.write(
        "Querying involves generating questions to research, researching answers to those questions, "
        "and then evaluating that research as the Persona and updating the Context."
    )
    c1, c2 = st.columns((3, 1))
    with c1:
        with st.expander("Generate Questions - Full Prompt"):
            st.write("The complete prompt sent to GPT-4")
            st.code(deep_dive_text.research_generate_questions_prompt)
        with st.expander("Generate Questions Response"):
            st.code(deep_dive_text.research_generate_questions_response)
        with st.expander("Generate Answers via GPT-4 - Full Prompt"):
            st.write("The complete prompt sent to GPT-4")
            st.code(deep_dive_text.research_generate_answers_prompt)
        with st.expander("Generate Answers Response"):
            st.code(deep_dive_text.research_generate_answers_prompt)
        with st.expander("Evaluate Research - Full Prompt"):
            st.write("The complete prompt sent to GPT-4")
            st.code(deep_dive_text.research_interpret_prompt)
        with st.expander("Updated Context Response"):
            st.code(deep_dive_text.research_interpret_response)
    with c2:
        st.image(str(Images.research_start))
        st.image(str(Images.research_mock_results))
        st.image(str(Images.research_evaluate))

    st.write("### ReadFromJournal")
    st.write("> Refresh my memory about my personal experiences and encounters with Beholders in my past D&D campaigns")
    st.write(
        "For this action the latest 3 journal entries the Persona has authored are gathered and sent along with the "
        "current context to GPT-4, so that it can add any other details from the "
        "journal into the context that it wishes"
    )
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.read_from_journal_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.read_from_journal_response)

    st.write("### WriteInJournal")
    st.write("> Organize the information and my personal anecdotes into a cohesive narrative")
    st.write("Here the Persona writes a new Journal entry; the contents of this overwrite the existing Context.")
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.write_journal_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.write_journal_response)

    st.write("### CreateArt")
    st.write(
        "> Generate an illustration of a Beholder, capturing its unique features to enhance the visual appeal of the blog post"
    )
    st.write(
        "First a detailed description of the Art is generated, then named, "
        "then finally sent to stable-diffusion-xl to be rendered"
    )
    c1, c2 = st.columns((3, 1))
    with c1:
        with st.expander("Creating Art - Full Prompt"):
            st.write("The complete prompt sent to GPT-4")
            st.code(deep_dive_text.create_art_prompt)
        with st.expander("Creating Art Response"):
            st.code(deep_dive_text.create_art_response)
        with st.expander("Naming Artwork - Full Prompt"):
            st.write("The complete prompt sent to GPT-4")
            st.code(deep_dive_text.title_art_prompt)
        with st.expander("Naming Artwork Response"):
            st.code(deep_dive_text.title_art_response)
    with c2:
        st.image(str(Images.creating_art))
        st.image(str(Images.rendering_image))
    st.image(str(Images.generated_art))
    st.write("The description of the generated artwork is added to the Context")

    st.write("### WriteBlogPost")
    st.write(
        "> Craft a long format blog post, incorporating the information, personal experiences, and the illustration to provide an immersive exploration of Beholders"
    )
    st.write("Next, the blog post itself is written; the contents are added to the Context")
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.write_blog_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.write_blog_response)

    st.write("### PostOnSocial")
    st.write("> Share a link to the newly published blog post, inviting followers to delve into the world of Beholders")
    st.write("Finally, a social media posting promoting the blog is written; the contents are added to the Context")
    with st.expander("Full Prompt"):
        st.write("The complete prompt sent to GPT-4")
        st.code(deep_dive_text.write_social_prompt)
    with st.expander("Full Response"):
        st.code(deep_dive_text.write_social_response)


if __name__ == "__main__":
    main()
