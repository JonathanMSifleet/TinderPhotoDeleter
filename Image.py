import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

class ImageReviewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Cleaner — A=Delete (to _deleted folder) | D=Keep | Z=Undo Last")
        self.root.configure(bg="black")
        self.root.minsize(800, 600)
        self.root.focus_force()

        # Image display
        self.image_label = tk.Label(root, bg="black", takefocus=True)
        self.image_label.pack(expand=True, fill="both")
        self.image_label.focus_set()

        # Stats bar
        self.stats_label = tk.Label(
            root,
            text="",
            font=("Arial", 14, "bold"),
            bg="black",
            fg="white"
        )
        self.stats_label.pack(side="bottom", fill="x", pady=12)

        # Data
        self.folder = None
        self.deleted_folder = None
        self.image_paths = []
        self.index = 0
        self.deleted_count = 0
        self.kept_count = 0
        self.history = []           # For undo (Z key)
        self.current_photo = None

        # Key bindings — use root.bind_all with proper event names for reliability
        self.root.bind_all("<Key-a>", self.delete_image)
        self.root.bind_all("<Key-A>", self.delete_image)
        self.root.bind_all("<Key-d>", self.keep_image)
        self.root.bind_all("<Key-D>", self.keep_image)
        self.root.bind_all("<Left>", self.delete_image)
        self.root.bind_all("<Right>", self.keep_image)
        self.root.bind_all("<Key-z>", self.go_back)
        self.root.bind_all("<Key-Z>", self.go_back)
        self.root.bind_all("<BackSpace>", self.go_back)

        self.root.bind("<Configure>", self.on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.select_folder()

    def select_folder(self):
        self.folder = filedialog.askdirectory(title="Select Folder with Images")
        if not self.folder:
            self.root.quit()
            return

        self.deleted_folder = os.path.join(self.folder, "_deleted")
        if not os.path.exists(self.deleted_folder):
            os.makedirs(self.deleted_folder)

        exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".heic", ".svg")
        self.image_paths = [
            os.path.join(self.folder, f)
            for f in os.listdir(self.folder)
            if f.lower().endswith(exts)
        ]
        self.image_paths.sort(key=str.lower)

        if not self.image_paths:
            self.image_label.config(text="No images found in this folder!", fg="red")
            return

        self.show_image()
        self.update_stats()

        # Extra focus
        self.root.lift()
        self.root.focus_force()
        self.image_label.focus_set()

    def show_image(self):
        if self.index >= len(self.image_paths):
            self.image_label.config(image="", text="All done!\nClose the window when ready.", fg="lime")
            self.current_photo = None  # Clear reference
            if hasattr(self, 'current_original'):
                del self.current_original  # Clear original
            self.update_stats()
            return

        path = self.image_paths[self.index]
        try:
            img = Image.open(path).convert("RGB")
            self.current_original = img
            self.render_resized_image()
        except Exception as e:
            print(f"Can't load {path}: {e}")
            self.delete_image()  # move broken files to _deleted
            return

        self.image_label.focus_set()

    def delete_image(self):
        print("Delete key pressed")  # Debug to confirm key event
        if self.index >= len(self.image_paths):
            return "break"

        original_path = self.image_paths[self.index]
        basename = os.path.basename(original_path)
        deleted_path = os.path.join(self.deleted_folder, basename)
        try:
            os.rename(original_path, deleted_path)
            print(f"Moved to _deleted: {basename}")
            self.history.append(("delete", deleted_path, original_path))
            self.deleted_count += 1
        except Exception as e:
            print(f"Move failed {original_path}: {e}")

        del self.image_paths[self.index]
        self.show_image()
        self.update_stats()
        return "break"

    def keep_image(self):
        print("Keep key pressed")  # Debug
        if self.index >= len(self.image_paths):
            return "break"

        path = self.image_paths[self.index]
        self.history.append(("keep", path))
        self.kept_count += 1
        print(f"Kept: {os.path.basename(path)}")

        self.index += 1
        self.show_image()
        self.update_stats()
        return "break"

    def go_back(self):
        print("Undo key pressed")  # Debug
        if not self.history:
            return "break"

        action_tup = self.history.pop()
        if action_tup[0] == "delete":
            deleted_path, original_path = action_tup
            try:
                os.rename(deleted_path, original_path)
                print(f"Undo delete: Restored {os.path.basename(original_path)}")
            except Exception as e:
                print(f"Restore failed: {e}")
            self.image_paths.insert(self.index, original_path)
            self.deleted_count -= 1
        else:
            path = action_tup
            self.kept_count -= 1
            self.index = max(0, self.index - 1)
            print(f"Undo keep: Going back to {os.path.basename(path)}")

        self.show_image()
        self.update_stats()
        return "break"

    def update_stats(self):
        remaining = len(self.image_paths) - self.index
        self.stats_label.config(
            text=f"   Remaining: {remaining}   |   Kept: {self.kept_count}   |   Deleted: {self.deleted_count}   |   Z = Undo"
        )

    def on_resize(self, event=None):
        if event and event.widget != self.root:
            return
        self.render_resized_image()

    def render_resized_image(self):
        if not hasattr(self, "current_original") or self.current_original is None:
            return

        w = self.root.winfo_width()
        h = self.root.winfo_height() - 100
        if w < 50 or h < 50:
            return

        img = self.current_original.copy()
        img.thumbnail((w, h), Image.Resampling.LANCZOS)
        self.current_photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.current_photo)

    def on_closing(self):
        delete_folder = False
        if self.deleted_folder and os.path.exists(self.deleted_folder) and os.listdir(self.deleted_folder):
            delete_folder = messagebox.askyesno("Permanently Delete", "Delete the _deleted folder permanently?")
            if delete_folder:
                try:
                    import shutil
                    shutil.rmtree(self.deleted_folder)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete folder: {e}")

        if messagebox.askokcancel("Quit", "Are you sure you want to exit?"):
            self.root.quit()
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageReviewer(root)
    root.mainloop()