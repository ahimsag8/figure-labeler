import sys
import csv
import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QSlider, QComboBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


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

        # Timeline slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)

        # Action dropdown
        self.action_combo = QComboBox()
        self.action_combo.addItems(["jump", "spin", "footwork", "transition"])

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.video_widget)
        layout.addWidget(self.slider)

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
        self.player.positionChanged.connect(self.update_slider)
        self.slider.sliderMoved.connect(self.seek)

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

    def save_segment(self):
        if not self.filename or self.in_time is None or self.out_time is None:
            return
        action = self.action_combo.currentText()
        with open("annotations.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([self.filename, self.in_time, self.out_time, action])
        print("Saved:", self.filename, self.in_time, self.out_time, action)

    def update_slider(self, pos):
        print(f"Updating slider to {pos}.")
        if self.player.duration() > 0:
            self.slider.setValue(int(pos * 1000 / self.player.duration()))

    def seek(self, value):
        print(f"Seeking to {value}.")
        if self.player.duration() > 0:
            self.player.setPosition(int(self.player.duration() * value / 1000))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VideoAnnotator()
    win.show()
    sys.exit(app.exec())
