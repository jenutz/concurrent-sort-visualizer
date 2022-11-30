import sys
import random
import threading
import time
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


class BaseSorter:
    def __init__(self, name, key, data_ref, get_params_func):
        self.name = name
        self.key = key
        self.nums = data_ref
        self.finished = False
        self.stopped = False
        self.priority = 1
        self.get_params = get_params_func
        self.base_time = 0.01

    def throttle(self):
        if self.stopped:
            return

        speed = self.get_params()

        for t in self.other_threads:
            threading.main_thread().join(timeout=self.base_time / speed / self.priority)


class InsertionSort(BaseSorter):
    def sort(self):
        self.throttle()
        for i in range(1, len(self.nums)):
            if self.stopped:
                break
            key_val = self.nums[i]
            j = i - 1
            while j >= 0 and self.nums[j] > key_val:
                if self.stopped:
                    break
                self.nums[j + 1] = self.nums[j]
                self.throttle()
                j -= 1
            self.nums[j + 1] = key_val
            self.throttle()
        self.finished = True


class QuickSort(BaseSorter):
    def sort(self):
        self.throttle()
        self._quick_sort(0, len(self.nums) - 1)
        self.finished = True

    def _quick_sort(self, low, high):
        if low < high and not self.stopped:
            p = self._partition(low, high)
            self._quick_sort(low, p)
            self._quick_sort(p + 1, high)

    def _partition(self, low, high):
        pivot = self.nums[(low + high) // 2]
        i, j = low - 1, high + 1
        while True:
            i += 1
            while i < len(self.nums) and self.nums[i] < pivot:
                i += 1
            j -= 1
            while j >= 0 and self.nums[j] > pivot:
                j -= 1
            if i >= j or self.stopped:
                return j
            self.nums[i], self.nums[j] = self.nums[j], self.nums[i]
            self.throttle()
            self.throttle()


class ShellSort(BaseSorter):
    def sort(self):
        self.throttle()
        n = len(self.nums)
        gap = n // 2
        while gap > 0 and not self.stopped:
            for i in range(gap, n):
                if self.stopped:
                    break
                temp = self.nums[i]
                j = i
                while j >= gap and self.nums[j - gap] > temp:
                    self.nums[j] = self.nums[j - gap]
                    j -= gap
                    self.throttle()
                self.nums[j] = temp
                self.throttle()
            gap //= 2
        self.finished = True


class ChartWidget(QFrame):
    def __init__(self, sorter):
        super().__init__()
        self.sorter = sorter
        self.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{sorter.name}</b>"))

        self.p_slider = QSlider(Qt.Horizontal)
        self.p_slider.setRange(1, 10)
        self.p_slider.setValue(1)
        self.p_label = QLabel(f"Priority: {self.p_slider.value()}")
        self.p_slider.valueChanged.connect(self._update_p)

        layout.addWidget(self.p_label)
        layout.addWidget(self.p_slider)

        self.pw = pg.PlotWidget()
        self.pw.setBackground("w")
        self.bar = pg.BarGraphItem(x=[], height=[], width=0.7, brush="b")
        self.pw.addItem(self.bar)
        layout.addWidget(self.pw)

        self.bar = pg.BarGraphItem(
            x=range(len(sorter.nums)), height=sorter.nums, width=0.7, brush="b", pen=None
        )
        self.prev_nums = list(sorter.nums)
        self.pw.addItem(self.bar)

    def _update_p(self, val):
        self.p_label.setText(f"Priority: {val}")
        self.sorter.priority = val

    def update_view(self):
        current_nums = self.sorter.nums
        n = len(current_nums)

        if self.sorter.finished:
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
        self.type_combo.addItems(["Random", "Shuffled"])

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

    def get_throttle_params(self):
        return self.speed_slider.value() / 100

    def generate_data(self):
        self.timer.stop()
        for s in self.sorters:
            s.stopped = True
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

        self.sorters = [
            QuickSort("Quick Sort", "q", d1, self.get_throttle_params),
            ShellSort("Shell Sort", "s", d2, self.get_throttle_params),
            InsertionSort("Insertion Sort", "i", d3, self.get_throttle_params),
        ]

        self.charts = [ChartWidget(s) for s in self.sorters]
        for c in self.charts:
            self.charts_layout.addWidget(c)
        self.refresh()
        self.run_btn.setEnabled(True)

    def run_all(self):
        self.run_btn.setEnabled(False)
        self.threads = []
        for s in self.sorters:
            s.finished = False
            s.stopped = False
            t = threading.Thread(target=s.sort, daemon=True)
            self.threads.append(t)

        for i, s in enumerate(self.sorters):
            s.other_threads = [t for j, _ in enumerate(self.threads) if i != j]

        for t in self.threads:
            t.start()
        self.timer.start(60)

    def refresh(self):
        for c in self.charts:
            c.update_view()
        if all(s.finished for s in self.sorters):
            self.timer.stop()
            self.run_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
