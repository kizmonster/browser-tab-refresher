from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QListWidget, QListWidgetItem, QPushButton, QGroupBox,
                             QTimeEdit, QCheckBox)
from PySide6.QtCore import QTime
import re

class TimeScheduleDialog(QDialog):
    def __init__(self, parent=None, current_times=None):
        super().__init__(parent)
        self.setWindowTitle("새로고침 시간 설정")
        self.times = [] if current_times is None else current_times.copy()
        # 유효한 시간 문자열만 필터링
        self.times = [t for t in self.times if isinstance(t, str) and self._validate_time_format(t)]
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 현재 설정된 시간 목록
        time_list_group = QGroupBox("설정된 시간 목록")
        time_list_layout = QVBoxLayout()
        
        self.time_list = QListWidget()
        self.time_list.setSelectionMode(QListWidget.ExtendedSelection)
        
        time_list_layout.addWidget(self.time_list)
        time_list_group.setLayout(time_list_layout)
        layout.addWidget(time_list_group)
        
        # 새 시간 추가 그룹
        add_time_group = QGroupBox("새 시간 추가")
        add_time_layout = QVBoxLayout()
        
        time_input_layout = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm:ss")  # 시, 분, 초까지 설정
        self.time_edit.setTime(QTime.currentTime())
        
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self.add_time)
        
        time_input_layout.addWidget(QLabel("시간:"))
        time_input_layout.addWidget(self.time_edit)
        time_input_layout.addWidget(add_btn)
        
        # 반복 실행 체크박스 추가
        repeat_layout = QHBoxLayout()
        self.repeat_checkbox = QCheckBox("매일 반복")
        self.repeat_checkbox.setToolTip("체크하면 매일 같은 시간에 반복 실행됩니다")
        repeat_layout.addWidget(self.repeat_checkbox)
        repeat_layout.addStretch()
        
        add_time_layout.addLayout(time_input_layout)
        add_time_layout.addLayout(repeat_layout)
        add_time_group.setLayout(add_time_layout)
        layout.addWidget(add_time_group)
        
        # 시간 관리 버튼
        button_layout = QHBoxLayout()
        
        remove_btn = QPushButton("선택한 시간 삭제")
        remove_btn.clicked.connect(self.remove_selected_times)
        
        clear_btn = QPushButton("모든 시간 삭제")
        clear_btn.clicked.connect(self.clear_all_times)
        
        button_layout.addWidget(remove_btn)
        button_layout.addWidget(clear_btn)
        layout.addLayout(button_layout)
        
        # 확인/취소 버튼
        dialog_buttons = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        
        dialog_buttons.addWidget(ok_btn)
        dialog_buttons.addWidget(cancel_btn)
        layout.addLayout(dialog_buttons)
        
        # 상태 표시 레이블
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        # 도움말 레이블 추가
        help_layout = QVBoxLayout()
        help_label1 = QLabel("* 설정한 시간에 정확히 1회만 실행됩니다.")
        help_label2 = QLabel("* '매일 반복' 체크 시 매일 같은 시간에 실행됩니다.")
        help_label3 = QLabel("* 초(seconds)까지 정확히 설정하세요. 정확한 시간에만 실행됩니다.")
        
        for label in [help_label1, help_label2, help_label3]:
            label.setStyleSheet("color: #666; font-style: italic;")
            help_layout.addWidget(label)
        
        layout.addLayout(help_layout)
        
        self.setLayout(layout)
        
        # 상태 레이블 초기화 후 update_time_list 호출
        self.update_time_list()
        self.update_status()
    
    def update_time_list(self):
        """시간 목록 업데이트"""
        self.time_list.clear()
        # 유효한 시간만 표시
        valid_times = []
        for time_item in self.times:
            # '*'로 시작하는 경우 반복 실행 시간으로 처리
            is_repeating = False
            display_time = time_item
            check_time = time_item
            
            if isinstance(time_item, str) and time_item.startswith("*"):
                is_repeating = True
                check_time = time_item[1:]  # '*' 제거하여 검증
                display_time = f"* {check_time} (매일 반복)"
            
            if isinstance(check_time, str) and self._validate_time_format(check_time):
                valid_times.append(time_item)  # 원래 형식으로 저장
                item = QListWidgetItem(display_time)
                self.time_list.addItem(item)
            else:
                print(f"경고: 올바르지 않은 시간 형식 무시됨: {time_item}")
        
        # 유효하지 않은 항목이 있으면 times 리스트 업데이트
        if len(valid_times) != len(self.times):
            self.times = valid_times
        
        # 상태 레이블 업데이트
        self.update_status()
    
    def _validate_time_format(self, time_str):
        """시간 형식 검증 (HH:MM 또는 HH:MM:SS)
        유효한 형식이면 True 반환, 아니면 False 반환
        """
        if not isinstance(time_str, str):
            return False
            
        if ":" not in time_str:
            return False
            
        parts = time_str.split(":")
        if not (2 <= len(parts) <= 3):
            return False
            
        try:
            h, m = int(parts[0]), int(parts[1])
            s = int(parts[2]) if len(parts) == 3 else 0
            
            if 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60:
                return True
            return False
        except ValueError:
            return False
    
    def add_time(self, time_str=None, repeating=None):
        """
        새로운 시간 추가
        
        Args:
            time_str: 추가할 시간 문자열 (None이면 QTimeEdit에서 가져옴)
            repeating: 반복 시간 여부 (None이면 checkbox에서 가져옴)
        """
        print(f"add_time 호출됨, 입력 파라미터: {time_str}, 타입: {type(time_str)}, 반복: {repeating}")
        
        # time_str이 None인 경우 QTimeEdit에서 시간 가져오기
        if time_str is None or time_str is False:  # False도 처리
            time_obj = self.time_edit.time()
            time_str = time_obj.toString("HH:mm:ss")
            print(f"QTimeEdit에서 가져온 시간: {time_str}, 타입: {type(time_str)}")
        elif not isinstance(time_str, str):
            try:
                time_str = str(time_str)
                print(f"문자열로 변환됨: {time_str}")
            except:
                if hasattr(self, 'status_label') and self.status_label is not None:
                    self.status_label.setText(f"올바르지 않은 시간 형식: {time_str}")
                print(f"문자열 변환 실패: {time_str}, 타입: {type(time_str)}")
                return False
        
        # 시간 형식 검증
        valid_time = None
        
        # 시간 형식 검증 및 정규화
        if ":" in time_str:
            parts = time_str.split(":")
            print(f"시간 파트: {parts}")
            
            if 2 <= len(parts) <= 3:
                try:
                    h, m = int(parts[0]), int(parts[1])
                    s = int(parts[2]) if len(parts) == 3 else 0
                    
                    if 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60:
                        # 형식화된 시간 문자열로 정규화
                        if len(parts) == 2:
                            valid_time = f"{h:02d}:{m:02d}"
                        else:
                            valid_time = f"{h:02d}:{m:02d}:{s:02d}"
                        print(f"유효한 시간 형식: {valid_time}")
                    else:
                        print(f"시간 범위 오류: 시간={h}, 분={m}, 초={s}")
                        if hasattr(self, 'status_label') and self.status_label is not None:
                            self.status_label.setText(f"시간 범위가 올바르지 않습니다: {time_str}")
                except ValueError as e:
                    print(f"숫자 변환 오류: {e}")
                    valid_time = None
            else:
                print(f"잘못된 부분 개수: {len(parts)}")
        else:
            print(f"콜론(:)이 없는 시간 형식: {time_str}")
        
        if valid_time is None:
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"올바르지 않은 시간 형식: {time_str}")
            print(f"유효하지 않은 시간 형식: {time_str}")
            return False
        
        # 반복 실행 여부 확인 (매개변수 우선, 없으면 체크박스 값 사용)
        is_repeating = repeating if repeating is not None else self.repeat_checkbox.isChecked()
        final_time = valid_time
        if is_repeating:
            final_time = f"*{valid_time}"
            print(f"반복 실행 시간으로 설정: {final_time}")
        
        # 중복 검사 - 정규화된 시간으로 비교
        if final_time not in self.times:
            self.times.append(final_time)
            print(f"시간이 성공적으로 추가됨: {final_time}")
            self.update_time_list()  # 목록과 상태 업데이트
            return True
        else:
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText(f"이미 존재하는 시간입니다: {final_time}")
            print(f"중복된 시간: {final_time}")
            return False
    
    def remove_selected_times(self):
        """선택한 시간 삭제"""
        selected_items = self.time_list.selectedItems()
        if not selected_items:
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText("삭제할 시간을 선택하세요")
            return
        
        removed_times = []
        for item in selected_items:
            display_text = item.text()
            
            # 표시 텍스트에서 실제 시간 추출
            # 두 가지 형식 처리: "* HH:MM:SS (매일 반복)" 또는 일반 "HH:MM:SS"
            index = self.time_list.row(item)
            if index < len(self.times):
                time_str = self.times[index]
                if time_str in self.times:
                    self.times.remove(time_str)
                    removed_times.append(display_text)
        
        self.update_time_list()
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setText(f"삭제된 시간: {', '.join(removed_times)}")
    
    def clear_all_times(self):
        """모든 시간 삭제"""
        if not self.times:
            if hasattr(self, 'status_label') and self.status_label is not None:
                self.status_label.setText("삭제할 시간이 없습니다")
            return
        
        self.times.clear()
        self.update_time_list()
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setText("모든 시간이 삭제되었습니다")
    
    def update_status(self):
        """상태 정보 업데이트"""
        if not hasattr(self, 'status_label') or self.status_label is None:
            return
        
        if self.times:
            # 일반 항목과 반복 항목 개수 계산
            repeat_count = sum(1 for t in self.times if isinstance(t, str) and t.startswith("*"))
            normal_count = len(self.times) - repeat_count
            
            status_text = f"설정된 시간: {len(self.times)}개"
            if repeat_count > 0:
                status_text += f" (일회성: {normal_count}개, 반복: {repeat_count}개)"
            
            self.status_label.setText(status_text)
        else:
            self.status_label.setText("설정된 시간이 없습니다")
    
    def get_times(self):
        """설정된 시간 목록 반환"""
        # 일반 항목과 반복 항목을 분리하여 정렬 후 다시 결합
        normal_times = [t for t in self.times if not (isinstance(t, str) and t.startswith("*"))]
        repeat_times = [t for t in self.times if isinstance(t, str) and t.startswith("*")]
        
        # 각각 정렬
        normal_times.sort()
        repeat_times.sort()
        
        # 결합: 일반 항목 먼저, 그 다음 반복 항목
        return normal_times + repeat_times
    
    def get_times_with_repeat(self):
        """
        설정된 시간을 반복 여부와 함께 반환
        
        Returns:
            list: 각 시간을 딕셔너리 형태로 담은 목록, 예: [{'time': '12:00', 'repeating': True}, {'time': '15:30', 'repeating': False}]
        """
        result = []
        for time_str in self.times:
            if isinstance(time_str, str):
                is_repeating = time_str.startswith('*')
                actual_time = time_str[1:] if is_repeating else time_str
                
                if self._validate_time_format(actual_time):
                    result.append({
                        'time': actual_time,
                        'repeating': is_repeating
                    })
        
        return result 