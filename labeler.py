import sys
import csv
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QSlider, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsItem, QSpinBox, QScrollBar
)
from PySide6.QtCore import Qt, QUrl, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QMouseEvent, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class Segment:
    def __init__(self, start, end, action="jump", color=None):
        self.start = start
        self.end = end
        self.action = action
        self.color = color
    
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
        self.selected_segment = None  # Index of selected segment
        self.in_marker = None  # IN marker position
        self.scroll_offset = 0  # 스크롤 오프셋
        
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
        # 스크롤바 범위 업데이트 (1초당 100px로 확대)
        if duration > 0:
            total_width = max(400, int(duration / 1000 * 100))  # 1초당 100px
            scrollbar_max = max(0, total_width - self.width())
            self.parent().timeline_scrollbar.setRange(0, scrollbar_max)
        self.update()
    
    def set_position(self, position):
        self.current_position = position
        self.update()
    
    def set_in_marker(self, position):
        self.in_marker = position
        self.update()
    
    def set_scroll_offset(self, offset):
        self.scroll_offset = offset
        self.update()
    
    def add_segment(self, start, end, action="jump", color=None):
        # Check for overlaps
        new_segment = Segment(start, end, action, color)
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
        
        # 1초당 100px 스케일로 계산
        total_width = max(400, int(self.duration / 1000 * 100))
        position = (x / total_width) * self.duration
        for i, segment in enumerate(self.segments):
            if segment.contains(position):
                return i
        return None
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x() + self.scroll_offset
            segment_idx = self.get_segment_at_position(x)
            
            # Always emit positionChanged first
            if self.duration > 0:
                total_width = max(400, int(self.duration / 1000 * 100))
                position = int((x / total_width) * self.duration)
                self.positionChanged.emit(position)
            
            if segment_idx is not None:
                # Select segment and emit segmentClicked
                self.select_segment(segment_idx)
            else:
                # Click on empty area - clear selection
                self.selected_segment = None
                self.update()
                self.selectionCleared.emit()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        if self.duration == 0:
            return
        
        # Draw segments
        for i, segment in enumerate(self.segments):
            # 1초당 100px 스케일로 계산
            total_width = max(400, int(self.duration / 1000 * 100))
            start_x = (segment.start / self.duration) * total_width - self.scroll_offset
            end_x = (segment.end / self.duration) * total_width - self.scroll_offset
            
            # Use segment's own color if available, otherwise fallback to default colors
            if segment.color:
                color = QColor(segment.color)
            else:
                color = self.segment_colors[i % len(self.segment_colors)]
            painter.fillRect(QRectF(start_x, 10, end_x - start_x, 40), color)
            
            # Draw segment border - thicker for selected segment
            border_width = 4 if i == self.selected_segment else 2
            painter.setPen(QPen(QColor(255, 255, 255), border_width))
            painter.drawRect(QRectF(start_x, 10, end_x - start_x, 40))
        
        # Draw IN marker (gray vertical line)
        if self.in_marker is not None and self.duration > 0:
            total_width = max(400, int(self.duration / 1000 * 100))
            in_x = (self.in_marker / self.duration) * total_width - self.scroll_offset
            painter.setPen(QPen(QColor(128, 128, 128), 3))  # Gray color
            painter.drawLine(in_x, 0, in_x, self.height())
        
        # Draw current position
        if self.duration > 0:
            total_width = max(400, int(self.duration / 1000 * 100))
            pos_x = (self.current_position / self.duration) * total_width - self.scroll_offset
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
        
        # Action-color mapping from CSV
        self.action_colors = {}

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
        
        # Time display textbox
        self.time_display = QLabel("00:00:00.000")
        self.time_display.setFixedWidth(100)
        self.time_display.setAlignment(Qt.AlignCenter)
        self.time_display.setStyleSheet("border: 1px solid gray; background-color: white;")
        
        # Horizontal scrollbar for timeline
        self.timeline_scrollbar = QScrollBar(Qt.Horizontal)
        self.timeline_scrollbar.setRange(0, 1000)  # 기본 범위 설정
        self.timeline_scrollbar.setValue(0)

        # Action dropdown
        self.action_combo = QComboBox()
        self.load_actions_from_csv()
        self.action_combo.setEnabled(False)  # Initially disabled
        
        # Remove button
        self.remove_btn = QPushButton("🗑️")
        self.remove_btn.setFixedSize(30, 30)
        self.remove_btn.setToolTip("Remove selected segment")
        
        # IN/OUT spin boxes for frame editing
        self.in_spin = QSpinBox()
        self.in_spin.setRange(0, 999999)
        self.in_spin.setSuffix(" ms")
        self.in_spin.setEnabled(False)
        self.in_spin.setToolTip("IN time in milliseconds (33ms = 1 frame)")
        self.in_spin.setSingleStep(33)  # 1 frame = 33ms
        self.in_spin.setFixedHeight(35)  # 높이 증가
        self.in_spin.setFixedWidth(100)  # 너비 고정
        # CSS 스타일로 버튼을 위/아래 배치
        self.in_spin.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                height: 15px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                height: 15px;
            }
        """)
        
        self.out_spin = QSpinBox()
        self.out_spin.setRange(0, 999999)
        self.out_spin.setSuffix(" ms")
        self.out_spin.setEnabled(False)
        self.out_spin.setToolTip("OUT time in milliseconds (33ms = 1 frame)")
        self.out_spin.setSingleStep(33)  # 1 frame = 33ms
        self.out_spin.setFixedHeight(35)  # 높이 증가
        self.out_spin.setFixedWidth(100)  # 너비 고정
        # CSS 스타일로 버튼을 위/아래 배치
        self.out_spin.setStyleSheet("""
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
                height: 15px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
                height: 15px;
            }
        """)

        # Layout
        layout = QVBoxLayout(self)
        
        # Project buttons layout
        project_layout = QHBoxLayout()
        project_layout.addWidget(self.open_project_btn)
        project_layout.addWidget(self.save_project_btn)
        project_layout.addWidget(self.save_as_project_btn)
        layout.addLayout(project_layout)
        
        layout.addWidget(self.video_widget)
        
        # Timeline row with time display and timeline
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.time_display)
        timeline_layout.addWidget(self.timeline)
        layout.addLayout(timeline_layout)
        
        layout.addWidget(self.timeline_scrollbar)

        controls = QHBoxLayout()
        controls.addWidget(self.open_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.in_btn)
        controls.addWidget(self.out_btn)
        layout.addLayout(controls)

        properties = QHBoxLayout()
        properties.setSpacing(10)  # 위젯 간 간격 증가
        
        # IN section
        properties.addWidget(self.in_label)
        properties.addWidget(self.in_spin)
        
        # OUT section  
        properties.addWidget(self.out_label)
        properties.addWidget(self.out_spin)
        
        # Action section
        properties.addWidget(QLabel("Action:"))
        properties.addWidget(self.action_combo)
        
        # Remove button
        properties.addWidget(self.remove_btn)
        
        # Add stretch to push everything to the left
        properties.addStretch()
        
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
        self.in_spin.valueChanged.connect(self.on_in_spin_changed)
        self.out_spin.valueChanged.connect(self.on_out_spin_changed)
        self.player.positionChanged.connect(self.update_timeline)
        self.timeline.positionChanged.connect(self.seek)
        self.timeline.segmentClicked.connect(self.on_segment_clicked)
        self.timeline.selectionCleared.connect(self.on_selection_cleared)
        self.timeline_scrollbar.valueChanged.connect(self.on_scrollbar_changed)

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
                        color = row.get('Color', '#FF9999')  # 기본 색상
                        
                        # Store action-color mapping
                        self.action_colors[technique] = color
                        
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
                # Default colors for fallback actions
                self.action_colors = {
                    "jump": "#FF9999",
                    "spin": "#99FF99", 
                    "footwork": "#9999FF",
                    "transition": "#FFFF99"
                }
        except Exception as e:
            print(f"Error loading actions from CSV: {e}")
            # Fallback to default actions
            self.action_combo.addItems(["jump", "spin", "footwork", "transition"])
            self.action_colors = {
                "jump": "#FF9999",
                "spin": "#99FF99", 
                "footwork": "#9999FF",
                "transition": "#FFFF99"
            }
    
    def open_project(self):
        """Open a project file"""
        file, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트 열기",
            self.last_directory,
            "프로젝트 파일 (*.csv);;모든 파일 (*)"
        )
        if file:
            self.load_project(file)
    
    def save_project(self):
        """Save current project"""
        if self.current_project_file:
            self.save_project_to_csv(self.current_project_file)
        else:
            self.save_as_project()
    
    def save_as_project(self):
        """Save project with new name"""
        file, _ = QFileDialog.getSaveFileName(
            self,
            "프로젝트 저장",
            self.last_directory,
            "프로젝트 파일 (*.csv);;모든 파일 (*)"
        )
        if file:
            self.save_project_to_csv(file)
            self.current_project_file = file
    
    def save_project_to_json(self, filepath):
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
                    'action': segment.action,
                    'color': segment.color
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            
            print(f"프로젝트 저장됨: {filepath}")
            
        except Exception as e:
            print(f"프로젝트 저장 오류: {e}")
    
    def save_project_to_csv(self, filepath):
        """Save project data to CSV file"""
        try:
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Write segments without header
                for segment in self.timeline.segments:
                    start_time = self.ms_to_time_string(segment.start)
                    end_time = self.ms_to_time_string(segment.end)
                    writer.writerow([start_time, end_time, segment.action])
            print(f"CSV 저장 완료: {filepath}")
        except Exception as e:
            print(f"CSV 저장 실패: {e}")
    
    def load_project(self, filepath):
        """Load project from CSV file"""
        try:
            import csv
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                # Clear existing segments
                self.timeline.segments.clear()
                
                # Load segments from CSV (no header)
                for row in reader:
                    if len(row) >= 3:  # Ensure we have at least 3 columns
                        start_ms = self.time_string_to_ms(row[0])
                        end_ms = self.time_string_to_ms(row[1])
                        technique = row[2]
                        
                        # Get color for technique
                        color = self.action_colors.get(technique, '#FF9999')
                        
                        self.timeline.add_segment(start_ms, end_ms, technique, color)
            
            self.current_project_file = filepath
            print(f"프로젝트 로드됨: {filepath}")
            
        except Exception as e:
            print(f"프로젝트 로드 오류: {e}")
    

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
            # Get color for the action
            clean_action = action.strip()
            color = self.action_colors.get(clean_action, "#FF9999")
            success = self.timeline.add_segment(self.in_time, self.out_time, action, color)
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
        self.update_time_display(pos)

    def seek(self, position):
        print(f"Seeking to {position}.")
        self.player.setPosition(position)
    
    def on_segment_clicked(self, segment_index):
        print("on_segment_clicked")
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
            # Update spin boxes
            self.in_spin.setValue(int(segment.start))
            self.out_spin.setValue(int(segment.end))
            self.in_spin.setEnabled(True)
            self.out_spin.setEnabled(True)
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
            # Update the segment's action and color
            self.timeline.segments[segment_index].action = clean_action
            self.timeline.segments[segment_index].color = self.action_colors.get(clean_action, "#FF9999")
            print(f"Updated segment {segment_index} action to: {clean_action}")
            # Refresh the timeline display
            self.timeline.update()
    
    def on_in_spin_changed(self, value):
        """Handle IN spin box change event"""
        if self.timeline.selected_segment is not None:
            segment_index = self.timeline.selected_segment
            segment = self.timeline.segments[segment_index]
            
            # Update segment start time
            segment.start = value
            
            # Update labels
            self.in_label.setText(f"IN: {value/1000:.2f}s")
            self.in_time = value
            
            # Move video to IN position
            self.player.setPosition(value)
            
            # Refresh timeline display
            self.timeline.update()
            print(f"Updated segment {segment_index} IN to: {value}ms")
    
    def on_out_spin_changed(self, value):
        """Handle OUT spin box change event"""
        if self.timeline.selected_segment is not None:
            segment_index = self.timeline.selected_segment
            segment = self.timeline.segments[segment_index]
            
            # Update segment end time
            segment.end = value
            
            # Update labels
            self.out_label.setText(f"OUT: {value/1000:.2f}s")
            self.out_time = value
            
            # Move video to OUT position
            self.player.setPosition(value)
            
            # Refresh timeline display
            self.timeline.update()
            print(f"Updated segment {segment_index} OUT to: {value}ms")
    

    # 여기서 in_time이 지워져버리는 게 문제!!!
    def on_selection_cleared(self):
        """Handle selection cleared event"""
        print("on_selection_cleared")
        # Clear the properties display
        self.in_label.setText("IN: -")
        self.out_label.setText("OUT: -")
        # self.in_time = None
        # self.out_time = None
        # Disable action combo and spin boxes
        self.action_combo.setEnabled(False)
        self.in_spin.setEnabled(False)
        self.out_spin.setEnabled(False)
    
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
    
    def on_scrollbar_changed(self, value):
        """Handle scrollbar value change"""
        self.timeline.set_scroll_offset(value)
    
    def update_time_display(self, position_ms):
        """Update time display textbox with current position"""
        time_str = self.ms_to_time_string(position_ms)
        self.time_display.setText(time_str)
    
    def ms_to_time_string(self, position_ms):
        """Convert milliseconds to HH:MM:SS.SSS format"""
        seconds = position_ms / 1000.0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    
    def time_string_to_ms(self, time_str):
        """Convert HH:MM:SS.SSS format to milliseconds"""
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
                return int(total_ms)
            else:
                return 0
        except (ValueError, IndexError):
            return 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoAnnotator()
    win.show()
    sys.exit(app.exec())
