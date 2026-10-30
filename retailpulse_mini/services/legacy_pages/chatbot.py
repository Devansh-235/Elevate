import uuid

import streamlit as st

from database.connection import DatabaseError
from database.queries import save_chat
from services.chatbot_service import ChatbotError, execute_select, explain_results, generate_query

st.title('Ask Elevate')
st.write('Ask a business question. Inspect the SQL and the actual MySQL results behind the answer.')
st.caption('Questions use all stored sales unless you specify filters in your question. '
           'Your question, the schema and recent questions/SQL are sent to Groq. Sales rows stay local; '
           'explanations are formatted directly from MySQL results.')
st.session_state.setdefault('conversation', [])
st.session_state.setdefault('chat_session_id', str(uuid.uuid4()))
with st.expander('Try a question'):
    st.write('• What is the total revenue?\n\n• Which five products generated the highest profit?'
             '\n\n• Show monthly sales trends.\n\n• Which category is underperforming?'
             '\n\n• Compare sales across different regions.\n\n• Which month generated the highest revenue?')
if st.button('Clear recent conversation'):
    st.session_state.conversation = []
    st.session_state.chat_session_id = str(uuid.uuid4())
    st.rerun()


def show_answer(item):
    with st.chat_message('assistant'):
        st.write(item['answer'])
        with st.expander('Generated SQL and parameters'):
            st.code(item['sql'], language='sql')
            st.json(item['params'])
        st.dataframe(item['results'], width='stretch', hide_index=True)


for item in st.session_state.conversation:
    with st.chat_message('user'):
        st.write(item['question'])
    show_answer(item)

if question := st.chat_input('Ask about revenue, products, regions, or monthly performance…', max_chars=1500):
    with st.chat_message('user'):
        st.write(question)
    try:
        with st.spinner('Generating a SELECT query and retrieving MySQL results…'):
            sql, params = generate_query(question, st.session_state.conversation)
            results = execute_select(sql, params)
            answer = explain_results(results)
        item = dict(question=question, sql=sql, params=params, results=results, answer=answer)
        st.session_state.conversation.append(item)
        st.session_state.conversation = st.session_state.conversation[-10:]
        show_answer(item)
        try:
            save_chat(st.session_state.chat_session_id, question, sql, params, answer)
        except DatabaseError:
            st.warning('The answer is available, but saving the conversation log failed.')
    except (ChatbotError, DatabaseError) as exc:
        st.error(str(exc))
