import os
import subprocess
import sys
import shutil

# ── Auto-install wkhtmltopdf on Streamlit Cloud ──────────────
def _find_wkhtmltoimage():
    """Return the path to wkhtmltoimage, or None if not found."""
    for p in ["/usr/local/bin/wkhtmltoimage", "/usr/bin/wkhtmltoimage"]:
        if os.path.exists(p):
            return p
    return shutil.which("wkhtmltoimage")

def _install_wkhtmltopdf():
    if _find_wkhtmltoimage():
        return
    deb_url = "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bullseye_amd64.deb"
    deb_path = "/tmp/wkhtmltox.deb"
    subprocess.run(["wget", "-q", "-O", deb_path, deb_url], check=True, timeout=120)
    subprocess.run(["dpkg", "-i", deb_path], capture_output=True)
    subprocess.run(["apt-get", "install", "-f", "-y"], capture_output=True)

try:
    _install_wkhtmltopdf()
except Exception:
    pass
# ─────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
from principle import principles, dimension_labels
from datetime import datetime
import base64
import subprocess
import os
import random

st.set_page_config(page_title="女主无CP评分系统", page_icon="📖", layout="wide")


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

st.title("女主无CP / 无男主小说评分")

with st.sidebar:
    st.header("评分规则")
    st.markdown("""
**1. 打分为减分制**
完结小说满分为10分，读者根据阅读后体验和感受，给一个印象得分，然后再根据组规进行减分。
即最终得分 = 印象分 - 减分项，最终得分 < 10分。
【谨慎打8分以上，禁止分数膨胀】

**2. 打分规则**
各项基础扣分分值为1分，情节严重的可以增加扣分分值，无上限，必须列出各项减分项存在与否。
【❗注意：没有明确标注/不完全/模棱两可的即需要扣分，请各位打分人严格执行！】

**维度说明**
- 📂 作者与作品（p1–p6）【有 = 扣分】
- 👤 角色设定（p7–p18）【有 = 扣分】
- 💬 语言叙事（p19–p22）【有 = 扣分】
- 🏳️ 立场（p23–p25）【没有 = 扣分】
""")

# ── 书目信息 ──
col1, col2 = st.columns(2)
with col1:
    book_name   = st.text_input("书名")
    book_author = st.text_input("作者")
with col2:
    book_plate = st.text_input("发布平台")
    ich        = st.text_input("评分人")

col3, col4 = st.columns([1, 2])
with col3:
    impressed_rate = st.number_input("印象分（满分10）", min_value=0.0, max_value=10.0, step=0.5)
with col4:
    now = datetime.now().date()
    st.caption(f"评分日期：{now}")

st.divider()

# ── 一键随机打分 ──
if st.button("⚡ 一键随机打分（演示）"):
    auto = [random.choice(["有", "没有"]) for _ in range(22)]
    auto += [random.choice(["没有", "没有", "有"]) for _ in range(3)]
    st.session_state.answers = auto
    st.session_state.remarks = [""] * 25
    st.success("已随机生成打分结果，可在下方调整。")

if "answers" not in st.session_state:
    st.session_state.answers = [None] * 25
if "remarks" not in st.session_state:
    st.session_state.remarks = [""] * 25

answers = list(st.session_state.answers)
remarks = list(st.session_state.remarks)

# ── 按维度打分 ──
dimensions = [
    ("📂 作者与作品", 0, 6,  "有"),
    ("👤 角色设定",   6, 18, "有"),
    ("💬 语言叙事",  18, 22, "有"),
    ("🏳️ 立场",     22, 25, "没有"),
]

for dim_name, start, end, deduct_when in dimensions:
    st.subheader(dim_name)
    for i in range(start, end):
        cols = st.columns([5, 2, 3])
        with cols[0]:
            hint = f"【{deduct_when} = 扣分】"
            st.write(f"**p{i+1}** {principles[i]}")
            st.caption(hint)
        with cols[1]:
            default_idx = 0 if answers[i] == "有" else (1 if answers[i] == "没有" else None)
            q = st.radio("", ["有", "没有"], index=default_idx,
                         key=f"radio_{i}", label_visibility="collapsed", horizontal=True)
            answers[i] = q
        with cols[2]:
            r = st.text_input("", value=remarks[i], key=f"remark_{i}",
                              placeholder="备注（可选）", label_visibility="collapsed")
            remarks[i] = r

