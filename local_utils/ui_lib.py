import json
from datetime import timedelta

import streamlit as st
from logzero import logger
from pydantic import BaseModel, TypeAdapter
from pydantic.v1 import BaseSettings

from local_utils.brainv2 import BrainV2, MappingMemory, OutputMemoryInterface
from local_utils.session_data import BaseSessionData
from local_utils.settings import StreamlitAppSettings
from local_utils.v2.personas import load_default_personas
from local_utils.v2.thoughts import Thought, ThoughtMemory


def check_or_x(value: bool) -> str:
    return "✅" if value else "❌"


@st.cache_resource
def setup_thought_memory() -> ThoughtMemory:
    settings = StreamlitAppSettings.load()
    return ThoughtMemory(table_name=settings.dynamodb_thoughts_table)


# @st.cache_resource
def setup_output_memory() -> OutputMemoryInterface:
    settings = StreamlitAppSettings.load()
    persona_manager = load_default_personas()
    return MappingMemory(
        table_name=settings.dynamodb_thoughts_table,
        persona_manager=persona_manager,
        bucket_name=settings.s3_data_bucket,
        web_url=settings.s3_web_address,
        prefix="images",
    )


def setup_brain() -> BrainV2:
    return BrainV2(
        logger=logger,
        output_memory=setup_output_memory(),
        thought_memory=setup_thought_memory(),
        personas=load_default_personas(),
    )


@st.cache_data(ttl=timedelta(seconds=5))
def _list_recent_thoughts(num: int) -> list[dict]:
    logger.info("Getting recent thoughts from memory")
    thoughts = setup_thought_memory().list_recently_completed_thoughts(num)
    return [x.model_dump() for x in thoughts]


def list_recent_thoughts(num=25) -> list[Thought]:
    ta = TypeAdapter(list[Thought])
    return ta.validate_python(_list_recent_thoughts(num))


@st.cache_data(ttl=timedelta(seconds=5))
def _list_incomplete_thoughts() -> list[dict]:
    logger.info("Getting incomplete thoughts from memory")
    thoughts = setup_thought_memory().list_incomplete_thoughts()
    return [x.model_dump() for x in thoughts]


def list_incomplete_thoughts() -> list[Thought]:
    ta = TypeAdapter(list[Thought])
    return ta.validate_python(_list_incomplete_thoughts())


def dump_model(obj: BaseModel | BaseSettings | list[BaseModel | BaseSettings]) -> str:
    if isinstance(obj, list):
        return json.dumps([json.loads(x.model_dump_json()) for x in obj], indent=2, sort_keys=True)
    else:
        return json.dumps(json.loads(obj.model_dump_json()), indent=2, sort_keys=True)


def create_tabs(idx: int):
    c = st.container()
    with c:
        return


def _hack_index() -> int:
    return st.session_state.get("debug-bn", 0)


def _incr_hack_index():
    st.session_state["debug-bn"] = _hack_index() + 1


def force_home_tab():
    _incr_hack_index()


def home_tab_hack():
    idx = _hack_index()

    for x in range(idx):
        st.empty()


def render_tabbar():
    home_tab_hack()
    return st.tabs(["Home", "AI Output Gallery", "Recent Thoughts", "Debug"])


def render_debug_tab(session: BaseSessionData):
    with st.expander("Settings"):
        st.code(dump_model(StreamlitAppSettings.load()))
    with st.expander("Session", expanded=True):
        st.button("Clear session data", on_click=session.clear_session)
        st.code(dump_model(session))
    if st.toggle("Show incomplete thoughts", key=f"incomplete-toggle-{_hack_index()}"):
        c1, c2 = st.columns((3, 1))
        with c2:
            form = st.form("Load incomplete")
        with form:
            st.write("Load an incomplete thought")
            st.warning("This can cause issues if multiple users or tabs have the same thought processing!")
            load_incomplete = st.text_input("Thought ID")
            submitted = st.form_submit_button("Load")

        with c1:
            st.dataframe([x.model_dump() for x in list_incomplete_thoughts()])
        if submitted:
            if not load_incomplete:
                form.error("Specify thought ID")
            else:
                session.clear_session()
                session.thought_id = load_incomplete
                force_home_tab()
                st.experimental_rerun()
