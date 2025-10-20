import sys
import csv
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QSlider, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsItem, QSpinBox, QScrollBar, QGroupBox
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
    
    # 타임라인 스케일 상수 (1초당 픽셀 수)
    PX_PER_SEC = 7.5
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)  # 높이를 60에서 40으로 줄임
        self.setMinimumWidth(400)
        
        self.duration = 0
        self.current_position = 0
        self.segments = []
        self.selected_segment = None  # Index of selected segment
        self.in_marker = None  # IN marker position
        self.scroll_offset = 0  # 스크롤 오프셋
        
        # 드래그 관련 변수들
        self.dragging = False
        self.drag_start_x = 0
        
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
        # 스크롤바 범위 업데이트
        if duration > 0:
            total_width = max(400, int(duration / 1000 * self.PX_PER_SEC))
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
        
        # 스케일로 계산
        total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
        position = (x / total_width) * self.duration
        for i, segment in enumerate(self.segments):
            if segment.contains(position):
                return i
        return None
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.position().x() + self.scroll_offset
            segment_idx = self.get_segment_at_position(x)
            
            # 드래그 시작
            self.dragging = True
            self.drag_start_x = x
            
            # Always emit positionChanged first
            if self.duration > 0:
                total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
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
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move event for dragging"""
        if self.dragging and self.duration > 0:
            x = event.position().x() + self.scroll_offset
            total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
            position = int((x / total_width) * self.duration)
            
            # 위치를 유효한 범위로 제한
            position = max(0, min(position, self.duration))
            
            # 위치 업데이트
            self.positionChanged.emit(position)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release event"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.bg_color)
        
        if self.duration == 0:
            return
        
        # Draw segments
        for i, segment in enumerate(self.segments):
            # 스케일로 계산
            total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
            start_x = (segment.start / self.duration) * total_width - self.scroll_offset
            end_x = (segment.end / self.duration) * total_width - self.scroll_offset
            
            # Use segment's own color if available, otherwise fallback to default colors
            if segment.color:
                color = QColor(segment.color)
            else:
                color = self.segment_colors[i % len(self.segment_colors)]
            painter.fillRect(QRectF(start_x, 5, end_x - start_x, 30), color)
            
            # Draw segment border - thicker for selected segment
            border_width = 4 if i == self.selected_segment else 2
            painter.setPen(QPen(QColor(255, 255, 255), border_width))
            painter.drawRect(QRectF(start_x, 5, end_x - start_x, 30))
        
        # Draw IN marker (gray vertical line)
        if self.in_marker is not None and self.duration > 0:
            total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
            in_x = (self.in_marker / self.duration) * total_width - self.scroll_offset
            painter.setPen(QPen(QColor(128, 128, 128), 3))  # Gray color
            painter.drawLine(in_x, 0, in_x, self.height())
        
        # Draw current position
        if self.duration > 0:
            total_width = max(400, int(self.duration / 1000 * self.PX_PER_SEC))
            pos_x = (self.current_position / self.duration) * total_width - self.scroll_offset
            painter.setPen(QPen(self.current_pos_color, 3))
            painter.drawLine(pos_x, 0, pos_x, self.height())


class VideoAnnotator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KBS Video Labeler by J. Oh")
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
        self.open_project_btn = QPushButton("프로젝트(비디오) 열기")
        self.save_project_btn = QPushButton("프로젝트 저장")

        # Buttons
        self.play_btn = QPushButton("▶️")
        self.play_btn.setStyleSheet("font-size: 20px;")  # 아이콘 크기 확대
        self.in_btn = QPushButton("Set IN")
        self.out_btn = QPushButton("Set OUT")

        # Labels
        self.in_label = QLabel("IN:")
        self.out_label = QLabel("OUT:")

        # Timeline widget
        self.timeline = TimelineWidget()
        
        # Time display widget (custom)
        self.time_display = QWidget()
        self.time_display.setFixedWidth(120)
        self.time_display.setFixedHeight(40)
        self.time_display.setStyleSheet("border: 1px solid gray; background-color: white;")
        
        # Time display layout
        time_layout = QHBoxLayout(self.time_display)
        time_layout.setContentsMargins(5, 0, 5, 0)
        
        # Time label (shows HH:MM:SS.SSS)
        self.time_label = QLabel("00:00:00.000")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-weight: bold;")
        
        # Time control buttons
        self.time_up_btn = QPushButton("▲")
        self.time_up_btn.setFixedSize(20, 15)
        self.time_up_btn.setStyleSheet("font-size: 10px;")
        
        self.time_down_btn = QPushButton("▼")
        self.time_down_btn.setFixedSize(20, 15)
        self.time_down_btn.setStyleSheet("font-size: 10px;")
        
        # Add to layout
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_up_btn)
        time_layout.addWidget(self.time_down_btn)
        
        # Scale control widgets
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 100)
        self.scale_spin.setValue(int(self.timeline.PX_PER_SEC))
        self.scale_spin.setSuffix(" px/sec")
        self.scale_spin.setFixedHeight(40)
        self.scale_spin.setFixedWidth(120)  # 너비를 80에서 120으로 증가
        # CSS 스타일로 버튼을 위/아래 배치
        self.scale_spin.setStyleSheet("""
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
        self.scale_label = QLabel("스케일:")
        
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
        layout.addLayout(project_layout)
        
        layout.addWidget(self.video_widget)
        
        # Timeline row with time display
        timeline_layout = QHBoxLayout()
        timeline_layout.addWidget(self.timeline)
        timeline_layout.addWidget(self.time_display)
        layout.addLayout(timeline_layout)
        
        layout.addWidget(self.timeline_scrollbar)

        controls = QHBoxLayout()
        
        # 위젯들의 크기를 키움
        self.time_display.setFixedHeight(40)
        self.play_btn.setFixedHeight(40)
        self.in_btn.setFixedHeight(40)
        self.out_btn.setFixedHeight(40)
        
        # 스케일 컨트롤을 별도 레이아웃으로 그룹화
        scale_layout = QHBoxLayout()
        scale_layout.setSpacing(2)  # 라벨과 스핀박스 사이 간격 최소화
        scale_layout.addWidget(self.scale_label)
        scale_layout.addWidget(self.scale_spin)
        
        controls.addLayout(scale_layout)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.in_btn)
        controls.addWidget(self.out_btn)
        layout.addLayout(controls)

        # Create properties group box
        properties_group = QGroupBox("세그먼트")
        properties_group.setFixedHeight(70)  # 그룹박스 높이를 적절하게 설정
        properties_layout = QHBoxLayout(properties_group)
        properties_layout.setContentsMargins(15, 10, 15, 10)  # 여유있는 여백 설정
        properties_layout.setSpacing(10)  # 위젯 간 간격 증가
        
        # IN section
        properties_layout.addWidget(self.in_label)
        properties_layout.addWidget(self.in_spin)
        
        # OUT section  
        properties_layout.addWidget(self.out_label)
        properties_layout.addWidget(self.out_spin)
        
        # Action section
        properties_layout.addWidget(QLabel("Action:"))
        properties_layout.addWidget(self.action_combo)
        
        # Remove button
        properties_layout.addWidget(self.remove_btn)
        
        # Add stretch to push everything to the left
        properties_layout.addStretch()
        
        layout.addWidget(properties_group)

        # State
        self.filename = None
        self.in_time = None
        self.out_time = None

        # Signals
        self.open_project_btn.clicked.connect(self.open_project)
        self.save_project_btn.clicked.connect(self.save_project)
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
        self.scale_spin.valueChanged.connect(self.on_scale_changed)
        self.time_up_btn.clicked.connect(self.on_time_up)
        self.time_down_btn.clicked.connect(self.on_time_down)
        
        # 스케일 설정 로드 (모든 위젯 생성 후)
        self.load_scale_config()

    def load_last_directory(self):
        """Load last used directory from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"Loaded config: {config}")
                    return config.get('last_directory', '')
        except Exception as e:
            print(f"Error loading config: {e}")
        return ''
    
    def load_scale_config(self):
        """Load scale setting from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 스케일 값 로드
                    scale_value = config.get('scale', 7.5)
                    self.timeline.PX_PER_SEC = scale_value
                    self.scale_spin.setValue(int(scale_value))
                    print(f"Loaded scale: {scale_value}")
        except Exception as e:
            print(f"Error loading scale config: {e}")

    def save_last_directory(self, directory):
        """Save last used directory and scale to config file"""
        print(f"SAVING last directory: {directory}")
        try:
            config = {
                'last_directory': directory,
                'scale': self.timeline.PX_PER_SEC
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def save_scale_config(self):
        """Save only scale setting to config file"""
        try:
            # 기존 설정 로드
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 스케일 값 업데이트
            config['scale'] = self.timeline.PX_PER_SEC
            
            # 설정 저장
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving scale config: {e}")
    
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
        """Open project file (mp4 or csv)"""
        file, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트(영상) 열기",
            self.last_directory,
            "비디오 및 프로젝트 파일 (*.mp4 *.csv);;비디오 파일 (*.mp4);;프로젝트 파일 (*.csv);;모든 파일 (*)"
        )
        if file:
            self.save_last_directory(os.path.dirname(file))
            if file.lower().endswith('.mp4'):
                # Open video file
                self.filename = file
                self.player.setSource(QUrl.fromLocalFile(file))
                self.player.play()
                self.play_btn.setText("⏸️")  # 재생 중이므로 일시정지 아이콘으로 변경
                
                # Set timeline duration when video is loaded
                def on_duration_changed():
                    print('on_duration_changed...')
                    duration = self.player.duration()
                    if duration > 0:
                        self.timeline.set_duration(duration)
                        # spinbox 최대값을 비디오 길이로 설정
                        print(f'Setting spinbox max to {duration}')
                        self.in_spin.setMaximum(duration)
                        self.out_spin.setMaximum(duration)
                        
                self.player.durationChanged.connect(on_duration_changed)
                
                # Try to load corresponding CSV file
                csv_file = file.rsplit('.', 1)[0] + '.csv'
                if os.path.exists(csv_file):
                    self.load_project(csv_file)
                else:
                    print(f"CSV 파일을 찾을 수 없습니다: {csv_file}")
                
            elif file.lower().endswith('.csv'):
                # Open CSV file
                self.load_project(file)
                
                # Try to load corresponding video file
                video_file = file.rsplit('.', 1)[0] + '.mp4'
                if os.path.exists(video_file):
                    self.filename = video_file
                    self.player.setSource(QUrl.fromLocalFile(video_file))
                    self.player.play()
                    self.play_btn.setText("⏸️")  # 재생 중이므로 일시정지 아이콘으로 변경
                    
                    # Set timeline duration when video is loaded
                    def on_duration_changed():
                        duration = self.player.duration()
                        if duration > 0:
                            self.timeline.set_duration(duration)
                    
                    self.player.durationChanged.connect(on_duration_changed)
                else:
                    print(f"비디오 파일을 찾을 수 없습니다: {video_file}")
    
    def save_project(self):
        """Save current project"""
        if self.filename:
            # Save to CSV with same name as current video file
            csv_file = self.filename.rsplit('.', 1)[0] + '.csv'
            self.save_project_to_csv(csv_file)
            self.current_project_file = csv_file
            
            # Show success dialog
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "저장 완료", f"프로젝트가 저장되었습니다:\n{csv_file}")
        else:
            # Show error dialog
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "저장 실패", "저장할 비디오 파일이 없습니다.")
    
    
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
    


    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶️")
        else:
            self.player.play()
            self.play_btn.setText("⏸️")

    def set_in(self):
        print(f"Setting IN at: {self.player.position()/1000:.2f}s")
        self.in_time = self.player.position()
        # self.in_label.setText(f"IN: {self.in_time/1000:.2f}s")
        # Set IN marker on timeline
        self.timeline.set_in_marker(self.in_time)

    def set_out(self):
        # print(f"Setting OUT at: {self.player.position()/1000:.2f}s")
        self.out_time = self.player.position()
        # self.out_label.setText(f"OUT: {self.out_time/1000:.2f}s")
        
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
                # self.timeline.clear_in_marker()
                self.in_time = None
                self.out_time = None
                self.in_label.setText("IN:")
                self.out_label.setText("OUT:")

    def update_timeline(self, pos):
        # print(f"Updating timeline to {pos}.")
        self.timeline.set_position(pos)
        self.update_time_display(pos)

    def seek(self, position):
        # print(f"Seeking to {position}.")
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
            # self.in_label.setText(f"IN: {segment.start/1000:.2f}s")
            # self.out_label.setText(f"OUT: {segment.end/1000:.2f}s")
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
            # self.in_label.setText(f"IN: {value/1000:.2f}s")
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
            # self.out_label.setText(f"OUT: {value/1000:.2f}s")
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
        self.in_label.setText("IN:")
        self.out_label.setText("OUT:")
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
            self.in_label.setText("IN:")
            self.out_label.setText("OUT:")
            self.in_time = None
            self.out_time = None
            # Disable action combo
            self.action_combo.setEnabled(False)
    
    def on_scrollbar_changed(self, value):
        """Handle scrollbar value change"""
        self.timeline.set_scroll_offset(value)
    
    def on_scale_changed(self, value):
        """Handle scale spin box change"""
        self.timeline.PX_PER_SEC = value
        # 타임라인 다시 그리기
        if self.timeline.duration > 0:
            self.timeline.set_duration(self.timeline.duration)
        # 설정 자동 저장
        self.save_scale_config()
    
    def update_time_display(self, position_ms):
        """Update time display with current position"""
        # 시간 형식을 HH:MM:SS.SSS로 표시
        time_str = self.ms_to_time_string(position_ms)
        self.time_label.setText(time_str)
    
    def on_time_up(self):
        """Handle time up button click"""
        current_pos = self.player.position()
        new_pos = current_pos + 33  # 1프레임 증가 (33ms)
        self.player.setPosition(new_pos)
        self.timeline.set_position(new_pos)
    
    def on_time_down(self):
        """Handle time down button click"""
        current_pos = self.player.position()
        new_pos = max(0, current_pos - 33)  # 1프레임 감소 (33ms, 0 이하로는 안됨)
        self.player.setPosition(new_pos)
        self.timeline.set_position(new_pos)
    
    # def ms_to_time_string(self, position_ms):
    #     """Convert milliseconds to HH:MM:SS.SSS format"""
    #     seconds = position_ms / 1000.0
    #     hours = int(seconds // 3600)
    #     minutes = int((seconds % 3600) // 60)
    #     seconds = seconds % 60
    #     return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

