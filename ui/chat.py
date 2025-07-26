# chat_ui.py
import streamlit as st
import requests

st.set_page_config(page_title="LLM Task Manager", layout="centered")
st.title("🧠 Task Manager Chat with LLM")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

API_URL = "http://localhost:8000/chat"


def send_message_to_backend(user_input):
    res = requests.post(API_URL, json={"message": user_input})
    print(res)
    print(res.json())
    return res.json()


# Display chat history

def display_chat_history():
    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.chat_message("user").write(msg)
        else:
            st.chat_message("assistant").write(msg)


with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("You:", placeholder="Add a task, list tasks, mark complete...")
    submitted = st.form_submit_button("Send")
    if submitted and user_input:
        st.session_state.chat_history.append(("user", user_input))
        reply = send_message_to_backend(user_input)
        st.session_state.chat_history.append(("bot", reply))
        display_chat_history()
