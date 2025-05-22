#!/usr/bin/env python3
from PySide6.QtWidgets import (QMainWindow, QWidget, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QListWidget, 
                            QListWidgetItem, QMessageBox, QInputDialog, QDialog,
                            QFormLayout, QTabWidget, QStatusBar, QGroupBox,
                            QRadioButton, QButtonGroup, QProgressBar, QApplication,
                            QTimeEdit, QScrollArea, QCheckBox)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer, Signal, QObject, Slot, QTime
import platform
import sys
import os
import time
import json
import traceback
from datetime import datetime, timedelta  # datetime과 timedelta 클래스를 직접 import
import threading
import random
import logging
from tab_manager import TabManager
from time_schedule_dialog import TimeScheduleDialog

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

class MainWindow(QMainWindow):
    def __init__(self, tab_manager):
        super().__init__()
        self.setWindowTitle("브라우저 탭 새로고침")
        self.resize(800, 600)
        
        self.tab_manager = tab_manager
        
        # 새로고침 관련 상태 변수
        self.auto_refresh_interval = 30  # 기본값
        self.auto_refresh_enabled = False
        self.last_refresh_time = None
        self.time_check_active = False  # 시간 체크 타이머 활성화 상태
        
        # 생성자에 현재 작업 디렉토리 로깅
        print(f"현재 작업 디렉토리: {os.getcwd()}")
        
        # GUI 초기화
        self.init_ui()
        
        # 타이머 설정
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh_tabs)
        
        # 시간 기반 새로고침을 위한 타이머
        self.time_check_timer = QTimer(self)
        self.time_check_timer.timeout.connect(self.check_scheduled_refreshes)
        
        # 한 번 새로고침 실행
        QTimer.singleShot(1000, self.update_time_check_timer)
        
        # 최근 설정 시간과 리프레시 방지를 위한 플래그
        self.last_schedule_set_time = None
    
    def init_ui(self):
        """UI 초기화"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 탭 위젯 생성
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 관리 탭 생성
        manage_tab = QWidget()
        manage_layout = QVBoxLayout(manage_tab)
        
        # 브라우저 선택 그룹
        browser_group = QGroupBox("브라우저 선택")
        browser_layout = QHBoxLayout()
        self.chrome_radio = QRadioButton("Chrome")
        self.chrome_radio.setChecked(True)
        self.firefox_radio = QRadioButton("Firefox")
        self.edge_radio = QRadioButton("Edge")
        self.safari_radio = QRadioButton("Safari")
        
        # 브라우저 선택 버튼 그룹 생성
        browser_button_group = QButtonGroup(self)
        browser_button_group.addButton(self.chrome_radio)
        browser_button_group.addButton(self.firefox_radio)
        browser_button_group.addButton(self.edge_radio)
        browser_button_group.addButton(self.safari_radio)
        browser_button_group.buttonClicked.connect(self.change_browser_type)
        
        browser_layout.addWidget(self.chrome_radio)
        browser_layout.addWidget(self.firefox_radio)
        browser_layout.addWidget(self.edge_radio)
        browser_layout.addWidget(self.safari_radio)
        browser_group.setLayout(browser_layout)
        manage_layout.addWidget(browser_group, stretch=1)
        
        # 탭 관리 영역
        tabs_group = QGroupBox("탭 관리")
        tabs_layout = QVBoxLayout()
        
        # 스캔된 탭 목록
        scan_label = QLabel("스캔된 탭:")
        self.scanned_tabs_list = QListWidget()
        self.scanned_tabs_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.scanned_tabs_list.itemDoubleClicked.connect(self.add_tab_from_scan)
        self.scanned_tabs_list.setMinimumHeight(200)  # 최소 높이 증가
        
        # 탭 관리 버튼
        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("탭 스캔")
        scan_btn.clicked.connect(self.scan_browser_tabs)
        add_btn = QPushButton("선택 탭 추가")
        add_btn.clicked.connect(self.add_selected_tabs)
        remove_btn = QPushButton("선택 탭 제거")
        remove_btn.clicked.connect(self.remove_selected_tab)
        
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        
        tabs_layout.addWidget(scan_label)
        tabs_layout.addWidget(self.scanned_tabs_list)
        tabs_layout.addLayout(btn_layout)
        
        # 관리 중인 탭 목록
        manage_label = QLabel("관리 중인 탭:")
        self.managed_tabs_list = QListWidget()
        self.managed_tabs_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.managed_tabs_list.setMinimumHeight(200)  # 최소 높이 증가
        
        tabs_layout.addWidget(manage_label)
        tabs_layout.addWidget(self.managed_tabs_list)
        
        # 탭 관리 영역에 더 많은 공간 할당
        tabs_group.setLayout(tabs_layout)
        manage_layout.addWidget(tabs_group, stretch=4)  # stretch 값 증가
        
        # 새로고침 설정 그룹
        refresh_group = QGroupBox("새로고침 설정")
        refresh_layout = QVBoxLayout()
        
        # 자동 새로고침 설정
        auto_refresh_layout = QHBoxLayout()
        self.auto_refresh_check = QCheckBox("자동 새로고침")
        self.auto_refresh_check.stateChanged.connect(self.toggle_auto_refresh)
        self.interval_edit = QLineEdit()
        self.interval_edit.setPlaceholderText("간격(초)")
        self.interval_edit.setText(str(self.auto_refresh_interval))
        self.interval_edit.textChanged.connect(self.update_refresh_interval)
        auto_refresh_layout.addWidget(self.auto_refresh_check)
        auto_refresh_layout.addWidget(self.interval_edit)
        refresh_layout.addLayout(auto_refresh_layout)
        
        # 수동 새로고침 버튼 추가
        manual_refresh_layout = QHBoxLayout()
        refresh_selected_btn = QPushButton("선택한 탭 새로고침")
        refresh_selected_btn.clicked.connect(self.refresh_selected_tabs)
        refresh_all_btn = QPushButton("모든 탭 새로고침")
        refresh_all_btn.clicked.connect(self.refresh_all_tabs)
        manual_refresh_layout.addWidget(refresh_selected_btn)
        manual_refresh_layout.addWidget(refresh_all_btn)
        refresh_layout.addLayout(manual_refresh_layout)
        
        # 시간 기반 새로고침 설정
        time_refresh_layout = QHBoxLayout()
        self.time_refresh_check = QCheckBox("시간 기반 새로고침")
        self.time_refresh_check.stateChanged.connect(self.toggle_time_refresh)
        self.time_set_btn = QPushButton("시간 설정")
        self.time_set_btn.clicked.connect(self.show_time_schedule_dialog)
        time_refresh_layout.addWidget(self.time_refresh_check)
        time_refresh_layout.addWidget(self.time_set_btn)
        refresh_layout.addLayout(time_refresh_layout)
        
        refresh_group.setLayout(refresh_layout)
        manage_layout.addWidget(refresh_group, stretch=1)
        
        # 상태 정보 그룹
        status_group = QGroupBox("상태 정보")
        status_layout = QVBoxLayout()
        
        self.next_refresh_label = QLabel("다음 새로고침: 비활성")
        self.last_refresh_label = QLabel("마지막 새로고침: 없음")
        self.scheduled_times_label = QLabel("예약된 시간: 없음")
        self.selected_tab_info = QLabel("선택된 탭: 없음")
        
        status_layout.addWidget(self.next_refresh_label)
        status_layout.addWidget(self.last_refresh_label)
        status_layout.addWidget(self.scheduled_times_label)
        status_layout.addWidget(self.selected_tab_info)
        
        status_group.setLayout(status_layout)
        manage_layout.addWidget(status_group, stretch=1)
        
        tab_widget.addTab(manage_tab, "탭 관리")
        
        # 상태바 설정
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("준비")
        
        # 진행바 설정
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.load_tabs()
        self.update_status_labels()
        
        # 탭 리스트 선택 이벤트 연결
        self.managed_tabs_list.itemSelectionChanged.connect(self.managed_tabs_selection_changed)
    
    def load_tabs(self):
        """저장된 탭 정보 로드"""
        self.update_managed_tabs_list()
    
    def scan_browser_tabs(self):
        """열린 브라우저 탭 스캔"""
        try:
            self.set_gui_enabled(False)
            self.status_bar.showMessage("브라우저 탭 스캔 중...")
            self.show_progress(30)
            
            # 현재 선택된 브라우저 타입 가져오기
            browser_type = self.get_current_browser_type()
            
            # 브라우저 타입 설정
            self.tab_manager.set_browser_type(browser_type)
            
            # 현재 열린 브라우저 창 가져오기
            browser_windows = self.tab_manager.get_browser_windows()
            self.show_progress(80)
            
            # 리스트 위젯 초기화
            self.scanned_tabs_list.clear()
            
            # 탭 수 카운팅을 위한 변수
            total_tabs = 0
            
            # 각 탭을 리스트에 추가
            for window in browser_windows:
                # Safari ID 형식 확인 및 정상화
                if browser_type == "safari":
                    # 로깅을 추가하여 디버깅
                    print(f"Safari 탭 정보: {window}")
                    
                    # ID가 있는지 확인하고 정수로 변환 가능한지 확인
                    if "id" in window:
                        try:
                            window["id"] = int(window["id"])
                        except (ValueError, TypeError):
                            # 변환할 수 없으면 해시값 사용
                            window["id"] = hash(str(window.get("title", ""))) % 100000
                            print(f"Safari 탭 ID 변환됨: {window['id']}")
                
                item = QListWidgetItem(window["name"])
                item.setData(Qt.UserRole, window)
                self.scanned_tabs_list.addItem(item)
                total_tabs += 1
            
            if not browser_windows:
                self.status_bar.showMessage("열린 브라우저 창을 찾을 수 없습니다")
            else:
                self.status_bar.showMessage(f"{len(browser_windows)}개의 브라우저 창에서 {total_tabs}개의 탭을 찾았습니다")
        except Exception as e:
            self.show_error(f"브라우저 탭 스캔 오류: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
    
    def add_tab_from_scan(self, item):
        """스캔된 탭 목록에서 관리 탭에 추가"""
        try:
            window = item.data(Qt.UserRole)
            window_id = window["id"]
            window_name = window["name"]
            
            # 현재 선택된 브라우저 타입 가져오기
            browser_type = self.get_current_browser_type()
            
            # ID 형식 로깅 (디버깅용)
            print(f"추가 시도 중인 탭: ID={window_id}, 타입={type(window_id)}, 이름={window_name}, 브라우저={browser_type}")
            
            # Safari ID 유효성 확인
            if browser_type == "safari" and not isinstance(window_id, int):
                try:
                    window_id = int(window_id)
                except (ValueError, TypeError):
                    window_id = hash(str(window_name)) % 100000
                    print(f"Safari 탭 ID 해시로 변환됨: {window_id}")
            
            # 탭 매니저에 추가 (브라우저 타입 포함)
            if self.tab_manager.add_tab(window_id, window_name, browser_type):
                self.status_bar.showMessage(f"탭 '{window_name}' 추가됨 (브라우저: {browser_type})")
                self.update_managed_tabs_list()
            else:
                self.status_bar.showMessage(f"탭 '{window_name}'은(는) 이미 관리 중입니다")
        except Exception as e:
            self.show_error(f"탭 추가 오류: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def add_selected_tabs(self):
        """선택한 스캔 탭들을 관리 목록에 추가"""
        selected_items = self.scanned_tabs_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("추가할 탭을 선택하세요")
            return
        
        # 현재 선택된 브라우저 타입 가져오기
        browser_type = self.get_current_browser_type()
        
        added_count = 0
        failed_count = 0
        for item in selected_items:
            try:
                window = item.data(Qt.UserRole)
                window_id = window["id"]
                window_name = window["name"]
                
                # Safari ID 유효성 확인
                if browser_type == "safari" and not isinstance(window_id, int):
                    try:
                        window_id = int(window_id)
                    except (ValueError, TypeError):
                        window_id = hash(str(window_name)) % 100000
                
                if self.tab_manager.add_tab(window_id, window_name, browser_type):
                    added_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                print(f"탭 추가 중 오류: {e}")
                import traceback
                traceback.print_exc()
        
        if added_count > 0:
            self.status_bar.showMessage(f"{added_count}개의 탭이 추가되었습니다 (브라우저: {browser_type})")
            self.update_managed_tabs_list()
        else:
            self.status_bar.showMessage("선택한 탭이 이미 모두 관리 중이거나 추가할 수 없습니다")
        
        if failed_count > 0:
            print(f"{failed_count}개의 탭을 추가하지 못했습니다.")
    
    def change_browser_type(self, button):
        """브라우저 타입 변경"""
        browser_type = "chrome"
        if button == self.firefox_radio:
            browser_type = "firefox"
        elif button == self.edge_radio:
            browser_type = "edge"
        elif button == self.safari_radio:
            browser_type = "safari"
            
        if self.tab_manager.set_browser_type(browser_type):
            self.status_bar.showMessage(f"브라우저 타입이 {browser_type.capitalize()}로 변경되었습니다")
            self.scanned_tabs_list.clear()  # 스캔된 탭 목록 초기화
    
    def update_managed_tabs_list(self):
        """관리 중인 탭 목록 업데이트"""
        self.managed_tabs_list.clear()
        for tab in self.tab_manager.managed_tabs:
            # 브라우저 타입 정보를 포함한 표시
            browser_type = tab.get('browser_type', '알 수 없음')
            display_name = f"{tab['name']} [{browser_type}]"
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, tab['id'])
            # 브라우저 타입에 따른 아이콘 또는 색상 설정
            self.managed_tabs_list.addItem(item)
    
    def toggle_auto_refresh(self, checked):
        """자동 새로고침 토글"""
        self.auto_refresh_enabled = checked
        if checked:
            try:
                interval = int(self.interval_edit.text())
                if interval < 5:
                    interval = 5
                    self.interval_edit.setText("5")
                self.auto_refresh_interval = interval
                self.refresh_timer.start(interval * 1000)
                self.status_bar.showMessage(f"자동 새로고침 활성화 ({interval}초 간격)")
            except ValueError:
                self.interval_edit.setText(str(self.auto_refresh_interval))
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
            interval = int(self.interval_edit.text())
            if interval < 5:
                return
            self.auto_refresh_interval = interval
            self.refresh_timer.start(interval * 1000)
            self.update_status_labels()
        except ValueError:
            pass
    
    def auto_refresh_tabs(self):
        """자동 새로고침 실행"""
        if self.auto_refresh_enabled:
            try:
                # 자동 새로고침 상태 표시
                self.status_bar.showMessage("자동 새로고침 실행 중...")
                
                # 자동 새로고침 시 선택된 탭 상관없이 모든 탭 새로고침 실행
                self.refresh_all_tabs(show_result=True)
            except Exception as e:
                self.status_bar.showMessage(f"자동 새로고침 오류: {str(e)}")
                logging.error(f"자동 새로고침 오류: {str(e)}")
    
    def refresh_all_tabs(self, show_result=True):
        """모든 탭 새로고침"""
        try:
            self.set_gui_enabled(False)
            if not self.tab_manager.managed_tabs:
                self.status_bar.showMessage("새로고침할 탭이 없습니다")
                return
            
            self.status_bar.showMessage("모든 탭 새로고침 중...")
            self.show_progress(50)
            
            results = self.tab_manager.refresh_all_tabs()
            success_count = sum(1 for r in results if r["success"])
            
            if success_count == len(results):
                self.status_bar.showMessage(f"모든 탭 새로고침 완료 ({success_count}개)")
            else:
                self.status_bar.showMessage(f"{len(results)}개 중 {success_count}개 탭 새로고침 완료")
            
            self.update_last_refresh_time()
        except Exception as e:
            self.show_error(f"새로고침 오류: {str(e)}")
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
            
    def refresh_selected_tabs(self, show_result=True):
        """선택된 탭만 새로고침 - 병렬 처리 방식"""
        try:
            selected_items = self.managed_tabs_list.selectedItems()
            if not selected_items:
                self.status_bar.showMessage("새로고침할 탭을 선택하세요")
                return
            
            self.set_gui_enabled(False)
            self.status_bar.showMessage(f"선택한 {len(selected_items)}개 탭 병렬 새로고침 중...")
            self.show_progress(50)
            
            # 병렬 처리를 위한 준비
            tab_ids = []
            for item in selected_items:
                tab_id = item.data(Qt.UserRole)
                tab_ids.append(tab_id)
            
            # 병렬 처리 실행
            results = self.tab_manager.refresh_tabs_parallel(tab_ids)
            
            if show_result:
                success_count = sum(1 for r in results if r["success"])
                if success_count == len(results):
                    self.status_bar.showMessage(f"선택한 {len(results)}개 탭 모두 병렬 새로고침 완료")
                else:
                    self.status_bar.showMessage(f"{len(results)}개 중 {success_count}개 탭 병렬 새로고침 완료")
            
            # 마지막 새로고침 시간 업데이트
            self.update_last_refresh_time()
            
        except Exception as e:
            self.show_error(f"새로고침 오류: {str(e)}")
        finally:
            self.hide_progress()
            self.set_gui_enabled(True)
    
    def quick_refresh_all(self):
        """빠른 새로고침 실행 - command line 실행에서 호출됨 (병렬 처리)"""
        # 시간 기반 새로고침이나 자동 새로고침에는 항상 모든 탭 새로고침
        self.refresh_all_tabs(show_result=True)
    
    def toggle_time_refresh(self, checked):
        """시간 기반 새로고침 토글"""
        if checked:
            self.show_time_schedule_dialog()
        else:
            # 선택된 탭들만 예약 시간 제거
            selected_items = self.managed_tabs_list.selectedItems()
            if selected_items:
                for item in selected_items:
                    tab_id = item.data(Qt.UserRole)
                    self.tab_manager.remove_scheduled_refresh(tab_id)
                self.status_bar.showMessage("선택된 탭의 예약된 새로고침이 취소되었습니다.")
            
            self.update_status_labels()
            # 시간 체크 타이머 상태 업데이트
            self.update_time_check_timer()
    
    def show_time_schedule_dialog(self):
        """선택된 탭에 대한 시간 예약 대화상자 표시"""
        selected_tab_ids = self.get_selected_tab_ids()
        if not selected_tab_ids:
            QMessageBox.warning(self, "선택 오류", "하나 이상의 탭을 선택해주세요.")
            return

        # 시간 스케줄 대화상자 생성
        dialog = TimeScheduleDialog(parent=self)
        
        # 선택된 탭의 기존 일정이 있으면 대화상자에 표시
        for tab_id in selected_tab_ids:
            scheduled_times = self.tab_manager.get_scheduled_refreshes(tab_id)
            # 문자열 타입인 시간만 추가
            for time_str in scheduled_times:
                if isinstance(time_str, str):
                    # 반복 시간은 '*' 접두사 제거하고 추가
                    if time_str.startswith('*'):
                        dialog.add_time(time_str[1:], repeating=True)
                    else:
                        dialog.add_time(time_str, repeating=False)
        
        # 대화상자 실행
        if dialog.exec_() == QDialog.Accepted:
            # 사용자가 확인을 눌렀을 때
            times_data = dialog.get_times_with_repeat()
            
            # 선택된 모든 탭에 대해 새로운 일정 설정
            for tab_id in selected_tab_ids:
                # 기존 일정 초기화
                self.tab_manager.clear_refresh_times(tab_id)
                
                # 새 일정 추가
                for time_data in times_data:
                    time_str = time_data['time']
                    is_repeating = time_data.get('repeating', False)
                    
                    # 반복 시간인 경우 별표 추가
                    if is_repeating:
                        time_str = f"*{time_str}"
                        
                    self.tab_manager.add_refresh_time(tab_id, time_str)
            
            # 상태 레이블 업데이트
            self.update_status_labels()
            
            # 시간 체크 타이머 상태 업데이트
            self.update_time_check_timer()
    
    def check_scheduled_refreshes(self):
        """
        현재 시간에 예약된 새로고침이 있는지 확인하고 있으면 실행
        """
        try:
            # 선택된 탭과 관계없이 모든 예약된 탭을 새로고침
            refreshed_tabs = self.tab_manager.check_scheduled_refreshes()
            
            if refreshed_tabs:
                # 새로고침 된 탭이 있으면 상태 표시줄 업데이트
                refreshed_tabs_str = ", ".join([f"{tab_id}" for tab_id in refreshed_tabs])
                self.status_bar.showMessage(f"예약된 새로고침 완료: 탭 {refreshed_tabs_str}", 5000)
                # 상태 레이블 업데이트
                self.update_status_labels()
                # 마지막 새로고침 시간 업데이트
                self.update_last_refresh_time()
                # 시간 체크 타이머 상태 업데이트 - 새로고침 후 예약된 시간이 변경됐을 수 있음
                self.update_time_check_timer()
        except Exception as e:
            self.status_bar.showMessage(f"예약된 새로고침 오류: {str(e)}", 3000)
            logging.error(f"예약된 새로고침 오류: {str(e)}")
    
    def update_time_check_timer(self):
        """
        시간 체크 타이머의 활성화 상태를 업데이트
        예약된 시간이 있을 때만 타이머 활성화
        """
        # 모든 탭의 예약된 시간 확인
        has_scheduled_times = False
        
        # 스케줄 확인
        for tab in self.tab_manager.managed_tabs:
            tab_id = tab["id"]
            times = self.tab_manager.get_scheduled_refreshes(tab_id)
            if times and len(times) > 0:
                has_scheduled_times = True
                break
        
        # 예약된 시간이 있으면 타이머 시작, 없으면 중지
        if has_scheduled_times and not self.time_check_timer.isActive():
            print("예약된 시간이 있어 시간 체크 타이머를 시작합니다.")
            self.time_check_timer.start(500)  # 0.5초마다 체크하여 정확도 향상
            self.time_check_active = True
        elif not has_scheduled_times and self.time_check_timer.isActive():
            print("예약된 시간이 없어 시간 체크 타이머를 중지합니다.")
            self.time_check_timer.stop()
            self.time_check_active = False
    
    def update_last_refresh_time(self):
        """마지막 새로고침 시간 업데이트"""
        self.last_refresh_time = datetime.now()
        self.update_status_labels()
    
    def update_status_labels(self):
        """상태 레이블 업데이트"""
        if self.auto_refresh_enabled:
            next_refresh = datetime.now() + timedelta(seconds=self.auto_refresh_interval)
            self.next_refresh_label.setText(f"다음 새로고침: {next_refresh.strftime('%H:%M:%S')}")
        else:
            self.next_refresh_label.setText("다음 새로고침: 비활성")
        
        if self.last_refresh_time:
            self.last_refresh_label.setText(f"마지막 새로고침: {self.last_refresh_time.strftime('%H:%M:%S')}")
        else:
            self.last_refresh_label.setText("마지막 새로고침: 없음")
        
        selected_items = self.managed_tabs_list.selectedItems()
        if selected_items:
            tab_info = []
            scheduled_times = set()
            
            for item in selected_items:
                tab_id = item.data(Qt.UserRole)
                tab_name = item.text()
                tab_info.append(tab_name)
                times = self.tab_manager.get_scheduled_refreshes(tab_id)
                # 문자열인 시간만 추가
                for t in times:
                    if isinstance(t, str):
                        scheduled_times.add(t)
            
            self.selected_tab_info.setText(f"선택된 탭: {', '.join(tab_info)}")
            
            if scheduled_times:
                # 일반 시간과 반복 시간 분리
                regular_times = []
                repeating_times = []
                
                for t in scheduled_times:
                    if t.startswith("*"):
                        # 반복 시간은 "* HH:MM:SS (매일)" 형식으로 표시
                        repeating_times.append(f"* {t[1:]} (매일)")
                    else:
                        regular_times.append(t)
                
                # 각각 정렬
                regular_times.sort()
                repeating_times.sort()
                
                # 시간 목록 표시 (일반 시간 먼저, 그 다음 반복 시간)
                all_times_display = regular_times + repeating_times
                self.scheduled_times_label.setText(f"예약된 시간: {', '.join(all_times_display)}")
                
                # 시간 체크 플래그 업데이트
                if not self.time_check_active:
                    self.update_time_check_timer()
            else:
                self.scheduled_times_label.setText("예약된 시간: 없음")
        else:
            self.selected_tab_info.setText("선택된 탭: 없음")
            self.scheduled_times_label.setText("예약된 시간: 탭을 선택하세요")
        
        # 모든 탭에 대한 예약 시간 갱신 (타이머 업데이트용)
        all_scheduled_times = []
        repeating_count = 0
        one_time_count = 0
        
        for tab in self.tab_manager.managed_tabs:
            tab_id = tab["id"]
            times = self.tab_manager.get_scheduled_refreshes(tab_id)
            if times:
                for t in times:
                    all_scheduled_times.append(t)
                    if isinstance(t, str) and t.startswith("*"):
                        repeating_count += 1
                    else:
                        one_time_count += 1
        
        # 상태바에 전체 예약 시간 표시 (디버그용)
        if all_scheduled_times:
            status_msg = f"전체 {len(self.tab_manager.managed_tabs)}개 탭, {len(all_scheduled_times)}개 예약됨"
            if repeating_count > 0:
                status_msg += f" (일회성: {one_time_count}개, 반복: {repeating_count}개)"
            self.status_bar.showMessage(status_msg, 3000)
    
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
        self.setEnabled(enabled)
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
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()
            if self.time_check_timer.isActive():
                self.time_check_timer.stop()
        except:
            pass
        event.accept()
    
    def remove_selected_tab(self):
        """선택한 탭 제거"""
        if not hasattr(self, 'managed_tabs_list') or self.managed_tabs_list is None:
            self.status_bar.showMessage("탭 목록이 초기화되지 않았습니다")
            return
            
        selected_items = self.managed_tabs_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("제거할 탭을 선택하세요")
            return
        
        removed_any = False
        for item in selected_items:
            tab_id = item.data(Qt.UserRole)
            tab_name = item.text()
            
            confirm = QMessageBox.question(
                self, "탭 제거 확인", 
                f"'{tab_name}' 탭을 관리 목록에서 제거하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if confirm == QMessageBox.Yes:
                if self.tab_manager.remove_tab(tab_id):
                    self.status_bar.showMessage(f"탭 '{tab_name}' 제거됨")
                    removed_any = True
        
        if removed_any:
            self.update_managed_tabs_list()
            self.update_status_labels()
            # 탭이 제거되었으므로 시간 체크 타이머 상태 업데이트
            self.update_time_check_timer()
    
    def get_current_browser_type(self):
        """현재 선택된 브라우저 타입 반환"""
        if self.chrome_radio.isChecked():
            return "chrome"
        elif self.firefox_radio.isChecked():
            return "firefox"
        elif self.edge_radio.isChecked():
            return "edge"
        elif self.safari_radio.isChecked():
            return "safari"
        else:
            return "chrome"  # 기본값 

    def get_selected_tab_ids(self):
        """선택된 탭의 ID 목록 반환"""
        selected_items = self.managed_tabs_list.selectedItems()
        return [item.data(Qt.UserRole) for item in selected_items]

    def update_table_view(self):
        """관리 중인 탭 목록 업데이트"""
        self.update_managed_tabs_list()

    def managed_tabs_selection_changed(self):
        """탭 목록에서 선택된 항목이 변경되면 호출됨"""
        self.update_status_labels() 