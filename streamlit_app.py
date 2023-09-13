from datetime import datetime
from typing import Optional

import streamlit as st
from pydantic import Field

from local_utils import ui_lib as ui
from local_utils.session_data import BaseSessionData
from local_utils.settings import StreamlitAppSettings
from local_utils.v2.thoughts import Thought, ThoughtData

st.set_page_config("Conciousness Simulator", initial_sidebar_state="collapsed", layout="wide")


class SessionData(BaseSessionData):
    session_started: datetime = Field(default_factory=datetime.now)
    thought_id: Optional[str] = None
    thought: Optional[Thought] = None


def main(session: SessionData):
    settings = StreamlitAppSettings.load()
    main_tab, blog, thoughts_tab, debug_tab = ui.render_tabbar()

    try:
        # with blog:
        #     render_blog(settings)
        #
        # with thoughts_tab:
        #     render_recent_thoughts(settings)

        with main_tab:
            container = st.container()
            if not session.thought_id:
                with container:
                    render_thought_selection(session)
            else:
                with container:
                    render_active_thought(session)
    finally:
        with debug_tab:
            ui.render_debug_tab(session, settings)


def render_active_thought(session):
    pass


def render_thought_selection(session: SessionData):
    st.write("Start new thought")

    def _start_new():
        with st.spinner("Triggering thought..."):
            thought = ui.setup_memory().write_new_thought(ThoughtData(descr="Thought triggered manually"))
            session.thought_id = thought.thought_id
        # smh = setup_state_machine_helper()
        # session.thought_id = smh.trigger_execution()
        # with st.spinner("Waiting for New Import to be visible in database"):
        #     load_thought_data(session.thought_id, num_attempts=10)

    st.button("Begin", on_click=_start_new)
    st.divider()
    st.write("Load previous thought")
    render_resume_thought_selection(session)


def render_resume_thought_selection(session: SessionData):
    def _load_existing(thought_id: str):
        session.thought_id = thought_id

    display_header = True
    if recent := ui.list_recent_thoughts():
        for data in recent:
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
