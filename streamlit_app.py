import re
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import streamlit as st
from dateutil.tz import tzutc
from PIL import Image
from pydantic import Field
from wordcloud import STOPWORDS, WordCloud

from local_utils import ui_lib as ui
from local_utils.brainv2 import (
    ActionCallback,
    ArtworkDoesNotExist,
    BlogEntry,
    BrainV2,
    JournalEntry,
    PieceOfArt,
    SocialPost,
)
from local_utils.session_data import BaseSessionData
from local_utils.v2.personas import Persona
from local_utils.v2.thoughts import Thought

st.set_page_config("Conciousness Simulator", initial_sidebar_state="collapsed")


class SessionData(BaseSessionData):
    session_started: datetime = Field(default_factory=datetime.now)
    initialize_new_thought: bool = False
    continue_thought: bool = False
    initialize_thought_persona: Optional[Persona] = None
    initialize_thought_nudge: Optional[str] = None
    thought_id: Optional[str] = None
    thought: Optional[Thought] = None
    last_full_response: Optional[str] = None


def main(session: SessionData):
    brain = ui.setup_brain()

    main_tab, ai_output_tab, thoughts_tab, debug_tab = ui.render_tabbar()

    try:
        with ai_output_tab:
            render_ai_output(brain)

        with thoughts_tab:
            render_recent_thoughts(brain)

        with main_tab:
            st.header("Consciousness Simulator")

            intro = """
                The *Consciousness Simulator* is designed to simulate AI-driven thought processes and tasks in an interactive environment. Here's how it works:
                
                - **Tools and Interactions**: The AI is equipped with a diverse toolkit to interact with the world. From querying information, crafting art, keeping a journal, to publishing blog posts, the AI has been designed to have multi-dimensional engagements.
                
                - **Starting a Thought**: Initiate a thought by selecting a **Persona**. This persona shapes the AI's approach, bringing unique characteristics and inclinations to the table.
                
                - **Decision Making**: Once initiated, the AI considers various factors to decide on its next task. It factors in recent activities, inherent personality traits, set goals, and an optional provided "nudge" to determine the best course of action. The AI's available tools play a pivotal role in this decision-making process.
                
                - **Planning & Execution**: After settling on a task, the AI plans the steps needed to achieve it. Watch as it maps out its strategy and then dives into execution, harnessing its vast toolkit.
                
                - **Exploring Outputs**: The app provides dedicated tabs where you can view the tangible results of the AI's endeavors. Visit the output tab to witness its artistic creations and introspective entries.
            """  # noqa: E501

            intro = dedent(intro)

            if session.thought:
                for x in range(session.thought.steps_completed + 1):
                    st.empty()

            container = st.container()
            if not (session.initialize_new_thought or session.thought_id):
                with container:
                    st.write(intro)
                    render_thought_selection(brain, session)
            else:
                with container:
                    with st.expander("Site intro"):
                        st.write(intro)
                    render_active_thought(brain, session)
    finally:
        with debug_tab:
            ui.render_debug_tab(session)


