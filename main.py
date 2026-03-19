import os
import sys
import io
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import streamlit as st
import pandas as pd
from principle import principles, dimension_labels

st.set_page_config(page_title="女主无CP/无男主小说评分", page_icon="📖", layout="wide")

# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("评分规则")
    st.markdown("""
### 1.打分为减分制。
完结小说满分为10分，读者根据阅读后体验和感受，给一个印象得分，
然后再根据组规进行减分，
即最终得分=印象分-减分项，最终得分<10分。
【谨慎打8分以上，禁止分数膨胀】

### 2.打分规则。
各项基础扣分分值为1分，情节严重的可以增加扣分分值，无上限，
必须列出各项减分项存在与否。
【❗❗❗注意：没有明确标注/提出的、不完全的、模棱两可的即需要扣分，请各位打分人严格执行！！】
""")

# ─────────────────────────────────────────────
# 初始化 session_state
# ─────────────────────────────────────────────
for key, default in [
    ("answers",       [None] * 25),
    ("remarks",       [""] * 25),
    ("impressed_val", 0.0),
    ("generated_imgs", None),   # 存储已生成的图片，防止 rerun 后消失
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────
# 书目信息
# ─────────────────────────────────────────────
book_name  = st.text_input("请输入书名：")

# ⚠️ 不给 number_input 设置 key，这样 value= 参数每次 rerun 都生效
# 一键满分时写入 session_state["impressed_val"]，下一次 rerun 就会读到 10.0
impressed_rate = st.number_input(
    "请输入你的印象分*：",
    min_value=0.0, max_value=10.0, step=0.5,
    value=float(st.session_state["impressed_val"]),
)
# 用户手动改值时也同步到 session_state
st.session_state["impressed_val"] = impressed_rate

book_author = st.text_input("请输入作者姓名：")
book_plate  = st.text_input("请输入作品发布平台：")
ich         = st.text_input("评分人：")
now         = datetime.now().date()

st.divider()


# ─────────────────────────────────────────────
# Radio 颜色 CSS 注入
# ─────────────────────────────────────────────
st.markdown("""
<style>
[data-qi-type="normal"] [data-baseweb="radio"]:nth-of-type(1)[aria-checked="true"] svg circle:last-child
    { fill: #e53935 !important; }
[data-qi-type="normal"] [data-baseweb="radio"]:nth-of-type(2)[aria-checked="true"] svg circle:last-child
    { fill: #2e7d32 !important; }
[data-qi-type="stance"] [data-baseweb="radio"]:nth-of-type(1)[aria-checked="true"] svg circle:last-child
    { fill: #2e7d32 !important; }
[data-qi-type="stance"] [data-baseweb="radio"]:nth-of-type(2)[aria-checked="true"] svg circle:last-child
    { fill: #e53935 !important; }
</style>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
<script>
(function() {
  function applyTypes() {
    var radios = window.parent.document.querySelectorAll('[data-testid="stRadio"]');
    radios.forEach(function(el, idx) {
      el.setAttribute('data-qi-type', idx < 22 ? 'normal' : 'stance');
    });
  }
  applyTypes();
  new MutationObserver(applyTypes).observe(
    window.parent.document.body, {childList:true, subtree:true}
  );
})();
</script>
""", height=0)

# ─────────────────────────────────────────────
# 按维度打分
# ─────────────────────────────────────────────
dimensions = [
    ("作者与作品", 0,  6),
    ("角色设定",   6,  18),
    ("语言叙事",   18, 22),
    ("立场",      22, 25),
]

for dim_name, start, end in dimensions:
    st.subheader(dim_name)
    for i in range(start, end):
        st.markdown(f"**{i+1}、{principles[i]}**")
        col_radio, col_empty = st.columns([2, 5])
        with col_radio:
            default_idx = 0 if answers[i] == "有" else (1 if answers[i] == "没有" else None)
            q = st.radio("", ["有", "没有"], index=default_idx,
                         key=f"radio_{i}", label_visibility="collapsed", horizontal=True)
            answers[i] = q
        remarks[i] = st.text_area("备注", value=remarks[i],
                                   key=f"remark_{i}", label_visibility="collapsed",
                                   placeholder="备注（可选）")

st.session_state["answers"] = answers
st.session_state["remarks"] = remarks

st.divider()

# ─────────────────────────────────────────────
# 额外扣分 & 评语
# ─────────────────────────────────────────────
extra_rate = st.number_input("因为其它恶劣情节，我还想减分：", min_value=0.0, max_value=10.0, step=0.5)
extra_note = st.text_area("备注：")
comment    = st.text_area("爱女姐有话说：")

# ─────────────────────────────────────────────
# 计算分数
# ─────────────────────────────────────────────
y, n = "有", "没有"
r = [0] * 25
deduct_details = []

for i, answer in enumerate(answers[:22]):
    if answer == y:
        r[i] = -1
        deduct_details.append(f"p{i+1}")

for i, answer in enumerate(answers[22:], 22):
    if answer == n:
        r[i] = -1
        deduct_details.append(f"p{i+1}")

criteria_deduct = sum(r)
sum_rate = impressed_rate + criteria_deduct - extra_rate
st.write(f"最终评分为：{sum_rate}")


# ─────────────────────────────────────────────
# HTML 构建（纯 table + 固定页面尺寸，解决 WeasyPrint 排版问题）
# ─────────────────────────────────────────────

# WeasyPrint 的关键修复：@page 设置页面宽高等于内容，禁止自动分页
_WEASY_BASE_STYLE = """
<style>
@page { size: 430px auto; margin: 0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { width:430px; background:#f7f5f2;
       font-family:'Noto Sans CJK SC','WenQuanYi Micro Hei','AR PL UMing CN',serif;
       color:#1a1a1a; }
table { border-collapse:collapse; width:100%; }
div { line-height: 1.4; }
</style>
"""

def build_page1_html(book_name, book_author, book_plate, ich, now,
                     impressed_rate, criteria_deduct, extra_rate, sum_rate,
                     deduct_count, score_color, extra_note, comment):

    extra_rows = ""
    if extra_rate > 0 or extra_note:
        extra_rows = f"""
  <tr><td colspan="2" style="padding:12px 20px;border-bottom:1px solid #e0dbd4;">
    <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:6px;font-family:Georgia,serif;">ADDITIONAL DEDUCTION · 额外扣分</div>
    <div style="font-size:12px;color:#333;line-height:1.6;">{extra_note}</div>
    <div style="font-size:11px;color:#b03a2e;font-weight:700;margin-top:3px;font-family:Georgia,serif;">&#8722;{extra_rate:.1f} 分</div>
  </td></tr>"""

    comment_rows = ""
    if comment:
        comment_rows = f"""
  <tr><td colspan="2" style="padding:14px 20px 18px;">
    <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:6px;font-family:Georgia,serif;">REVIEWER'S NOTE</div>
    <div style="font-size:12px;color:#444;line-height:1.8;font-style:italic;font-family:Georgia,serif;">「{comment}」</div>
  </td></tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{_WEASY_BASE_STYLE}</head><body>
<table style="background:#fff;border:1px solid #ddd;">
  <tr><td colspan="2" style="padding:26px 24px 20px;text-align:center;background:#fffdf9;border-bottom:1px solid #e8e2d8;">
    <div style="font-size:7px;letter-spacing:4px;color:#c8b89a;margin-bottom:8px;font-family:Georgia,serif;">FEMINIST LITERATURE RATING CERTIFICATE</div>
    <div style="font-size:18px;font-weight:800;color:#111;letter-spacing:3px;line-height:1.5;">女主无CP<br/>无男主小说评分</div>
    <div style="margin:10px auto 0;width:160px;border-top:1px solid #e0d5c0;"></div>
  </td></tr>
  <tr><td colspan="2" style="padding:22px 24px 16px;text-align:center;border-bottom:1px solid #e0dbd4;background:#fff;">
    <div style="font-size:8px;color:#c8b89a;letter-spacing:4px;margin-bottom:5px;font-family:Georgia,serif;">FINAL SCORE</div>
    <div style="font-size:72px;font-weight:800;color:{score_color};line-height:1;font-family:Georgia,serif;">{sum_rate:.1f}</div>
    <div style="font-size:10px;color:#bbb;margin-top:4px;letter-spacing:3px;">/ 10</div>
  </td></tr>
  <tr>
    <td style="padding:13px 24px;border-bottom:1px solid #f0eeec;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:2px;font-family:Georgia,serif;">IMPRESSION</div>
      <div style="font-size:13px;color:#555;letter-spacing:1px;">印 象 分</div>
    </td>
    <td style="padding:13px 24px;text-align:right;border-bottom:1px solid #f0eeec;">
      <span style="font-size:32px;font-weight:300;color:#c09430;font-family:Georgia,serif;">+{impressed_rate:.1f}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:13px 24px;border-bottom:1px solid #f0eeec;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:2px;font-family:Georgia,serif;">CRITERIA</div>
      <div style="font-size:13px;color:#555;letter-spacing:1px;">准则扣分 <span style="font-size:10px;color:#bbb;">共{deduct_count}项</span></div>
    </td>
    <td style="padding:13px 24px;text-align:right;border-bottom:1px solid #f0eeec;">
      <span style="font-size:32px;font-weight:300;color:#b03a2e;font-family:Georgia,serif;">{criteria_deduct:.0f}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:13px 24px;border-bottom:2px solid #1a1a1a;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:2px;font-family:Georgia,serif;">ADDITIONAL</div>
      <div style="font-size:13px;color:#555;letter-spacing:1px;">额外扣分</div>
    </td>
    <td style="padding:13px 24px;text-align:right;border-bottom:2px solid #1a1a1a;">
      <span style="font-size:32px;font-weight:300;color:#888;font-family:Georgia,serif;">&#8722;{extra_rate:.1f}</span>
    </td>
  </tr>
  <tr>
    <td style="padding:11px 18px;border-right:1px solid #ece8e0;border-bottom:1px solid #ece8e0;width:50%;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">TITLE</div>
      <div style="font-size:13px;font-weight:700;color:#111;">{book_name}</div>
    </td>
    <td style="padding:11px 18px;border-bottom:1px solid #ece8e0;width:50%;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">AUTHOR</div>
      <div style="font-size:13px;font-weight:700;color:#111;">{book_author or "—"}</div>
    </td>
  </tr>
  <tr>
    <td style="padding:11px 18px;border-right:1px solid #ece8e0;border-bottom:1px solid #e0dbd4;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">PLATFORM</div>
      <div style="font-size:13px;font-weight:700;color:#111;">{book_plate or "—"}</div>
    </td>
    <td style="padding:11px 18px;border-bottom:1px solid #e0dbd4;">
      <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">REVIEWER · DATE</div>
      <div style="font-size:12px;font-weight:600;color:#111;">{ich or "—"}<br/>{now}</div>
    </td>
  </tr>
  {extra_rows}
  {comment_rows}
  <tr><td colspan="2" style="padding:9px 20px;background:#fffdf9;border-top:1px solid #e0dbd4;text-align:center;">
    <span style="font-size:7px;color:#c8b89a;letter-spacing:3px;font-family:Georgia,serif;">PAGE 1</span>
  </td></tr>
</table>
</body></html>"""


def build_detail_page_html(book_name, dim_chunks, page_num, principles):
    blocks = ""
    for dim_zh, dim_en, items in dim_chunks:
        rows = ""
        for (i, is_deduct, remark_text) in items:
            dot_color = "#c0392b" if is_deduct else "#aab8b0"
            badge = (
                '<span style="font-size:11px;font-weight:700;color:#b03a2e;font-family:Georgia,serif;">&#8722;1</span>'
                if is_deduct else
                '<span style="font-size:11px;color:#ccc;font-family:Georgia,serif;">0</span>'
            )
            remark_html = (
                f'<div style="margin-top:2px;color:#aaa;font-size:10px;line-height:1.5;font-style:italic;">&#8627; {remark_text}</div>'
                if remark_text else ""
            )
            bg = "#fffbfb" if is_deduct else "#fff"
            sep = "#f0eeec" if is_deduct else "#f5f5f5"
            rows += f"""
<tr style="background:{bg};">
  <td style="padding:9px 5px 9px 14px;width:14px;vertical-align:top;border-bottom:1px solid {sep};">
    <div style="width:7px;height:7px;border-radius:50%;background:{dot_color};margin-top:3px;"></div>
  </td>
  <td style="padding:9px 5px 9px 0;font-size:12px;color:#2c2c2c;line-height:1.6;vertical-align:top;border-bottom:1px solid {sep};">
    <span style="color:#c8b89a;font-size:9px;margin-right:4px;font-family:Georgia,serif;">p{i+1}</span>{principles[i]}{remark_html}
  </td>
  <td style="padding:9px 14px 9px 5px;text-align:right;vertical-align:top;white-space:nowrap;border-bottom:1px solid {sep};">{badge}</td>
</tr>"""
        blocks += f"""
<tr><td colspan="3" style="padding:9px 14px;background:#fafaf8;border-top:1px solid #e0dbd4;border-bottom:1px solid #e0dbd4;">
  <span style="font-size:12px;font-weight:700;color:#1a1a1a;letter-spacing:1px;">{dim_zh}</span>
  <span style="font-size:7px;color:#c8b89a;letter-spacing:2px;margin-left:7px;font-family:Georgia,serif;">{dim_en}</span>
</td></tr>
{rows}"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">{_WEASY_BASE_STYLE}</head><body>
<table style="background:#fff;border:1px solid #ddd;">
  <tr><td colspan="3" style="padding:14px 18px 10px;text-align:center;background:#fffdf9;border-bottom:1px solid #e8e2d8;">
    <div style="font-size:7px;letter-spacing:4px;color:#c8b89a;font-family:Georgia,serif;">SCORING DETAIL · 评分明细</div>
    <div style="font-size:13px;font-weight:700;color:#111;margin-top:3px;letter-spacing:2px;">《{book_name}》</div>
  </td></tr>
  <tr><td colspan="3" style="padding:6px 14px;background:#fafaf8;border-bottom:1px solid #ece8e0;">
    <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#c0392b;margin-right:4px;vertical-align:middle;"></span>
    <span style="font-size:10px;color:#777;margin-right:12px;">扣分（&#8722;1）</span>
    <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#aab8b0;margin-right:4px;vertical-align:middle;"></span>
    <span style="font-size:10px;color:#777;">无扣分（0）</span>
  </td></tr>
  {blocks}
  <tr><td colspan="3" style="padding:9px 18px;background:#fffdf9;border-top:1px solid #e0dbd4;text-align:center;">
    <span style="font-size:7px;color:#c8b89a;letter-spacing:3px;font-family:Georgia,serif;">PAGE {page_num}</span>
  </td></tr>
</table>
</body></html>"""


# ─────────────────────────────────────────────
# 渲染函数（WeasyPrint，缓存字体实例加速）
# ─────────────────────────────────────────────

@st.cache_resource
def get_weasyprint_html_class():
    """缓存 WeasyPrint 的 HTML 类，避免每次重新初始化字体，大幅提速。"""
    from weasyprint import HTML as WeasyprintHTML
    return WeasyprintHTML

def _autocrop(img):
    """裁掉图片底部空白，只保留实际内容高度。"""
    from PIL import Image as PilImage, ImageChops
    bg_color = img.getpixel((0, 0))
    bg_img = PilImage.new(img.mode, img.size, bg_color)  # 修复：用 PilImage.new 而非 img.new
    diff = ImageChops.difference(img, bg_img)
    bbox = diff.getbbox()
    if bbox:
        bottom = min(bbox[3] + 4, img.height)
        return img.crop((0, 0, img.width, bottom))
    return img

def html_to_png_bytes(html_str):
    from pdf2image import convert_from_bytes
    WeasyprintHTML = get_weasyprint_html_class()
    pdf_bytes = WeasyprintHTML(string=html_str).write_pdf()
    images = convert_from_bytes(pdf_bytes, dpi=150, first_page=1, last_page=1)
    if images:
        cropped = _autocrop(images[0])
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    return None


# ─────────────────────────────────────────────
# 生成图片按钮
# ─────────────────────────────────────────────

if st.button("🖼️ 生成图片"):
    if not book_name:
        st.warning("请先填写书名！")
    else:
        with st.spinner("正在生成图片，请稍候..."):
            score_color = (
                "#b03a2e" if sum_rate < 4 else
                "#a04000" if sum_rate < 6 else
                "#1a3a5c" if sum_rate < 8 else
                "#1d6a3a"
            )
            deduct_count = len(deduct_details)

            html1 = build_page1_html(
                book_name, book_author, book_plate, ich, now,
                impressed_rate, criteria_deduct, extra_rate, sum_rate,
                deduct_count, score_color, extra_note, comment
            )

            dim_defs = [
                ("作者与作品", "AUTHOR & WORK", 0, 6),
                ("角色设定",   "CHARACTER DESIGN", 6, 18),
                ("语言叙事",   "LANGUAGE & NARRATIVE", 18, 22),
                ("立场",       "FEMINIST STANCE", 22, 25),
            ]
            all_dims = []
            for dim_zh, dim_en, start, end in dim_defs:
                items = []
                for i in range(start, end):
                    ans = answers[i] if answers[i] else "—"
                    is_deduct = (i < 22 and ans == "有") or (i >= 22 and ans == "没有")
                    items.append((i, is_deduct, remarks[i] if remarks[i] else ""))
                all_dims.append((dim_zh, dim_en, items))

            html2 = build_detail_page_html(book_name, all_dims[:2], 2, principles)
            html3 = build_detail_page_html(book_name, all_dims[2:], 3, principles)

            # 并行渲染三页
            with ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(html_to_png_bytes, [html1, html2, html3]))

            page_labels = ["评分总览", "明细·作者与角色", "明细·语言与立场"]
            # ✅ 存入 session_state，download_button 触发 rerun 后仍能显示
            st.session_state["generated_imgs"] = list(zip(page_labels, results))

# ─────────────────────────────────────────────
# 显示图片区（从 session_state 读取，rerun 安全）
# ─────────────────────────────────────────────
if st.session_state["generated_imgs"]:
    st.divider()
    for label, img_bytes in st.session_state["generated_imgs"]:
        if img_bytes:
            st.markdown(f"#### {label}")
            st.image(img_bytes, use_container_width=True)
            st.download_button(
                label=f"⬇ 下载 {label}",
                data=img_bytes,
                file_name=f"{label}.png",
                mime="image/png",
                key=f"dl_{label}",
            )
