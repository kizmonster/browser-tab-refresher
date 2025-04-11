#!/usr/bin/env python3
from PySide6.QtWidgets import (QMainWindow, QWidget, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QListWidget, 
                            QListWidgetItem, QMessageBox, QInputDialog, QDialog,
                            QFormLayout, QTabWidget, QStatusBar, QGroupBox,
                            QRadioButton, QButtonGroup, QProgressBar, QApplication,
                            QTimeEdit, QScrollArea)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer, Signal, QObject, Slot
import platform
import sys
import os
import traceback
import datetime
from tab_manager import TabManager

# 작업 상태 전달을 위한 시그널 클래스
class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)

class TabNameDialog(QDialog):
    def __init__(self, tab_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Name Your Tab")
        self.tab_data = tab_data
        self.init_ui()
    
    def init_ui(self):
        layout = QFormLayout()
        
        self.name_input = QLineEdit(self.tab_data["title"])
        layout.addRow("Tab Name:", self.name_input)
        
        # Display tab title and URL as read-only info
        title_label = QLineEdit(self.tab_data["title"])
        title_label.setReadOnly(True)
        layout.addRow("Tab Title:", title_label)
        
        url_label = QLineEdit(self.tab_data["url"])
        url_label.setReadOnly(True)
        layout.addRow("Tab URL:", url_label)
        
        # Button layout
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow("", btn_layout)
        self.setLayout(layout)
    
    def get_name(self):
        return self.name_input.text()

class TimeScheduleDialog(QDialog):
    def __init__(self, current_times=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새로고침 시간 설정")
        self.current_times = current_times or []
        self.times = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 시간 목록
        self.time_list = QListWidget()
        self.update_time_list()
        layout.addWidget(QLabel("설정된 시간:"))
        layout.addWidget(self.time_list)
        
        # 새 시간 추가
        time_input_layout = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self.add_time)
        time_input_layout.addWidget(self.time_edit)
        time_input_layout.addWidget(add_btn)
        layout.addLayout(time_input_layout)
        
        # 삭제 버튼
        remove_btn = QPushButton("선택한 시간 삭제")
        remove_btn.clicked.connect(self.remove_selected_time)
        layout.addWidget(remove_btn)
        
        # 확인/취소 버튼
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def update_time_list(self):
        self.time_list.clear()
        for time_str in sorted(self.times):
            self.time_list.addItem(time_str)
    
    def add_time(self):
        time_str = self.time_edit.time().toString("HH:mm")
        if time_str not in self.times:
            self.times.append(time_str)
            self.update_time_list()
    
    def remove_selected_time(self):
        current_item = self.time_list.currentItem()
        if current_item:
            time_str = current_item.text()
            self.times.remove(time_str)
            self.update_time_list()
    
    def get_times(self):
        return sorted(self.times)

class MainWindow(QMainWindow):
    def __init__(self, tab_manager):
        super().__init__()
        self.setWindowTitle("Browser Tab Manager")
        self.resize(800, 600)
        
        # Set up the tab manager
        self.tab_manager = tab_manager
        
        # Create the central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create tabs for different functions
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        
        # Create the tab identification tab
        self.tab_id_widget = QWidget()
        self.tab_id_layout = QVBoxLayout(self.tab_id_widget)
        self.tab_widget.addTab(self.tab_id_widget, "Tab Identification")
        
        # Create the tab management tab
        self.tab_manage_widget = QWidget()
        self.tab_manage_layout = QVBoxLayout(self.tab_manage_widget)
        self.tab_widget.addTab(self.tab_manage_widget, "Tab Management")
        
        # Create the settings tab
        self.settings_widget = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_widget)
        self.tab_widget.addTab(self.settings_widget, "Settings")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Progress bar in status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # 자동 새로고침 타이머 초기화
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh_tabs)
        self.auto_refresh_enabled = False
        self.auto_refresh_interval = 300  # 기본 5분(300초)
        
        # 마지막 새로고침 시간
        self.last_refresh_time = None
        
        # 단축키 설정
        self.setup_shortcuts()
        
        # Set up UI components
        self.setup_id_tab()
        self.setup_manage_tab()
        self.setup_settings_tab()
        
        # 기본 상태 업데이트
        self.update_status_labels()
        
    def setup_shortcuts(self):
        """단축키 설정"""
        # F5 키로 빠른 리프레시 (등록된 모든 탭)
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.quick_refresh_all)
        
        # Ctrl+R로 빠른 리프레시 (등록된 모든 탭)
        self.refresh_shortcut2 = QShortcut(QKeySequence("Ctrl+R"), self)
        self.refresh_shortcut2.activated.connect(self.quick_refresh_all)

    def setup_id_tab(self):
        """탭 인식 탭 UI 설정"""
        # 브라우저 선택 그룹
        browser_group = QGroupBox("브라우저 선택")
        browser_layout = QVBoxLayout()
        
        self.chrome_radio = QRadioButton("Chrome")
        self.edge_radio = QRadioButton("Edge")
        
        # 현재 설정된 브라우저 타입으로 라디오 버튼 설정
        if self.tab_manager.browser_type == "chrome":
            self.chrome_radio.setChecked(True)
        else:
            self.edge_radio.setChecked(True)
        
        # 라디오 버튼 그룹으로 묶기
        self.browser_button_group = QButtonGroup()
        self.browser_button_group.addButton(self.chrome_radio)
        self.browser_button_group.addButton(self.edge_radio)
        self.browser_button_group.buttonClicked.connect(self.change_browser_type)
        
        browser_layout.addWidget(self.chrome_radio)
        browser_layout.addWidget(self.edge_radio)
        browser_group.setLayout(browser_layout)
        
        # 브라우저 탭 검색 버튼
        self.scan_button = QPushButton("열린 브라우저 탭 스캔")
        self.scan_button.clicked.connect(self.scan_browser_tabs)
        
        # 스캔된 탭 목록
        self.scanned_tabs_label = QLabel("검색된 탭:")
        self.scanned_tabs_list = QListWidget()
        self.scanned_tabs_list.itemDoubleClicked.connect(self.add_tab_from_scan)
        
        # Add to layout
        self.tab_id_layout.addWidget(browser_group)
        self.tab_id_layout.addWidget(self.scan_button)
        self.tab_id_layout.addWidget(self.scanned_tabs_label)
        self.tab_id_layout.addWidget(self.scanned_tabs_list)
        self.tab_id_layout.addStretch(1)
    
    def setup_manage_tab(self):
        """탭 관리 탭 UI 설정"""
        # 스크롤 영역 추가
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll.setWidget(scroll_widget)
        self.tab_manage_layout = QVBoxLayout(scroll_widget)
        
        # Managed tabs list
        self.managed_tabs_label = QLabel("관리 중인 탭:")
        self.managed_tabs_list = QListWidget()
        self.managed_tabs_list.itemDoubleClicked.connect(self.refresh_selected_tab)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.refresh_selected_button = QPushButton("선택한 탭 새로고침")
        self.refresh_selected_button.clicked.connect(self.refresh_selected_tab)
        self.refresh_all_button = QPushButton("모든 탭 새로고침")
        self.refresh_all_button.clicked.connect(lambda: self.refresh_all_tabs(True))
        self.remove_tab_button = QPushButton("선택한 탭 제거")
        self.remove_tab_button.clicked.connect(self.remove_selected_tab)
        
        button_layout.addWidget(self.refresh_selected_button)
        button_layout.addWidget(self.refresh_all_button)
        button_layout.addWidget(self.remove_tab_button)
        
        # 새로고침 설정 그룹
        refresh_settings_group = QGroupBox("새로고침 설정")
        refresh_settings_layout = QVBoxLayout()
        
        # 자동 새로고침 설정
        interval_refresh_layout = QHBoxLayout()
        self.auto_refresh_check = QRadioButton("간격 기반 새로고침")
        self.auto_refresh_check.setChecked(self.auto_refresh_enabled)
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        
        self.auto_refresh_interval_label = QLabel("간격 (초):")
        self.auto_refresh_interval_input = QLineEdit(str(self.auto_refresh_interval))
        self.auto_refresh_interval_input.setFixedWidth(60)
        self.auto_refresh_interval_input.textChanged.connect(self.update_refresh_interval)
        
        interval_refresh_layout.addWidget(self.auto_refresh_check)
        interval_refresh_layout.addWidget(self.auto_refresh_interval_label)
        interval_refresh_layout.addWidget(self.auto_refresh_interval_input)
        interval_refresh_layout.addStretch(1)
        
        # 시간 기반 새로고침 설정
        time_refresh_layout = QHBoxLayout()
        self.time_refresh_check = QRadioButton("시간 기반 새로고침")
        self.time_refresh_check.toggled.connect(self.toggle_time_refresh)
        
        self.schedule_time_button = QPushButton("시간 설정")
        self.schedule_time_button.clicked.connect(self.show_time_schedule_dialog)
        self.schedule_time_button.setEnabled(False)
        
        time_refresh_layout.addWidget(self.time_refresh_check)
        time_refresh_layout.addWidget(self.schedule_time_button)
        time_refresh_layout.addStretch(1)
        
        # 새로고침 모드 그룹으로 묶기
        self.refresh_mode_group = QButtonGroup()
        self.refresh_mode_group.addButton(self.auto_refresh_check)
        self.refresh_mode_group.addButton(self.time_refresh_check)
        
        refresh_settings_layout.addLayout(interval_refresh_layout)
        refresh_settings_layout.addLayout(time_refresh_layout)
        refresh_settings_group.setLayout(refresh_settings_layout)
        
        # 상태 정보
        self.refresh_status_layout = QFormLayout()
        self.next_refresh_label = QLabel("다음 새로고침: 비활성")
        self.last_refresh_label = QLabel("마지막 새로고침: 없음")
        self.scheduled_times_label = QLabel("예약된 시간: 없음")
        
        self.refresh_status_layout.addRow("상태:", self.next_refresh_label)
        self.refresh_status_layout.addRow("", self.last_refresh_label)
        self.refresh_status_layout.addRow("", self.scheduled_times_label)
        
        # Add to layout
        self.tab_manage_layout.addWidget(self.managed_tabs_label)
        self.tab_manage_layout.addWidget(self.managed_tabs_list)
        self.tab_manage_layout.addLayout(button_layout)
        self.tab_manage_layout.addWidget(refresh_settings_group)
        self.tab_manage_layout.addLayout(self.refresh_status_layout)
        self.tab_manage_layout.addStretch(1)
        
        # Add scroll area to tab
        self.tab_manage_widget.setLayout(QVBoxLayout())
        self.tab_manage_widget.layout().addWidget(scroll)
        
        # 현재 관리 중인 탭 표시
        self.update_managed_tabs_list()
        
        # 시간 체크 타이머 설정
        self.time_check_timer = QTimer()
        self.time_check_timer.timeout.connect(self.check_scheduled_refreshes)
        self.time_check_timer.start(30000)  # 30초마다 체크
    
    def setup_settings_tab(self):
        """설정 탭 UI 설정"""
        # 중간에 추가할 수 있음
        pass
    
    def change_browser_type(self, button):
        """브라우저 타입 변경"""
        browser_type = "chrome" if button == self.chrome_radio else "edge"
        if self.tab_manager.set_browser_type(browser_type):
            self.status_bar.showMessage(f"브라우저 타입이 {browser_type.capitalize()}으로 변경되었습니다")
    
    def scan_browser_tabs(self):
        """열린 브라우저 탭 스캔"""
        try:
            self.set_gui_enabled(False)
            self.status_bar.showMessage("브라우저 탭 스캔 중...")
            self.show_progress(30)
            
            # 현재 열린 브라우저 창 가져오기
            browser_windows = self.tab_manager.get_browser_windows()
            self.show_progress(80)
            
            # 리스트 위젯 초기화
            self.scanned_tabs_list.clear()
            
            # 각 탭을 리스트에 추가
            for window in browser_windows:
                item = QListWidgetItem(window["name"])
                item.setData(Qt.UserRole, window)
                self.scanned_tabs_list.addItem(item)
            
            if not browser_windows:
                self.status_bar.showMessage("열린 브라우저 창을 찾을 수 없습니다")
            else:
                self.status_bar.showMessage(f"{len(browser_windows)}개의 브라우저 창을 찾았습니다")
        except Exception as e:
            self.show_error(f"브라우저 탭 스캔 오류: {str(e)}")
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
    
    def add_tab_from_scan(self, item):
        """스캔된 탭 목록에서 관리 탭에 추가"""
        try:
            window = item.data(Qt.UserRole)
            window_id = window["id"]
            window_name = window["name"]
            
            # 탭 매니저에 추가
            if self.tab_manager.add_tab(window_id, window_name):
                self.status_bar.showMessage(f"탭 '{window_name}' 추가됨")
                self.update_managed_tabs_list()
            else:
                self.status_bar.showMessage(f"탭 '{window_name}'은(는) 이미 관리 중입니다")
        except Exception as e:
            self.show_error(f"탭 추가 오류: {str(e)}")
    
    def update_managed_tabs_list(self):
        """관리 중인 탭 목록 업데이트"""
        self.managed_tabs_list.clear()
        
        for tab in self.tab_manager.managed_tabs:
            item = QListWidgetItem(tab["name"])
            item.setData(Qt.UserRole, tab)
            self.managed_tabs_list.addItem(item)
    
    def refresh_selected_tab(self):
        """선택한 탭 새로고침"""
        selected_items = self.managed_tabs_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("새로고침할 탭을 선택하세요")
            return
        
        item = selected_items[0]
        tab = item.data(Qt.UserRole)
        
        try:
            self.set_gui_enabled(False)
            self.status_bar.showMessage(f"탭 '{tab['name']}' 새로고침 중...")
            self.show_progress(50)
            
            success = self.tab_manager.refresh_tab(tab["id"])
            
            if success:
                self.status_bar.showMessage(f"탭 '{tab['name']}' 새로고침 완료")
                self.update_last_refresh_time()
            else:
                self.status_bar.showMessage(f"탭 '{tab['name']}' 새로고침 실패")
        except Exception as e:
            self.show_error(f"탭 새로고침 오류: {str(e)}")
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
    
    def remove_selected_tab(self):
        """선택한 탭 제거"""
        selected_items = self.managed_tabs_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("제거할 탭을 선택하세요")
            return
        
        item = selected_items[0]
        tab = item.data(Qt.UserRole)
        
        confirm = QMessageBox.question(
            self, "탭 제거 확인", 
            f"'{tab['name']}' 탭을 관리 목록에서 제거하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            if self.tab_manager.remove_tab(tab["id"]):
                self.status_bar.showMessage(f"탭 '{tab['name']}' 제거됨")
                self.update_managed_tabs_list()
    
    def quick_refresh_all(self):
        """단축키로 모든 관리 탭 빠르게 새로고침 (대화상자 없음)"""
        if not self.tab_manager.managed_tabs:
            self.status_bar.showMessage("새로고침할 탭이 없습니다")
            return
        
        self.status_bar.showMessage("모든 탭 새로고침 중...")
        results = self.tab_manager.refresh_all_tabs()
        success_count = sum(1 for r in results if r["success"])
        
        if success_count == len(results):
            self.status_bar.showMessage(f"모든 {success_count}개 탭 새로고침 완료")
        else:
            failed_tabs = [r["name"] for r in results if not r["success"]]
            self.status_bar.showMessage(f"{len(results)}개 중 {success_count}개 탭 새로고침 완료")
        
        self.update_last_refresh_time()
    
    def refresh_all_tabs(self, show_result=True):
        """모든 관리 탭 새로고침"""
        try:
            self.set_gui_enabled(False)
            
            if not self.tab_manager.managed_tabs:
                if show_result:
                    QMessageBox.warning(self, "탭 없음", "새로고침할 탭이 없습니다.")
                self.status_bar.showMessage("새로고침할 탭이 없습니다")
                return
            
            self.status_bar.showMessage("모든 탭 새로고침 중...")
            self.show_progress(30)
            
            results = self.tab_manager.refresh_all_tabs()
            self.show_progress(80)
            
            success_count = sum(1 for r in results if r["success"])
            
            if success_count == len(results):
                self.status_bar.showMessage(f"모든 {success_count}개 탭 새로고침 완료")
            else:
                failed_tabs = [r["name"] for r in results if not r["success"]]
                if show_result:
                    QMessageBox.warning(self, "새로고침 결과", 
                                    f"{len(results)}개 중 {success_count}개 탭 새로고침 완료.\n\n"
                                    f"실패: {', '.join(failed_tabs)}")
                self.status_bar.showMessage(f"{len(results)}개 중 {success_count}개 탭 새로고침 완료")
            
            self.update_last_refresh_time()
        except Exception as e:
            self.show_error(f"탭 새로고침 오류: {str(e)}")
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
    
    def toggle_auto_refresh(self, checked):
        """자동 새로고침 토글"""
        self.auto_refresh_enabled = checked
        
        if checked:
            # 새로고침 간격 검증
            try:
                interval = int(self.auto_refresh_interval_input.text())
                if interval < 5:
                    interval = 5
                    self.auto_refresh_interval_input.setText("5")
                
                self.auto_refresh_interval = interval
                self.refresh_timer.start(interval * 1000)  # 밀리초로 변환
                self.status_bar.showMessage(f"자동 새로고침 활성화 ({interval}초 간격)")
            except ValueError:
                self.auto_refresh_interval_input.setText(str(self.auto_refresh_interval))
                self.refresh_timer.start(self.auto_refresh_interval * 1000)
                self.status_bar.showMessage(f"자동 새로고침 활성화 ({self.auto_refresh_interval}초 간격)")
        else:
            self.refresh_timer.stop()
            self.status_bar.showMessage("자동 새로고침 비활성화")
        
        self.update_status_labels()
    
    def update_refresh_interval(self):
        """새로고침 간격 업데이트"""
        if not self.auto_refresh_enabled:
            return
            
        try:
            interval = int(self.auto_refresh_interval_input.text())
            if interval < 5:
                return
                
            self.auto_refresh_interval = interval
            self.refresh_timer.start(interval * 1000)  # 밀리초로 변환
            self.update_status_labels()
        except ValueError:
            pass
    
    def auto_refresh_tabs(self):
        """자동 새로고침 수행"""
        if self.auto_refresh_enabled:
            self.refresh_all_tabs(show_result=False)
            self.update_status_labels()
    
    def update_last_refresh_time(self):
        """마지막 새로고침 시간 업데이트"""
        self.last_refresh_time = datetime.datetime.now()
        self.update_status_labels()
    
    def update_status_labels(self):
        """상태 레이블 업데이트"""
        super().update_status_labels()  # 기존 상태 업데이트
        
        # 예약된 시간 표시
        selected_items = self.managed_tabs_list.selectedItems()
        if selected_items:
            window_id = selected_items[0].data(Qt.UserRole)
            times = self.tab_manager.get_scheduled_refreshes(window_id)
            if times:
                self.scheduled_times_label.setText(f"예약된 시간: {', '.join(sorted(times))}")
            else:
                self.scheduled_times_label.setText("예약된 시간: 없음")
        else:
            self.scheduled_times_label.setText("예약된 시간: 탭을 선택하세요")
    
    def show_progress(self, value):
        """진행 표시줄 표시"""
        self.progress_bar.show()
        self.progress_bar.setValue(value)
        QApplication.processEvents()
    
    def hide_progress(self):
        """진행 표시줄 숨김"""
        self.progress_bar.hide()
        QApplication.processEvents()
    
    def set_gui_enabled(self, enabled):
        """GUI 활성화/비활성화"""
        self.tab_widget.setEnabled(enabled)
        QApplication.processEvents()
    
    def show_error(self, message):
        """오류 메시지 표시"""
        self.status_bar.showMessage(f"오류: {message}")
        QMessageBox.critical(self, "오류", message)
        print(f"오류: {message}")
        traceback.print_exc()
    
    def closeEvent(self, event):
        """프로그램 종료 시 처리"""
        try:
            self.refresh_timer.stop()  # 타이머 중지
            # TabManager에 close 메서드가 없음
        except:
            pass
        event.accept()
    
    def toggle_time_refresh(self, checked):
        """시간 기반 새로고침 토글"""
        self.schedule_time_button.setEnabled(checked)
        if checked:
            self.show_time_schedule_dialog()
        else:
            # 선택된 탭의 예약된 시간 모두 제거
            selected_items = self.managed_tabs_list.selectedItems()
            for item in selected_items:
                window_id = item.data(Qt.UserRole)
                self.tab_manager.remove_scheduled_refresh(window_id)
            self.update_status_labels()
    
    def show_time_schedule_dialog(self):
        """시간 설정 다이얼로그 표시"""
        selected_items = self.managed_tabs_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "알림", "시간을 설정할 탭을 선택해주세요.")
            self.time_refresh_check.setChecked(False)
            return
        
        window_id = selected_items[0].data(Qt.UserRole)
        current_times = self.tab_manager.get_scheduled_refreshes(window_id)
        
        dialog = TimeScheduleDialog(current_times, self)
        if dialog.exec_():
            times = dialog.get_times()
            if times:
                self.tab_manager.add_scheduled_refresh(window_id, times)
                self.update_status_labels()
            else:
                self.tab_manager.remove_scheduled_refresh(window_id)
                self.time_refresh_check.setChecked(False)
    
    def check_scheduled_refreshes(self):
        """예약된 새로고침 확인 및 실행"""
        refreshed_tabs = self.tab_manager.check_scheduled_refreshes()
        if refreshed_tabs:
            self.update_last_refresh_time()
            self.update_status_labels() 