def render_active_thought(brain: BrainV2, session: SessionData):
    proceed_automatically = st.toggle(
        "Allow thought to proceed automatically",
        help=(
            "When disabled, the user must click to continue the thought "
            "for every step; when enabled the thought will proceed without user interaction"
        ),
    )
    chat_col, info_col = st.columns((3, 1))

    if session.thought_id:
        thought = brain.thought_memory.read_thought(session.thought_id)
        persona = brain.personas.get_persona_by_name(thought.persona_name)
    else:
        thought = None
        persona = session.initialize_thought_persona

    with info_col:
        st.image(str(persona.image))
        st.caption("Image generated by stable-diffusion-xl from GPT-4 description", help=persona.physical_description)
        st.write(f"**{persona.name}**")
        st.write(persona.short_description)
        st.caption("Persona generated by GPT-4")

    with info_col:
        with st.expander("Raw Thought Data"):
            obj_dump_placeholder = st.empty()

    def _display_thought(display: Thought):
        if display:
            obj_dump_placeholder.code(ui.dump_model(thought))

    with chat_col:
        with st.chat_message("ai", avatar=str(persona.avatar)):
            thought_status = st.status("Starting a new thought...")
            task_placeholder = st.empty()
            with thought_status:
                st.info("Generating a new task")
                if thought is None:
                    thought = brain.start_new_thought(
                        session.initialize_thought_persona, session.initialize_thought_nudge
                    )
                    _display_thought(thought)
                    session.thought_id = thought.thought_id
                st.write(thought.it_rationale)
                with task_placeholder:
                    st.write(thought.initial_thought)
                st.info("Developing task plan")
                thought_status.update(label="Generating plan for task...")
                if not thought.plan:
                    thought = brain.develop_thought_plan(thought)
                    _display_thought(thought)
                thought_status.update(label="Decided upon a task")
                st.code(ui.dump_model(thought.plan))
            if thought.generated_content_ids:
                ids = sorted(
                    [x for x in thought.generated_content_ids],
                    key=lambda x: x.split(":", maxsplit=1)[1],
                )
                st.subheader("Content Produced")
                for this_id in ids:
                    content = brain.output_memory.read_content_with_type(this_id)
                    with st.expander(content.get_label()):
                        st.write(content.format())
                        if isinstance(content, PieceOfArt):
                            st.image(brain.output_memory.read_art_contents(content))

    with chat_col:
        steps_completed = thought.steps_completed
        if not thought.thought_complete:
            st.divider()
            st.subheader("Up Next")
            try:
                next_step = thought.plan[steps_completed]
            except IndexError:
                st.error("Ran out of steps in plan but thought not marked complete!")
                st.stop()

            st.write(f"**{next_step.tool_name}: {next_step.purpose}**")

            def clicked():
                session.continue_thought = True

            if proceed_automatically:
                clicked()

            if not session.continue_thought:
                st.button("Continue thought", use_container_width=True, type="primary", on_click=clicked)

            continue_thought_placeholder = st.empty()

            with st.expander("Current thought context", expanded=True):
                st.write(thought.context)
            st.divider()
        else:
            st.write("This thought has completed!")
            st.button("Close thought", on_click=session.clear_session)
            with st.expander("Final thought context"):
                st.write(thought.context)
            session.continue_thought = False

        st.subheader("Plan")

        active_step_placeholder = None
        current_task = "Continuing thought..."
        for idx, step in enumerate(thought.plan):
            step_num = idx + 1
            if step_num > steps_completed:
                # step not completed yet
                st.write(f"{step_num}. {step.tool_name}: {step.purpose}")
                if active_step_placeholder is None:
                    # placeholder where work will occur
                    current_task = f"Performing action - {step.tool_name}"
                    active_step_placeholder = st.empty()
            else:
                st.write(f"{step_num}. ~{step.tool_name}: {step.purpose}~")

    if session.continue_thought:
        session.continue_thought = False

        with active_step_placeholder:
            st.info("Step in progress...")
        with continue_thought_placeholder:
            status = st.status(current_task, expanded=True)

            def _callback(data: ActionCallback):
                if data.status:
                    status.update(label=f"{current_task}: {data.status}")
                if data.details:
                    status.update(expanded=True)
                    status.write(data.details)

            with status:
                _, full_response = brain.continue_thought(thought, _callback)
                st.info("Action complete!")

            session.last_full_response = full_response
            st.experimental_rerun()
    else:
        if active_step_placeholder:
            with active_step_placeholder:
                st.info("Waiting for user to continue thought...")

    _display_thought(thought)


def render_thought_selection(brain: BrainV2, session: SessionData):
    # smh = setup_state_machine_helper()
    # session.thought_id = smh.trigger_execution()
    # with st.spinner("Waiting for New Import to be visible in database"):
    #     load_thought_data(session.thought_id, num_attempts=10)

    persona_name = st.selectbox("Persona", brain.personas.list_persona_names())
    persona = brain.personas.get_persona_by_name(persona_name)

    def _start_new():
        session.initialize_new_thought = True
        session.initialize_thought_nudge = user_nudge
        session.initialize_thought_persona = persona

    c1, c2 = st.columns(2)
    with c1:
        st.write(persona.format())
        st.caption("Persona generated by GPT-4")
    with c2:
        st.image(persona.image.read_bytes())
        st.caption("Image generated by stable-diffusion-xl from GPT-4 description", help=persona.physical_description)

    st.write("**Start new thought or view a recently completed one**")
    user_nudge = st.text_input("Nudge thought", max_chars=100) or None
    st.button("Begin", on_click=_start_new, use_container_width=True)

    st.divider()
    render_load_prior_thought_selection(brain, persona, session)


