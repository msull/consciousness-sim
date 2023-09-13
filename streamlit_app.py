import json
from datetime import datetime
from typing import Optional

import streamlit as st
from logzero import logger
from pydantic import BaseModel, Field
from pydantic.v1 import BaseSettings

from local_utils.session_data import BaseSessionData
from local_utils.settings import StreamlitAppSettings
from local_utils.v2.thoughts import Thought, ThoughtData, ThoughtMemory

st.set_page_config("Conciousness Simulator", initial_sidebar_state="collapsed", layout="wide")

settings = StreamlitAppSettings.load()
logger.debug(settings.json)
DEBUG = st.sidebar.checkbox("Debug mode")


def check_or_x(value: bool) -> str:
    return "✅" if value else "❌"


@st.cache_resource
def setup_memory() -> ThoughtMemory:
    return ThoughtMemory(table_name=settings.dynamodb_thoughts_table)


memory = setup_memory()


class SessionData(BaseSessionData):
    session_started: datetime = Field(default_factory=datetime.now)
    thought_id: Optional[str] = None
    thought: Optional[Thought] = None


def _dump(obj: BaseModel | BaseSettings) -> str:
    obj.model_dump_json()
    return json.dumps(json.loads(obj.model_dump_json()), indent=2, sort_keys=True)


def _clear_thought(session: SessionData):
    session.clear_session()
    # st.experimental_set_query_params(s="")


def main(session: SessionData):
    main_tab, blog, thoughts_tab, debug_tab = st.tabs(["Home", "AI Generated Blog", "Recent Thoughts", "Debug"])
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
            with st.expander("Settings"):
                st.code(_dump(settings))
            with st.expander("Session", expanded=True):
                st.button("Clear session data", on_click=_clear_thought, args=[session])
                st.code(_dump(session))


def render_active_thought(session):
    pass


def render_thought_selection(session: SessionData):
    st.write("Start new thought")

    def _start_new():
        memory.write_new_thought(ThoughtData(descr="My first thought!"))
        # smh = setup_state_machine_helper()
        # session.thought_id = smh.trigger_execution()
        # with st.spinner("Waiting for New Import to be visible in database"):
        #     load_thought_data(session.thought_id, num_attempts=10)

    st.button("Begin", on_click=_start_new)
    # st.subheader("or")
    st.divider()
    st.write("Load previous thought")
    render_resume_thought_selection(session)


def render_resume_thought_selection(session: SessionData):
    def _load_existing(thought_id: str):
        session.thought_id = thought_id

    display_header = True
    if recent := memory.list_recent_thoughts(25):
        for data in recent:
            display_data = data.model_dump(include={"thought_id", "descr", "version"})
            display_data["done"] = check_or_x(data.thought_complete)
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
    if DEBUG:
        with st.expander("Session state"):
            st.code(session.json(indent=2))
