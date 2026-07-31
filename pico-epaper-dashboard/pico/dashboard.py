"""
仪表盘渲染器 v2 — Pico 2.66-B (152x296 竖屏)
黑/白/红三色设计: 红色外框+标题栏+进度条
自动换行 + 结构化布局
"""
import utime, gc

W, H = 152, 296
CHAR_W, CHAR_H = 8, 8
COLS = W // CHAR_W  # 19
ROWS = H // CHAR_H  # 37
BUF_SZ = 5624


def _wrap(text, width):
    """按宽度拆行, 尽量在空格/标点断开"""
    lines = []
    while len(text) > width:
        cut = width
        for i in range(width, max(width - 6, 0), -1):
            if i < len(text) and text[i] in " ,，。；;、-":
                cut = i
                break
        lines.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        lines.append(text)
    return lines


def render(epd, data):
    now = utime.localtime()
    bal = data.get("ds_balance", 0)
    total = data.get("ds_total", 0)
    todos = data.get("todos", [])
    err = data.get("error")

    # ━━ 清空 ━━
    epd.buffer_black[:] = b'\xff' * BUF_SZ
    epd.buffer_red[:] = b'\xff' * BUF_SZ

    # ═══ 红色双线边框 ═══
    # 外框 — 黑线
    epd.imageblack.rect(2, 2, W - 4, H - 4, 0)
    # 内框 — 红线
    epd.imagered.rect(4, 4, W - 8, H - 8, 0)

    # ═══ 标题栏: 红底黑框 ═══
    epd.imagered.fill_rect(5, 5, W - 10, 14, 0)    # 红底
    epd.imageblack.rect(5, 5, W - 10, 14, 0)        # 黑边
    epd.imageblack.text("DASHBOARD", 8, 6, 0)        # 黑字

    # 时间 — 右上角小黑框
    ts = "{:02d}:{:02d}".format(now[3], now[4])
    tw = len(ts) * CHAR_W
    tx = W - 9 - tw
    epd.imageblack.fill_rect(tx, 6, tw + 2, 12, 0)   # 黑底
    epd.imageblack.text(ts, tx + 1, 7, 1)             # 白字(黑底上)

    # ═══ DeepSeek 区 ═══
    y0 = 24
    epd.imagered.hline(6, y0 - 2, W - 12, 0)  # 红色分隔线

    epd.imageblack.text("DeepSeek", 6, y0, 0)
    if err:
        epd.imageblack.text("offline", 6, y0 + 10, 0)
    else:
        s = "Y {:.2f}".format(bal)
        epd.imageblack.text(s, 6, y0 + 10, 0)
        if bal < 2:
            epd.imagered.text(" LOW ", W - 38, y0 + 10, 0)

    # 余额进度条
    by = y0 + 24
    bw = W - 16
    pct = bal / total if total > 0 else 0
    filled = max(2, int(bw * pct))
    epd.imageblack.rect(6, by, bw, 6, 0)
    epd.imageblack.fill_rect(7, by + 1, filled, 4, 0)
    if pct < 0.15:
        epd.imagered.fill_rect(7, by + 1, filled, 4, 0)  # <15% 红色

    # ═══ 分隔 ═══
    y = by + 12
    epd.imagered.hline(6, y, W - 12, 0)
    y += 3

    # ═══ 待办区 ═══
    epd.imageblack.text("TODO", 6, y, 0)
    epd.imageblack.text(str(len(todos)), 6 + 5 * CHAR_W, y, 0)
    y += 10

    if not todos:
        epd.imageblack.text("( empty )", 8, y, 0)
    else:
        shown = 0
        for i, todo in enumerate(todos):
            # 兼容新旧格式
            if isinstance(todo, dict):
                text = todo.get('t', '')
                done = todo.get('d', False)
            else:
                text = str(todo)
                done = False

            wrapped = _wrap(text, COLS - 4)
            for li, line in enumerate(wrapped):
                if y > H - 22:
                    remaining = sum(
                        len(_wrap(
                            t.get('t', str(t)) if isinstance(t, dict) else str(t),
                            COLS - 4
                        ))
                        for t in todos[shown:]
                    )
                    epd.imageblack.text("...{} more".format(remaining), 8, y, 0)
                    y = H + 1
                    break

                if li == 0:
                    if done:
                        epd.imageblack.text("[x]", 8, y, 0)
                    elif i == 0:
                        epd.imagered.text(">", 8, y, 0)
                    else:
                        epd.imageblack.text(">", 8, y, 0)
                else:
                    epd.imageblack.text(" ", 8, y, 0)

                epd.imageblack.text(line, 8 + CHAR_W * 3, y, 0)
                y += 9

            if y > H:
                break
            y += 1
            shown += 1

    # ═══ 底栏 ═══
    y = H - 14
    epd.imagered.hline(6, y - 2, W - 12, 0)
    now_short = "{:02d}-{:02d}".format(now[1], now[2])
    epd.imageblack.text(now_short, 6, y, 0)
    epd.imageblack.text("5m", W - 20, y, 0)

    epd.display()
    gc.collect()
