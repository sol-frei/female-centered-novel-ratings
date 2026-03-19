import os
import sys
import io
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import streamlit as st
import pandas as pd
from principle import principles, dimension_labels

# 基础配置
st.set_page_config(page_title="女主无CP评分系统", page_icon="📖", layout="wide")

# ─────────────────────────────────────────────
# 1. 初始化 session_state
# ─────────────────────────────────────────────
if "answers" not in st.session_state:
    st.session_state.update({
        "answers": [None] * 25,
        "remarks": [""] * 25,
        "impressed_val": 0.0,
        "generated_imgs": None
    })

# ─────────────────────────────────────────────
# 2. Sidebar & 输入区域
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("评分规则")
    st.markdown("1. 减分制：满分10分。\n2. 基础扣分1分，情节严重无上限。")

book_name = st.text_input("请输入书名：", key="book_name")
impressed_rate = st.number_input(
    "请输入你的印象分*：",
    min_value=0.0, max_value=10.0, step=0.5,
    value=float(st.session_state["impressed_val"]),
)
st.session_state["impressed_val"] = impressed_rate

col1, col2 = st.columns(2)
with col1:
    book_author = st.text_input("请输入作者姓名：")
with col2:
    book_plate = st.text_input("请输入作品发布平台：")

ich = st.text_input("评分人：")
now = datetime.now().date()

if st.button("⚡ 一键满分打分"):
    st.session_state["answers"] = ["没有"] * 22 + ["有"] * 3
    st.session_state["remarks"] = [""] * 25
    st.session_state["impressed_val"] = 10.0
    st.session_state["generated_imgs"] = None
    st.rerun()

# ─────────────────────────────────────────────
# 3. 评分逻辑 (Radio & CSS)
# ─────────────────────────────────────────────
st.markdown("""
<style>
[data-qi-type="normal"] [data-baseweb="radio"]:nth-of-type(1)[aria-checked="true"] svg circle:last-child { fill: #e53935 !important; }
[data-qi-type="normal"] [data-baseweb="radio"]:nth-of-type(2)[aria-checked="true"] svg circle:last-child { fill: #2e7d32 !important; }
[data-qi-type="stance"] [data-baseweb="radio"]:nth-of-type(1)[aria-checked="true"] svg circle:last-child { fill: #2e7d32 !important; }
[data-qi-type="stance"] [data-baseweb="radio"]:nth-of-type(2)[aria-checked="true"] svg circle:last-child { fill: #e53935 !important; }
</style>
""", unsafe_allow_html=True)

# 动态打标签脚本
import streamlit.components.v1 as components
components.html("""
<script>
  const applyTypes = () => {
    const radios = window.parent.document.querySelectorAll('[data-testid="stRadio"]');
    radios.forEach((el, idx) => el.setAttribute('data-qi-type', idx < 22 ? 'normal' : 'stance'));
  };
  applyTypes();
  new MutationObserver(applyTypes).observe(window.parent.document.body, {childList:true, subtree:true});
</script>
""", height=0)

dimensions = [
    ("📂 作者与作品", 0, 6),
    ("👤 角色设定", 6, 18),
    ("💬 语言叙事", 18, 22),
    ("🏳️ 立场", 22, 25),
]

answers = st.session_state["answers"]
remarks = st.session_state["remarks"]

for dim_name, start, end in dimensions:
    st.subheader(dim_name)
    for i in range(start, end):
        st.write(f"**{i+1}、{principles[i]}**")
        c1, c2 = st.columns([2, 5])
        with c1:
            ans = st.radio(f"q_{i}", ["有", "没有"], 
                           index=(0 if answers[i]=="有" else 1 if answers[i]=="没有" else None),
                           key=f"r_{i}", label_visibility="collapsed", horizontal=True)
            answers[i] = ans
        with c2:
            remarks[i] = st.text_area(f"rem_{i}", value=remarks[i], key=f"t_{i}", 
                                      label_visibility="collapsed", placeholder="备注...")

