import sys
import random
import threading
import time
import random
import signal
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QSlider,
    QFrame,
    QComboBox,
    QCheckBox,
)
from PyQt5.QtCore import QTimer, Qt
import pyqtgraph as pg
from collections import Counter


class SortScheduler:
    def __init__(self, get_speed):
        self._condition = threading.Condition()
        self._turn = None
        self._priorities = Counter()
        self._time_frames = Counter()
        self._stopped = False
        self._last_start = time.time()
        self._get_speed = get_speed
        self._delta_sec = 0.01
        self._TIME_MULT = 10

    def stop(self, value=True):
        self._stopped = value

    def subscribe(self, sorter):
        with self._condition:
            self._priorities[sorter.get_name()] = sorter.get_priority()
            self._time_frames[sorter.get_name()] = sorter.get_priority()
            self._last_start = time.time()

    def unsubscribe(self, sorter):
        with self._condition:
            del self._priorities[sorter.get_name()]
            del self._time_frames[sorter.get_name()]
            self.pick_next()

    def pick_next(self):
        with self._condition:
            if not self._priorities:
                return

            while sum(self._time_frames.values()) <= 0:
                self._time_frames += self._priorities

            self._turn = random.choices(
                list(self._time_frames.keys()), weights=self._time_frames.values(), k=1
            )[0]
            self._condition.notify_all()

    def _stat(self):
        print(f"\n{'Algorithm':<15} | {'Time (ms)':<10}")
        print("-" * 28)

        for algo, duration in self._time_frames.items():
            print(f"{algo:<15} | {duration:>10.4f}")
        print()
        print(f"Currently running: {self._turn}")

    def sync(self, caller_id):
        with self._condition:
            passed_time = time.time() - self._last_start
            time.sleep(self._delta_sec / self._get_speed())
            self._time_frames[caller_id] -=  passed_time * self._TIME_MULT
            self.pick_next()
            self._condition.wait_for(lambda: self._turn == caller_id or self._stopped)
            self._last_start = time.time()


class BaseSorter:
    def __init__(self, name, data_ref, scheduler):
        self._name = name
        self._priority = None
        self._nums = data_ref
        self._finished = False
        self._stopped = False
        self._scheduler = scheduler

    def get_name(self):
        return self._name

    def get_priority(self):
        return self._priority

    def get_nums(self):
        return self._nums

    def is_finished(self):
        return self._finished

    def stop(self, value=True):
        self._stopped = value

    def _sync(self):
        self._scheduler.sync(self._name)

    def set_priority(self, priority):
        self._priority = priority


class InsertionSort(BaseSorter):
    def sort(self):
        self._scheduler.subscribe(self)
        self._sync()
        for i in range(1, len(self._nums)):
            if self._stopped:
                break
            key_val = self._nums[i]
            j = i - 1
            while j >= 0 and self._nums[j] > key_val:
                if self._stopped:
                    break
                self._nums[j + 1] = self._nums[j]
                self._sync()
                j -= 1
            self._nums[j + 1] = key_val
            self._sync()
        self._finished = True
        self._scheduler.unsubscribe(self)


