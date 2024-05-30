import sys
import subprocess
import time
import glob
from PyQt6.QtWidgets import (QApplication, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QMainWindow, QInputDialog, QLineEdit,
                             QGroupBox, QGridLayout, QComboBox, QFormLayout, QCheckBox, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from pynvml import *

class OverclockApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('NVIDIA GPU Overclocking')

        layout = QVBoxLayout()

        self.gpu_index_label = QLabel('Select GPU:', self)
        layout.addWidget(self.gpu_index_label)
        self.gpu_index_combo = QComboBox(self)
        self.populate_gpu_list()
        layout.addWidget(self.gpu_index_combo)

        self.gpu_offset_label = QLabel('GPU Offset:', self)
        layout.addWidget(self.gpu_offset_label)
        self.gpu_offset_input = QLineEdit(self)
        layout.addWidget(self.gpu_offset_input)
        self.default_gpu_offset_checkbox = QCheckBox('Use default GPU offset', self)
        self.default_gpu_offset_checkbox.stateChanged.connect(self.update_offsets)
        layout.addWidget(self.default_gpu_offset_checkbox)

        self.mem_offset_label = QLabel('Memory Offset:', self)
        layout.addWidget(self.mem_offset_label)
        self.mem_offset_input = QLineEdit(self)
        layout.addWidget(self.mem_offset_input)
        self.default_mem_offset_checkbox = QCheckBox('Use default Memory offset', self)
        self.default_mem_offset_checkbox.stateChanged.connect(self.update_offsets)
        layout.addWidget(self.default_mem_offset_checkbox)

        self.power_limit_label = QLabel('Power Limit (mW):', self)
        layout.addWidget(self.power_limit_label)
        self.power_limit_input = QLineEdit(self)
        layout.addWidget(self.power_limit_input)
        self.default_power_limit_checkbox = QCheckBox('Use default power limit', self)
        self.default_power_limit_checkbox.stateChanged.connect(self.update_power_limit)
        layout.addWidget(self.default_power_limit_checkbox)

        self.fan_speed_label = QLabel('Fan Speed (%):', self)
        layout.addWidget(self.fan_speed_label)
        self.fan_speed_combo = QComboBox(self)
        self.fan_speed_combo.addItem("Default")
        for i in range(10, 110, 10):
            self.fan_speed_combo.addItem(f"{i}%")
        layout.addWidget(self.fan_speed_combo)
        self.manual_fan_control_checkbox = QCheckBox('Enable manual fan control', self)
        self.manual_fan_control_checkbox.stateChanged.connect(self.update_fan_control)
        layout.addWidget(self.manual_fan_control_checkbox)

        self.apply_button = QPushButton('Apply Overclock', self)
        self.apply_button.clicked.connect(self.apply_overclock)
        layout.addWidget(self.apply_button)

        self.setLayout(layout)

    def populate_gpu_list(self):
        try:
            nvmlInit()
            device_count = nvmlDeviceGetCount()
            for i in range(device_count):
                handle = nvmlDeviceGetHandleByIndex(i)
                name = nvmlDeviceGetName(handle)
                self.gpu_index_combo.addItem(f"GPU {i}: {name}", i)
        except Exception as e:
            print(f"Error populating GPU list: {str(e)}")
            QMessageBox.critical(self, "Error", "Failed to retrieve GPU list")

    def get_default_power_limit(self, gpu_index):
        try:
            result = subprocess.run(['nvidia-smi', '-i', str(gpu_index), '-q', '-d', 'POWER'], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("nvidia-smi command failed")

            for line in result.stdout.split('\n'):
                if 'Default Power Limit' in line:
                    value_str = line.split(':')[1].strip().split(' ')[0]
                    return int(float(value_str) * 1000)  # Convert W to mW
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    def get_default_gpu_offset(self, gpu_index):
        return 0

    def get_default_mem_offset(self, gpu_index):
        return 0

    def update_offsets(self):
        gpu_index = self.gpu_index_combo.currentData()
        if self.default_gpu_offset_checkbox.isChecked():
            self.gpu_offset_input.setText(str(self.get_default_gpu_offset(gpu_index)))
        else:
            self.gpu_offset_input.clear()

        if self.default_mem_offset_checkbox.isChecked():
            self.mem_offset_input.setText(str(self.get_default_mem_offset(gpu_index)))
        else:
            self.mem_offset_input.clear()

    def update_power_limit(self):
        if self.default_power_limit_checkbox.isChecked():
            gpu_index = self.gpu_index_combo.currentData()
            power_limit = self.get_default_power_limit(gpu_index)
            if power_limit is not None:
                self.power_limit_input.setText(str(power_limit))
            else:
                QMessageBox.critical(self, "Error", "Failed to get default power limit")
                self.default_power_limit_checkbox.setChecked(False)
        else:
            self.power_limit_input.clear()

    def update_fan_control(self):
        self.fan_speed_combo.setEnabled(self.manual_fan_control_checkbox.isChecked())

    def apply_overclock(self):
        try:
            gpu_index = self.gpu_index_combo.currentData()
            gpu_offset = int(self.gpu_offset_input.text())
            mem_offset = int(self.mem_offset_input.text()) * 2

            if self.default_power_limit_checkbox.isChecked():
                power_limit = self.get_default_power_limit(gpu_index)
                if power_limit is None:
                    QMessageBox.critical(self, "Error", "Failed to get default power limit")
                    return
            else:
                power_limit = int(self.power_limit_input.text())

            gpu_handle = nvmlDeviceGetHandleByIndex(gpu_index)
            min_power_limit = nvmlDeviceGetPowerManagementLimitConstraints(gpu_handle)[0]
            max_power_limit = nvmlDeviceGetPowerManagementLimitConstraints(gpu_handle)[1]

            if power_limit < min_power_limit or power_limit > max_power_limit:
                QMessageBox.critical(self, "Error", f"Power limit must be between {min_power_limit} mW and {max_power_limit} mW")
                return

            fan_speed_script = ""
            if self.manual_fan_control_checkbox.isChecked():
                fan_speed_text = self.fan_speed_combo.currentText()
                if fan_speed_text == "Default":
                    fan_speed_script = "nvmlDeviceSetDefaultFanSpeed(myGPU)\n"
                else:
                    fan_speed = int(fan_speed_text.replace('%', ''))
                    fan_speed_script = f"nvmlDeviceSetGpuFanSpeed(myGPU, {fan_speed})\n"

            script_content = f"""
from pynvml import *
nvmlInit()
myGPU = nvmlDeviceGetHandleByIndex({gpu_index})
nvmlDeviceSetGpcClkVfOffset(myGPU, {gpu_offset})
nvmlDeviceSetMemClkVfOffset(myGPU, {mem_offset})
nvmlDeviceSetPowerManagementLimit(myGPU, {power_limit})
{fan_speed_script}
nvmlShutdown()
"""
            temp_script_path = "/tmp/temp_overclock.py"
            with open(temp_script_path, "w") as f:
                f.write(script_content)

            os.chmod(temp_script_path, 0o755)

            # Run the script using pkexec for root privileges
            result = subprocess.run(["pkexec", "python3", temp_script_path], capture_output=True, text=True)
            if result.returncode == 0:
                QMessageBox.information(self, "Success", "Overclock settings applied successfully")
            else:
                QMessageBox.critical(self, "Error", result.stderr)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class WattageMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cpu_name, self.cpu_codename = self.get_cpu_info()
        self.gpu_info = self.get_gpu_info()
        self.ram_info = self.get_ram_info()
        self.initUI()
        self.setWindowTitle("CPU and GPU Monitor")
        self.setGeometry(100, 100, 800, 1000)
        self.sudo_password = self.get_sudo_password()
        self.last_energy_uj = None
        self.last_time = None
        self.wattage_values = []
        self.vcore_values = []
        self.freq_values = []
        self.temp_values = []

        self.gpu_core_clock_values = []
        self.gpu_memory_clock_values = []
        self.gpu_temp_values = []

        self.max_wattage = 0
        self.min_wattage = float('inf')
        self.max_vcore = 0
        self.min_vcore = float('inf')
        self.max_freq = 0
        self.min_freq = float('inf')
        self.max_temp = 0
        self.min_temp = float('inf')

        self.max_gpu_core_clock = 0
        self.min_gpu_core_clock = float('inf')
        self.max_gpu_memory_clock = 0
        self.min_gpu_memory_clock = float('inf')
        self.max_gpu_temp = 0
        self.min_gpu_temp = float('inf')

        if self.sudo_password:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_metrics)
            self.timer.start(1000)  # Update every second
            self.update_metrics()

    def initUI(self):
        main_layout = QVBoxLayout()

        # CPU Information
        cpu_info_group = QGroupBox("Informasi CPU")
        cpu_info_layout = QFormLayout()
        self.cpu_name_label = QLineEdit(self.cpu_name)
        self.cpu_name_label.setReadOnly(True)
        self.cpu_freq_label = QLineEdit()
        self.cpu_freq_label.setReadOnly(True)
        self.min_freq_label = QLineEdit()
        self.min_freq_label.setReadOnly(True)
        self.max_freq_label = QLineEdit()
        self.max_freq_label.setReadOnly(True)
        self.clock_label = QLineEdit()
        self.clock_label.setReadOnly(True)

        cpu_info_layout.addRow("Nama CPU:", self.cpu_name_label)
        cpu_info_layout.addRow("Frekuensi CPU:", self.cpu_freq_label)
        cpu_info_layout.addRow("Minimum Frequency:", self.min_freq_label)
        cpu_info_layout.addRow("Maximum Frequency:", self.max_freq_label)
        cpu_info_layout.addRow("Real-time Clock:", self.clock_label)
        cpu_info_group.setLayout(cpu_info_layout)

        main_layout.addWidget(cpu_info_group)

        # Wattage Information
        wattage_group = QGroupBox("Wattage")
        wattage_layout = QFormLayout()
        self.realtime_wattage_label = QLineEdit()
        self.realtime_wattage_label.setReadOnly(True)
        self.min_wattage_label = QLineEdit()
        self.min_wattage_label.setReadOnly(True)
        self.max_wattage_label = QLineEdit()
        self.max_wattage_label.setReadOnly(True)
        self.avg_wattage_label = QLineEdit()
        self.avg_wattage_label.setReadOnly(True)

        wattage_layout.addRow("Realtime Wattage:", self.realtime_wattage_label)
        wattage_layout.addRow("Min Wattage:", self.min_wattage_label)
        wattage_layout.addRow("Max Wattage:", self.max_wattage_label)
        wattage_layout.addRow("Average Wattage:", self.avg_wattage_label)
        wattage_group.setLayout(wattage_layout)

        main_layout.addWidget(wattage_group)

        # Voltage Information
        voltage_group = QGroupBox("Voltage")
        voltage_layout = QFormLayout()
        self.realtime_voltage_label = QLineEdit()
        self.realtime_voltage_label.setReadOnly(True)
        self.min_voltage_label = QLineEdit()
        self.min_voltage_label.setReadOnly(True)
        self.max_voltage_label = QLineEdit()
        self.max_voltage_label.setReadOnly(True)
        self.avg_voltage_label = QLineEdit()
        self.avg_voltage_label.setReadOnly(True)

        voltage_layout.addRow("Realtime Voltage:", self.realtime_voltage_label)
        voltage_layout.addRow("Min Voltage:", self.min_voltage_label)
        voltage_layout.addRow("Max Voltage:", self.max_voltage_label)
        voltage_layout.addRow("Average Voltage:", self.avg_voltage_label)
        voltage_group.setLayout(voltage_layout)

        main_layout.addWidget(voltage_group)

        # Temperature Information
        temperature_group = QGroupBox("CPU Temperature")
        temperature_layout = QFormLayout()
        self.realtime_temperature_label = QLineEdit()
        self.realtime_temperature_label.setReadOnly(True)
        self.min_temperature_label = QLineEdit()
        self.min_temperature_label.setReadOnly(True)
        self.max_temperature_label = QLineEdit()
        self.max_temperature_label.setReadOnly(True)
        self.avg_temperature_label = QLineEdit()
        self.avg_temperature_label.setReadOnly(True)

        temperature_layout.addRow("Realtime Temperature:", self.realtime_temperature_label)
        temperature_layout.addRow("Min Temperature:", self.min_temperature_label)
        temperature_layout.addRow("Max Temperature:", self.max_temperature_label)
        temperature_layout.addRow("Average Temperature:", self.avg_temperature_label)
        temperature_group.setLayout(temperature_layout)

        main_layout.addWidget(temperature_group)

        # Dropdown for core frequency
        core_freq_group = QGroupBox("Core Frequency")
        core_freq_layout = QVBoxLayout()
        self.core_freq_dropdown = QComboBox(self)
        self.core_freq_dropdown.addItems([f"Core {i}" for i in range(32)])  # Assuming a maximum of 32 cores
        self.core_freq_dropdown.currentIndexChanged.connect(self.update_core_freq)
        self.core_freq_label = QLineEdit("Select a core to view frequency")
        self.core_freq_label.setReadOnly(True)
        core_freq_layout.addWidget(self.core_freq_dropdown)
        core_freq_layout.addWidget(self.core_freq_label)
        core_freq_group.setLayout(core_freq_layout)

        main_layout.addWidget(core_freq_group)

        # Dropdown for core temperature
        core_temp_group = QGroupBox("Core Temperature")
        core_temp_layout = QVBoxLayout()
        self.core_temp_dropdown = QComboBox(self)
        self.core_temp_dropdown.addItems([f"Core {i}" for i in range(32)])  # Assuming a maximum of 32 cores
        self.core_temp_dropdown.currentIndexChanged.connect(self.update_core_temp)
        self.core_temp_label = QLineEdit("Select a core to view temperature")
        self.core_temp_label.setReadOnly(True)
        core_temp_layout.addWidget(self.core_temp_dropdown)
        core_temp_layout.addWidget(self.core_temp_label)
        core_temp_group.setLayout(core_temp_layout)

        main_layout.addWidget(core_temp_group)

        # GPU Information
        gpu_info_group = QGroupBox("GPU Information")
        gpu_info_layout = QFormLayout()
        self.gpu_name_label = QLineEdit(self.gpu_info.get('name', 'Unknown'))
        self.gpu_name_label.setReadOnly(True)
        self.gpu_type_label = QLineEdit(self.gpu_info.get('type', 'Unknown'))
        self.gpu_type_label.setReadOnly(True)
        self.gpu_core_clock_label = QLineEdit()
        self.gpu_core_clock_label.setReadOnly(True)
        self.gpu_memory_clock_label = QLineEdit()
        self.gpu_memory_clock_label.setReadOnly(True)
        self.gpu_min_core_clock_label = QLineEdit()
        self.gpu_min_core_clock_label.setReadOnly(True)
        self.gpu_max_core_clock_label = QLineEdit()
        self.gpu_max_core_clock_label.setReadOnly(True)
        self.gpu_min_memory_clock_label = QLineEdit()
        self.gpu_min_memory_clock_label.setReadOnly(True)
        self.gpu_max_memory_clock_label = QLineEdit()
        self.gpu_max_memory_clock_label.setReadOnly(True)
        self.gpu_temp_label = QLineEdit()
        self.gpu_temp_label.setReadOnly(True)
        self.gpu_min_temp_label = QLineEdit()
        self.gpu_min_temp_label.setReadOnly(True)
        self.gpu_max_temp_label = QLineEdit()
        self.gpu_max_temp_label.setReadOnly(True)

        gpu_info_layout.addRow("GPU Name:", self.gpu_name_label)
        gpu_info_layout.addRow("GPU Type:", self.gpu_type_label)
        gpu_info_layout.addRow("GPU Core Clock:", self.gpu_core_clock_label)
        gpu_info_layout.addRow("GPU Memory Clock:", self.gpu_memory_clock_label)
        gpu_info_layout.addRow("Min GPU Core Clock:", self.gpu_min_core_clock_label)
        gpu_info_layout.addRow("Max GPU Core Clock:", self.gpu_max_core_clock_label)
        gpu_info_layout.addRow("Min GPU Memory Clock:", self.gpu_min_memory_clock_label)
        gpu_info_layout.addRow("Max GPU Memory Clock:", self.gpu_max_memory_clock_label)
        gpu_info_layout.addRow("GPU Temperature:", self.gpu_temp_label)
        gpu_info_layout.addRow("Min GPU Temperature:", self.gpu_min_temp_label)
        gpu_info_layout.addRow("Max GPU Temperature:", self.gpu_max_temp_label)
        gpu_info_group.setLayout(gpu_info_layout)

        # Add a clickable OC button next to GPU Information
        gpu_info_with_oc_layout = QVBoxLayout()
        gpu_info_with_oc_layout.addWidget(gpu_info_group)
        self.oc_button = QPushButton("Overclock (OC)")
        self.oc_button.clicked.connect(self.open_overclock_window)
        gpu_info_with_oc_layout.addWidget(self.oc_button)
        main_layout.addLayout(gpu_info_with_oc_layout)

        # RAM Information
        ram_info_group = QGroupBox("RAM Information")
        ram_layout = QVBoxLayout()
        for info in self.ram_info:
            if "No Module Installed" not in info:
                layout = QVBoxLayout()
                for line in info.split(", "):
                    label = QLineEdit(line)
                    label.setReadOnly(True)
                    layout.addWidget(label)
                ram_box = QGroupBox()
                ram_box.setLayout(layout)
                ram_layout.addWidget(ram_box)
        ram_info_group.setLayout(ram_layout)
        main_layout.addWidget(ram_info_group)

        refresh_button = QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.update_metrics)
        main_layout.addWidget(refresh_button)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def open_overclock_window(self):
        self.oc_window = OverclockApp()
        self.oc_window.show()

    def create_label(self, text, attribute=None):
        label = QLabel(text, self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if attribute:
            setattr(self, f"{attribute}_label", label)
        return label

    def create_metric_group(self, title, labels):
        group_box = QGroupBox(title)
        layout = QVBoxLayout()
        for label in labels:
            layout.addWidget(self.create_label(f"{label}: Calculating...", attribute=label.lower().replace(" ", "_")))
        group_box.setLayout(layout)
        return group_box

    def create_ram_info_group(self):
        group_box = QGroupBox("RAM Information")
        layout = QVBoxLayout()
        for info in self.ram_info:
            layout.addWidget(QLabel(info, self))
        group_box.setLayout(layout)
        return group_box

    def get_sudo_password(self):
        password, ok = QInputDialog.getText(self, "Sudo Password", "Enter sudo password:", QLineEdit.EchoMode.Password)
        if ok and password:
            return password
        else:
            self.realtime_wattage_label.setText("No sudo password provided")
            return None

    def get_cpu_info(self):
        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True)
            output = result.stdout
            cpu_name = ""
            cpu_codename = ""
            for line in output.split('\n'):
                if 'Model name:' in line:
                    cpu_name = line.split(':')[1].strip()
                if 'CPU family:' in line:
                    cpu_codename = line.split(':')[1].strip()
            return cpu_name, cpu_codename
        except Exception as e:
            return "Unknown", "Unknown"

    def get_gpu_info(self):
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,gpu_bus_id', '--format=csv,noheader'], capture_output=True, text=True)
            output = result.stdout.strip()
            if output:
                name, gpu_type = output.split(',')
                return {'name': name.strip(), 'type': gpu_type.strip()}
            return {'name': 'Unknown', 'type': 'Unknown'}
        except Exception as e:
            return {'name': 'Unknown', 'type': 'Unknown'}

    def get_ram_info(self):
        try:
            result = subprocess.run(['sudo', 'dmidecode', '--type', 'memory'], capture_output=True, text=True)
            output = result.stdout
            ram_info = []
            current_info = {}
            for line in output.split('\n'):
                if line.startswith('Memory Device'):
                    if current_info:
                        ram_info.append(
                            f"Size: {current_info.get('Size', 'Unknown')}, "
                            f"Vendor: {current_info.get('Vendor', 'Unknown')}, "
                            f"Speed: {current_info.get('Speed', 'Unknown')}, "
                            f"Min Voltage: {current_info.get('Configured Voltage', 'Unknown')}, "
                            f"Max Voltage: {current_info.get('Maximum Voltage', 'Unknown')}"
                        )
                    current_info = {}
                elif line.strip().startswith('Size:'):
                    current_info['Size'] = line.split(':')[-1].strip()
                elif line.strip().startswith('Manufacturer:'):
                    current_info['Vendor'] = line.split(':')[-1].strip()
                elif line.strip().startswith('Speed:'):
                    current_info['Speed'] = line.split(':')[-1].strip()
                elif line.strip().startswith('Configured Voltage:'):
                    current_info['Configured Voltage'] = line.split(':')[-1].strip()
                elif line.strip().startswith('Maximum Voltage:'):
                    current_info['Maximum Voltage'] = line.split(':')[-1].strip()

            if current_info:
                ram_info.append(
                    f"Size: {current_info.get('Size', 'Unknown')}, "
                    f"Vendor: {current_info.get('Vendor', 'Unknown')}, "
                    f"Speed: {current_info.get('Speed', 'Unknown')}, "
                    f"Min Voltage: {current_info.get('Configured Voltage', 'Unknown')}, "
                    f"Max Voltage: {current_info.get('Maximum Voltage', 'Unknown')}"
                )
            return ram_info
        except Exception as e:
            return [f"Error: {str(e)}"]

    def get_vcore(self):
        try:
            command = f"echo {self.sudo_password} | sudo -S rdmsr 0x198 -u --bitfield 47:32"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            voltage_raw = int(result.stdout.strip())
            voltage = voltage_raw / 8192  # Convert to volts
            return voltage
        except Exception as e:
            return None

    def get_core_temperatures(self):
        try:
            core_temp_files = sorted(glob.glob('/sys/class/hwmon/hwmon*/temp*_input'), key=lambda x: int(x.split('/')[-1].split('_')[0][4:]))
            core_temperatures = []
            for temp_file in core_temp_files:
                with open(temp_file, 'r') as f:
                    temp = int(f.read().strip()) / 1000  # Convert from millidegree Celsius to degree Celsius
                    core_temperatures.append(temp)
            return core_temperatures
        except Exception as e:
            return None

    def update_metrics(self):
        if not self.sudo_password:
            return

        try:
            # Update the real-time clock
            current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            self.clock_label.setText(current_time)

            # Change the file permission using sudo
            command = f"echo {self.sudo_password} | sudo -S chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj"
            subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)

            # Read the energy value
            with open("/sys/class/powercap/intel-rapl:0/energy_uj", "r") as f:
                energy_uj = int(f.read().strip())

            current_time = time.time()

            if self.last_energy_uj is not None and self.last_time is not None:
                # Calculate the time interval in seconds
                time_interval = current_time - self.last_time
                # Calculate the energy difference in joules
                energy_diff_j = (energy_uj - self.last_energy_uj) / 1e6
                # Calculate the power in watts
                wattage = energy_diff_j / time_interval
                self.wattage_values.append(wattage)

                self.realtime_wattage_label.setText(f"{wattage:.2f} W")
                self.min_wattage_label.setText(f"{min(self.wattage_values):.2f} W")
                self.max_wattage_label.setText(f"{max(self.wattage_values):.2f} W")
                self.avg_wattage_label.setText(f"{sum(self.wattage_values) / len(self.wattage_values):.2f} W")

                # Update max and min wattage
                self.max_wattage = max(self.max_wattage, wattage)
                self.min_wattage = min(self.min_wattage, wattage)

                self.max_wattage_label.setText(f"{self.max_wattage:.2f} W")
                self.min_wattage_label.setText(f"{self.min_wattage:.2f} W")
            else:
                self.realtime_wattage_label.setText("Calculating...")

            # Update the last energy and time values
            self.last_energy_uj = energy_uj
            self.last_time = current_time

            # Read CPU frequencies
            freq_files = glob.glob('/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq')
            frequencies = []
            for freq_file in freq_files:
                with open(freq_file, 'r') as f:
                    freq = int(f.read().strip()) / 1000  # Convert from kHz to MHz
                    frequencies.append(freq)

            if frequencies:
                min_freq = min(frequencies)
                max_freq = max(frequencies)
                avg_freq = sum(frequencies) / len(frequencies)

                self.min_freq_label.setText(f"{min_freq:.2f} MHz")
                self.max_freq_label.setText(f"{max_freq:.2f} MHz")
                self.cpu_freq_label.setText(f"{avg_freq:.2f} MHz")

                self.freq_values = frequencies  # Update the frequency values list

                # Update core frequency label
                self.update_core_freq()

                # Update max and min frequencies
                self.max_freq = max(self.max_freq, max(frequencies))
                self.min_freq = min(self.min_freq, min(frequencies))

                self.max_freq_label.setText(f"{self.max_freq:.2f} MHz")
                self.min_freq_label.setText(f"{self.min_freq:.2f} MHz")

            else:
                self.min_freq_label.setText("Calculating...")
                self.max_freq_label.setText("Calculating...")
                self.cpu_freq_label.setText("Calculating...")

            # Get Vcore value
            vcore = self.get_vcore()
            if vcore is not None:
                self.vcore_values.append(vcore)

                self.realtime_voltage_label.setText(f"{vcore:.3f} V")
                self.min_voltage_label.setText(f"{min(self.vcore_values):.3f} V")
                self.max_voltage_label.setText(f"{max(self.vcore_values):.3f} V")
                self.avg_voltage_label.setText(f"{sum(self.vcore_values) / len(self.vcore_values):.3f} V")

                # Update max and min vcore
                self.max_vcore = max(self.max_vcore, vcore)
                self.min_vcore = min(self.min_vcore, vcore)

                self.max_voltage_label.setText(f"{self.max_vcore:.3f} V")
                self.min_voltage_label.setText(f"{self.min_vcore:.3f} V")
            else:
                self.realtime_voltage_label.setText("Unknown")

            # Get core temperatures
            temperatures = self.get_core_temperatures()
            if temperatures:
                min_temp = min(temperatures)
                max_temp = max(temperatures)
                avg_temp = sum(temperatures) / len(temperatures)

                self.realtime_temperature_label.setText(f"{avg_temp:.2f} °C")
                self.min_temperature_label.setText(f"{min_temp:.2f} °C")
                self.max_temperature_label.setText(f"{max_temp:.2f} °C")
                self.avg_temperature_label.setText(f"{avg_temp:.2f} °C")

                self.temp_values = temperatures  # Update the temperature values list

                # Update core temperature label
                self.update_core_temp()

                # Update max and min temperatures
                self.max_temp = max(self.max_temp, max(temperatures))
                self.min_temp = min(self.min_temp, min(temperatures))

                self.max_temperature_label.setText(f"{self.max_temp:.2f} °C")
                self.min_temperature_label.setText(f"{self.min_temp:.2f} °C")

            else:
                self.realtime_temperature_label.setText("Calculating...")
                self.min_temperature_label.setText("Calculating...")
                self.max_temperature_label.setText("Calculating...")
                self.avg_temperature_label.setText("Calculating...")

            # Update GPU information
            gpu_result = subprocess.run(['nvidia-smi', '--query-gpu=clocks.current.graphics,clocks.current.memory,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True)
            gpu_output = gpu_result.stdout.strip()
            if gpu_output:
                core_clock, memory_clock, gpu_temp = map(float, gpu_output.split(', '))
                self.gpu_core_clock_values.append(core_clock)
                self.gpu_memory_clock_values.append(memory_clock)
                self.gpu_temp_values.append(gpu_temp)

                self.gpu_core_clock_label.setText(f"{core_clock} MHz")
                self.gpu_memory_clock_label.setText(f"{memory_clock} MHz")
                self.gpu_temp_label.setText(f"{gpu_temp} °C")

                self.gpu_min_core_clock_label.setText(f"{min(self.gpu_core_clock_values)} MHz")
                self.gpu_max_core_clock_label.setText(f"{max(self.gpu_core_clock_values)} MHz")
                self.gpu_min_memory_clock_label.setText(f"{min(self.gpu_memory_clock_values)} MHz")
                self.gpu_max_memory_clock_label.setText(f"{max(self.gpu_memory_clock_values)} MHz")
                self.gpu_min_temp_label.setText(f"{min(self.gpu_temp_values)} °C")
                self.gpu_max_temp_label.setText(f"{max(self.gpu_temp_values)} °C")

                self.max_gpu_core_clock = max(self.max_gpu_core_clock, core_clock)
                self.min_gpu_core_clock = min(self.min_gpu_core_clock, core_clock)
                self.max_gpu_memory_clock = max(self.max_gpu_memory_clock, memory_clock)
                self.min_gpu_memory_clock = min(self.min_gpu_memory_clock, memory_clock)
                self.max_gpu_temp = max(self.max_gpu_temp, gpu_temp)
                self.min_gpu_temp = min(self.min_gpu_temp, gpu_temp)
            else:
                self.gpu_core_clock_label.setText("Unknown")
                self.gpu_memory_clock_label.setText("Unknown")
                self.gpu_temp_label.setText("Unknown")
                self.gpu_min_core_clock_label.setText("Unknown")
                self.gpu_max_core_clock_label.setText("Unknown")
                self.gpu_min_memory_clock_label.setText("Unknown")
                self.gpu_max_memory_clock_label.setText("Unknown")
                self.gpu_min_temp_label.setText("Unknown")
                self.gpu_max_temp_label.setText("Unknown")

        except Exception as e:
            self.realtime_wattage_label.setText(f"Error: {str(e)}")
            self.min_wattage_label.setText(f"Error: {str(e)}")
            self.max_wattage_label.setText(f"Error: {str(e)}")
            self.avg_wattage_label.setText(f"Error: {str(e)}")
            self.realtime_voltage_label.setText(f"Error: {str(e)}")
            self.min_voltage_label.setText(f"Error: {str(e)}")
            self.max_voltage_label.setText(f"Error: {str(e)}")
            self.avg_voltage_label.setText(f"Error: {str(e)}")
            self.realtime_temperature_label.setText(f"Error: {str(e)}")
            self.min_temperature_label.setText(f"Error: {str(e)}")
            self.max_temperature_label.setText(f"Error: {str(e)}")
            self.avg_temperature_label.setText(f"Error: {str(e)}")
            self.min_freq_label.setText(f"Error: {str(e)}")
            self.max_freq_label.setText(f"Error: {str(e)}")
            self.cpu_freq_label.setText(f"Error: {str(e)}")
            self.gpu_core_clock_label.setText(f"Error: {str(e)}")
            self.gpu_memory_clock_label.setText(f"Error: {str(e)}")
            self.gpu_temp_label.setText(f"Error: {str(e)}")
            self.gpu_min_core_clock_label.setText(f"Error: {str(e)}")
            self.gpu_max_core_clock_label.setText(f"Error: {str(e)}")
            self.gpu_min_memory_clock_label.setText(f"Error: {str(e)}")
            self.gpu_max_memory_clock_label.setText(f"Error: {str(e)}")
            self.gpu_min_temp_label.setText(f"Error: {str(e)}")
            self.gpu_max_temp_label.setText(f"Error: {str(e)}")

    def update_core_freq(self):
        core_index = self.core_freq_dropdown.currentIndex()
        if core_index < len(self.freq_values):
            self.core_freq_label.setText(f"{self.freq_values[core_index]} MHz")
        else:
            self.core_freq_label.setText("Calculating...")

    def update_core_temp(self):
        core_index = self.core_temp_dropdown.currentIndex()
        if core_index < len(self.temp_values):
            self.core_temp_label.setText(f"{self.temp_values[core_index]} °C")
        else:
            self.core_temp_label.setText("Calculating...")

    def toggle_gpu_info(self):
        if self.gpu_info_group.isVisible():
            self.gpu_info_group.hide()
        else:
            self.gpu_info_group.show()

    def toggle_ram_info(self):
        if self.ram_info_group.isVisible():
            self.ram_info_group.hide()
        else:
            self.ram_info_group.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    monitor = WattageMonitor()
    monitor.show()
    sys.exit(app.exec())
