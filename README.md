# 📟 Pico ePaper Dashboard

> 基于 Raspberry Pi Pico 2 W + Waveshare 2.66" 三色墨水屏的个人仪表盘，DeepSeek API 余额物理化展示 + 待办管理。

![screen](/screen.jpg)

## 功能

- 💰 **DeepSeek 余额显示** — API 余额 + 进度条，低余额红色警告
- ✅ **待办管理** — 手机 Web 界面添加/勾选/清除，屏幕实时同步
- 🎨 **三色墨水屏设计** — 充分利用黑/白/红三色，红色边框 + 标题栏
- 🌐 **WiFi 通信** — Pico 直连 PHP API 服务端，无需电脑中转
- 📱 **移动端 Web UI** — 手机浏览器直接操控，深色界面
- ⏱️ **自动刷新** — 默认 5 分钟，可调整

## 硬件

| 组件 | 型号 |
|------|------|
| 主控 | Raspberry Pi Pico 2 W (RP2350) |
| 屏幕 | Waveshare 2.66" e-Paper (B) — 152×296, 黑/白/红 |
| 连接 | SPI1 |

### 接线
值得一提的是如果你手上的是跟我型号相同的显示屏，显示屏背面是自带引脚的，直接将PICO一整个插入即可
![screen](/beim.jpg)
| Pico 2W | e-Paper |
|---------|---------|
| GP10 (SCK) | SCK |
| GP11 (MOSI) | MOSI |
| GP9 (CS) | CS |
| GP8 (DC) | DC |
| GP12 (RST) | RST |
| GP13 (BUSY) | BUSY |
| 3.3V | VCC |
| GND | GND |

## 架构

```
┌─────────────┐     HTTP      ┌─────────────────┐     HTTPS     ┌──────────────┐
│  Pico 2 W   │──────────────▶│  PHP 服务端      │──────────────▶│  DeepSeek API │
│  墨水屏显示  │               │  api.php         │               │  /user/balance│
│  Web 服务   │◀──────────────│  JSON 存储       │               └──────────────┘
└─────────────┘               └─────────────────┘
       │
       ▼
  📱 手机浏览器
  http://192.168.3.250
```

-关于为啥不直接在PICO上调用deepseek的API，是因为PICO貌似并没有SSL,所以只能在电脑或者其它服务器上设置一个服务端
- Pico 通过原始 socket（无 SSL）GET/POST → PHP 服务端
- PHP 服务端代理 DeepSeek HTTPS API，存储待办到 JSON 文件
- Pico 运行微型 HTTP 服务器，手机浏览器直接连接操控

## 部署

### 1. 服务端 (PHP)

将 `server/api.php` 上传到任意 PHP 8+ 服务器（需 curl 扩展）。

编辑 `api.php`，替换 DeepSeek API Key：
```php
$DS_KEY = 'YOUR_DEEPSEEK_API_KEY';
```

确保 Nginx/Apache 允许直接 HTTP 访问 `api.php`（Pico 不支持 HTTPS）。

测试：
```bash
curl http://YOUR_SERVER_IP/api.php?action=all
# {"ds_balance":9.75,"ds_total":9.75,"todos":[],"error":null}
```

### 2. Pico 固件

固件要求：**MicroPython (Pico 2 W 版本)**

1. 复制 `pico/config.example.py` → `pico/config.py`
2. 填写 WiFi 和服务器信息
3. 上传所有 `pico/` 下文件到 Pico：
   - `epaper_2in66_b.py` — 屏幕驱动
   - `dashboard.py` — 渲染器
   - `main.py` — 主程序
   - `config.py` — 配置文件

4. 重启 Pico，屏幕显示仪表盘

### 3. 使用

手机连接同一 WiFi，浏览器打开 `http://<PICO_IP>`（屏幕底部会显示 IP）。

- **添加待办**：输入框 + 点 +
- **完成**：点 V 按钮
- **清除已完成**：点「清除已完成」
- **刷新**：点「刷新」
- **相框模式**：上传图片（需 5624×2 字节 .bin 格式）

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `?action=all` | GET | 获取余额 + 全部待办 |
| `?action=todos` | POST | 保存待办列表 |
| `?action=done&idx=0` | POST | 标记第 N 项完成 |
| `?action=undone&idx=0` | POST | 取消完成 |
| `?action=clear_done` | POST | 清除已完成项 |

##你也许会遇到的问题
-在我使用的时候，PICO疑似只能连接2.4G的无线网络
-而且网络的加密不能太复杂，WPA2PSK是可以兼容的
-而且好像自动分配DHCP也有点问题，所以我在代码里直接手动分配了一个地址
## 截图

| 墨水屏 | Web 界面 |
|:---:|:---:|
| ![screen](/screen.jpg) | ![web](/web.jpg) |

## 技术细节

- 待办数据存储在 `dashboard_data.json`（PHP 服务端）
- 余额进度条 <15% 时红色警告
- 文本自动换行，按中文标点断行
- MicroPython 不支持 `bytes.format()`，使用字符串拼接
- 2.66-B 屏幕编码：`buffer=0` 为有颜色，`display()` 发送 `~buffer`（按位取反）

## License

MIT
