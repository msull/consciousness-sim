from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st
from boto3.dynamodb.conditions import Key
from pydantic import Field

from local_utils import ui_lib as ui
from local_utils.brainv2 import PieceOfArt
from local_utils.session_data import BaseSessionData
from local_utils.v2.thoughts import Thought

st.set_page_config("Thought Browser", initial_sidebar_state="collapsed", layout="wide")


class SessionData(BaseSessionData):
    session_started: datetime = Field(default_factory=datetime.now)


@st.cache_resource
def get_all_thoughts(_brain) -> list[Thought]:
    complete_thoughts = _brain.thought_memory._query_to_thoughts(
        index="gsi1",
        key_condition=Key("gsi1pk").eq("t|COMPLETE"),
        # filter_expression=Attr("persona_name").eq(persona_name),
        ascending=True,
        limit=5000,
    )
    incomplete_thoughts = _brain.thought_memory._query_to_thoughts(
        index="gsi1",
        key_condition=Key("gsi1pk").eq("t|INCOMPLETE"),
        # filter_expression=Attr("persona_name").eq(persona_name),
        ascending=True,
        limit=5000,
    )
    return sorted(complete_thoughts + incomplete_thoughts, key=lambda x: x.created_at)


@st.cache_resource
def thoughts_for_persona(_brain, persona_name: str) -> list[Thought]:
    return [x for x in get_all_thoughts(_brain) if x.persona_name == persona_name]


@st.cache_resource
def art_for_persona(_brain, persona_name: str) -> list[PieceOfArt]:
    return _brain.output_memory.get_latest_art_pieces(persona_name=persona_name, num=1000)


def main(session: SessionData):
    st.header("Thought Browser")
    brain = ui.setup_brain()
    persona_name = st.selectbox("Choose a persona", [""] + brain.personas.list_persona_names())
    if not persona_name:
        return
    persona = brain.personas.get_persona_by_name(persona_name)
    thoughts = thoughts_for_persona(brain, persona_name)
    created_art = art_for_persona(brain, persona_name)
    cols = iter(st.columns((1, 3)))

    num_thoughts = len(thoughts)
    with next(cols):
        st.metric("Total Thoughts", num_thoughts)
        st.metric("Complete", len([x for x in thoughts if x.thought_complete]))
        st.metric("Incomplete", len([x for x in thoughts if not x.thought_complete]))

    with next(cols):
        toggle_cols = iter(st.columns(3))
        with next(toggle_cols):
            newest_first = st.toggle("Newest First", value=False)
        with next(toggle_cols):
            hide_incomplete = st.toggle("Hide Incomplete", value=True)
        with next(toggle_cols):
            nudged_only = st.toggle('"Nudged" thoughts only', value=False)
        st.divider()
        for idx, thought in enumerate(thoughts[:: -1 if newest_first else 1]):
            if hide_incomplete and not thought.thought_complete:
                continue
            if nudged_only and not thought.user_nudge:
                continue

            if newest_first:
                thought_num = num_thoughts - idx
            else:
                thought_num = idx + 1

            thought_col, art_col = st.columns(2)
            with thought_col:
                st.write(f"Thought {thought_num} of {num_thoughts}")
                if thought.thought_complete:
                    st.info("This thought completed " + thought.updated_at.isoformat())
                else:
                    if thought.plan:
                        st.warning(
                            f"This thought is incomplete; on step {thought.steps_completed +1} of {len(thought.plan)}"
                        )
                    else:
                        st.warning("This thought is incomplete; no plan developed")

                with st.chat_message(name="ai", avatar=str(persona.avatar)):
                    st.write(f"> {thought.initial_thought}")
                # st.write('"' + thought.initial_thought + '"')
                if thought.user_nudge:
                    st.caption(f'Thought was "nudged"\n> "{thought.user_nudge}"')

            with st.expander("Thought rationale"):
                st.write(thought.it_rationale)

            if st.toggle("View Full Thought Object", key=f"versions-for-{thought.thought_id}", value=False):
                num_versions = thought.version

                control_cols = iter(st.columns(3))
                with next(control_cols):
                    version = st.number_input(
                        "version",
                        min_value=1,
                        max_value=num_versions,
                        value=1,
                        key=f"view-version-for-{thought.thought_id}",
                    )

                if version == num_versions:
                    thought_obj = thought
                else:
                    thought_obj = brain.thought_memory.read_thought(thought.thought_id, version)

                df = pd.DataFrame(
                    [
                        {
                            "thoughtId": thought_obj.thought_id,
                            "version": thought_obj.version,
                            "complete": thought_obj.thought_complete,
                            "hasPlan": bool(thought_obj.plan),
                            "totalSteps": len(thought_obj.plan) if thought_obj.plan else None,
                            "stepsCompleted": thought_obj.steps_completed if thought_obj.plan else None,
                        }
                    ]
                )

                st.dataframe(df, hide_index=True)

                st.json(
                    thought_obj.model_dump_json(
                        exclude={
                            "thought_id",
                            "version",
                            "thought_complete",
                            "it_rationale",
                            "last_full_response",
                        }
                    )
                )
                st.divider()

            if thought.generated_content_ids:
                st.subheader("Content Produced")
                count_by_type = Counter([x.split(":")[0] for x in thought.generated_content_ids])
                metric_cols = iter(st.columns(len(count_by_type)))

                for k, v in sorted(count_by_type.items()):
                    with next(metric_cols):
                        st.metric(k, v)

                art_ids = [x.split(":")[1] for x in thought.generated_content_ids if x.startswith("PieceOfArt")]
                for art_id in art_ids:
                    art = next(x for x in created_art if x.get_content_id() == art_id)
                    # st.write(art)
                    with art_col:
                        st.image(brain.output_memory.get_art_content_location(art))

            st.divider()


if __name__ == "__main__":
    session = SessionData.init_session()
    session.save_to_session_state()
    main(session)