class QuickSort(BaseSorter):
    def sort(self):
        self._scheduler.subscribe(self)
        self._quick_sort(0, len(self._nums) - 1)
        self._finished = True
        self._scheduler.unsubscribe(self)

    def _quick_sort(self, low, high):
        if low < high and not self._stopped:
            p = self._partition(low, high)
            self._quick_sort(low, p)
            self._quick_sort(p + 1, high)

    def _partition(self, low, high):
        pivot = self._nums[(low + high) // 2]
        i, j = low - 1, high + 1
        while True:
            i += 1
            while i < len(self._nums) and self._nums[i] < pivot:
                i += 1
            j -= 1
            while j >= 0 and self._nums[j] > pivot:
                j -= 1
            if i >= j or self._stopped:
                return j
            self._nums[i], self._nums[j] = self._nums[j], self._nums[i]
            self._sync()


class ShellSort(BaseSorter):
    def sort(self):
        self._scheduler.subscribe(self)
        n = len(self._nums)
        gap = n // 2
        while gap > 0 and not self._stopped:
            for i in range(gap, n):
                if self._stopped:
                    break
                temp = self._nums[i]
                j = i
                while j >= gap and self._nums[j - gap] > temp:
                    self._nums[j] = self._nums[j - gap]
                    j -= gap
                self._nums[j] = temp
                self._sync()
            gap //= 2
        self._finished = True
        self._scheduler.unsubscribe(self)


class ChartWidget(QFrame):
    def __init__(self, sorter):
        super().__init__()
        self.sorter = sorter
        self.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{sorter.get_name()}</b>"))

        self.p_slider = QSlider(Qt.Horizontal)
        self.p_slider.setRange(1, 10)
        self.p_slider.setValue(1)
        self.p_label = QLabel(f"Priority: {self.p_slider.value()}")
        self.p_slider.valueChanged.connect(self._update_p)
        self._update_p(self.p_slider.value())

        layout.addWidget(self.p_label)
        layout.addWidget(self.p_slider)

        self.pw = pg.PlotWidget()
        self.pw.setBackground("w")
        self.bar = pg.BarGraphItem(x=[], height=[], width=0.7, brush="b")
        self.pw.addItem(self.bar)
        layout.addWidget(self.pw)

        self.bar = pg.BarGraphItem(
            x=range(len(sorter.get_nums())),
            height=sorter.get_nums(),
            width=0.7,
            brush="b",
            pen=None,
        )
        self.prev_nums = list(sorter.get_nums())
        self.pw.addItem(self.bar)

    def _update_p(self, val):
        self.p_label.setText(f"Priority: {val}")
        self.sorter.set_priority(self.p_slider.value())

    def update_view(self):
        current_nums = self.sorter.get_nums()
        n = len(current_nums)

        if self.sorter.is_finished():
            color_list = ["g"] * n
        else:
            color_list = ["r" if current_nums[i] != self.prev_nums[i] else "b" for i in range(n)]

        brushes = [pg.mkBrush(c) for c in color_list]
        self.bar.setOpts(height=current_nums, brushes=brushes)
        self.prev_nums = list(current_nums)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sorts Visualizer")
        self.resize(1400, 750)
        self.sorters = []
        self.threads = []
        self._setup_ui()

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)

        controls = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_all)
        self.reset_btn = QPushButton("Reset Data")
        self.reset_btn.clicked.connect(self.generate_data)
        self.share_checkbox = QCheckBox("Share Memory")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Shuffled", "Random"])

        controls.addWidget(self.run_btn)
        controls.addWidget(self.reset_btn)
        controls.addWidget(self.share_checkbox)
        controls.addWidget(QLabel("Data:"))
        controls.addWidget(self.type_combo)
        controls.setSpacing(5)
        controls.addStretch(1)
        self.layout.addLayout(controls)

        params = QHBoxLayout()
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(10, 1000)
        self.size_slider.setValue(80)
        self.size_lbl = QLabel(f"Size: {self.size_slider.value()}")
        self.size_slider.valueChanged.connect(lambda v: self.size_lbl.setText(f"Size: {v}"))

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 1000)
        self.speed_slider.setValue(100)
        self.speed_lbl = QLabel(f"Model speed: {self.speed_slider.value()/100}")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_lbl.setText(f"Model speed: {v/100}")
        )

        v_box1 = QVBoxLayout()
        v_box1.addWidget(self.size_lbl)
        v_box1.addWidget(self.size_slider)
        v_box3 = QVBoxLayout()
        v_box3.addWidget(self.speed_lbl)
        v_box3.addWidget(self.speed_slider)

        params.addLayout(v_box1)
        params.addLayout(v_box3)
        self.layout.addLayout(params)

        self.charts_layout = QHBoxLayout()
        self.layout.addLayout(self.charts_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.generate_data()

    def generate_data(self):
        self.timer.stop()
        for s in self.sorters:
            s.stop()
        self.threads.clear()

        size = self.size_slider.value()
        if self.type_combo.currentText() == "Random":
            master_data = [random.randint(5, 100) for _ in range(size)]
        else:
            master_data = list(range(1, size + 1))
            random.shuffle(master_data)

        while self.charts_layout.count():
            item = self.charts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        is_shared = self.share_checkbox.isChecked()
        d1 = master_data if is_shared else list(master_data)
        d2 = master_data if is_shared else list(master_data)
        d3 = master_data if is_shared else list(master_data)

        self.scheduler = SortScheduler(self.get_speed)
        self.sorters = [
            QuickSort("Quick Sort", d1, self.scheduler),
            ShellSort("Shell Sort", d2, self.scheduler),
            InsertionSort("Insertion Sort", d3, self.scheduler),
        ]

        self.charts = [ChartWidget(s) for s in self.sorters]
        for c in self.charts:
            self.charts_layout.addWidget(c)
        self.refresh()
        self.run_btn.setEnabled(True)

    def get_speed(self):
        return self.speed_slider.value() / 100

    def run_all(self):
        self.run_btn.setEnabled(False)
        for chart in self.charts:
            chart.p_slider.setEnabled(False)

        self.threads = []
        for s in self.sorters:
            t = threading.Thread(target=s.sort, daemon=True)
            self.threads.append(t)

        for t in self.threads:
            t.start()
        self.timer.start(60)

    def refresh(self):
        for c in self.charts:
            c.update_view()
        if all(s.is_finished() for s in self.sorters):
            self.scheduler.stop()
            self.timer.stop()
            for chart in self.charts:
                chart.p_slider.setEnabled(True)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

