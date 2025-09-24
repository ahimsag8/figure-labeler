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
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QMouseEvent, QIcon
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
    selectionCleared = Signal()  # when clicking empty area
    
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
        self.selected_segment = None  # Index of selected segment
        self.in_marker = None  # IN marker position
        
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
    
    def set_in_marker(self, position):
        self.in_marker = position
        self.update()
    
    def clear_in_marker(self):
        self.in_marker = None
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
            if self.selected_segment == index:
                self.selected_segment = None
            elif self.selected_segment is not None and self.selected_segment > index:
                self.selected_segment -= 1
            self.update()
    
    def get_selected_segment(self):
        if self.selected_segment is not None and 0 <= self.selected_segment < len(self.segments):
            return self.segments[self.selected_segment]
        return None
    
    def select_segment(self, index):
        if 0 <= index < len(self.segments):
            self.selected_segment = index
            self.update()
            self.segmentClicked.emit(index)
    
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
            
            # Always emit positionChanged first
            if self.duration > 0:
                position = int((x / self.width()) * self.duration)
                self.positionChanged.emit(position)
            
            if segment_idx is not None:
                # Select segment and emit segmentClicked
                self.select_segment(segment_idx)
                # Start dragging segment
                self.dragging = True
                self.drag_segment = segment_idx
                self.drag_start_pos = x
            else:
                # Click on empty area - clear selection
                self.selected_segment = None
                self.update()
                self.selectionCleared.emit()
    
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
            
            # Use original color for all segments
            color = self.segment_colors[i % len(self.segment_colors)]
            painter.fillRect(QRectF(start_x, 10, end_x - start_x, 40), color)
            
            # Draw segment border - thicker for selected segment
            border_width = 4 if i == self.selected_segment else 2
            painter.setPen(QPen(QColor(255, 255, 255), border_width))
            painter.drawRect(QRectF(start_x, 10, end_x - start_x, 40))
        
        # Draw IN marker (gray vertical line)
        if self.in_marker is not None and self.duration > 0:
            in_x = (self.in_marker / self.duration) * self.width()
            painter.setPen(QPen(QColor(128, 128, 128), 3))  # Gray color
            painter.drawLine(in_x, 0, in_x, self.height())
        
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
        self.current_project_file = None

        # Project buttons
        self.open_project_btn = QPushButton("프로젝트 열기")
        self.save_project_btn = QPushButton("프로젝트 저장")
        self.save_as_project_btn = QPushButton("다른 이름으로 저장")

        # Buttons
        self.open_btn = QPushButton("Open Video")
        self.play_btn = QPushButton("Play/Pause")
        self.in_btn = QPushButton("Set IN")
        self.out_btn = QPushButton("Set OUT")

        # Labels
        self.in_label = QLabel("IN: -")
        self.out_label = QLabel("OUT: -")

        # Timeline widget
        self.timeline = TimelineWidget()

        # Action dropdown
        self.action_combo = QComboBox()
        self.load_actions_from_csv()
        self.action_combo.setEnabled(False)  # Initially disabled
        
        # Remove button
        self.remove_btn = QPushButton("🗑️")
        self.remove_btn.setFixedSize(30, 30)
        self.remove_btn.setToolTip("Remove selected segment")

        # Layout
        layout = QVBoxLayout(self)
        
        # Project buttons layout
        project_layout = QHBoxLayout()
        project_layout.addWidget(self.open_project_btn)
        project_layout.addWidget(self.save_project_btn)
        project_layout.addWidget(self.save_as_project_btn)
        layout.addLayout(project_layout)
        
        layout.addWidget(self.video_widget)
        layout.addWidget(self.timeline)

        controls = QHBoxLayout()
        controls.addWidget(self.open_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.in_btn)
        controls.addWidget(self.out_btn)
        layout.addLayout(controls)

        properties = QHBoxLayout()
        properties.addWidget(self.in_label)
        properties.addWidget(self.out_label)
        properties.addWidget(QLabel("Action:"))
        properties.addWidget(self.action_combo)
        properties.addWidget(self.remove_btn)
        layout.addLayout(properties)

        # State
        self.filename = None
        self.in_time = None
        self.out_time = None

        # Signals
        self.open_project_btn.clicked.connect(self.open_project)
        self.save_project_btn.clicked.connect(self.save_project)
        self.save_as_project_btn.clicked.connect(self.save_as_project)
        self.open_btn.clicked.connect(self.open_file)
        self.play_btn.clicked.connect(self.toggle_play)
        self.in_btn.clicked.connect(self.set_in)
        self.out_btn.clicked.connect(self.set_out)
        self.remove_btn.clicked.connect(self.remove_selected_segment)
        self.action_combo.currentTextChanged.connect(self.on_action_changed)
        self.player.positionChanged.connect(self.update_timeline)
        self.timeline.positionChanged.connect(self.seek)
        self.timeline.segmentClicked.connect(self.on_segment_clicked)
        self.timeline.selectionCleared.connect(self.on_selection_cleared)

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
    
    def load_actions_from_csv(self):
        """Load actions from actions.csv and populate the combo box with categories"""
        try:
            if os.path.exists("actions.csv"):
                with open("actions.csv", 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    current_category = None
                    
                    for row in reader:
                        category = row['Category']
                        technique = row['Technique']
                        
                        # Add category separator if it's a new category
                        if category != current_category:
                            if current_category is not None:
                                # Add separator (non-selectable item)
                                self.action_combo.addItem("─" * 20)
                            # Add category header (non-selectable)
                            self.action_combo.addItem(f"📁 {category}")
                            current_category = category
                        
                        # Add technique as selectable item
                        self.action_combo.addItem(f"  {technique}")
            else:
                # Fallback to default actions if CSV doesn't exist
                self.action_combo.addItems(["jump", "spin", "footwork", "transition"])
        except Exception as e:
            print(f"Error loading actions from CSV: {e}")
            # Fallback to default actions
            self.action_combo.addItems(["jump", "spin", "footwork", "transition"])
    
    def open_project(self):
        """Open a project file"""
        file, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트 열기",
            self.last_directory,
            "프로젝트 파일 (*.json);;모든 파일 (*)"
        )
        if file:
            self.load_project(file)
    
    def save_project(self):
        """Save current project"""
        if self.current_project_file:
            self.save_project_to_file(self.current_project_file)
        else:
            self.save_as_project()
    
    def save_as_project(self):
        """Save project with new name"""
        file, _ = QFileDialog.getSaveFileName(
            self,
            "프로젝트 저장",
            self.last_directory,
            "프로젝트 파일 (*.json);;모든 파일 (*)"
        )
        if file:
            self.save_project_to_file(file)
            self.current_project_file = file
    
    def save_project_to_file(self, filepath):
        """Save project data to file"""
        try:
            project_data = {
                'video_file': self.filename,
                'segments': []
            }
            
            # Save segments
            for segment in self.timeline.segments:
                project_data['segments'].append({
                    'start': segment.start,
                    'end': segment.end,
                    'action': segment.action
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            
            print(f"프로젝트 저장됨: {filepath}")
            
        except Exception as e:
            print(f"프로젝트 저장 오류: {e}")
    
    def load_project(self, filepath):
        """Load project from file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Load video file if specified
            if 'video_file' in project_data and project_data['video_file']:
                video_file = project_data['video_file']
                if os.path.exists(video_file):
                    self.filename = video_file
                    self.player.setSource(QUrl.fromLocalFile(video_file))
                    self.player.play()
                    
                    # Set timeline duration when video is loaded
                    def on_duration_changed():
                        duration = self.player.duration()
                        if duration > 0:
                            self.timeline.set_duration(duration)
                            # Load segments after duration is set
                            self.load_segments_from_project(project_data)
                    
                    self.player.durationChanged.connect(on_duration_changed)
                else:
                    print(f"비디오 파일을 찾을 수 없습니다: {video_file}")
                    # Load segments anyway
                    self.load_segments_from_project(project_data)
            else:
                # Load segments only
                self.load_segments_from_project(project_data)
            
            self.current_project_file = filepath
            print(f"프로젝트 로드됨: {filepath}")
            
        except Exception as e:
            print(f"프로젝트 로드 오류: {e}")
    
    def load_segments_from_project(self, project_data):
        """Load segments from project data"""
        try:
            # Clear existing segments
            self.timeline.segments.clear()
            
            # Load segments
            if 'segments' in project_data:
                for segment_data in project_data['segments']:
                    segment = Segment(
                        segment_data['start'],
                        segment_data['end'],
                        segment_data['action']
                    )
                    self.timeline.segments.append(segment)
            
            # Refresh timeline display
            self.timeline.update()
            print(f"로드된 segments: {len(self.timeline.segments)}개")
            
        except Exception as e:
            print(f"Segments 로드 오류: {e}")

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
        print(f"Setting IN at: {self.player.position()/1000:.2f}s")
        self.in_time = self.player.position()
        self.in_label.setText(f"IN: {self.in_time/1000:.2f}s")
        # Set IN marker on timeline
        self.timeline.set_in_marker(self.in_time)

    def set_out(self):
        print(f"Setting OUT at: {self.player.position()/1000:.2f}s")
        self.out_time = self.player.position()
        self.out_label.setText(f"OUT: {self.out_time/1000:.2f}s")
        
        # Add segment to timeline if both IN and OUT are set
        if self.in_time is not None and self.out_time is not None:
            # Check if OUT time is after IN time
            if self.out_time <= self.in_time:
                print("Warning: OUT time must be after IN time!")
                return
            
            action = self.action_combo.currentText()
            success = self.timeline.add_segment(self.in_time, self.out_time, action)
            if not success:
                print("Warning: Segment overlaps with existing segments!")
            else:
                # Clear IN marker after successful segment creation
                self.timeline.clear_in_marker()
                self.in_time = None
                self.out_time = None
                self.in_label.setText("IN: -")
                self.out_label.setText("OUT: -")


    def update_timeline(self, pos):
        print(f"Updating timeline to {pos}.")
        self.timeline.set_position(pos)

    def seek(self, position):
        print(f"Seeking to {position}.")
        self.player.setPosition(position)
    
    def on_segment_clicked(self, segment_index):
        """Handle segment click event"""
        segment = self.timeline.get_selected_segment()
        if segment:
            print(f"Selected segment {segment_index}: {segment.action} ({segment.start/1000:.2f}s - {segment.end/1000:.2f}s)")
            # Update action combo to match selected segment (with proper formatting)
            self.action_combo.setCurrentText(f"  {segment.action}")
            # Enable action combo for editing
            self.action_combo.setEnabled(True)
            # Update properties display with segment information
            self.in_label.setText(f"IN: {segment.start/1000:.2f}s")
            self.out_label.setText(f"OUT: {segment.end/1000:.2f}s")
            # Update internal state
            self.in_time = segment.start
            self.out_time = segment.end
            # Seek video to segment start position
            # self.player.setPosition(segment.start)
    
    def on_action_changed(self, new_action):
        """Handle action combo change event"""
        if self.timeline.selected_segment is not None:
            # Skip if user selected a category header or separator
            if new_action.startswith("📁") or new_action.startswith("─"):
                # Reset to previous valid selection
                segment = self.timeline.get_selected_segment()
                if segment:
                    self.action_combo.setCurrentText(f"  {segment.action}")
                return
            
            # Extract clean technique name (remove leading spaces)
            clean_action = new_action.strip()
            segment_index = self.timeline.selected_segment
            # Update the segment's action
            self.timeline.segments[segment_index].action = clean_action
            print(f"Updated segment {segment_index} action to: {clean_action}")
            # Refresh the timeline display
            self.timeline.update()
    

    # 여기서 in_time이 지워져버리는 게 문제!!!
    def on_selection_cleared(self):
        """Handle selection cleared event"""
        print("on_selection_cleared")
        # Clear the properties display
        self.in_label.setText("IN: -")
        self.out_label.setText("OUT: -")
        # self.in_time = None
        # self.out_time = None
        # Disable action combo
        self.action_combo.setEnabled(False)
    
    def remove_selected_segment(self):
        """Remove the currently selected segment"""
        if self.timeline.selected_segment is not None:
            segment_index = self.timeline.selected_segment
            self.timeline.remove_segment(segment_index)
            print(f"Removed segment {segment_index}")
            # Clear the properties display
            self.in_label.setText("IN: -")
            self.out_label.setText("OUT: -")
            self.in_time = None
            self.out_time = None
            # Disable action combo
            self.action_combo.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoAnnotator()
    win.show()
    sys.exit(app.exec())
