import random
from datetime import datetime
from pathlib import Path
from string import ascii_lowercase
from typing import Optional, Type, TypeVar

import streamlit as st
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


def date_id(now=None):
    now = now or datetime.utcnow()
    return now.strftime("%Y%m%d%H%M%S") + "".join(random.choices(ascii_lowercase, k=6))


class BaseSessionData(BaseModel):
    session_id: str = Field(default_factory=date_id)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        self.save_to_session_state()

    def save_to_session_state(self):
        for k, v in self.model_dump().items():
            st.session_state[k] = v

    def persist_session_state(self, session_dir: Path, set_query_param=True):
        if set_query_param:
            st.experimental_set_query_params(s=st.session_state.session_id)

        path = session_dir / (st.session_state.session_id + ".json")
        path.write_text(self.model_dump_json())

    def clear_session(self):
        st.experimental_set_query_params()
        for field_name, field in self.model_fields.items():
            if field_name in st.session_state:
                del st.session_state[field_name]

    def switch_sessions(self, session_dir: Path, new_session_id: str):
        self.clear_session()
        path = session_dir / (new_session_id + ".json")
        if path.exists():
            incoming_session = self.model_validate_json(path.read_text())
            for field_name in self.model_fields:
                setattr(self, field_name, getattr(incoming_session, field_name))
            self.save_to_session_state()

    @classmethod
    def init_session(cls: Type[T], session_dir: Optional[Path] = None) -> T:
        # if we have a saved sessions dir and a query param, check correct session is loaded
        query_session = st.experimental_get_query_params().get("s")
        if query_session:
            query_session = query_session[0]
        if session_dir and query_session:
            # we have a session dir and session id -- is it already loaded?
            if st.session_state.get("session_id") != query_session:
                # no, the requested session isn't loaded -- clear out any existing session data
                for field_name, field in cls.model_fields.items():
                    if field_name in st.session_state:
                        del st.session_state[field_name]

        session: Optional[T] = None
        if st.session_state.get("session_id"):
            # since we have a session id in the session_state already, we've done an init and can load the data
            session = cls.parse_obj(st.session_state)
        elif session_dir and query_session:
            path = session_dir / (query_session + ".json")
            if path.exists():
                session = cls.model_validate_json(path.read_text())

        if not session:
            session: T = cls(session_dir=session_dir)
        session.save_to_session_state()
        return session
