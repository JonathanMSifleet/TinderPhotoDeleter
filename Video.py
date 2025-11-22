#!/usr/bin/env python3
"""
video_cleaner.py

A simple Tkinter-based video reviewer:
  - A = move current video to _deleted folder
  - D = keep (advance)
  - P = play / pause
  - Z or Backspace = undo last action

Now includes:
  - Seek bar with draggable progress control
  - Click-to-seek (jump to any position instantly)
  - Live progress updates while playing

Requirements:
  pip install python-vlc
  VLC must be installed on the system.
"""

import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import vlc
except Exception as exc:
    raise SystemExit(
        "python-vlc is required. Install with: pip install python-vlc\n"
        "Also ensure VLC is installed on your system.\n"
        f"Original error: {exc}"
    )


class VideoReviewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Cleaner — A=Delete | D=Keep | P=Play/Pause | Z=Undo")
        self.root.configure(bg="black")
        self.root.minsize(800, 600)
        self.root.focus_force()

        # --- Video display area ---
        self.video_panel = tk.Frame(root, bg="black")
        self.video_panel.pack(expand=True, fill="both")
        self.video_panel.update_idletasks()

        # Overlay label
        self.overlay_label = tk.Label(
            self.video_panel,
            text="",
            bg="black",
            fg="white",
            font=("Arial", 20),
            justify="center"
        )
        self.overlay_label.place(relx=0.5, rely=0.5, anchor="center")

        # Stats bar
        self.stats_label = tk.Label(
            root,
            text="",
            font=("Arial", 14, "bold"),
            bg="black",
            fg="white"
        )
        self.stats_label.pack(side="bottom", fill="x", pady=8)

        # --- Seek bar ---
        self.seek_var = tk.DoubleVar()
        self.seek_bar = tk.Scale(
            root,
            from_=0,
            to=1000,
            orient="horizontal",
            variable=self.seek_var,
            command=self.on_seek,
            length=400,
            bg="black",
            fg="white",
            troughcolor="gray",
            highlightthickness=0,
        )
        self.seek_bar.pack(side="bottom", fill="x")

        self.user_is_seeking = False

        # Mouse-based seeking
        self.seek_bar.bind("<ButtonPress-1>", self.on_seek_click)
        self.seek_bar.bind("<B1-Motion>", self.start_seek)
        self.seek_bar.bind("<ButtonRelease-1>", self.end_seek)

        # --- VLC setup ---
        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()

        # Data
        self.folder = None
        self.deleted_folder = None
        self.video_paths = []
        self.index = 0
        self.deleted_count = 0
        self.kept_count = 0
        self.history = []

        # Key bindings
        self.root.bind_all("<Key-a>", self.delete_video)
        self.root.bind_all("<Key-A>", self.delete_video)
        self.root.bind_all("<Key-d>", self.keep_video)
        self.root.bind_all("<Key-D>", self.keep_video)
        self.root.bind_all("<Key-p>", self.play_pause_video)
        self.root.bind_all("<Key-P>", self.play_pause_video)
        self.root.bind_all("<Left>", self.delete_video)
        self.root.bind_all("<Right>", self.keep_video)
        self.root.bind_all("<Key-z>", self.go_back)
        self.root.bind_all("<Key-Z>", self.go_back)
        self.root.bind_all("<BackSpace>", self.go_back)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Poll seek bar updates
        self.update_seek_bar()

        # Ask for folder
        self.select_folder()

    # ---------------- SEEKING LOGIC ---------------- #

    def on_seek_click(self, event):
        """Jump directly where the user clicks on the seek bar."""
        bar_width = self.seek_bar.winfo_width()
        click_x = event.x
        click_x = max(0, min(bar_width, click_x))

        new_val = int((click_x / bar_width) * 1000)
        self.seek_var.set(new_val)

        self.apply_seek()

        # Mark as seeking to avoid auto-overwrite from polling
        self.user_is_seeking = True

    def start_seek(self, event=None):
        """User is dragging the slider."""
        self.user_is_seeking = True

    def end_seek(self, event=None):
        """User stopped dragging — apply change."""
        self.user_is_seeking = False
        self.apply_seek()

    def on_seek(self, value):
        """Apply seek when user clicks or drags the bar."""
        if self.user_is_seeking:
            return
        self.apply_seek()

    def apply_seek(self):
        """Convert seek bar 0–1000 range to VLC position."""
        try:
            pos = float(self.seek_var.get()) / 1000.0
            self.media_player.set_position(pos)
        except:
            pass

    def update_seek_bar(self):
        """Poll video position and update bar when not being dragged."""
        try:
            if not self.user_is_seeking and self.media_player.is_playing():
                pos = self.media_player.get_position()
                if 0 <= pos <= 1:
                    self.seek_var.set(pos * 1000)
        except:
            pass

        self.root.after(100, self.update_seek_bar)

    # ---------------- END SEEKING ---------------- #

    def select_folder(self):
        self.folder = filedialog.askdirectory(title="Select Folder with Videos")
        if not self.folder:
            self.root.quit()
            return

        self.deleted_folder = os.path.join(self.folder, "_deleted")
        if not os.path.exists(self.deleted_folder):
            os.makedirs(self.deleted_folder, exist_ok=True)

        exts = (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm")
        self.video_paths = [
            os.path.join(self.folder, f)
            for f in os.listdir(self.folder)
            if f.lower().endswith(exts)
        ]
        self.video_paths.sort(key=str.lower)

        if not self.video_paths:
            self.overlay_label.config(text="No videos found in this folder!", fg="red")
            return

        self.index = 0
        self.show_video()
        self.update_stats()
        self.root.lift()
        self.root.focus_force()

    def attach_player_to_widget(self):
        self.root.update_idletasks()
        self.root.update()

        wid = self.video_panel.winfo_id()
        try:
            if sys.platform.startswith("win"):
                self.media_player.set_hwnd(wid)
            elif sys.platform == "darwin":
                self.media_player.set_nsobject(wid)
            else:
                self.media_player.set_xwindow(wid)
        except Exception as e:
            print("Could not attach VLC output:", e)

    def show_video(self):
        try:
            self.media_player.stop()
        except:
            pass

        if self.index >= len(self.video_paths):
            self.overlay_label.config(text="All done!\nClose the window when ready.", fg="lime")
            self.update_stats()
            return

        path = self.video_paths[self.index]
        basename = os.path.basename(path)

        self.overlay_label.config(text=basename, fg="white")

        media = self.vlc_instance.media_new(str(path))
        self.media_player.set_media(media)
        self.attach_player_to_widget()

        self.media_player.play()

        # Reset seek bar to zero
        self.seek_var.set(0)

        self.root.after(600, lambda: self.overlay_label.config(text=""))

    def delete_video(self, event=None):
        if self.index >= len(self.video_paths):
            return "break"

        try:
            self.media_player.stop()
        except:
            pass

        original_path = self.video_paths[self.index]
        basename = os.path.basename(original_path)
        deleted_path = os.path.join(self.deleted_folder, basename)

        try:
            os.rename(original_path, deleted_path)
            self.history.append(("delete", deleted_path, original_path, self.index))
            self.deleted_count += 1
        except Exception as e:
            messagebox.showerror("Error", f"Could not move file: {e}")
            return "break"

        del self.video_paths[self.index]

        if self.index >= len(self.video_paths):
            self.index = max(0, len(self.video_paths))

        self.show_video()
        self.update_stats()
        return "break"

    def keep_video(self, event=None):
        if self.index >= len(self.video_paths):
            return "break"

        try:
            self.media_player.stop()
        except:
            pass

        path = self.video_paths[self.index]
        self.history.append(("keep", path, self.index))
        self.kept_count += 1

        self.index += 1
        self.show_video()
        self.update_stats()
        return "break"

    def play_pause_video(self, event=None):
        if self.index >= len(self.video_paths):
            return "break"

        try:
            if self.media_player.is_playing():
                self.media_player.pause()
            else:
                curr_media = self.media_player.get_media()
                expected_path = os.path.abspath(self.video_paths[self.index])

                mismatch = True
                if curr_media:
                    m = curr_media.get_mrl()
                    try:
                        if m.startswith("file://"):
                            from urllib.parse import unquote, urlparse
                            parsed = urlparse(m)
                            mpath = unquote(parsed.path)
                            if sys.platform.startswith("win") and mpath.startswith("/"):
                                mpath = mpath.lstrip("/")
                            if os.path.abspath(mpath) == expected_path:
                                mismatch = False
                    except:
                        mismatch = True

                if mismatch:
                    self.show_video()
                else:
                    self.media_player.play()

        except Exception as e:
            print("Playback error:", e)

        return "break"

    def go_back(self, event=None):
        if not self.history:
            return "break"

        try:
            self.media_player.stop()
        except:
            pass

        action = self.history.pop()

        if action[0] == "delete":
            _, deleted_path, original_path, prev_index = action
            try:
                os.rename(deleted_path, original_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not restore file: {e}")
                return "break"

            insert_index = min(prev_index, len(self.video_paths))
            self.video_paths.insert(insert_index, original_path)
            self.index = insert_index
            self.deleted_count -= 1

        else:
            _, path, prev_index = action
            self.kept_count -= 1

            try:
                pos = self.video_paths.index(path)
                self.index = pos
            except ValueError:
                insert_index = min(prev_index, len(self.video_paths))
                self.video_paths.insert(insert_index, path)
                self.index = insert_index

        self.show_video()
        self.update_stats()
        return "break"

    def update_stats(self):
        remaining = max(0, len(self.video_paths) - self.index)
        self.stats_label.config(
            text=f"   Remaining: {remaining}   |   Kept: {self.kept_count}   |   Deleted: {self.deleted_count}   |   Z = Undo"
        )

    def on_closing(self):
        try:
            self.media_player.stop()
        except:
            pass

        if self.deleted_folder and os.path.exists(self.deleted_folder) and os.listdir(self.deleted_folder):
            if messagebox.askyesno("Permanently Delete", "Delete the _deleted folder permanently?"):
                try:
                    shutil.rmtree(self.deleted_folder)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete folder: {e}")

        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass


def main():
    root = tk.Tk()
    app = VideoReviewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