st.session_state.answers = answers
st.session_state.remarks = remarks

st.divider()

# ── 额外扣分 & 评语 ──
col5, col6 = st.columns([1, 2])
with col5:
    extra_rate = st.number_input("其它恶劣情节额外扣分", min_value=0.0, max_value=10.0, step=0.5)
with col6:
    extra_note = st.text_area("额外扣分备注")

comment = st.text_area("评分人综合评语")


# ─────────────────────────────────────────────
# Generate Image
# ─────────────────────────────────────────────

def build_page1_html(book_name, book_author, book_plate, ich, now,
                     impressed_rate, criteria_deduct, extra_rate, sum_rate,
                     deduct_count, score_color, extra_note, comment):

    extra_block = ""
    if extra_rate > 0 or extra_note:
        extra_block = (
            '<div style="padding:14px 20px 16px;border-bottom:1px solid #e0dbd4;">'
            '<div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:8px;font-family:Georgia,serif;">ADDITIONAL DEDUCTION · 额外扣分</div>'
            f'<div style="font-size:13px;color:#333;line-height:1.6;">{extra_note}</div>'
            f'<div style="font-size:11px;color:#b03a2e;font-weight:700;margin-top:4px;font-family:Georgia,serif;">−{extra_rate:.1f} 分</div>'
            '</div>'
        )

    comment_block = ""
    if comment:
        comment_block = (
            '<div style="padding:16px 20px 20px;border-top:1px solid #e0dbd4;">'
            '<div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:8px;font-family:Georgia,serif;">REVIEWER\'S NOTE</div>'
            f'<div style="font-size:13px;color:#444;line-height:1.8;font-style:italic;font-family:Georgia,serif;">「{comment}」</div>'
            '</div>'
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:430px; background:#f7f5f2; font-family:'PingFang SC','Microsoft YaHei','Noto Sans CJK SC',sans-serif; color:#1a1a1a; }}
</style></head><body>
<div style="background:#fff;border:1px solid #ddd;">
  <div style="padding:32px 28px 26px;text-align:center;background:#fffdf9;border-bottom:1px solid #e8e2d8;">
    <div style="font-size:8px;letter-spacing:5px;color:#c8b89a;margin-bottom:10px;font-family:Georgia,serif;">FEMINIST LITERATURE RATING CERTIFICATE</div>
    <div style="font-size:20px;font-weight:800;color:#111;letter-spacing:3px;line-height:1.3;">女主无CP<br>无男主小说评鉴书</div>
    <div style="display:flex;align-items:center;gap:10px;margin:14px auto 0;width:200px;">
      <div style="flex:1;height:1px;background:#e0d5c0;"></div>
      <div style="width:5px;height:5px;background:#c8b89a;transform:rotate(45deg);flex-shrink:0;"></div>
      <div style="flex:1;height:1px;background:#e0d5c0;"></div>
    </div>
  </div>
  <div style="border-bottom:2px solid #1a1a1a;">
    <div style="padding:28px 28px 20px;text-align:center;border-bottom:1px solid #e0dbd4;background:#fff;">
      <div style="font-size:9px;color:#c8b89a;letter-spacing:4px;margin-bottom:8px;font-family:Georgia,serif;">FINAL SCORE</div>
      <div style="font-size:88px;font-weight:800;color:{score_color};line-height:1;letter-spacing:-3px;font-family:Georgia,serif;">{sum_rate:.1f}</div>
      <div style="font-size:11px;color:#bbb;margin-top:6px;letter-spacing:3px;">/ 10</div>
    </div>
    <div style="background:#fff;">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 28px;border-bottom:1px solid #f0eeec;">
        <div>
          <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">IMPRESSION</div>
          <div style="font-size:14px;color:#555;letter-spacing:1px;">印　象　分</div>
        </div>
        <div style="font-size:40px;font-weight:300;color:#c09430;letter-spacing:-1px;font-family:Georgia,serif;">+{impressed_rate:.1f}</div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 28px;border-bottom:1px solid #f0eeec;">
        <div>
          <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">CRITERIA</div>
          <div style="font-size:14px;color:#555;letter-spacing:1px;">准则扣分 <span style="font-size:11px;color:#bbb;">共{deduct_count}项</span></div>
        </div>
        <div style="font-size:40px;font-weight:300;color:#b03a2e;letter-spacing:-1px;font-family:Georgia,serif;">{criteria_deduct:.0f}</div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 28px;">
        <div>
          <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:3px;font-family:Georgia,serif;">ADDITIONAL</div>
          <div style="font-size:14px;color:#555;letter-spacing:1px;">额外扣分</div>
        </div>
        <div style="font-size:40px;font-weight:300;color:#888;letter-spacing:-1px;font-family:Georgia,serif;">−{extra_rate:.1f}</div>
      </div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid #e0dbd4;">
    <div style="padding:14px 20px;border-right:1px solid #ece8e0;border-bottom:1px solid #ece8e0;">
      <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:5px;font-family:Georgia,serif;">TITLE</div>
      <div style="font-size:15px;font-weight:700;color:#111;">{book_name}</div>
    </div>
    <div style="padding:14px 20px;border-bottom:1px solid #ece8e0;">
      <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:5px;font-family:Georgia,serif;">AUTHOR</div>
      <div style="font-size:15px;font-weight:700;color:#111;">{book_author or "—"}</div>
    </div>
    <div style="padding:14px 20px;border-right:1px solid #ece8e0;">
      <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:5px;font-family:Georgia,serif;">PLATFORM</div>
      <div style="font-size:15px;font-weight:700;color:#111;">{book_plate or "—"}</div>
    </div>
    <div style="padding:14px 20px;">
      <div style="font-size:8px;color:#c8b89a;letter-spacing:3px;margin-bottom:5px;font-family:Georgia,serif;">REVIEWER · DATE</div>
      <div style="font-size:13px;font-weight:600;color:#111;">{ich or "—"}<br>{now}</div>
    </div>
  </div>
  {extra_block}
  {comment_block}
  <div style="padding:12px 20px;background:#fffdf9;border-top:1px solid #e0dbd4;display:flex;align-items:center;gap:10px;">
    <div style="flex:1;height:1px;background:#e0d5c0;"></div>
    <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;font-family:Georgia,serif;white-space:nowrap;">PAGE 1</div>
    <div style="flex:1;height:1px;background:#e0d5c0;"></div>
  </div>
</div>
</body></html>"""


def build_detail_page_html(book_name, dim_chunks, page_num, principles):
    blocks = ""
    for dim_zh, dim_en, items in dim_chunks:
        rows = ""
        for (i, is_deduct, remark_text) in items:
            dot = "#c0392b" if is_deduct else "#aab8b0"
            badge = (
                '<span style="font-size:13px;font-weight:700;color:#b03a2e;font-family:Georgia,serif;">−1</span>'
                if is_deduct else
                '<span style="font-size:13px;color:#ccc;font-family:Georgia,serif;">0</span>'
            )
            remark_html = ('<div style="margin-top:4px;color:#aaa;font-size:11px;line-height:1.5;font-style:italic;">↳ ' + remark_text + '</div>') if remark_text else ""
            sep = "#f0eeec" if is_deduct else "#f5f5f5"
            bg = "#fffbfb" if is_deduct else "#fff"
            rows += (
                f'<tr style="background:{bg};border-bottom:1px solid {sep};">'
                f'<td style="padding:11px 8px 11px 20px;width:16px;vertical-align:top;">'
                f'<div style="width:9px;height:9px;border-radius:50%;background:{dot};margin-top:4px;"></div></td>'
                f'<td style="padding:11px 8px 11px 0;font-size:13px;color:#2c2c2c;line-height:1.6;vertical-align:top;">'
                f'<span style="color:#c8b89a;font-size:10px;margin-right:5px;font-family:Georgia,serif;">p{i+1}</span>'
                f'{principles[i]}' + remark_html + '</td>'
                f'<td style="padding:11px 20px 11px 8px;text-align:right;vertical-align:top;white-space:nowrap;">{badge}</td>'
                f'</tr>'
            )
        blocks += (
            '<div>'
            f'<div style="padding:11px 20px;background:#fff;border-top:1px solid #e0dbd4;display:flex;align-items:baseline;gap:10px;">'
            f'<span style="font-size:13px;font-weight:700;color:#1a1a1a;letter-spacing:2px;">{dim_zh}</span>'
            f'<span style="font-size:8px;color:#c8b89a;letter-spacing:3px;">{dim_en}</span>'
            f'</div>'
            f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:430px; background:#f7f5f2; font-family:'PingFang SC','Microsoft YaHei','Noto Sans CJK SC',sans-serif; color:#1a1a1a; }}
</style></head><body>
<div style="background:#fff;border:1px solid #ddd;">
  <div style="padding:18px 20px 14px;text-align:center;background:#fffdf9;border-bottom:1px solid #e8e2d8;">
    <div style="font-size:8px;letter-spacing:5px;color:#c8b89a;font-family:Georgia,serif;">SCORING DETAIL · 评分明细</div>
    <div style="font-size:14px;font-weight:700;color:#111;margin-top:4px;letter-spacing:2px;">《{book_name}》</div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;padding:8px 20px;background:#fafaf8;border-bottom:1px solid #ece8e0;">
    <div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#777;">
      <div style="width:8px;height:8px;border-radius:50%;background:#c0392b;"></div>扣分（−1）
    </div>
    <div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#777;">
      <div style="width:8px;height:8px;border-radius:50%;background:#aab8b0;"></div>无扣分（0）
    </div>
  </div>
  <div>{blocks}</div>
  <div style="padding:12px 20px;background:#fffdf9;border-top:1px solid #e0dbd4;display:flex;align-items:center;gap:10px;">
    <div style="flex:1;height:1px;background:#e0d5c0;"></div>
    <div style="font-size:7px;color:#c8b89a;letter-spacing:3px;font-family:Georgia,serif;white-space:nowrap;">PAGE {page_num}</div>
    <div style="flex:1;height:1px;background:#e0d5c0;"></div>
  </div>
</div>
</body></html>"""


if st.button("🖼️ 生成评鉴图片"):
    if not book_name:
        st.warning("请先填写书名！")
    else:
        with st.spinner("正在生成评鉴证书图片..."):
            score_color = "#b03a2e" if sum_rate < 4 else ("#a04000" if sum_rate < 6 else ("#1a3a5c" if sum_rate < 8 else "#1d6a3a"))
            deduct_count = len(deduct_details)

            # Page 1: summary
            html1 = build_page1_html(
                book_name, book_author, book_plate, ich, now,
                impressed_rate, criteria_deduct, extra_rate, sum_rate,
                deduct_count, score_color, extra_note, comment
            )

            # Build dimension item lists
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
                    is_deduct = (i < 22 and ans == '有') or (i >= 22 and ans == '没有')
                    items.append((i, is_deduct, remarks[i] if remarks[i] else ""))
                all_dims.append((dim_zh, dim_en, items))

            # Page 2: 作者与作品 + 角色设定
            # Page 3: 语言叙事 + 立场
            html2 = build_detail_page_html(book_name, all_dims[:2], 2, principles)
            html3 = build_detail_page_html(book_name, all_dims[2:], 3, principles)

            pages = [html1, html2, html3]
            page_labels = ["评分总览", "明细·作者与角色", "明细·语言与立场"]
            img_bytes_list = []

            for idx, html in enumerate(pages):
                tmp_html = f"/tmp/rating_p{idx+1}.html"
                tmp_png  = f"/tmp/rating_p{idx+1}.png"
                with open(tmp_html, "w", encoding="utf-8") as f:
                    f.write(html)
                subprocess.run(
                    [_find_wkhtmltoimage() or "wkhtmltoimage", "--width", "430", "--quality", "95",
                     "--enable-local-file-access", tmp_html, tmp_png],
                    capture_output=True
                )
                if os.path.exists(tmp_png):
                    with open(tmp_png, "rb") as f:
                        img_bytes_list.append((page_labels[idx], f.read()))

            if img_bytes_list:
                for label, img_bytes in img_bytes_list:
                    st.markdown(f"#### {label}")
                    st.image(img_bytes, use_container_width=True)
                    b64 = base64.b64encode(img_bytes).decode()
                    dl = f'<a href="data:image/png;base64,{b64}" download="{book_name}_{label}.png" style="display:inline-block;background:#111;color:#fff;border-radius:4px;padding:8px 24px;text-decoration:none;font-size:13px;letter-spacing:2px;margin-bottom:20px;">⬇ 下载 {label}</a>'
                    st.markdown(dl, unsafe_allow_html=True)
            else:
                st.error("图片生成失败，请检查环境。")
