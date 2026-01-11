import flet as ft
import easyocr
import cv2
import numpy as np
import threading
import os
import time
import warnings
import subprocess
import tempfile
import atexit
from googletrans import Translator
from PIL import Image, ImageGrab, ImageEnhance, ImageFilter
import io

warnings.filterwarnings("ignore", category=UserWarning)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

def cleanup_temp_files():
    temp_files = [
        "temp_area_screenshot.png",
        "temp_fullscreen.png", 
        "temp_clipboard.png",
        "temp_preview.png",
        "temp_processed_simple.png"
    ]
    
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass

atexit.register(cleanup_temp_files)

class ScreenTranslator:
    def __init__(self, page: ft.Page):
        self.page = page
        self.reader = None
        self.translator = None
        self.additional_readers = {}
        self.current_image_path = None
        
        self.setup_ui()
        self.setup_ocr_and_translator()
        
    def setup_ui(self):
        self.page.title = "🌐 OCR Screen Translator by @florichdev"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window.width = 900
        self.page.window.height = 700
        self.page.window.center()
        self.page.window.resizable = True
        self.page.window.min_width = 600
        self.page.window.min_height = 500
        
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TRANSLATE, size=32, color="#3b82f6"),
                ft.Text(
                    "OCR Screen Translator",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                    color="#3b82f6"
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.all(20),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            margin=ft.margin.only(bottom=20)
        )
        
        button_height = 50
        
        self.area_btn = ft.ElevatedButton(
            text="Область",
            icon=ft.Icons.CROP_FREE,
            on_click=self.select_screen_area,
            style=ft.ButtonStyle(
                bgcolor="#3b82f6",
                color=ft.Colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=12)
            ),
            height=button_height,
            expand=True
        )
        
        self.fullscreen_btn = ft.ElevatedButton(
            text="Весь экран",
            icon=ft.Icons.FULLSCREEN,
            on_click=self.capture_fullscreen,
            style=ft.ButtonStyle(
                bgcolor="#6366f1",
                color=ft.Colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=12)
            ),
            height=button_height,
            expand=True
        )
        
        self.clipboard_btn = ft.ElevatedButton(
            text="Буфер",
            icon=ft.Icons.CONTENT_PASTE,
            on_click=self.paste_from_clipboard,
            style=ft.ButtonStyle(
                bgcolor="#10b981",
                color=ft.Colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=12)
            ),
            height=button_height,
            expand=True
        )
        
        self.file_btn = ft.ElevatedButton(
            text="Файл",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self.choose_file,
            style=ft.ButtonStyle(
                bgcolor="#0ea5e9",
                color=ft.Colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=12)
            ),
            height=button_height,
            expand=True
        )
        
        self.translate_btn = ft.ElevatedButton(
            text="Перевести",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self.process_image,
            style=ft.ButtonStyle(
                bgcolor="#1d4ed8",
                color=ft.Colors.WHITE,
                padding=ft.padding.symmetric(horizontal=20, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=12)
            ),
            height=button_height,
            expand=True
        )
        
        buttons_row = ft.Row([
            self.area_btn,
            self.fullscreen_btn,
            self.clipboard_btn,
            self.file_btn,
            self.translate_btn
        ], spacing=15)
        
        buttons_container = ft.Container(
            content=buttons_row,
            padding=ft.padding.all(20),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            margin=ft.margin.only(bottom=20)
        )
        
        self.source_lang = ft.Dropdown(
            label="Исходный язык",
            options=[
                ft.dropdown.Option("auto", "Авто"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("ru", "Русский"),
                ft.dropdown.Option("uk", "Українська"),
                ft.dropdown.Option("ja", "日本語"),
                ft.dropdown.Option("ko", "한국어"),
            ],
            value="auto",
            width=200,
            border_radius=10
        )
        
        self.target_lang = ft.Dropdown(
            label="Целевой язык",
            options=[
                ft.dropdown.Option("ru", "Русский"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("uk", "Українська"),
                ft.dropdown.Option("ja", "日本語"),
                ft.dropdown.Option("ko", "한국어"),
                ft.dropdown.Option("de", "Deutsch"),
                ft.dropdown.Option("fr", "Français"),
                ft.dropdown.Option("es", "Español"),
            ],
            value="ru",
            width=200,
            border_radius=10
        )
        
        lang_row = ft.Row([
            ft.Icon(ft.Icons.LANGUAGE, size=24, color="#3b82f6"),
            self.source_lang,
            ft.Icon(ft.Icons.ARROW_FORWARD, size=24, color="#3b82f6"),
            self.target_lang
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=15)
        
        lang_container = ft.Container(
            content=ft.Column([
                ft.Text("🌍 Настройки перевода", size=16, weight=ft.FontWeight.BOLD),
                lang_row
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            padding=ft.padding.all(20),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            margin=ft.margin.only(bottom=20)
        )
        
        self.image_preview = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.IMAGE, size=48, color=ft.Colors.GREY_400),
                ft.Text(
                    "📸 Изображение не выбрано",
                    size=14,
                    color=ft.Colors.GREY_400,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            padding=ft.padding.all(20),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            height=120,
            alignment=ft.alignment.center,
            margin=ft.margin.only(bottom=20)
        )
        
        self.original_text = ft.TextField(
            label="📝 Распознанный текст",
            multiline=True,
            min_lines=5,
            max_lines=10,
            border_radius=10,
            read_only=True
        )
        
        self.translated_text = ft.TextField(
            label="🌍 Перевод",
            multiline=True,
            min_lines=5,
            max_lines=10,
            border_radius=10,
            read_only=True
        )
        
        results_row = ft.Row([
            ft.Container(
                content=self.original_text,
                expand=True,
                margin=ft.margin.only(right=10)
            ),
            ft.Container(
                content=self.translated_text,
                expand=True,
                margin=ft.margin.only(left=10)
            )
        ], spacing=0)
        
        results_container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TEXT_FIELDS, size=20, color="#3b82f6"),
                    ft.Text("Результат", size=16, weight=ft.FontWeight.BOLD)
                ], spacing=10),
                results_row
            ], spacing=15),
            padding=ft.padding.all(20),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            margin=ft.margin.only(bottom=20)
        )
        
        self.status_text = ft.Text(
            "Готов к работе",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_400
        )
        
        self.status_icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=20, color=ft.Colors.GREEN_400)
        
        status_container = ft.Container(
            content=ft.Row([
                self.status_icon,
                self.status_text
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            padding=ft.padding.all(15),
            bgcolor=ft.Colors.SURFACE,
            border_radius=15
        )
        
        main_content = ft.Column([
            header,
            buttons_container,
            lang_container,
            self.image_preview,
            results_container,
            status_container
        ], spacing=0, scroll=ft.ScrollMode.AUTO)
        
        self.page.add(
            ft.Container(
                content=main_content,
                padding=ft.padding.all(25),
                expand=True
            )
        )
        
    def setup_ocr_and_translator(self):
        def init_in_thread():
            try:
                self.update_status("Инициализация OCR...", ft.Colors.ORANGE_400, ft.Icons.SETTINGS)
                
                language_sets = [
                    ['en', 'ru'],
                    ['en'],
                ]
                
                ocr_initialized = False
                for lang_set in language_sets:
                    try:
                        self.reader = easyocr.Reader(lang_set, gpu=False, verbose=False)
                        ocr_initialized = True
                        self.update_status(f"OCR инициализирован с языками: {', '.join(lang_set)}", ft.Colors.BLUE_400, ft.Icons.VISIBILITY)
                        break
                    except Exception as e:
                        continue
                
                if not ocr_initialized:
                    raise Exception("Не удалось инициализировать OCR")
                
                self.update_status("Инициализация переводчика...", ft.Colors.ORANGE_400, ft.Icons.TRANSLATE)
                
                try:
                    self.translator = Translator()
                    test_result = self.translator.translate("test", dest="ru")
                    if test_result and hasattr(test_result, 'text'):
                        self.update_status("Переводчик инициализирован", ft.Colors.BLUE_400, ft.Icons.TRANSLATE)
                    else:
                        raise Exception("Тест переводчика не прошел")
                except Exception as e:
                    self.update_status("Переводчик работает в ограниченном режиме", ft.Colors.ORANGE_400, ft.Icons.WARNING)
                    self.translator = Translator()
                
                self.update_status("Загрузка дополнительных языков...", ft.Colors.ORANGE_400, ft.Icons.DOWNLOAD)
                additional_languages = ['ja', 'ko', 'uk']
                
                for lang in additional_languages:
                    try:
                        if lang == 'uk':
                            reader = easyocr.Reader(['uk', 'ru', 'en'], gpu=False, verbose=False)
                        else:
                            reader = easyocr.Reader([lang, 'en'], gpu=False, verbose=False)
                        self.additional_readers[lang] = reader
                    except Exception:
                        pass
                
                lang_count = len(self.additional_readers) + 2
                self.update_status(f"Готов к работе ({lang_count} языков OCR)", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                
            except Exception as e:
                error_msg = str(e)
                self.update_status(f"Ошибка инициализации: {error_msg}", ft.Colors.RED_400, ft.Icons.ERROR)
        
        thread = threading.Thread(target=init_in_thread)
        thread.daemon = True
        thread.start()
        
    def update_status(self, message, color=ft.Colors.GREEN_400, icon=ft.Icons.CHECK_CIRCLE):
        self.status_text.value = message
        self.status_text.color = color
        self.status_icon.name = icon
        self.status_icon.color = color
        self.page.update()
        
    def select_screen_area(self, e):
        self.update_status("🎯 Выделите область экрана...", ft.Colors.ORANGE_400, ft.Icons.CROP_FREE)
        
        def capture_area():
            try:
                area_script = '''# -*- coding: utf-8 -*-
import tkinter as tk
from PIL import Image, ImageGrab
import sys
import os

class AreaSelector:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black', cursor='crosshair')
        
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='black')
        self.canvas.pack(fill='both', expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        instruction = tk.Label(
            self.root, 
            text="Select area with mouse • ESC - cancel",
            fg='white', 
            bg='black',
            font=('Arial', 16, 'bold')
        )
        instruction.pack(pady=20)
        
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.root.bind('<Escape>', self.cancel)
        
        self.root.focus_set()
        self.root.mainloop()
        
    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
    def on_drag(self, event):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='#00ff00', width=3, dash=(5, 5)
        )
        
    def on_release(self, event):
        if self.start_x and self.start_y:
            x1 = min(self.start_x, event.x)
            y1 = min(self.start_y, event.y)
            x2 = max(self.start_x, event.x)
            y2 = max(self.start_y, event.y)
            
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:
                self.root.destroy()
                self.capture_area(x1, y1, x2 - x1, y2 - y1)
            else:
                self.cancel()
                
    def cancel(self, event=None):
        self.root.destroy()
        sys.exit(1)
        
    def capture_area(self, x, y, width, height):
        try:
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            screenshot.save("temp_area_screenshot.png")
            print("SUCCESS")
        except Exception as e:
            print("ERROR: " + str(e))
            sys.exit(1)

if __name__ == "__main__":
    AreaSelector()
'''
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                    f.write(area_script)
                    script_path = f.name
                
                result = subprocess.run([
                    'python', '-u', script_path
                ], capture_output=True, text=True, cwd=os.getcwd(), encoding='utf-8', errors='ignore')
                
                os.unlink(script_path)
                
                if result.returncode == 0 and "SUCCESS" in result.stdout:
                    if os.path.exists("temp_area_screenshot.png"):
                        self.current_image_path = "temp_area_screenshot.png"
                        self.show_image_preview("temp_area_screenshot.png")
                        self.update_status("Область экрана захвачена", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                    else:
                        self.update_status("Файл скриншота не найден", ft.Colors.RED_400, ft.Icons.ERROR)
                else:
                    self.update_status("Выбор области отменен", ft.Colors.ORANGE_400, ft.Icons.CANCEL)
                    
            except Exception as e:
                self.update_status(f"Ошибка захвата области: {str(e)}", ft.Colors.RED_400, ft.Icons.ERROR)
        
        thread = threading.Thread(target=capture_area)
        thread.daemon = True
        thread.start()
        
    def capture_fullscreen(self, e):
        self.update_status("Создание скриншота экрана...", ft.Colors.ORANGE_400, ft.Icons.CAMERA_ALT)
        
        def capture():
            try:
                screenshot = ImageGrab.grab()
                screenshot_path = "temp_fullscreen.png"
                screenshot.save(screenshot_path)
                
                self.current_image_path = screenshot_path
                self.show_image_preview(screenshot_path)
                self.update_status("Скриншот экрана создан", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                
            except Exception as e:
                self.update_status(f"Ошибка создания скриншота: {str(e)}", ft.Colors.RED_400, ft.Icons.ERROR)
        
        thread = threading.Thread(target=capture)
        thread.daemon = True
        thread.start()
        
    def paste_from_clipboard(self, e):
        self.update_status("Получение изображения из буфера обмена...", ft.Colors.ORANGE_400, ft.Icons.CONTENT_PASTE)
        
        def paste():
            try:
                clipboard_image = ImageGrab.grabclipboard()
                
                if clipboard_image is not None:
                    if isinstance(clipboard_image, Image.Image):
                        clipboard_path = "temp_clipboard.png"
                        clipboard_image.save(clipboard_path)
                        
                        self.current_image_path = clipboard_path
                        self.show_image_preview(clipboard_path)
                        self.update_status("Изображение получено из буфера обмена", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                    elif isinstance(clipboard_image, list):
                        if len(clipboard_image) > 0:
                            file_path = clipboard_image[0]
                            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')):
                                self.current_image_path = file_path
                                self.show_image_preview(file_path)
                                self.update_status("Файл изображения получен из буфера обмена", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                            else:
                                self.update_status("Файл в буфере не является изображением", ft.Colors.RED_400, ft.Icons.ERROR)
                        else:
                            self.update_status("Пустой список файлов в буфере", ft.Colors.RED_400, ft.Icons.ERROR)
                    else:
                        self.update_status("Неподдерживаемый тип данных в буфере обмена", ft.Colors.RED_400, ft.Icons.ERROR)
                else:
                    self.update_status("В буфере обмена нет изображения", ft.Colors.RED_400, ft.Icons.ERROR)
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("В буфере обмена нет изображения. Скопируйте изображение (Ctrl+C) и попробуйте снова."),
                        bgcolor=ft.Colors.ORANGE_600
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    
            except Exception as e:
                self.update_status(f"Ошибка получения из буфера: {str(e)}", ft.Colors.RED_400, ft.Icons.ERROR)
        
        thread = threading.Thread(target=paste)
        thread.daemon = True
        thread.start()
        
    def capture_fullscreen(self, e):
        self.update_status("Создание скриншота экрана...", ft.Colors.ORANGE_400, ft.Icons.CAMERA_ALT)
        try:
            screenshot = ImageGrab.grab()
            screenshot_path = "temp_fullscreen.png"
            screenshot.save(screenshot_path)
            
            self.current_image_path = screenshot_path
            self.show_image_preview(screenshot_path)
            self.update_status("Скриншот экрана создан", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
            
        except Exception as e:
            self.update_status(f"Ошибка создания скриншота: {str(e)}", ft.Colors.RED_400, ft.Icons.ERROR)
            
    def choose_file(self, e):
        def file_picker_result(e: ft.FilePickerResultEvent):
            if e.files:
                file_path = e.files[0].path
                self.current_image_path = file_path
                self.show_image_preview(file_path)
                self.update_status(f"Выбран файл: {os.path.basename(file_path)}", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
        
        file_picker = ft.FilePicker(on_result=file_picker_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="Выберите изображение",
            allowed_extensions=["png", "jpg", "jpeg", "bmp", "tiff", "gif"]
        )
        
    def show_image_preview(self, image_path):
        try:
            image = Image.open(image_path)
            max_width, max_height = 400, 80
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            preview_path = "temp_preview.png"
            image.save(preview_path)
            
            self.image_preview.content = ft.Column([
                ft.Image(
                    src=preview_path,
                    width=min(image.width, max_width),
                    height=min(image.height, max_height),
                    fit=ft.ImageFit.CONTAIN,
                    border_radius=10
                ),
                ft.Text(
                    f"Загружено: {os.path.basename(image_path)}",
                    size=14,
                    color=ft.Colors.GREEN_400,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.Text(
                    "Нажмите 'Перевести' для обработки",
                    size=12,
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            self.page.update()
            
        except Exception as e:
            self.update_status(f"Ошибка загрузки изображения: {str(e)}", ft.Colors.RED_400, ft.Icons.ERROR)
            
    def advanced_preprocess_image(self, image_path):
        """Улучшенная предобработка изображения для лучшего OCR"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise Exception("Не удалось загрузить изображение")
            
            height, width = img.shape[:2]
            if width < 800:
                scale_factor = 800 / width
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            denoised = cv2.medianBlur(enhanced, 3)
            
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            processed_path = "temp_processed_simple.png"
            cv2.imwrite(processed_path, binary)
            
            return processed_path
            
        except Exception as e:
            raise Exception(f"Ошибка предобработки изображения: {str(e)}")
            
    def extract_text(self, image_path):
        try:
            source_lang = self.source_lang.value
            
            if source_lang in self.additional_readers:
                results_raw = self.additional_readers[source_lang].readtext(image_path)
            else:
                results_raw = self.reader.readtext(image_path)
            
            if results_raw and any(result[2] > 0.6 for result in results_raw):
                results = results_raw
            else:
                processed_path = self.advanced_preprocess_image(image_path)
                
                if source_lang in self.additional_readers:
                    results = self.additional_readers[source_lang].readtext(processed_path)
                else:
                    results = self.reader.readtext(processed_path)
                
                if os.path.exists(processed_path):
                    os.remove(processed_path)
                
                if not results or not any(result[2] > 0.3 for result in results):
                    results = results_raw
                
            if results:
                results.sort(key=lambda x: (x[0][0][1], x[0][0][0]))
                
                filtered_results = []
                for result in results:
                    text = result[1].strip()
                    confidence = result[2]
                    
                    if len(text) < 1:
                        continue
                    
                    min_confidence = 0.2 if len(text) > 2 else 0.4
                    
                    if confidence > min_confidence:
                        filtered_results.append(text)
                
                if filtered_results:
                    extracted_text = ' '.join(filtered_results)
                    extracted_text = ' '.join(extracted_text.split())
                    extracted_text = extracted_text.replace(' | ', ' ')
                    extracted_text = extracted_text.replace('|', 'l')
                    
                    return extracted_text.strip()
                    
            return ""
                
        except Exception as e:
            raise Exception(f"Ошибка извлечения текста: {str(e)}")
            
    def translate_text(self, text, source_lang, target_lang):
        """Улучшенный перевод текста с обработкой ошибок"""
        try:
            if not text.strip():
                return "Нет текста для перевода"
            
            for attempt in range(3):
                try:
                    translator = Translator()
                    
                    max_length = 500
                    if len(text) > max_length:
                        sentences = text.split('. ')
                        translated_parts = []
                        current_part = ""
                        
                        for sentence in sentences:
                            if len(current_part + sentence) < max_length:
                                current_part += sentence + ". "
                            else:
                                if current_part:
                                    if source_lang == "auto":
                                        result = translator.translate(current_part.strip(), dest=target_lang)
                                    else:
                                        result = translator.translate(current_part.strip(), src=source_lang, dest=target_lang)
                                    
                                    if result and hasattr(result, 'text') and result.text:
                                        translated_parts.append(result.text)
                                    else:
                                        translated_parts.append(current_part.strip())
                                        
                                current_part = sentence + ". "
                        
                        if current_part:
                            if source_lang == "auto":
                                result = translator.translate(current_part.strip(), dest=target_lang)
                            else:
                                result = translator.translate(current_part.strip(), src=source_lang, dest=target_lang)
                            
                            if result and hasattr(result, 'text') and result.text:
                                translated_parts.append(result.text)
                            else:
                                translated_parts.append(current_part.strip())
                        
                        return ' '.join(translated_parts)
                    else:
                        if source_lang == "auto":
                            result = translator.translate(text, dest=target_lang)
                        else:
                            result = translator.translate(text, src=source_lang, dest=target_lang)
                        
                        if result and hasattr(result, 'text') and result.text:
                            return result.text
                        else:
                            raise Exception("Пустой результат перевода")
                            
                except Exception as e:
                    if attempt == 2: 
                        return f"[Ошибка перевода] {text}"
                    else:
                        time.sleep(1)
                        continue
                        
        except Exception as e:
            return f"[Ошибка перевода: {str(e)}] {text}"
            
    def process_image(self, e):
        if not self.current_image_path:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Сначала сделайте скриншот или выберите изображение"),
                bgcolor=ft.Colors.ORANGE_600
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        if not self.reader:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("OCR не инициализирован. Подождите завершения загрузки."),
                bgcolor=ft.Colors.RED_600
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
            
        if not self.translator:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Переводчик работает в ограниченном режиме. Проверьте интернет-соединение."),
                bgcolor=ft.Colors.ORANGE_600
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        def process():
            try:
                self.update_status("Распознавание текста...", ft.Colors.ORANGE_400, ft.Icons.SEARCH)
                
                self.original_text.value = ""
                self.translated_text.value = ""
                self.page.update()
                
                extracted_text = self.extract_text(self.current_image_path)
                
                if not extracted_text:
                    self.update_status("Текст не найден на изображении", ft.Colors.RED_400, ft.Icons.ERROR)
                    self.original_text.value = "Текст не обнаружен на изображении\n\n💡 Советы:\n• Убедитесь, что текст четкий и достаточно крупный\n• Попробуйте выбрать конкретный язык вместо 'auto'\n• Проверьте качество изображения"
                    self.page.update()
                    return
                    
                self.original_text.value = extracted_text
                self.page.update()
                
                self.update_status("Перевод текста...", ft.Colors.ORANGE_400, ft.Icons.TRANSLATE)
                source_lang = self.source_lang.value
                target_lang = self.target_lang.value
                
                translated = self.translate_text(extracted_text, source_lang, target_lang)
                self.translated_text.value = translated
                self.page.update()
                
                self.update_status("Готово! Текст успешно распознан и переведен", ft.Colors.GREEN_400, ft.Icons.CHECK_CIRCLE)
                
            except Exception as e:
                error_msg = str(e)
                self.update_status(f"Ошибка: {error_msg}", ft.Colors.RED_400, ft.Icons.ERROR)
                
        thread = threading.Thread(target=process)
        thread.daemon = True
        thread.start()

def main(page: ft.Page):
    app = ScreenTranslator(page)

if __name__ == "__main__":
    ft.app(target=main)