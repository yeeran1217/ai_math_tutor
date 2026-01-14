import streamlit as st
import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv
import tempfile

# ==========================================
# 1. 环境与配置加载
# ==========================================
if "DASHSCOPE_API_KEY" in st.secrets:
    api_key = st.secrets["DASHSCOPE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")

dashscope.api_key = api_key

# ==========================================
# 2. v8.0 逻辑增强与物理防复读版系统提示词
# ==========================================
SYSTEM_PROMPT = """
# Role
你是一位精通人教版初中数学的金牌导师。你采用苏格拉底式教学法。

# 核心约束
1. 【拒绝剧透】：严禁给出答案、完整步骤或结果算式。
2. 【单点步进】：每次只引导一个微小逻辑。
3. 【禁止标签】：严禁输出 [肯定]、[提问] 或“第一步”等标题。
4. 【拒绝复读】：严禁在回复中大量重复任何词句。如果用户只是打招呼，请简短回应并直接邀请其提问或发图，不要重复问候语。

# 交互结构
- [反馈]：简短评价学生的思考。
- [引导]：针对题目具体元素（点/线/角）提一个问题。
- [微提示]：若有必要，给个极小的提示。

# 范畴护栏
- 严禁闲聊。若偏离数学，立即礼貌带回。
"""

# ==========================================
# 3. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="精准学AI导师", layout="centered", page_icon="👨‍🏫")
st.title("👨‍🏫 初中数学苏格拉底导师")
st.markdown("---")

st.sidebar.title("操作区")
uploaded_file = st.sidebar.file_uploader("📷 上传题目照片", type=["png", "jpg", "jpeg"])
if st.sidebar.button("🗑️ 清空对话记录"):
    st.session_state.messages = []
    st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 4. 核心 API 调用函数 (增加防复读参数)
# ==========================================
def get_ai_response(prompt, img_path=None):
    messages = [{"role": "system", "content": [{"text": SYSTEM_PROMPT}]}]
    
    # 携带上下文
    for m in st.session_state.messages[-10:]:
        messages.append({"role": m["role"], "content": [{"text": m["content"]}]})
    
    current_user_content = []
    if img_path:
        current_user_content.append({"image": f"file://{img_path}"})
    current_user_content.append({"text": prompt})
    messages.append({"role": "user", "content": current_user_content})

    try:
        responses = MultiModalConversation.call(
            model='qwen-vl-max', 
            messages=messages, 
            stream=True,
            # --- 物理防复读三剑客 ---
            temperature=0.1,         # 降到极低，确保严谨
            repetition_penalty=1.2,  # 关键！如果模型开始复读，强制降低重复词的权重
            top_p=0.5,               # 限制采样
            max_tokens=300           # 截断
        )
        return responses
    except Exception as e:
        st.error(f"❌ API 异常: {str(e)}")
        return None

# ==========================================
# 5. 对话逻辑
# ==========================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("向老师请教这道题..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
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
