"""
Pico-ePaper-2.66-B 驱动
Waveshare 2.66寸 三色(红/黑/白) 墨水屏
分辨率: 152×296 (竖屏)
基于 Waveshare 官方驱动精简
"""

from machine import Pin, SPI
import framebuf
import utime

EPD_WIDTH = 152
EPD_HEIGHT = 296

# --- 波形查找表 (Partial Refresh LUT) ---
WF_PARTIAL_2IN66 = [
    0x00,0x40,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x80,0x80,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x40,0x40,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x80,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x0A,0x00,0x00,0x00,0x00,0x00,0x02,0x01,0x00,0x00,
    0x00,0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x22,0x22,0x22,0x22,0x22,0x22,
    0x00,0x00,0x00,0x22,0x17,0x41,0xB0,0x32,0x36,
]


class EPD_2in66_B:
    """2.66寸三色墨水屏驱动"""

    def __init__(self):
        # 引脚配置
        self.reset_pin = Pin(12, Pin.OUT)
        self.busy_pin = Pin(13, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(9, Pin.OUT)
        self.dc_pin = Pin(8, Pin.OUT)

        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        # SPI1: SCK=GP10, MOSI=GP11
        self.spi = SPI(1)
        self.spi.init(baudrate=4_000_000)

        # 双缓冲区: 黑色层 + 红色层
        self.buffer_black = bytearray(self.height * self.width // 8)
        self.buffer_red = bytearray(self.height * self.width // 8)
        self.imageblack = framebuf.FrameBuffer(
            self.buffer_black, self.width, self.height, framebuf.MONO_HLSB
        )
        self.imagered = framebuf.FrameBuffer(
            self.buffer_red, self.width, self.height, framebuf.MONO_HLSB
        )
        self._init_hardware()

    # ---- 硬件底层 ----

    def _init_hardware(self):
        self._reset()
        self._read_busy()
        self._send_command(0x12)  # SWRESET
        self._read_busy()

        self._send_command(0x11)
        self._send_data(0x03)

        self._set_window(0, 0, self.width - 1, self.height - 1)

        self._send_command(0x21)  # 分辨率设置
        self._send_data(0x00)
        self._send_data(0x80)

        self._set_cursor(0, 0)
        self._read_busy()

    def _reset(self):
        self.reset_pin.value(1)
        utime.sleep_ms(50)
        self.reset_pin.value(0)
        utime.sleep_ms(2)
        self.reset_pin.value(1)
        utime.sleep_ms(50)

    def _read_busy(self):
        utime.sleep_ms(50)
        while self.busy_pin.value() == 1:
            utime.sleep_ms(10)
        utime.sleep_ms(50)

    def _send_command(self, cmd):
        self.dc_pin.value(0)
        self.cs_pin.value(0)
        self.spi.write(bytearray([cmd]))
        self.cs_pin.value(1)

    def _send_data(self, data):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray([data]))
        self.cs_pin.value(1)

    def _send_data_bulk(self, buf):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray(buf))
        self.cs_pin.value(1)

    def _set_window(self, xs, ys, xe, ye):
        self._send_command(0x44)
        self._send_data((xs >> 3) & 0x1F)
        self._send_data((xe >> 3) & 0x1F)
        self._send_command(0x45)
        self._send_data(ys & 0xFF)
        self._send_data((ys >> 8) & 0x01)
        self._send_data(ye & 0xFF)
        self._send_data((ye >> 8) & 0x01)

    def _set_cursor(self, x, y):
        self._send_command(0x4E)
        self._send_data(x & 0x1F)
        self._send_command(0x4F)
        self._send_data(y & 0xFF)
        self._send_data((y >> 8) & 0x01)

    def _turn_on(self):
        self._send_command(0x20)
        self._read_busy()

    # ---- 高级操作 ----

    def display(self):
        """将缓冲区内容刷新到屏幕"""
        wide = self.width // 8

        # 黑色层 (0x24)
        self._send_command(0x24)
        for j in range(self.height):
            for i in range(wide):
                self._send_data(~self.buffer_black[i + j * wide])

        # 红色层 (0x26)
        self._send_command(0x26)
        for j in range(self.height):
            for i in range(wide):
                self._send_data(~self.buffer_red[i + j * wide])

        self._turn_on()

    def clear(self):
        """清屏 (全白)"""
        wide = self.width // 8

        self._send_command(0x24)
        self._send_data_bulk([0xFF] * self.height * wide)

        self._send_command(0x26)
        self._send_data_bulk([0x00] * self.height * wide)

        self._turn_on()

    def load_raw(self, data):
        """
        直接加载二进制图像数据
        data: 11248 字节 (5624 黑色 + 5624 红色)
        """
        self.buffer_black[:] = data[:5624]
        self.buffer_red[:] = data[5624:11248]

    def show_raw(self):
        """显示load_raw加载的数据"""
        self.display()

    def sleep(self):
        """进入深度睡眠 (省电)"""
        self._send_command(0x10)
        self._send_data(0x01)