def render_load_prior_thought_selection(brain: BrainV2, persona: Persona, session: SessionData):
    def _load_existing(thought_id: str):
        session.thought_id = thought_id

    display_header = True
    persona_name = persona.name
    recent = [x for x in ui.list_recent_thoughts() if x.persona_name == persona_name]

    if recent:
        for data in recent:
            if data.persona_name != persona_name:
                continue
            display_data = data.model_dump(include={"thought_id", "descr", "version"})
            display_data["done"] = ui.check_or_x(data.thought_complete)
            columns = iter(st.columns(len(display_data) + 1))
            for k, v in display_data.items():
                with next(columns):
                    if display_header:
                        st.subheader(k)
                    st.write(v)
            with next(columns):
                if display_header:
                    st.button("Refresh")
                st.button("Load", key=f"load-{data.thought_id}", on_click=_load_existing, args=(data.thought_id,))
            if display_header:
                display_header = False
    else:
        st.write("*No recent thoughts*")


def render_ai_output(brain: BrainV2):
    media_types = st.multiselect("Filter Media Types", ("Art", "Journal Entries", "Social Posts", "Blog Posts"))
    persona_name = st.selectbox("Filter Persona", [""] + brain.personas.list_persona_names()) or None

    if not media_types:
        get_art = True
        get_journal = True
        get_blog = True
        get_social = True
    else:
        get_art = "Art" in media_types
        get_journal = "Journal Entries" in media_types
        get_blog = "Blog Posts" in media_types
        get_social = "Social Posts" in media_types

    output_entries = []
    if get_art:
        output_entries.extend(brain.output_memory.get_latest_art_pieces(persona_name, num=10))
    if get_journal:
        output_entries.extend(brain.output_memory.get_latest_journal_entries(persona_name, num=10))
    if get_blog:
        output_entries.extend(brain.output_memory.get_latest_blog_entries(persona_name, num=10))
    if get_social:
        output_entries.extend(brain.output_memory.get_latest_social_posts(persona_name, num=10))

    sorted_entries = sorted(output_entries, key=lambda x: x.date_added, reverse=True)
    for entry in sorted_entries:
        match entry:
            case JournalEntry():
                render_ai_output_journal(brain, entry)
            case PieceOfArt():
                render_ai_output_art(brain, entry)
            case BlogEntry():
                render_ai_output_blog(brain, entry)
            case SocialPost():
                render_ai_output_social(brain, entry)
            case _:
                st.error("UNHANDLED OUTPUT ENTRY")


def render_ai_output_blog(brain: BrainV2, entry: BlogEntry):
    persona = brain.personas.get_persona_by_name(entry.persona_name)
    with st.chat_message("ai", avatar=str(persona.avatar)):
        st.write(f"**{persona.name} published a new blog post!**")
        date_as_pacific = entry.date_added.replace(tzinfo=tzutc()).astimezone(ZoneInfo("US/Pacific"))
        st.write(date_as_pacific.strftime("%d %b %Y %l:%M %p"))
    with st.expander(f"View blog post: **{entry.title}**"):
        if st.toggle("View Raw", key=entry.title):
            st.code(entry.format())
        else:
            st.subheader(entry.title)
            st.caption(f"Written by: {entry.persona_name}")
            st.caption("ALL CONTENT GENERATED BY AI")

            chunks = split_on_images(entry.content)
            for idx, chunk in enumerate(chunks):
                st.write(chunk)
                if entry.generated_art and idx + 1 <= len(entry.generated_art):
                    st.image(brain.output_memory.read_art_contents(entry.generated_art[idx]))

            # output and remaining images
            if entry.generated_art and idx + 1 < len(entry.generated_art):
                for art in entry.generated_art[idx:]:
                    st.image(brain.output_memory.read_art_contents(art))
            # st.write(entry.format())
    st.caption("All content generated by AI")
    st.divider()


