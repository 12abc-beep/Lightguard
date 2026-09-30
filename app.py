import os

import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

SYSTEM_PROMPT = """
你是一个叫做“轻卫士”的校园健康生活管家。你的职责是帮助大学生在生病时进行科学自我照护。
【绝对红线】：绝对不能提供医学诊断，绝对不能推荐任何具体药物。
你需要结合当前的天气环境来给出饮食、护理和运动建议。比如降温要提醒加衣，下雨要提醒防滑。

【核心交互规则（非常重要！）】：
当用户向你描述症状时，**不要立刻输出长篇的护理建议**。
1. **精准追问**：你必须先根据用户的症状，提出1-2个关键问题来获取更多信息。
   - 如果是【胃痛】：你必须问清楚是“上腹部、中腹部还是下腹部疼痛？是隐痛、绞痛还是胀痛？是否伴随恶心腹泻？”
   - 如果是【发烧】：你必须问清楚“体温最高到了多少度？（低烧37.3-38℃，高烧38.5℃以上）是否伴随畏寒、剧烈头痛？”
   - 如果是【头痛】：必须问清楚“是偏头痛、全头痛还是刺痛？是否伴随恶心或视力模糊？”
2. **等待回复**：你必须等用户回答了你的追问后，再给出最终的详细建议。
3. **如果信息足够**：当用户提供的症状非常明确（例如“我发烧39度并且胸闷”），立刻跳过追问，直接输出最终建议。

【最终建议输出格式】（只有在收集完信息后才输出）：
- 【初步分析】用通俗易懂的语言分析可能原因（强调不代表诊断）。
- 【就医研判】明确判断是否需要就医。如果是高烧、剧痛、胸闷、呼吸困难，必须加粗强制警告“⚠️请立刻前往校医院或就医！”
- 【缓解方案】当下的急救或缓解建议（如平躺、喝水、冷敷）。
- 【饮食建议】近期吃什么、忌口什么。
- 【运动建议】近期适宜的运动（或明确要求卧床休息）。
- 【日常护理】作息、生活习惯方面的照护建议。

请语气温和，像学长/学姐一样关心用户。
"""


def get_weather():
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return None

    try:
        response = requests.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={"city": "360100", "key": api_key},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "1" or not data.get("lives"):
            raise ValueError(data.get("info", "天气接口未返回有效数据"))

        city = data.get("lives")[0].get("city", "南昌")
        temperature = data.get("lives")[0].get("temperature", "未知")
        condition = data.get("lives")[0].get("weather", "未知")
        return f"【当前环境天气：{city}，温度{temperature}度，{condition}】"
    except Exception:
        return None


def get_client():
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")

    if not api_key or not base_url:
        raise ValueError("请确认 .env 文件中已配置 API_KEY 和 BASE_URL。")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    return client


st.set_page_config(page_title="轻卫士", page_icon="🏥")
st.title("轻卫士")
st.caption("学生生病自护AI助手")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("请输入你的症状或疑问...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    weather_context = get_weather()

    try:
        client = get_client()
        conversation_messages = [
            dict(message) for message in st.session_state.messages
        ]
        if weather_context:
            conversation_messages[-1]["content"] = (
                f"{weather_context}\n用户症状：{user_input}"
            )

        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation_messages,
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        reply = response.choices[0].message.content
        if not weather_context:
            reply = f"当前天气获取失败。\n\n{reply}"
        st.session_state.messages.append({"role": "assistant", "content": reply})

        with st.chat_message("assistant"):
            st.markdown(reply)

    except Exception as e:
        error_message = f"发生错误：{e}"
        st.session_state.messages.append({"role": "assistant", "content": error_message})
        with st.chat_message("assistant"):
            st.error(error_message)
