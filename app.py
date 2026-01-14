import streamlit as st
import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv
import tempfile

# ==========================================
# 1. 核心配置加载
# ==========================================
if "DASHSCOPE_API_KEY" in st.secrets:
    api_key = st.secrets["DASHSCOPE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")

dashscope.api_key = api_key

# ==========================================
# 2. v9.0 极简引导版系统提示词
# ==========================================
SYSTEM_PROMPT = """
# Role
你是一位初中数学苏格拉底导师。你的任务是引导学生思考，而不是给答案。

# 任务逻辑 (请严格按此结构回复)
1. 认可：用一句话简短肯定学生的提问或思考。
2. 观察：指出题目或图片中的一个具体关键点（如：某个角、某条线）。
3. 提问：抛出一个具体的、能引导下一步思考的问题。

# 核心戒律
- 严禁给出最终数值、解题步骤或完整等式。
- 回复字数必须在 100 字以内，保持极简。
- 所有数学符号用 $ 包裹。
"""

# ==========================================
# 3. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="精准学AI导师", layout="centered", page_icon="👨‍🏫")
st.title("👨‍🏫 初中数学苏格拉底导师")
st.markdown("---")

# 侧边栏：上传与清空
st.sidebar.title("操作区")
uploaded_file = st.sidebar.file_uploader("📷 上传题目照片", type=["png", "jpg", "jpeg"])
if st.sidebar.button("🗑️ 彻底清空对话记录"):
    st.session_state.messages = []
    st.success("对话已清空，建议此时重新开始对话以避免复读干扰。")
    st.rerun()

st.sidebar.info("💡 **PM建议**：如果AI开始复读，请务必点击上方按钮清空历史记录。")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 4. API 调用函数 (极高稳定性参数)
# ==========================================
def get_ai_response(prompt, img_path=None):
    messages = [{"role": "system", "content": [{"text": SYSTEM_PROMPT}]}]
    
    # 仅携带最近 6 轮对话，防止历史错误污染
    for m in st.session_state.messages[-6:]:
        messages.append({"role": m["role"], "content": [{"text": m["content"]}]})
    
    user_content = []
    if img_path:
        user_content.append({"image": f"file://{img_path}"})
    user_content.append({"text": prompt})
    messages.append({"role": "user", "content": user_content})

    try:
        responses = MultiModalConversation.call(
            model='qwen-vl-max', 
            messages=messages, 
            stream=True,
            # --- 物理防复读极限参数 ---
            temperature=0.1,         # 极低随机性
            repetition_penalty=1.5,  # 极强重复惩罚
            top_p=0.1,               # 极窄采样
            max_tokens=200           # 严格截断
        )
        return responses
    except Exception as e:
        st.error(f"❌ API 异常: {str(e)}")
        return None

# ==========================================
# 5. 交互逻辑 (加入规则过滤)
# ==========================================
# 展现历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入处理
if prompt := st.chat_input("向老师请教数学题..."):
    # 在界面展示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 1. 规则引擎拦截：处理简单招呼，不走 AI
    greetings = ["你好", "您好", "hi", "hello", "嗨"]
    if any(greet == prompt.strip().lower() for greet in greetings):
        res = "你好！我是你的数学苏格拉底导师。请上传题目照片，或者描述一下你遇到的数学难点，我们一起来攻克它！"
        with st.chat_message("assistant"):
            st.markdown(res)
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": res})
    
    # 2. 正常业务走 AI 推理
    else:
        tmp_img_path = None
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_img_path = tmp.name
                st.image(uploaded_file, caption="当前题目", width=350)

        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            res_stream = get_ai_response(prompt, tmp_img_path)
            
            if res_stream:
                for res in res_stream:
                    if res.status_code == 200:
                        chunk = res.output.choices[0].message.content[0]['text']
                        full_response += chunk
                        placeholder.markdown(full_response + "▌")
                    else:
                        placeholder.error(f"API Error: {res.message}")
                
                placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
