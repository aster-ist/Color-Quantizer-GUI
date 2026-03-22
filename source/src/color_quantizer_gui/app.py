"""Tkinter GUI for the color quantizer project."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .core import ComparisonResult, compare_quantization, load_image, save_image


MAX_PREVIEW_SIZE = 400
CANVAS_PREVIEW_SIZE = 300


class ImageQuantizerGUI:
    """Desktop GUI for image color quantization."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Color Quantizer")
        self.root.geometry("1080x720")
        self.root.minsize(960, 640)

        self.image_path: Path | None = None
        self.original_image: Image.Image | None = None
        self.comparison_result: ComparisonResult | None = None
        self.is_processing = False
        self.photo_ref: dict[str, ImageTk.PhotoImage] = {}

        self.color_var = tk.IntVar(value=64)
        self.sample_var = tk.IntVar(value=1000)
        self._build_ui()

    def _build_ui(self) -> None:
        control_frame = ttk.LabelFrame(self.root, text="Parameters / 参数设置", padding=10)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Target colors / 目标颜色数").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(control_frame, from_=2, to=256, textvariable=self.color_var, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Training samples / 训练样本数").pack(side=tk.LEFT, padx=5)
        ttk.Spinbox(control_frame, from_=100, to=100000, textvariable=self.sample_var, width=10).pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT, padx=20)

        self.load_btn = ttk.Button(button_frame, text="Open Image / 选择图片", command=self.load_image)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.process_btn = ttk.Button(button_frame, text="Run Quantization / 开始处理", command=self.start_processing)
        self.process_btn.pack(side=tk.LEFT, padx=5)
        self.process_btn.config(state=tk.DISABLED)

        self.save_btn = ttk.Button(button_frame, text="Save K-Means Result / 保存结果", command=self.save_result)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        self.save_btn.config(state=tk.DISABLED)

        self.progress = ttk.Progressbar(control_frame, mode="indeterminate", length=220)
        self.progress.pack(side=tk.LEFT, padx=20)

        image_frame = ttk.LabelFrame(self.root, text="Preview / 图像对比", padding=8)
        image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas1 = self._create_canvas(image_frame, "Original / 原图")
        self.canvas2 = self._create_canvas(image_frame, "K-Means")
        self.canvas3 = self._create_canvas(image_frame, "Random Baseline / 随机基线")

        self.status_label = ttk.Label(self.root, text="Ready / 准备就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def _create_canvas(self, parent: ttk.LabelFrame, title: str) -> tk.Canvas:
        frame = ttk.Frame(parent)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        ttk.Label(frame, text=title).pack()
        canvas = tk.Canvas(frame, bg="#d9d9d9", width=CANVAS_PREVIEW_SIZE, height=CANVAS_PREVIEW_SIZE, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        return canvas

    def load_image(self) -> None:
        filetypes = (
            ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"),
            ("All files", "*.*"),
        )
        filepath = filedialog.askopenfilename(title="Choose an image", filetypes=filetypes)
        if not filepath:
            return

        try:
            image = load_image(filepath)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load image: {exc}")
            return

        self.image_path = Path(filepath)
        self.original_image = image
        self.comparison_result = None
        self._display_on_canvas(self.canvas1, image, "original")
        self._clear_canvas(self.canvas2)
        self._clear_canvas(self.canvas3)
        self.process_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.update_status(f"Loaded image / 已加载: {self.image_path.name} ({image.width}x{image.height})")

    def start_processing(self) -> None:
        if self.is_processing:
            return
        if self.original_image is None:
            messagebox.showwarning("Warning", "Please load an image first.")
            return

        thread = threading.Thread(target=self.process_image, daemon=True)
        thread.start()

    def process_image(self) -> None:
        try:
            self.is_processing = True
            self.root.after(0, self._set_processing_state, True)
            self.update_status("Running K-Means quantization...")

            result = compare_quantization(
                self.original_image,
                n_colors=self.color_var.get(),
                sample_size=self.sample_var.get(),
                random_state=0,
            )

            self.comparison_result = result
            self.root.after(0, self._display_results, result)
            self.update_status("Done / 处理完成")
        except Exception as exc:
            self.update_status("Processing failed / 处理失败")
            self.root.after(0, lambda: messagebox.showerror("Processing error", str(exc)))
        finally:
            self.is_processing = False
            self.root.after(0, self._set_processing_state, False)

    def _set_processing_state(self, processing: bool) -> None:
        if processing:
            self.process_btn.config(state=tk.DISABLED)
            self.load_btn.config(state=tk.DISABLED)
            self.save_btn.config(state=tk.DISABLED)
            self.progress.start()
        else:
            self.load_btn.config(state=tk.NORMAL)
            self.process_btn.config(state=tk.NORMAL if self.original_image is not None else tk.DISABLED)
            self.save_btn.config(state=tk.NORMAL if self.comparison_result is not None else tk.DISABLED)
            self.progress.stop()

    def _display_results(self, result: ComparisonResult) -> None:
        self._display_on_canvas(self.canvas2, result.kmeans.image, "kmeans")
        self._display_on_canvas(self.canvas3, result.random.image, "random")
        self.save_btn.config(state=tk.NORMAL)

    def _display_on_canvas(self, canvas: tk.Canvas, image: Image.Image, key: str) -> None:
        preview = image.copy()
        preview.thumbnail((MAX_PREVIEW_SIZE, MAX_PREVIEW_SIZE), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(preview)
        canvas.delete("all")
        canvas.create_image(0, 0, image=photo, anchor=tk.NW)
        self.photo_ref[key] = photo

    def _clear_canvas(self, canvas: tk.Canvas) -> None:
        canvas.delete("all")

    def update_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_label.config(text=message))

    def save_result(self) -> None:
        if self.comparison_result is None:
            messagebox.showwarning("Warning", "Please process an image first.")
            return

        destination = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=(("PNG file", "*.png"), ("JPEG file", "*.jpg"), ("All files", "*.*")),
        )
        if not destination:
            return

        try:
            save_image(self.comparison_result.kmeans.image, destination)
        except Exception as exc:
            messagebox.showerror("Error", f"Save failed: {exc}")
            return

        messagebox.showinfo("Saved", f"Result saved to:\n{destination}")


def main() -> None:
    root = tk.Tk()
    ImageQuantizerGUI(root)
    root.mainloop()