def render_ai_output_art(brain: BrainV2, art: PieceOfArt):
    persona = brain.personas.get_persona_by_name(art.persona_name)
    try:
        art_contents = brain.output_memory.read_art_contents(art)
    except ArtworkDoesNotExist:
        art_contents = None

    with st.chat_message("ai", avatar=str(persona.avatar)):
        st.write(f"**{persona.name} generated new art!**")
        date_as_pacific = art.date_added.replace(tzinfo=tzutc()).astimezone(ZoneInfo("US/Pacific"))
        st.write(date_as_pacific.strftime("%d %b %Y %l:%M %p"))
        if art_contents:
            st.image(art_contents, width=150)

    with st.expander(f"View generated art: **{art.title}**"):
        c1, c2 = st.columns((1, 2))
        with c1:
            st.caption(art.art_descr)
            st.caption("Art description generated by GPT-4")
        with c2:
            st.write(f"**{art.title}**")
            if art_contents:
                st.image(art_contents)
            else:
                st.write("Artwork not yet rendered")
    st.caption("All content generated by AI")
    st.divider()


def render_ai_output_journal(brain: BrainV2, entry: JournalEntry):
    persona = brain.personas.get_persona_by_name(entry.persona_name)
    with st.chat_message("ai", avatar=str(persona.avatar)):
        st.write(f"**{persona.name} wrote in their journal...**")
        date_as_pacific = entry.date_added.replace(tzinfo=tzutc()).astimezone(ZoneInfo("US/Pacific"))
        st.write(date_as_pacific.strftime("%d %b %Y %l:%M %p"))
    with st.expander("View journal entry"):
        st.write(entry.content)
    st.caption("All content generated by AI")
    st.divider()


def render_ai_output_social(brain: BrainV2, entry: SocialPost):
    persona = brain.personas.get_persona_by_name(entry.persona_name)
    with st.chat_message("ai", avatar=str(persona.avatar)):
        st.write(f"**{persona.name} posted on social media!**")
        date_as_pacific = entry.date_added.replace(tzinfo=tzutc()).astimezone(ZoneInfo("US/Pacific"))
        st.write(date_as_pacific.strftime("%d %b %Y %l:%M %p"))
    st.write(entry.content)
    if entry.generated_art:
        st.image(brain.output_memory.read_art_contents(entry.generated_art))

    st.caption("All content generated by AI")
    st.divider()


def render_recent_thoughts(brain: BrainV2):
    here = Path(__file__).parent

    brain_mask = np.array(Image.open(str(here / "brain-outline.png")))
    text = []

    persona_name = st.selectbox(
        "View thoughts for Persona", ["blend thoughts from all"] + brain.personas.list_persona_names()
    )
    if persona_name == "blend thoughts from all":
        st.info("Produces a wordcloud using the 3 latest journal entries from each persona")
        persona_names = brain.personas.list_persona_names()
    else:
        st.info(f"Produces a wordcloud using the 3 latest journal entries from {persona_name}")
        persona_names = [persona_name]

    for persona_name in persona_names:
        for entry in brain.output_memory.get_latest_journal_entries(num=3, persona_name=persona_name):
            text.append(entry.content)

    stopwords = set(STOPWORDS)
    stopwords.add("article")
    stopwords.add("articles")

    if text:
        wc = WordCloud(
            max_words=2000,
            scale=2,
            background_color="white",
            stopwords=stopwords,
            contour_width=1,
            contour_color="black",
            # color_func=grey_color_func,
            mask=brain_mask,
        )

        # generate word cloud
        wc.generate("\n".join(text))
        wordcloud = wc.to_array()
        st.image(wordcloud)
    else:
        st.write("No recent thoughts")


def split_on_images(content_str):
    # The regex you provided
    regex = r"^!\[.*?\]\(.*?\)$"

    # This splits the content based on image identifiers. We're using the re.split function.
    # The re.MULTILINE flag allows the start-of-line (^) and end-of-line ($) to match each line of the input string.
    chunks = re.split(regex, content_str, flags=re.MULTILINE)

    # Remove any empty strings from the chunks
    chunks = [chunk for chunk in chunks if chunk.strip() != ""]

    return chunks


def extract_image_titles(content_str):
    # This regex is to capture the titles inside the image identifiers
    regex = r"^!\[(.*?)\]\(.*?\)$"

    # The re.findall function finds all matches of the regex in the string.
    # The re.MULTILINE flag is used again to match each line of the input string.
    titles = re.findall(regex, content_str, flags=re.MULTILINE)

    return titles


if __name__ == "__main__":
    session = SessionData.init_session()
    session.save_to_session_state()
    main(session)
