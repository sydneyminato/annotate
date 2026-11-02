import sys
import time
import math
import random
import select
import tty
import termios

class AnnotateVJController:
    def __init__(self, cols=64, rows=18, bpm=135):
        self.RAM_SIZE = 32768
        self.HEAP_SIZE = 5000
        self.cells = [{"car": 0, "cdr": 0, "marked": False} for _ in range(self.HEAP_SIZE)]
        self.free_list = 1
        for i in range(1, self.HEAP_SIZE - 1):
            self.cells[i]["cdr"] = i + 1

        self.cols = cols
        self.rows = rows
        self.display_cells = cols * rows
        self.step_count = 0
        self.last_purged = 0
        self.bpm = bpm
        self.update_timing()

        # VJリアルタイム制御ステート
        self.mode = "NORMAL"        # NORMAL, STROBE, INVERT
        self.force_flash = False
        self.manual_purge_flag = False

    def update_timing(self):
        self.bpm = max(60, min(240, self.bpm))
        self.frame_sec = (60.0 / self.bpm) / 4.0  # 16分音符ごとの秒数

    def garbage_collect_safe(self, root_env):
        stack = [root_env]
        while stack:
            idx = stack.pop()
            if idx == 0 or idx >= self.HEAP_SIZE or self.cells[idx]["marked"]:
                continue
            self.cells[idx]["marked"] = True
            c = self.cells[idx]["car"]
            d = self.cells[idx]["cdr"]
            if 0 < c < self.HEAP_SIZE:
                stack.append(c)
            if 0 < d < self.HEAP_SIZE:
                stack.append(d)

        purged = 0
        self.free_list = 0
        for i in range(1, self.HEAP_SIZE):
            if self.cells[i]["marked"]:
                self.cells[i]["marked"] = False
            else:
                self.cells[i]["car"] = 0
                self.cells[i]["cdr"] = self.free_list
                self.free_list = i
                purged += 1
        return purged

    def get_key(self):
        """ノンブロッキングで1キー入力を取得"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    def render(self, status_text="RUNNING"):
        buf = ["\033[H"]
        bar_step = self.step_count % 16
        is_quarter = (bar_step % 4 == 0)

        # フラッシュ／ストロボ判定
        flash_active = self.force_flash or (self.mode == "STROBE" and bar_step % 2 == 0)

        # ステータスヘッダー
        state_color = "\033[1;37;41m" if flash_active else "\033[1;32m"
        header = (
            f"\033[1;36m=== ANNOTATE VJ CONSOLE [32KB METABOLIC FIELD] ===\033[0m\n"
            f"BPM: \033[1;33m{self.bpm:<3}\033[0m [+/-] | "
            f"FX: \033[1;35m{self.mode:<6}\033[0m [1-3] | "
            f"STATE: {state_color}{status_text:<9}\033[0m | "
            f"PURGE: [SPACE]\n"
            f"STEP: {self.step_count:06d} | "
            f"LAST PURGED: \033[1;31m{self.last_purged:04d} cells\033[0m | "
            f"EXIT: [q]\n"
            f"{'=' * self.cols}\n"
        )
        buf.append(header)

        # セル空間サンプリング
        stride = max(1, self.HEAP_SIZE // self.display_cells)
        grid = []
        for r in range(self.rows):
            line = []
            for c in range(self.cols):
                idx = (r * self.cols + c) * stride + 1
                if idx < self.HEAP_SIZE:
                    cell = self.cells[idx]
                    
                    if self.mode == "INVERT":
                        # 反転グリッチモード
                        if cell["marked"]:
                            line.append("\033[7;35m \033[0m")
                        elif cell["car"] != 0:
                            line.append("\033[7;31m.\033[0m")
                        else:
                            line.append("\033[1;37m#\033[0m")
                    else:
                        # 通常・ストロボモード
                        if flash_active:
                            line.append("\033[1;37;45m#\033[0m" if cell["marked"] else "\033[1;37m.\033[0m")
                        elif cell["marked"]:
                            line.append("\033[1;37m@\033[0m" if is_quarter else "\033[1;35m#\033[0m")
                        elif cell["car"] != 0:
                            line.append("\033[31m*\033[0m")
                        else:
                            line.append("\033[90m.\033[0m")
                else:
                    line.append(" ")
            grid.append("".join(line))

        buf.append("\n".join(grid))
        buf.append(f"\n{'=' * self.cols}\n")

        # 下段：XORビット波形
        t = self.step_count * 0.2
        wave_chars = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        wave_line = []
        for c in range(self.cols):
            xor_mod = (c ^ (self.step_count & 0x1F)) * 0.08
            v = int((math.sin(t + c * 0.12) + math.cos(t * 0.5 + xor_mod)) * 2.2)
            val_clamped = max(0, min(8, v + 4))
            wave_line.append(wave_chars[val_clamped])

        wave_color = "\033[1;33m" if is_quarter else "\033[36m"
        buf.append(wave_color + "".join(wave_line) + "\033[0m\n")

        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    def run(self):
        # 端末を生入力モード（raw mode）に切り替え
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        sys.stdout.write("\033[2J\033[?25l")
        root_env = 0

        try:
            tty.setcbreak(fd)
            while True:
                start_time = time.time()
                self.step_count += 1
                bar_step = self.step_count % 16

                # --- キーボード入力判定 ---
                key = self.get_key()
                if key == 'q':
                    break
                elif key == ' ':
                    self.manual_purge_flag = True
                    self.force_flash = True
                elif key in ('+', '='):
                    self.bpm += 5
                    self.update_timing()
                elif key == '-':
                    self.bpm -= 5
                    self.update_timing()
                elif key == '1':
                    self.mode = "NORMAL"
                elif key == '2':
                    self.mode = "STROBE"
                elif key == '3':
                    self.mode = "INVERT"

                # --- データ流入フェーズ ---
                burst = random.randint(30, 80)
                for _ in range(burst):
                    target = random.randint(1, self.HEAP_SIZE - 1)
                    self.cells[target]["car"] = random.randint(1, 0xFFFF)
                    if random.random() < 0.2:
                        root_env = target

                # --- 代謝・忘却判定（定期またはスペース強制） ---
                if self.manual_purge_flag or bar_step == 15:
                    self.render(status_text="PURGING")
                    time.sleep(self.frame_sec * 0.3)
                    
                    if self.manual_purge_flag:
                        # 手動ブレイク時は全更地化
                        root_env = 0
                        self.manual_purge_flag = False

                    self.last_purged = self.garbage_collect_safe(root_env)
                    
                    if self.step_count % 64 == 0:
                        root_env = 0

                    self.render(status_text="CLEARED")
                    self.force_flash = False
                else:
                    self.render(status_text="SURGING")

                # タイミングキープ
                elapsed = time.time() - start_time
                wait_time = self.frame_sec - elapsed
                if wait_time > 0:
                    time.sleep(wait_time)

        finally:
            # 終了時に必ず端末設定とカーソルを元の状態に復帰
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            sys.stdout.write("\033[?25h\033[0m\n")
            print("[ANNOTATE] VJ Console terminated cleanly.")

if __name__ == "__main__":
    vj = AnnotateVJController(cols=64, rows=18, bpm=135)
    vj.run()
