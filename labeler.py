import sys
import csv
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QSlider, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsItem
)
from PySide6.QtCore import Qt, QUrl, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QMouseEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class Segment:
    def __init__(self, start, end, action="jump"):
        self.start = start
        self.end = end
        self.action = action
    
    def overlaps_with(self, other):
        return not (self.end <= other.start or other.end <= self.start)
    
    def contains(self, position):
        return self.start <= position <= self.end


class TimelineWidget(QWidget):
    positionChanged = Signal(int)
    segmentClicked = Signal(int)  # segment index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setMinimumWidth(400)
        
        self.duration = 0
        self.current_position = 0
        self.segments = []
        self.dragging = False
        self.drag_segment = None
        self.drag_start_pos = None
        
        # Colors
        self.bg_color = QColor(50, 50, 50)
        self.segment_colors = [
            QColor(255, 100, 100),  # Red
            QColor(100, 255, 100),  # Green
            QColor(100, 100, 255),  # Blue
            QColor(255, 255, 100),  # Yellow
        ]
        self.current_pos_color = QColor(255, 255, 255)
        
    def set_duration(self, duration):
        self.duration = duration
        self.update()
    
    def set_position(self, position):
        self.current_position = position
        self.update()
    
    def add_segment(self, start, end, action="jump"):
        # Check for overlaps
        new_segment = Segment(start, end, action)
        for segment in self.segments:
            if new_segment.overlaps_with(segment):
                return False  # Overlap detected
        
        self.segments.append(new_segment)
        self.update()
        return True
    
    def remove_segment(self, index):
        if 0 <= index < len(self.segments):
            del self.segments[index]
            self.update()
    
    def get_segment_at_position(self, x):
        if self.duration == 0:
            return None
        
        position = (x / self.width()) * self.duration
        for i, segment in enumerate(self.segments):
            if segment.contains(position):
                return i
        return None
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            segment_idx = self.get_segment_at_position(x)
            
            if segment_idx is not None:
                # Start dragging segment
                self.dragging = True
                self.drag_segment = segment_idx
                self.drag_start_pos = x
            else:
                # Click on empty area - set position
                if self.duration > 0:
                    position = int((x / self.width()) * self.duration)
                    self.positionChanged.emit(position)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and self.drag_segment is not None:
            x = event.position().x()
            if self.duration > 0:
                new_position = (x / self.width()) * self.duration
                new_position = max(0, min(self.duration, new_position))
                
                # Update segment position
                segment = self.segments[self.drag_segment]
                if x > self.drag_start_pos:
                    # Dragging right - extend end
                    segment.end = new_position
                else:
                    # Dragging left - extend start
                    segment.start = new_position
                
                # Ensure start < end
                if segment.start > segment.end:
                    segment.start, segment.end = segment.end, segment.start
                
                self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.drag_segment = None
            self.drag_start_pos = None
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        if self.duration == 0:
            return
        
        # Draw segments
        for i, segment in enumerate(self.segments):
            start_x = (segment.start / self.duration) * self.width()
            end_x = (segment.end / self.duration) * self.width()
            
            color = self.segment_colors[i % len(self.segment_colors)]
            painter.fillRect(QRectF(start_x, 10, end_x - start_x, 40), color)
            
            # Draw segment border
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawRect(QRectF(start_x, 10, end_x - start_x, 40))
        
        # Draw current position
        if self.duration > 0:
            pos_x = (self.current_position / self.duration) * self.width()
            painter.setPen(QPen(self.current_pos_color, 3))
            painter.drawLine(pos_x, 0, pos_x, self.height())


class VideoAnnotator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Annotator (In/Out + Action)")
        self.resize(800, 600)

        # Video player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)
        
        # Load last used directory from config file
        self.config_file = "labeler_config.json"
        self.last_directory = self.load_last_directory()

        # Buttons
        self.open_btn = QPushButton("Open Video")
        self.play_btn = QPushButton("Play/Pause")
        self.in_btn = QPushButton("Set IN")
        self.out_btn = QPushButton("Set OUT")
        self.save_btn = QPushButton("Save Segment")

        # Labels
        self.in_label = QLabel("IN: -")
        self.out_label = QLabel("OUT: -")

        # Timeline widget
        self.timeline = TimelineWidget()

        # Action dropdown
        self.action_combo = QComboBox()
        self.action_combo.addItems(["jump", "spin", "footwork", "transition"])

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.timeline)

        controls = QHBoxLayout()
        controls.addWidget(self.open_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.in_btn)
        controls.addWidget(self.out_btn)
        controls.addWidget(QLabel("Action:"))
        controls.addWidget(self.action_combo)
        controls.addWidget(self.save_btn)
        layout.addLayout(controls)

        labels = QHBoxLayout()
        labels.addWidget(self.in_label)
        labels.addWidget(self.out_label)
        layout.addLayout(labels)

        # State
        self.filename = None
        self.in_time = None
        self.out_time = None

        # Signals
        self.open_btn.clicked.connect(self.open_file)
        self.play_btn.clicked.connect(self.toggle_play)
        self.in_btn.clicked.connect(self.set_in)
        self.out_btn.clicked.connect(self.set_out)
        self.save_btn.clicked.connect(self.save_segment)
        self.player.positionChanged.connect(self.update_timeline)
        self.timeline.positionChanged.connect(self.seek)

    def load_last_directory(self):
        """Load last used directory from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('last_directory', '')
        except Exception as e:
            print(f"Error loading config: {e}")
        return ''

    def save_last_directory(self, directory):
        """Save last used directory to config file"""
        try:
            config = {'last_directory': directory}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def open_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Video", 
            self.last_directory,
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm);;All Files (*)"
        )
        if file:
            self.filename = file
            # Extract directory from file path and save it
            directory = os.path.dirname(file)
            if directory != self.last_directory:
                self.last_directory = directory
                self.save_last_directory(directory)
            self.player.setSource(QUrl.fromLocalFile(file))
            self.player.play()
            
            # Set timeline duration when video is loaded
            def on_duration_changed():
                duration = self.player.duration()
                if duration > 0:
                    self.timeline.set_duration(duration)
            
            self.player.durationChanged.connect(on_duration_changed)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def set_in(self):
        self.in_time = self.player.position()
        self.in_label.setText(f"IN: {self.in_time/1000:.2f}s")

    def set_out(self):
        self.out_time = self.player.position()
        self.out_label.setText(f"OUT: {self.out_time/1000:.2f}s")
        
        # Add segment to timeline if both IN and OUT are set
        if self.in_time is not None and self.out_time is not None:
            action = self.action_combo.currentText()
            success = self.timeline.add_segment(self.in_time, self.out_time, action)
            if not success:
                print("Warning: Segment overlaps with existing segments!")

    def save_segment(self):
        if not self.filename or self.in_time is None or self.out_time is None:
            return
        action = self.action_combo.currentText()
        with open("annotations.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([self.filename, self.in_time, self.out_time, action])
        print("Saved:", self.filename, self.in_time, self.out_time, action)

    def update_timeline(self, pos):
        print(f"Updating timeline to {pos}.")
        self.timeline.set_position(pos)

    def seek(self, position):
        print(f"Seeking to {position}.")
        self.player.setPosition(position)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoAnnotator()
    win.show()
    sys.exit(app.exec())
