import dotenv

dotenv.load_dotenv()
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach Agent",
        model="gpt-4o-mini",
        instructions="""
        당신은 따뜻하고 격려하는 라이프 코치입니다.

        동기부여, 자기 개발, 습관 형성에 대해 유저를 도와주세요.
        실용적이고 실행 가능한 조언을 응원하는 톤으로 전달하세요.

        사용 가능한 도구:
            - Web Search Tool: 유저가 습관, 동기부여, 자기 개발, 생활 개선에 관한 질문을 하면 사용하세요. 답변하기 전에 항상 최신 팁과 검증된 방법을 먼저 검색하세요. 자신의 지식에 의존하기 전에 웹 검색을 먼저 시도하세요.
        """,
        tools=[
            WebSearchTool(),
        ],
    )
agent = st.session_state["agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "life-coach-agent-memory.db",
    )
session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"].replace("$", "\$"))
        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("ai"):
                query = message.get("query", "")
                st.write(f'웹 검색: "{query}"')


asyncio.run(paint_history())


def update_status(status_container, event):

    status_messages = {
        "response.web_search_call.completed": ("✅ Web search completed.", "complete"),
        "response.web_search_call.in_progress": (
            "🔍 Starting web search...",
            "running",
        ),
        "response.web_search_call.searching": (
            "🔍 Web search in progress...",
            "running",
        ),
        "response.completed": (" ", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("⏳", expanded=False)
        text_placeholder = st.empty()
        response = ""

        stream = Runner.run_streamed(
            agent,
            message,
            session=session,
        )

        async for event in stream.stream_events():
            if event.type == "raw_response_event":

                update_status(status_container, event.data.type)

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response.replace("$", "\$"))

            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    raw = event.item.raw_item
                    if raw.type == "web_search_call":
                        query = raw.action.query
                        st.write(f'웹 검색: "{query}"')


prompt = st.chat_input("오늘 어떤 코칭을 받고 싶으신가요?")

if prompt:
    with st.chat_message("human"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))


with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
