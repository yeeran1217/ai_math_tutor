import streamlit as st
import dashscope
from dashscope import MultiModalConversation
import os
from dotenv import load_dotenv
import tempfile

# ==========================================
# 1. 环境与配置加载
# ==========================================
# 优先从 Streamlit Secrets 获取，本地开发则从 .env 获取
if "DASHSCOPE_API_KEY" in st.secrets:
    api_key = st.secrets["DASHSCOPE_API_KEY"]
else:
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")

dashscope.api_key = api_key

# ==========================================
# 2. v7.0 深度平衡版系统提示词
# ==========================================
SYSTEM_PROMPT = """
# Role
你是一位精通人教版初中数学的金牌导师。你采用苏格拉底式教学法，通过“高质量提问”引导学生自主思考。你的回复应当充满启发性、温暖且逻辑严密。

# 核心目标
1. 【拒绝剧透】：绝对禁止直接给出最终答案、完整的解题步骤或化简后的最终算式。
2. 【深度引导】：回复必须包含：对学生当前状态的反馈 + 针对题目具体元素的逻辑分析 + 一个启发性的提问。
3. 【单步推进】：每次只解决一个逻辑难点，确保学生真正理解后再进行下一步。

# 交互行为准则 (防止复读与发疯)
- 【禁止标签】：严禁输出“第一步”、“提示问题”、“[肯定]”等任何显性标题、中括号或列表符号。
- 【拒绝复读】：严禁在回复中大量重复题干文字或自我重复。
- 【自然对话】：像真正的老师一样交流，字数控制在 150 字以内。
- 【数学规范】：所有数学符号和公式必须用 $ 包裹，如 $\angle ABC$。
- 【空间锚点】：几何题必须指明图中的点、线、角。例如：“观察三角形 ABC，哪两条边是相等的？”

# 题型策略
- 运算类：不替学生计算，询问其打算处理哪个项或应用哪个法则。
- 几何类：引导学生关联已知条件与判定定理，寻找隐含条件。
- 应用类：辅助学生将文字描述翻译成代数式或方程模型。

# 范畴护栏
- 若学生询问非数学话题（如娱乐、明星），请礼貌提醒：“我是你的数学辅助老师，咱们还是先把这个有趣的数学题解开吧。”
"""

# ==========================================
# 3. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="精准学AI导师", layout="centered", page_icon="👨‍🏫")

st.title("👨‍🏫 初中数学苏格拉底导师")
st.markdown("---")

# 侧边栏操作
st.sidebar.title("操作区")
uploaded_file = st.sidebar.file_uploader("📷 上传题目照片", type=["png", "jpg", "jpeg"])
if st.sidebar.button("🗑️ 清空对话记录"):
    st.session_state.messages = []
    st.rerun()

st.sidebar.info("📌 **提示**：老师不会直接给你答案，但他会带你一步步思考。")

# 初始化聊天记录
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# 4. 核心 API 调用函数 (稳定性调优版)
# ==========================================
def get_ai_response(prompt, img_path=None):
    # 构建消息列表
    messages = [{"role": "system", "content": [{"text": SYSTEM_PROMPT}]}]
    
    # 携带最近 5 轮上下文，保证对话连贯
    for m in st.session_state.messages[-10:]:
        messages.append({"role": m["role"], "content": [{"text": m["content"]}]})
    
    # 构建当前用户输入
    current_user_content = []
    if img_path:
        current_user_content.append({"image": f"file://{img_path}"})
    current_user_content.append({"text": prompt})
    messages.append({"role": "user", "content": current_user_content})

    try:
        # 调用多模态模型
        responses = MultiModalConversation.call(
            model='qwen-vl-max', 
            messages=messages, 
            stream=True,
            # --- 关键稳定性参数 ---
            temperature=0.2,   # 保持严谨，降低发疯概率
            top_p=0.5,         # 限制采样范围
            max_tokens=350     # 强制截断，防止无限输出
        )
        return responses
    except Exception as e:
        st.error(f"❌ API 调用出错了: {str(e)}")
        return None

# ==========================================
# 5. 对话逻辑实现
# ==========================================
# 展示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 处理用户输入
if prompt := st.chat_input("向老师请教这道题..."):
    # 在界面展示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 处理上传的题目图片
    tmp_img_path = None
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_img_path = tmp.name
            st.image(uploaded_file, caption="当前讨论的题目", width=350)

    # 存入历史记录
    st.session_state.messages.append({"role": "user", "content": prompt})

    # AI 回复环节
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        
        res_stream = get_ai_response(prompt, tmp_img_path)
        
        if res_stream:
            for res in res_stream:
                if res.status_code == 200:
                    chunk = res.output.choices[0].message.content[0]['text']
                    full_response += chunk
                    # 实时渲染打字机效果
                    placeholder.markdown(full_response + "▌")
                else:
                    placeholder.error(f"API 报错: {res.message}")
            
            # 最终渲染完整内容
            placeholder.markdown(full_response)
            # 存入历史记录
            st.session_state.messages.append({"role": "assistant", "content": full_response})
