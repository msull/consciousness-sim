import json
import random
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import streamlit as st
from PIL import Image
from pydantic import BaseModel, Field
from pydantic.v1 import BaseSettings
from wordcloud import STOPWORDS, WordCloud

from local_utils.brain import Brain, StartNewThoughtResponse
from local_utils.session_data import BaseSessionData
from local_utils.settings import StreamlitAppSettings

st.set_page_config("Conciousness Simulator", layout="wide")


class ThoughtData(BaseSessionData):
    thought_model: str = ""
    trigger_new_thought: bool = False
    new_thought: Optional[StartNewThoughtResponse] = None
    thought_complete: bool = False
    thought_had_error: bool = False
    thought_status_msgs: list[str] = Field(default_factory=list)

    def add_thought_status_msg(self, msg: str):
        self.thought_status_msgs.append(msg)
        self.save_to_session_state()

    def get_thought_status(self) -> Literal["running", "complete", "error"]:
        if self.thought_had_error:
            return "error"
        elif self.thought_complete:
            return "complete"
        return "running"


def trigger_chain_of_thought(session: ThoughtData, model: str):
    session.trigger_new_thought = True
    session.thought_model = model


def _dump(obj: BaseModel | BaseSettings) -> str:
    obj.model_dump_json()
    return json.dumps(json.loads(obj.model_dump_json()), indent=2, sort_keys=True)


def main():
    settings = StreamlitAppSettings.load()
    session_data = ThoughtData.init_session(settings.session_data)
    main_tab, knowledge_tab, thoughts_tab, debug_tab = st.tabs(["Main", "Knowledgebase", "Recent Thoughts", "Debug"])

    try:
        with knowledge_tab:
            render_knowledgebase(settings)

        with thoughts_tab:
            render_recent_thoughts(settings)

        with main_tab:
            render_main_functionality(settings, session_data)
    finally:
        with debug_tab:
            with st.expander("Settings"):
                st.code(_dump(settings))
            with st.expander("Session", expanded=True):
                st.button("Clear session data", on_click=_clear_thought, args=[session_data])
                st.code(_dump(session_data))


def render_main_functionality(settings: StreamlitAppSettings, session_data: ThoughtData):
    chat_col, sidebar = st.columns((2, 2))

    if not session_data.trigger_new_thought:
        with chat_col:
            with st.chat_message(name="user"):
                st.write("Awaiting thought...")
        with sidebar:
            with st.form("New thought"):
                model = st.selectbox("Thought model", ("gpt-3.5-turbo", "gpt-4"))
                if st.form_submit_button("Trigger new thought"):
                    trigger_chain_of_thought(session_data, model)
                    st.experimental_rerun()

            st.write("OR")
            thought_id = st.text_input("Load specific thought")
            st.write("OR")
            if not thought_id:
                sessions = sorted(
                    [x.name.removesuffix(".json") for x in settings.session_data.iterdir()],
                    reverse=True,
                )

                thought_id = st.selectbox("Select specific thought", [""] + sessions)

            if thought_id:
                session_data.clear_session()
                st.experimental_set_query_params(s=thought_id)
                st.experimental_rerun()

        st.stop()

    # brain = Brain(settings=settings, model="gpt-4")
    brain = Brain(settings=settings, model=session_data.thought_model)
    with sidebar:
        status = st.status("This thought chain", state=session_data.get_thought_status(), expanded=True)

        st.button("Clear thought", on_click=_clear_thought, args=[session_data])
        st.caption("This does not stop the thought from processing")
    status_msgs = status.container().empty()

    def _display_status_msgs():
        status_msgs.code("\n".join(session_data.thought_status_msgs))

    def _add_status_msg(msg: str):
        session_data.add_thought_status_msg(msg)
        _display_status_msgs()

    if not session_data.thought_status_msgs:
        _add_status_msg(f"Thought initiated {session_data.session_id}")

    _display_status_msgs()

    with chat_col:
        with st.chat_message(name="user"):
            with st.expander("Prompt for new thought chain"):
                st.write(brain.standard_chat_context())
        with st.chat_message(name="ai", avatar="assistant"):
            if not session_data.new_thought:
                with st.spinner("Selecting thought type..."):
                    session_data.new_thought = brain.get_new_thought_type()
                    _add_status_msg(f"Thought Type: {session_data.new_thought.thought_type}")

            st.write(str(session_data.new_thought))
            session_data.persist_session_state(settings.session_data)

    status.update(state="complete")
    _display_status_msgs()


def grey_color_func(word, font_size, position, orientation, random_state=None, **kwargs):
    return "hsl(0, 0%%, %d%%)" % random.randint(60, 100)


def _clear_thought(session: ThoughtData):
    session.clear_session()
    st.experimental_set_query_params(s="")


def render_recent_thoughts(settings: StreamlitAppSettings, n=5):
    Brain(settings=settings)
    here = Path(__file__).parent

    brain_mask = np.array(Image.open(str(here / "brain-outline.png")))
    settings.session_data.mkdir(exist_ok=True, parents=True)
    text = []
    for session_file in sorted([x.name for x in settings.session_data.iterdir()], reverse=True)[:n]:
        session_text = (settings.session_data / session_file).read_text()
        obj = ThoughtData.model_validate_json(session_text)
        text.append(obj.new_thought.rationale)

    stopwords = set(STOPWORDS)

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


def render_knowledgebase(settings: StreamlitAppSettings):
    pass


if __name__ == "__main__":
    main()