# ...existing code...
    def ms_to_time_string(self, position_ms):
        """Convert milliseconds to HH:MM:SS.mmm format"""
        total_ms = int(position_ms)
        hours = total_ms // 3_600_000
        minutes = (total_ms % 3_600_000) // 60_000
        seconds = (total_ms % 60_000) // 1000
        ms = total_ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
# ...existing code...

# ...existing code...
    def time_string_to_ms(self, time_str):
        """Convert HH:MM:SS[.SSS], MM:SS[.SSS], or S[.SSS] to milliseconds"""
        try:
            s = (time_str or "").strip()
            if not s:
                return 0
            parts = s.split(':')
            hours = 0
            minutes = 0
            sec_str = "0"
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                sec_str = parts[2]
            elif len(parts) == 2:
                minutes = int(parts[0])
                sec_str = parts[1]
            else:
                sec_str = parts[0]
            import re
            m = re.search(r'(\d+(?:[.,]\d+)?)', sec_str)
            if m:
                seconds = float(m.group(1).replace(',', '.'))
            else:
                seconds = 0.0
            total_ms = int(round((hours * 3600 + minutes * 60 + seconds) * 1000))
            return total_ms
        except (ValueError, IndexError):
            return 0
# ...existing code...

    def time_string_to_ms_buggy(self, time_str):
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
    print('Starting Video Annotator...')
    app = QApplication(sys.argv)
    win = VideoAnnotator()
    win.show()
    sys.exit(app.exec())
