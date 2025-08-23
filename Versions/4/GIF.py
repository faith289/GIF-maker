import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox, QLabel, 
    QSpinBox, QGroupBox, QProgressBar, QTextEdit, QSplitter, QCheckBox, QSlider, QComboBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from PIL import Image



class DragDropListWidget(QListWidget):
    """Custom list widget with drag and drop reordering capability"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
    
    def dropEvent(self, event):
        # Get the item being dragged
        source_row = self.currentRow()
        
        # Call parent's drop event to handle the move
        super().dropEvent(event)
        
        # Get the new position
        target_row = self.currentRow()
        
        # Update the parent's image_paths list to match the new order
        if hasattr(self.parent(), 'reorder_images'):
            self.parent().reorder_images(source_row, target_row)


class EnhancedGifCreatorThread(QThread):
    """Enhanced thread with quality and crop options"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, image_paths, output_path, fade_steps, hold_duration, fade_duration,
             preserve_quality=False, quality=95, resampling_method="LANCZOS (Best)",
             crop_area=None, dither_method="Floyd-Steinberg (Best)", sharpen_strength=0,
             quantization_method="Median Cut (Best)"):
        super().__init__()
        self.image_paths = image_paths
        self.output_path = output_path
        self.fade_steps = fade_steps
        self.hold_duration = hold_duration
        self.fade_duration = fade_duration
        self.preserve_quality = preserve_quality
        self.quality = quality
        self.resampling_method = resampling_method
        self.crop_area = crop_area
        self.dither_method = dither_method
        self.sharpen_strength = sharpen_strength
        self.quantization_method = quantization_method

    def run(self):
        try:
            creator = GifFadeCreator()
            creator.progress_callback = self.progress.emit
            target_size = None if self.preserve_quality else (1920, 1080)
            
            creator.create_fade_gif(
                self.image_paths,
                self.output_path,
                fade_steps=self.fade_steps,
                hold_duration=self.hold_duration,
                fade_duration=self.fade_duration,
                target_size=target_size,
                preserve_quality=self.preserve_quality,
                quality=self.quality,
                resampling_method=self.resampling_method,
                crop_area=self.crop_area,
                dither_method=self.dither_method,
                sharpen_strength=self.sharpen_strength,
                quantization_method=self.quantization_method
            )
            
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))



