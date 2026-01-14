import streamlit as st
import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv
import tempfile

# 1. 加载配置
load_dotenv()
# 优先从环境变量(本地.env或云端Secrets)获取Key
api_key = os.getenv("DASHSCOPE_API_KEY") or st.secrets.get("DASHSCOPE_API_KEY")
dashscope.api_key = api_key

# 2. 页面设置
st.set_page_config(page_title="精准学AI导师", layout="centered")

# 3. 系统提示词 (v5.0 终极版)
SYSTEM_PROMPT = """你是一位精通人教版初中数学的金牌导师。
核心原则：
1. 采用苏格拉底式提问，严禁直接给答案或推导步骤。
2. 每次只引导一个微小逻辑点（单点步进）。
3. 几何题必须指向具体点、线、角（空间锚点）。
4. 屏蔽非数学话题，一句话转回。
5. 必须使用 LaTeX 格式输出公式（如 $a^2 + b^2 = c^2$）。"""

# 4. 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# 5. API 调用函数
def get_ai_response(prompt, img_path=None):
    messages = [{"role": "system", "content": [{"text": SYSTEM_PROMPT}]}]
    
    # 构造上下文（包含之前对话，防止AI断片）
    for m in st.session_state.messages[-5:]:
        messages.append({"role": m["role"], "content": [{"text": m["content"]}]})
    
    # 当前输入
    current_user_content = []
    if img_path:
        current_user_content.append({"image": f"file://{img_path}"})
    current_user_content.append({"text": prompt})
    messages.append({"role": "user", "content": current_user_content})

    try:
        responses = MultiModalConversation.call(model='qwen-vl-max', messages=messages, stream=True)
        return responses
    except Exception as e:
        st.error(f"API调用失败: {e}")
        return None

# 6. UI 界面
st.title("👨‍🏫 初中数学苏格拉底导师")
st.sidebar.title("操作区")
uploaded_file = st.sidebar.file_uploader("📷 上传题目照片", type=["png", "jpg", "jpeg"])

if st.sidebar.button("🗑️ 清空对话"):
    st.session_state.messages = []
    st.rerun()

# 展示对话
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("向老师提问..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 临时存储图片
    tmp_img_path = None
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_img_path = tmp.name
            st.image(uploaded_file, width=300)

    st.session_state.messages.append({"role": "user", "content": prompt})

    # AI 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        res_stream = get_ai_response(prompt, tmp_img_path)
        
        if res_stream:
            for res in res_stream:
                if res.status_code == 200:
                    chunk = res.output.choices[0].message.content[0]['text']
                    full_res += chunk
                    placeholder.markdown(full_res + "▌")
            placeholder.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})