# ─────────────────────────────────────────────
# 4. 计算分数
# ─────────────────────────────────────────────
extra_rate = st.number_input("额外扣分：", min_value=0.0, step=0.5)
comment = st.text_area("爱女姐有话说：")

deduct_count = 0
for i, ans in enumerate(answers):
    if (i < 22 and ans == "有") or (i >= 22 and ans == "没有"):
        deduct_count += 1

sum_rate = max(0.0, impressed_rate - deduct_count - extra_rate)
st.metric("最终评分", f"{sum_rate:.1f} / 10")

# ─────────────────────────────────────────────
# 5. 图片生成逻辑 (HTML & WeasyPrint)
# ─────────────────────────────────────────────
_WEASY_STYLE = """
<style>
@page { size: 450px auto; margin: 0; }
body { margin: 0; padding: 0; background: #fff; font-family: 'Noto Sans CJK SC', sans-serif; }
.container { width: 450px; background: #fff; border: 1px solid #eee; }
table { width: 100%; border-collapse: collapse; }
.header { background: #fffdf9; padding: 25px; text-align: center; border-bottom: 1px solid #e8e2d8; }
.score-box { padding: 20px; text-align: center; border-bottom: 1px solid #e0dbd4; }
.data-row { padding: 12px 20px; border-bottom: 1px solid #f0eeec; }
.label { font-size: 8px; color: #c8b89a; letter-spacing: 2px; text-transform: uppercase; }
.val { font-size: 13px; font-weight: bold; color: #111; }
</style>
"""

def build_p1(score_color):
    return f"""
    <html><head><meta charset="utf-8">{_WEASY_STYLE}</head><body>
    <div class="container">
        <div class="header">
            <div class="label">FEMINIST RATING CERTIFICATE</div>
            <div style="font-size:18px; font-weight:800;">女主无CP小说评鉴书</div>
        </div>
        <div class="score-box">
            <div class="label">FINAL SCORE</div>
            <div style="font-size:70px; font-weight:800; color:{score_color};">{sum_rate:.1f}</div>
        </div>
        <table>
            <tr>
                <td class="data-row"><div class="label">TITLE</div><div class="val">{book_name}</div></td>
                <td class="data-row"><div class="label">AUTHOR</div><div class="val">{book_author or "—"}</div></td>
            </tr>
            <tr>
                <td class="data-row"><div class="label">PLATFORM</div><div class="val">{book_plate or "—"}</div></td>
                <td class="data-row"><div class="label">REVIEWER</div><div class="val">{ich or "—"}</div></td>
            </tr>
        </table>
        <div class="data-row" style="text-align:center; background:#fffdf9;">
            <div class="label">PAGE 1</div>
        </div>
    </div></body></html>"""

# (此处省略 build_detail 逻辑，结构与 p1 类似)

# ─────────────────────────────────────────────
# 6. 渲染执行
# ─────────────────────────────────────────────
@st.cache_resource
def get_wp():
    from weasyprint import HTML
    return HTML

def _autocrop(img):
    from PIL import ImageChops
    diff = ImageChops.difference(img, img.new(img.mode, img.size, img.getpixel((0,0))))
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def html_to_png(html_str):
    from pdf2image import convert_from_bytes
    pdf = get_wp()(string=html_str).write_pdf()
    imgs = convert_from_bytes(pdf, dpi=150)
    if imgs:
        buf = io.BytesIO()
        _autocrop(imgs[0]).save(buf, format="PNG")
        return buf.getvalue()
    return None

if st.button("🖼️ 生成评鉴图片"):
    if not book_name:
        st.error("请输入书名")
    else:
        with st.spinner("生成中..."):
            color = "#1d6a3a" if sum_rate >= 8 else "#b03a2e"
            p1_bytes = html_to_png(build_p1(color))
            st.session_state["generated_imgs"] = [("总览", p1_bytes)]

if st.session_state["generated_imgs"]:
    for label, data in st.session_state["generated_imgs"]:
        st.image(data)
        st.download_button(f"下载 {label}", data, f"{label}.png", "image/png")