class GifFadeCreator:
    def __init__(self):
        self.progress_callback = None
    
    def get_resampling_filter(self, method_name):
        """Get PIL resampling filter from method name"""
        filters = {
            "LANCZOS (Best)": Image.Resampling.LANCZOS,
            "BICUBIC": Image.Resampling.BICUBIC,
            "BILINEAR": Image.Resampling.BILINEAR,
            "NEAREST": Image.Resampling.NEAREST
        }
        return filters.get(method_name, Image.Resampling.LANCZOS)

    def get_quantization_method(self, method_name):
        """Get PIL quantization method from method name"""
        methods = {
            "Median Cut (Best)": Image.Quantize.MEDIANCUT,
            "Maximum Coverage": Image.Quantize.MAXCOVERAGE,
            "Fast Octree": Image.Quantize.FASTOCTREE
        }
        return methods.get(method_name, Image.Quantize.MEDIANCUT)

    
    def resize_images_to_match(self, images, target_size=None, preserve_quality=False, resampling_filter=Image.Resampling.LANCZOS):
        """Enhanced resize with quality preservation options"""
        if preserve_quality:
            # Find the largest dimensions among all images
            max_width = max(img.size[0] for img in images)
            max_height = max(img.size[1] for img in images)
            target_size = (max_width, max_height)
        elif target_size is None:
            target_size = (1920, 1080)

        target_width, target_height = target_size
        resized_images = []

        for img in images:
            if preserve_quality and img.size == target_size:
                # No resize needed, keep original
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                resized_images.append(img)
                continue

            # Calculate scaling
            img_width, img_height = img.size
            width_ratio = target_width / img_width
            height_ratio = target_height / img_height
            scale_ratio = min(width_ratio, height_ratio)

            new_width = int(img_width * scale_ratio)
            new_height = int(img_height * scale_ratio)

            # Use multi-stage resize for better quality
            img_resized = self.multi_stage_resize(img, (new_width, new_height), resampling_filter)

            # Create canvas
            canvas = Image.new('RGBA', target_size, (0, 0, 0, 0))
            x_offset = (target_width - new_width) // 2
            y_offset = (target_height - new_height) // 2
            canvas.paste(img_resized, (x_offset, y_offset))

            resized_images.append(canvas)

        return resized_images


    def create_fade_transition(self, image1, image2, fade_steps=10):
        """Create fade transition frames between two images"""
        frames = []
        img1 = image1.convert('RGBA')
        img2 = image2.convert('RGBA')

        for i in range(fade_steps):
            alpha = i / (fade_steps - 1) if fade_steps > 1 else 1
            blended = Image.blend(img1, img2, alpha)
            frames.append(blended)

        return frames
    
    def create_fade_gif(self, image_paths, output_path, fade_steps=15, hold_duration=500,
                   fade_duration=50, loop=0, target_size=None, preserve_quality=False,
                   quality=95, resampling_method="LANCZOS (Best)", crop_area=None,
                   dither_method="Floyd-Steinberg (Best)", sharpen_strength=0, 
                   quantization_method="Median Cut (Best)"):

        """Enhanced GIF creation with quality and crop options"""
        
        # Load images
        images = []
        total_steps = len(image_paths) * 2
        current_step = 0

        for path in image_paths:
            if os.path.exists(path):
                img = Image.open(path).convert('RGBA')
                
                # Apply color space preservation
                img = self.preserve_color_space(img)
                
                # Apply cropping if specified
                if crop_area:
                    img = self.crop_image(img, crop_area)
                
                # Apply sharpening if enabled
                if sharpen_strength > 0:
                    img = self.apply_sharpening(img, sharpen_strength)
                
                images.append(img)
                current_step += 1
                if self.progress_callback:
                    self.progress_callback(int((current_step / total_steps) * 50))

        if len(images) < 2:
            raise ValueError("Need at least 2 images to create transitions")

        # Resize images with quality settings
        resampling_filter = self.get_resampling_filter(resampling_method)
        images = self.resize_images_to_match(images, target_size, preserve_quality, resampling_filter)

        # Create frames with fade transitions
        all_frames = []
        durations = []

        for i in range(len(images)):
            all_frames.append(images[i])
            durations.append(hold_duration)

            if i < len(images) - 1:
                fade_frames = self.create_fade_transition(images[i], images[i + 1], fade_steps)
                all_frames.extend(fade_frames)
                durations.extend([fade_duration] * len(fade_frames))

            current_step += 1
            if self.progress_callback:
                self.progress_callback(int(50 + (current_step / len(images)) * 50))

        # Use enhanced quantization
        dither_filter = self.get_dither_method(dither_method)
        quantize_filter = self.get_quantization_method(quantization_method)
        rgb_frames = self.enhanced_quantization(all_frames, preserve_quality, dither_filter, quantize_filter)


        # Save GIF with custom quality
        rgb_frames[0].save(
            output_path,
            save_all=True,
            append_images=rgb_frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,
            optimize=quality < 90,  # Only optimize for lower quality
            quality=quality,
            method=6
        )

    
    def crop_image(self, img, crop_area):
        """Crop image to specified area (left, top, right, bottom)"""
        return img.crop(crop_area)

    def get_dither_method(self, method_name):
        """Get PIL dithering method"""
        methods = {
            "Floyd-Steinberg (Best)": Image.Dither.FLOYDSTEINBERG,
            "Ordered": Image.Dither.ORDERED,
            "None (Faster)": Image.Dither.NONE
        }
        return methods.get(method_name, Image.Dither.FLOYDSTEINBERG)

    def enhanced_quantization(self, frames, preserve_quality=False, dither_method=Image.Dither.FLOYDSTEINBERG, quantize_method=Image.Quantize.MEDIANCUT):
        """Enhanced color quantization for better quality"""
        if preserve_quality:
            # Use adaptive palette for each frame
            quantized_frames = []
            for frame in frames:
                # Convert RGBA to RGB with white background
                if frame.mode == 'RGBA':
                    background = Image.new('RGB', frame.size, (255, 255, 255))
                    background.paste(frame, mask=frame.split()[-1])
                    frame = background
                
                # Use adaptive quantization with maximum colors and selected method
                quantized = frame.quantize(colors=256, method=quantize_method, dither=dither_method)
                quantized_frames.append(quantized.convert('RGB'))
            return quantized_frames
        else:
            # Convert all frames first
            rgb_frames = []
            for frame in frames:
                if frame.mode == 'RGBA':
                    background = Image.new('RGB', frame.size, (255, 255, 255))
                    background.paste(frame, mask=frame.split()[-1])
                    frame = background
                rgb_frames.append(frame)
            return rgb_frames


    def multi_stage_resize(self, img, target_size, resampling_filter):
        """Multi-stage resizing for better quality when downscaling significantly"""
        current_size = img.size
        target_width, target_height = target_size
        
        # Calculate if we need multi-stage resizing (when downscaling > 50%)
        scale_x = target_width / current_size[0]
        scale_y = target_height / current_size[1]
        min_scale = min(scale_x, scale_y)
        
        if min_scale < 0.5:  # Significant downscaling
            # Use multiple stages
            current_img = img
            while True:
                current_w, current_h = current_img.size
                next_scale = max(min_scale * 2, 0.5)  # Don't go below 50% per stage
                
                if next_scale >= 1.0:
                    break
                    
                new_w = int(current_w * next_scale)
                new_h = int(current_h * next_scale)
                current_img = current_img.resize((new_w, new_h), resampling_filter)
                
                if new_w <= target_width and new_h <= target_height:
                    break
            
            # Final resize to exact target
            return current_img.resize(target_size, resampling_filter)
        else:
            # Single-stage resize
            return img.resize(target_size, resampling_filter)

    def apply_sharpening(self, img, strength=1.0):
        """Apply unsharp mask for crisper images"""
        from PIL import ImageFilter
        
        if strength == 0:
            return img
        
        # Apply unsharp mask
        sharpened = img.filter(ImageFilter.UnsharpMask(
            radius=1.0 * strength,
            percent=int(100 * strength),
            threshold=3
        ))
        return sharpened

    def preserve_color_space(self, img):
        """Preserve original color space information"""
        # Check if image has color profile
        if hasattr(img, 'info') and 'icc_profile' in img.info:
            # Preserve ICC profile
            profile = img.info['icc_profile']
            # Apply profile-aware conversion if needed
            try:
                from PIL import ImageCms
                import io
                profile_obj = ImageCms.ImageCmsProfile(io.BytesIO(profile))
                # Convert to sRGB for web display while preserving quality
                img = ImageCms.profileToProfile(img, profile_obj, 
                                              ImageCms.createProfile('sRGB'))
            except:
                pass  # Fall back to standard conversion
        
        return img


class GifMakerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GIF Maker with Fade Effects')
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Create splitter for better layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Image list section
        image_group = QGroupBox("Images")
        image_layout = QVBoxLayout(image_group)
        
        # Use custom drag-drop list widget
        self.image_list_widget = DragDropListWidget(self)
        self.image_list_widget.setMinimumHeight(200)
        image_layout.addWidget(self.image_list_widget)
        
        # Buttons for image management
        button_layout = QHBoxLayout()
        self.load_button = QPushButton('Add Images')  # Changed text
        self.load_button.clicked.connect(self.load_images)  # Changed method name
        
        #self.load_single_button = QPushButton('Add Single')  # New button
        #self.load_single_button.clicked.connect(self.load_single_image)
        
        self.remove_button = QPushButton('Remove Selected')
        self.remove_button.clicked.connect(self.remove_image)
        
        self.clear_button = QPushButton('Clear All')
        self.clear_button.clicked.connect(self.clear_images)
        
        button_layout.addWidget(self.load_button)
        #button_layout.addWidget(self.load_single_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.clear_button)
        image_layout.addLayout(button_layout)
        
        # Add drag & drop instructions
        instruction_label = QLabel("💡 Tip: Drag images to reorder them")
        instruction_label.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        image_layout.addWidget(instruction_label)
        
        left_layout.addWidget(image_group)
        
        # Settings section (keep the same as before)
        settings_group = QGroupBox("GIF Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Fade steps
        fade_layout = QHBoxLayout()
        fade_layout.addWidget(QLabel("Fade Steps:"))
        self.fade_steps_spin = QSpinBox()
        self.fade_steps_spin.setRange(5, 50)
        self.fade_steps_spin.setValue(15)
        self.fade_steps_spin.setToolTip("More steps = smoother transition")
        fade_layout.addWidget(self.fade_steps_spin)
        fade_layout.addStretch()
        settings_layout.addLayout(fade_layout)
        
        # Hold duration
        hold_layout = QHBoxLayout()
        hold_layout.addWidget(QLabel("Hold Duration (ms):"))
        self.hold_duration_spin = QSpinBox()
        self.hold_duration_spin.setRange(100, 5000)
        self.hold_duration_spin.setValue(1000)
        self.hold_duration_spin.setSingleStep(100)
        self.hold_duration_spin.setToolTip("How long each image is displayed")
        hold_layout.addWidget(self.hold_duration_spin)
        hold_layout.addStretch()
        settings_layout.addLayout(hold_layout)
        
        # Fade duration
        fade_dur_layout = QHBoxLayout()
        fade_dur_layout.addWidget(QLabel("Fade Duration (ms):"))
        self.fade_duration_spin = QSpinBox()
        self.fade_duration_spin.setRange(10, 500)
        self.fade_duration_spin.setValue(50)
        self.fade_duration_spin.setSingleStep(10)
        self.fade_duration_spin.setToolTip("Speed of fade transition")
        fade_dur_layout.addWidget(self.fade_duration_spin)
        fade_dur_layout.addStretch()
        settings_layout.addLayout(fade_dur_layout)
        
        left_layout.addWidget(settings_group)

        # Quality Settings Group
        quality_group = QGroupBox("Quality Settings")
        quality_layout = QVBoxLayout(quality_group)

        # Original quality toggle
        self.preserve_quality_check = QCheckBox("Preserve Original Quality")
        self.preserve_quality_check.setChecked(False)
        self.preserve_quality_check.setToolTip("Keep original image dimensions and quality")
        quality_layout.addWidget(self.preserve_quality_check)

        # Quality slider
        quality_slider_layout = QHBoxLayout()
        quality_slider_layout.addWidget(QLabel("JPEG Quality:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(50, 100)
        self.quality_slider.setValue(95)
        self.quality_label = QLabel("95")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        quality_slider_layout.addWidget(self.quality_slider)
        quality_slider_layout.addWidget(self.quality_label)
        quality_layout.addLayout(quality_slider_layout)

        # Resampling method
        resample_layout = QHBoxLayout()
        resample_layout.addWidget(QLabel("Resampling:"))
        self.resample_combo = QComboBox()
        self.resample_combo.addItems(["LANCZOS (Best)", "BICUBIC", "BILINEAR", "NEAREST"])
        resample_layout.addWidget(self.resample_combo)
        quality_layout.addLayout(resample_layout)

        left_layout.addWidget(quality_group)

        # ADD THIS NEW ADVANCED QUALITY GROUP:
        # Advanced Quality Settings Group
        advanced_group = QGroupBox("Advanced Quality")
        advanced_layout = QVBoxLayout(advanced_group)

        # Dithering method
        dither_layout = QHBoxLayout()
        dither_layout.addWidget(QLabel("Dithering:"))
        self.dither_combo = QComboBox()
        self.dither_combo.addItems([
            "Floyd-Steinberg (Best)", 
            "Ordered", 
            "None (Faster)"
        ])
        dither_layout.addWidget(self.dither_combo)
        advanced_layout.addLayout(dither_layout)

        # Sharpening
        sharpen_layout = QHBoxLayout()
        sharpen_layout.addWidget(QLabel("Sharpening:"))
        self.sharpen_slider = QSlider(Qt.Orientation.Horizontal)
        self.sharpen_slider.setRange(0, 20)  # 0 to 2.0 in 0.1 increments
        self.sharpen_slider.setValue(0)  # 0.0 default (no sharpening)
        self.sharpen_label = QLabel("0.0")
        self.sharpen_slider.valueChanged.connect(lambda v: self.sharpen_label.setText(str(v/10.0)))
        sharpen_layout.addWidget(self.sharpen_slider)
        sharpen_layout.addWidget(self.sharpen_label)
        advanced_layout.addLayout(sharpen_layout)

        # Color quantization method
        color_method_layout = QHBoxLayout()
        color_method_layout.addWidget(QLabel("Color Quantization:"))
        self.quantization_combo = QComboBox()
        self.quantization_combo.addItems([
            "Median Cut (Best)", "Maximum Coverage", "Fast Octree"
        ])
        color_method_layout.addWidget(self.quantization_combo)
        advanced_layout.addLayout(color_method_layout)

        left_layout.addWidget(advanced_group)

        # Continue with existing crop group...
        # Crop Settings Group
        crop_group = QGroupBox("Crop Settings")
        # ... rest of your existing code


        # Crop Settings Group
        crop_group = QGroupBox("Crop Settings")
        crop_layout = QVBoxLayout(crop_group)

        # Enable cropping checkbox
        self.enable_crop_check = QCheckBox("Enable Cropping")
        self.enable_crop_check.setChecked(False)
        self.enable_crop_check.stateChanged.connect(self.toggle_crop_controls)
        crop_layout.addWidget(self.enable_crop_check)

        # Crop presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset Ratios:"))
        self.crop_preset_combo = QComboBox()
        self.crop_preset_combo.addItems([
            "Custom", "16:9 (Widescreen)", "4:3 (Standard)", 
            "1:1 (Square)", "9:16 (Vertical)", "21:9 (Ultra-wide)"
        ])
        self.crop_preset_combo.currentTextChanged.connect(self.apply_crop_preset)
        preset_layout.addWidget(self.crop_preset_combo)
        crop_layout.addLayout(preset_layout)

        # Manual crop coordinates
        coord_group = QGroupBox("Crop Coordinates (pixels)")
        coord_layout = QGridLayout(coord_group)

        self.crop_left_spin = QSpinBox()
        self.crop_left_spin.setRange(0, 9999)
        self.crop_top_spin = QSpinBox()
        self.crop_top_spin.setRange(0, 9999)
        self.crop_right_spin = QSpinBox()
        self.crop_right_spin.setRange(1, 9999)
        self.crop_right_spin.setValue(1920)
        self.crop_bottom_spin = QSpinBox()
        self.crop_bottom_spin.setRange(1, 9999)
        self.crop_bottom_spin.setValue(1080)

        coord_layout.addWidget(QLabel("Left:"), 0, 0)
        coord_layout.addWidget(self.crop_left_spin, 0, 1)
        coord_layout.addWidget(QLabel("Top:"), 0, 2)
        coord_layout.addWidget(self.crop_top_spin, 0, 3)
        coord_layout.addWidget(QLabel("Right:"), 1, 0)
        coord_layout.addWidget(self.crop_right_spin, 1, 1)
        coord_layout.addWidget(QLabel("Bottom:"), 1, 2)
        coord_layout.addWidget(self.crop_bottom_spin, 1, 3)

        crop_layout.addWidget(coord_group)

        # Initially disable crop controls
        self.crop_controls = [
            self.crop_preset_combo, self.crop_left_spin, self.crop_top_spin, 
            self.crop_right_spin, self.crop_bottom_spin, coord_group
        ]
        self.toggle_crop_controls(False)

        left_layout.addWidget(crop_group)

        
        # Generate button (keep the same styling)
        self.generate_button = QPushButton('Generate GIF')
        self.generate_button.clicked.connect(self.generate_gif)
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        left_layout.addWidget(self.generate_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        left_layout.addStretch()
        
        # Right panel for preview (keep the same)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Select an image to preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(300, 300)
        self.preview_label.setStyleSheet("border: 1px solid gray;")
        preview_layout.addWidget(self.preview_label)
        
        right_layout.addWidget(preview_group)
        
        # Log area (keep the same)
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        right_layout.addWidget(log_group)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400])
        
        # Main layout
        main_layout = QHBoxLayout(main_widget)
        main_layout.addWidget(splitter)
        
        # Connect list selection to preview
        self.image_list_widget.itemSelectionChanged.connect(self.update_preview)
        
        # Store image paths
        self.image_paths = []
        
        self.log("Application started. Ready to create GIFs!")
        self.log("💡 Use 'Add Images' to select multiple files at once")

    def load_images(self):
        """Load multiple images using file dialog"""
        file_paths, _ = QFileDialog.getOpenFileNames(  # Changed to getOpenFileNames
            self, 
            'Select Images', 
            '', 
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;All Files (*)'
        )
        
        if file_paths:
            added_count = 0
            for file_path in file_paths:
                if file_path not in self.image_paths:  # Avoid duplicates
                    self.image_paths.append(file_path)
                    filename = Path(file_path).name
                    self.image_list_widget.addItem(f"{len(self.image_paths)}. {filename}")
                    added_count += 1
            
            if added_count > 0:
                self.log(f"Added {added_count} images")
                self.update_button_states()
            else:
                self.log("No new images added (duplicates filtered)")
    
    

    def reorder_images(self, source_row, target_row):
        """Reorder images in the internal list to match the UI"""
        if 0 <= source_row < len(self.image_paths) and 0 <= target_row < len(self.image_paths):
            # Move the item in the image_paths list
            moved_path = self.image_paths.pop(source_row)
            self.image_paths.insert(target_row, moved_path)
            
            # Update all item texts to reflect new numbering
            self.refresh_list_numbering()
            
            self.log(f"Reordered: moved item from position {source_row + 1} to {target_row + 1}")

    def refresh_list_numbering(self):
        """Refresh the numbering in the list widget"""
        for i in range(self.image_list_widget.count()):
            item = self.image_list_widget.item(i)
            if i < len(self.image_paths):
                filename = Path(self.image_paths[i]).name
                item.setText(f"{i + 1}. {filename}")

    def remove_image(self):
        """Remove selected image from list"""
        current_row = self.image_list_widget.currentRow()
        if current_row >= 0:
            removed_path = self.image_paths.pop(current_row)
            self.image_list_widget.takeItem(current_row)
            
            # Update numbering for all remaining items
            self.refresh_list_numbering()
            
            self.log(f"Removed image: {Path(removed_path).name}")
            self.update_button_states()

    def clear_images(self):
        """Clear all images from list"""
        if self.image_paths:
            self.image_paths.clear()
            self.image_list_widget.clear()
            self.preview_label.setText("Select an image to preview")
            self.preview_label.setPixmap(QPixmap())
            self.log("Cleared all images")
            self.update_button_states()

    def toggle_crop_controls(self, enabled):
        """Enable/disable crop controls"""
        for control in self.crop_controls:
            control.setEnabled(enabled)

    def apply_crop_preset(self, preset):
        """Apply predefined crop ratios"""
        if not hasattr(self, 'crop_right_spin'):
            return
            
        presets = {
            "16:9 (Widescreen)": (0, 0, 1920, 1080),
            "4:3 (Standard)": (0, 0, 1440, 1080),
            "1:1 (Square)": (0, 0, 1080, 1080),
            "9:16 (Vertical)": (0, 0, 608, 1080),
            "21:9 (Ultra-wide)": (0, 0, 2560, 1080)
        }
        
        if preset in presets:
            left, top, right, bottom = presets[preset]
            self.crop_left_spin.setValue(left)
            self.crop_top_spin.setValue(top)
            self.crop_right_spin.setValue(right)
            self.crop_bottom_spin.setValue(bottom)

    def get_crop_area(self):
        """Get current crop area if cropping is enabled"""
        if self.enable_crop_check.isChecked():
            return (
                self.crop_left_spin.value(),
                self.crop_top_spin.value(),
                self.crop_right_spin.value(),
                self.crop_bottom_spin.value()
            )
        return None


    def update_button_states(self):
        """Update button enabled/disabled states"""
        has_images = len(self.image_paths) > 0
        has_multiple = len(self.image_paths) >= 2
        
        self.remove_button.setEnabled(has_images)
        self.clear_button.setEnabled(has_images)
        self.generate_button.setEnabled(has_multiple)

    def update_preview(self):
        """Update preview when list selection changes"""
        current_row = self.image_list_widget.currentRow()
        if current_row >= 0 and current_row < len(self.image_paths):
            try:
                pixmap = QPixmap(self.image_paths[current_row])
                if not pixmap.isNull():
                    # Scale pixmap to fit preview area
                    scaled_pixmap = pixmap.scaled(
                        280, 280, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled_pixmap)
                    self.preview_label.setText("")
                else:
                    self.preview_label.setText("Could not load image")
                    self.preview_label.setPixmap(QPixmap())
            except Exception as e:
                self.preview_label.setText(f"Error loading image:\n{str(e)}")
                self.preview_label.setPixmap(QPixmap())

    # Keep all other methods the same (log, generate_gif, on_gif_finished, on_gif_error)
    def log(self, message):
        """Add message to log area"""
        self.log_text.append(f"• {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def generate_gif(self):
        """Generate GIF with enhanced quality and crop options"""
        if len(self.image_paths) < 2:
            QMessageBox.warning(
                self,
                'Insufficient Images',
                'Please load at least two images to create a GIF.'
            )
            return

        # Get output file path
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            'Save GIF As',
            'fade_effect.gif',
            'GIF Files (*.gif);;All Files (*)'
        )

        if not output_path:
            return

        # Disable UI during generation
        self.generate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log("Starting GIF generation with enhanced quality settings...")

        # Get crop area
        crop_area = self.get_crop_area()
        if crop_area:
            self.log(f"Applying crop: {crop_area}")

        # Create and start enhanced worker thread
        self.worker_thread = EnhancedGifCreatorThread(
            self.image_paths,
            output_path,
            self.fade_steps_spin.value(),
            self.hold_duration_spin.value(),
            self.fade_duration_spin.value(),
            preserve_quality=self.preserve_quality_check.isChecked(),
            quality=self.quality_slider.value(),
            resampling_method=self.resample_combo.currentText(),
            crop_area=crop_area,
            dither_method=self.dither_combo.currentText(),
            sharpen_strength=self.sharpen_slider.value() / 10.0,
            quantization_method=self.quantization_combo.currentText()
        )



        self.worker_thread.progress.connect(self.progress_bar.setValue)
        self.worker_thread.finished.connect(self.on_gif_finished)
        self.worker_thread.error.connect(self.on_gif_error)
        self.worker_thread.start()


    def on_gif_finished(self, output_path):
        """Called when GIF generation is complete"""
        self.progress_bar.setVisible(False)
        self.generate_button.setEnabled(True)
        self.update_button_states()
        
        self.log(f"GIF created successfully: {Path(output_path).name}")
        
        QMessageBox.information(
            self, 
            'Success!', 
            f'GIF created successfully!\n\nSaved to: {output_path}'
        )

    def on_gif_error(self, error_message):
        """Called when GIF generation encounters an error"""
        self.progress_bar.setVisible(False)
        self.generate_button.setEnabled(True)
        self.update_button_states()
        
        self.log(f"Error: {error_message}")
        
        QMessageBox.critical(
            self, 
            'Error', 
            f'Failed to create GIF:\n\n{error_message}'
        )


def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("GIF Maker with Fade Effects")
    app.setApplicationVersion("1.0")
    
    window = GifMakerApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
