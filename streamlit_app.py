from datetime import datetime
from time import sleep
from typing import Optional

import streamlit as st
from pydantic import Field

from local_utils import ui_lib as ui
from local_utils.brainv2 import BrainV2
from local_utils.session_data import BaseSessionData
from local_utils.v2.personas import Persona
from local_utils.v2.thoughts import Thought

st.set_page_config("Conciousness Simulator", initial_sidebar_state="collapsed", layout="wide")


class SessionData(BaseSessionData):
    session_started: datetime = Field(default_factory=datetime.now)
    initialize_new_thought: bool = False
    continue_thought: bool = False
    initialize_thought_persona: Optional[Persona] = None
    initialize_thought_nudge: Optional[str] = None
    thought_id: Optional[str] = None
    thought: Optional[Thought] = None


def main(session: SessionData):
    brain = ui.setup_brain()

    main_tab, blog, thoughts_tab, debug_tab = ui.render_tabbar()

    try:
        # with blog:
        #     render_blog(settings)
        #
        # with thoughts_tab:
        #     render_recent_thoughts(settings)

        with main_tab:
            container = st.container()
            if not (session.initialize_new_thought or session.thought_id):
                with container:
                    render_thought_selection(brain, session)
            else:
                with container:
                    render_active_thought(brain, session)
    finally:
        with debug_tab:
            ui.render_debug_tab(session)


def render_active_thought(brain: BrainV2, session: SessionData):
    chat_col, info_col = st.columns((3, 1))

    if session.thought_id:
        thought = brain.thought_memory.read_thought(session.thought_id)
        persona = brain.personas.get_persona_by_name(thought.persona_name)
    else:
        thought = None
        persona = session.initialize_thought_persona

    with info_col:
        st.image(str(persona.image))

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

    with chat_col:
        steps_completed = thought.steps_completed
        st.divider()
        if not thought.thought_complete:
            st.info("Active thought - proceed?")
            st.subheader("Up Next")
            try:
                next_step = thought.plan[steps_completed]
            except IndexError:
                st.error("Ran out of steps in plan but thought not marked complete!")
                st.stop()

            st.write(f"**{next_step.tool_name}: {next_step.purpose}**")

            def clicked():
                session.continue_thought = True

            if not session.continue_thought:
                st.button("Continue thought", use_container_width=True, type="primary", on_click=clicked)
            continue_thought_placeholder = st.empty()
        else:
            st.write("Thought complete")
            session.continue_thought = False

        st.divider()

        st.subheader("Plan")

        active_step_placeholder = None
        for idx, step in enumerate(thought.plan):
            step_num = idx + 1
            if step_num > steps_completed:
                # step not completed yet
                st.write(f"{step_num}. {step.purpose}")
                if active_step_placeholder is None:
                    # placeholder where work will occur
                    active_step_placeholder = st.empty()
            else:
                st.write(f"{step_num}. ~{step.purpose}~")
                with st.expander(f"Step {step_num} results"):
                    st.write(f"{step_num}. {step.purpose}")
                    st.write("stuff here")

    if session.continue_thought:
        with active_step_placeholder:
            st.info("Step in progress...")
        with continue_thought_placeholder:
            status = st.status("Continuing thought...")
            with status:
                st.write("Executing next action...")
                sleep(10)
                thought = brain.continue_thought(thought)
                _display_thought(thought)
                session.continue_thought = False
    else:
        with active_step_placeholder:
            st.info("Waiting for user to continue thought...")

    _display_thought(thought)


def render_thought_selection(brain: BrainV2, session: SessionData):
    st.write("Start new thought")

    # smh = setup_state_machine_helper()
    # session.thought_id = smh.trigger_execution()
    # with st.spinner("Waiting for New Import to be visible in database"):
    #     load_thought_data(session.thought_id, num_attempts=10)

    persona_name = st.selectbox("Persona for thought", brain.personas.list_persona_names())
    persona = brain.personas.get_persona_by_name(persona_name)

    user_nudge = st.text_input("Nudge thought", max_chars=100) or None

    def _start_new():
        session.initialize_new_thought = True
        session.initialize_thought_nudge = user_nudge
        session.initialize_thought_persona = persona

    st.button("Begin", on_click=_start_new, use_container_width=True, type="primary")
    c1, c2 = st.columns(2)
    with c1:
        st.write(persona.format())
        st.caption("Persona generated by GPT-4")
    with c2:
        st.image(persona.image.read_bytes())
        st.caption("Image generated by stable-diffusion-xl from GPT-4 description", help=persona.physical_description)
    st.divider()
    render_load_prior_thought_selection(brain, persona, session)


def render_load_prior_thought_selection(brain: BrainV2, persona: Persona, session: SessionData):
    def _load_existing(thought_id: str):
        session.thought_id = thought_id

    display_header = True
    recent = [x for x in ui.list_recent_thoughts() if x.persona == persona]

    if recent:
        for data in recent:
            if data.persona != persona:
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


if __name__ == "__main__":
    session = SessionData.init_session()
    session.save_to_session_state()
    main(session)
