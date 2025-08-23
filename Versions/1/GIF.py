import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QFileDialog, QMessageBox, QLabel, 
    QSpinBox, QGroupBox, QProgressBar, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from PIL import Image

class GifCreatorThread(QThread):
    """Thread for creating GIF to prevent UI freezing"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, image_paths, output_path, fade_steps, hold_duration, fade_duration):
        super().__init__()
        self.image_paths = image_paths
        self.output_path = output_path
        self.fade_steps = fade_steps
        self.hold_duration = hold_duration
        self.fade_duration = fade_duration

    def run(self):
        try:
            creator = GifFadeCreator()
            creator.progress_callback = self.progress.emit
            creator.create_fade_gif(
                self.image_paths, 
                self.output_path,
                fade_steps=self.fade_steps,
                hold_duration=self.hold_duration,
                fade_duration=self.fade_duration,
                target_size=(800, 600)
            )
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))

class GifFadeCreator:
    def __init__(self):
        self.progress_callback = None

    def resize_images_to_match(self, images, target_size=None):
        """Resize all images to match the largest dimensions or a target size"""
        if target_size is None:
            max_width = max(img.width for img in images)
            max_height = max(img.height for img in images)
            target_size = (max_width, max_height)
        
        resized_images = []
        for img in images:
            img_resized = img.resize(target_size, Image.Resampling.LANCZOS)
            resized_images.append(img_resized)
        
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

    def create_fade_gif(self, image_paths, output_path, fade_steps=15, hold_duration=500, fade_duration=50, loop=0, target_size=None):
        """Create a GIF with fade transitions between images"""
        
        # Load images
        images = []
        total_steps = len(image_paths) * 2  # Loading + processing
        current_step = 0
        
        for path in image_paths:
            if os.path.exists(path):
                img = Image.open(path).convert('RGBA')
                images.append(img)
                current_step += 1
                if self.progress_callback:
                    self.progress_callback(int((current_step / total_steps) * 50))
        
        if len(images) < 2:
            raise ValueError("Need at least 2 images to create transitions")
        
        # Resize images
        images = self.resize_images_to_match(images, target_size)
        
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
        
        # Convert to RGB for GIF
        rgb_frames = []
        for frame in all_frames:
            rgb_frame = Image.new('RGB', frame.size, (255, 255, 255))
            rgb_frame.paste(frame, mask=frame.split()[-1] if frame.mode == 'RGBA' else None)
            rgb_frames.append(rgb_frame)
        
        # Save GIF
        rgb_frames[0].save(
            output_path,
            save_all=True,
            append_images=rgb_frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,
            optimize=True
        )

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
        
        self.image_list_widget = QListWidget()
        self.image_list_widget.setMinimumHeight(200)
        image_layout.addWidget(self.image_list_widget)
        
        # Buttons for image management
        button_layout = QHBoxLayout()
        self.load_button = QPushButton('Add Image')
        self.load_button.clicked.connect(self.load_image)
        
        self.remove_button = QPushButton('Remove Selected')
        self.remove_button.clicked.connect(self.remove_image)
        
        self.clear_button = QPushButton('Clear All')
        self.clear_button.clicked.connect(self.clear_images)
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.clear_button)
        image_layout.addLayout(button_layout)
        
        left_layout.addWidget(image_group)
        
        # Settings section
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
        
        # Generate button
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
        
        # Right panel for preview
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
        
        # Log area
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

    def log(self, message):
        """Add message to log area"""
        self.log_text.append(f"• {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def load_image(self):
        """Load a single image using file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            'Select an Image', 
            '', 
            'Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;All Files (*)'
        )
        
        if file_path:
            self.image_paths.append(file_path)
            filename = Path(file_path).name
            self.image_list_widget.addItem(f"{len(self.image_paths)}. {filename}")
            self.log(f"Added image: {filename}")
            
            # Update button states
            self.update_button_states()

    def remove_image(self):
        """Remove selected image from list"""
        current_row = self.image_list_widget.currentRow()
        if current_row >= 0:
            removed_path = self.image_paths.pop(current_row)
            self.image_list_widget.takeItem(current_row)
            
            # Update numbering
            for i in range(self.image_list_widget.count()):
                item = self.image_list_widget.item(i)
                filename = Path(self.image_paths[i]).name
                item.setText(f"{i+1}. {filename}")
            
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

    def generate_gif(self):
        """Generate GIF with fade effects"""
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
        self.log("Starting GIF generation...")
        
        # Create and start worker thread
        self.worker_thread = GifCreatorThread(
            self.image_paths,
            output_path,
            self.fade_steps_spin.value(),
            self.hold_duration_spin.value(),
            self.fade_duration_spin.value()
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
