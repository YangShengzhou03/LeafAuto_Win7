import ctypes
import json
import os
import threading
from datetime import datetime

import requests
from PyQt5 import QtCore, QtMultimedia
from PyQt5.QtCore import QThread, pyqtSignal

from common import log, get_current_time


# self.parent.update_wx()

class AiWorkerThread(QThread):
    pause_changed = pyqtSignal(bool)
    finished = pyqtSignal()

    def __init__(self, app_instance, receiver, model="月之暗面", role="你很温馨,回复简单明了。"):
        super().__init__()
        self.app_instance = app_instance
        self.receiver = receiver
        self.model = model
        self.stop_event = threading.Event()
        self.running = True
        self.system_content = role
        self.rules = self.load_rules()

    def load_rules(self):
        try:
            with open('_internal/AutoReply_Rules.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            log("WARNING", "回复规则未创建,您可新建规则")
            return None
        except json.JSONDecodeError:
            log("ERROR", "接管规则文件格式错误")
            return []

    def match_rule(self, msg):
        matched_replies = []
        for rule in self.rules:
            if rule['match_type'] == '全匹配':
                if msg.strip() == rule['keyword'].strip():
                    matched_replies.append(rule['reply_content'])
            elif rule['match_type'] == '半匹配':
                if rule['keyword'].strip() in msg.strip():
                    matched_replies.append(rule['reply_content'])
        return matched_replies

    def run(self):
        if self.receiver != "全局Ai接管":
            try:
                self.app_instance.wx.SendMsg(msg=" ", who=self.receiver)
            except Exception as e:
                log("ERROR", f"{str(e)}")
                self.app_instance.on_thread_finished()

        while self.running and not self.stop_event.is_set():
            try:
                if self.receiver == "全局Ai接管":
                    new_msg = self.app_instance.wx.GetAllNewMessage()
                    if new_msg is not None and new_msg:
                        who = next(iter(new_msg))
                        msgs = self.app_instance.wx.GetAllMessage()
                        if msgs and msgs[-1].type == "friend":
                            msg = msgs[-1].content
                            if self.rules is not None:
                                matched_replies = self.match_rule(msg)
                                if matched_replies:
                                    for reply in matched_replies:
                                        if os.path.isdir(os.path.dirname(reply)):
                                            if os.path.isfile(reply):
                                                log("INFO", f"根据规则发送文件 {os.path.basename(reply)}")
                                                self.app_instance.wx.SendFiles(filepath=reply, who=who)
                                            else:
                                                raise FileNotFoundError(
                                                    f"回复规则有误,没有 {os.path.basename(reply)} 文件")
                                        else:
                                            log("INFO", f"根据规则自动回复 {reply}")
                                            self.app_instance.wx.SendMsg(msg=reply, who=who)
                                else:
                                    self.main(msg, who)
                            else:
                                self.main(msg, who)
                else:
                    msgs = self.app_instance.wx.GetAllMessage()
                    if msgs and msgs[-1].type == "friend":
                        msg = msgs[-1].content
                        if self.rules is not None:
                            matched_replies = self.match_rule(msg)
                            if matched_replies:
                                for reply in matched_replies:
                                    if os.path.isdir(os.path.dirname(reply)):
                                        if os.path.isfile(reply):
                                            log("INFO", f"根据规则发送文件 {os.path.basename(reply)}")
                                            self.app_instance.wx.SendFiles(filepath=reply, who=self.receiver)
                                        else:
                                            raise FileNotFoundError(f"回复规则有误,没有 {os.path.basename(reply)} 文件")
                                    else:
                                        log("INFO", f"根据规则自动回复 {reply}")
                                        self.app_instance.wx.SendMsg(msg=reply, who=self.receiver)
                            else:
                                self.main(msg, self.receiver)
                        else:
                            self.main(msg, self.receiver)
            except Exception as e:
                log("ERROR", f"{str(e)}")
                break
            finally:
                self.msleep(100)
        self.app_instance.on_thread_finished()

    def requestInterruption(self):
        self.stop_event.set()

    def query_api(self, url, payload=None, headers=None, params=None, method='POST'):
        try:
            response = requests.request(method=method, url=url, json=payload, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log("ERROR", f"Request failed: {e}")
            return None

    def get_access_token(self):
        return self.query_api(
            "https://aip.baidubce.com/oauth/2.0/token",
            params={'grant_type': 'client_credentials', 'client_id': 'eCB39lMiTbHXV0mTt1d6bBw7',
                    'client_secret': 'WUbEO3XdMNJLTJKNQfFbMSQvtBVzRhvu'}
        ).get("access_token")

    def main(self, msg, who):
        if self.model == "文心一言":
            access_token = self.get_access_token()
            payload = {"messages": [{"role": "user", "content": msg}]}
            result = self.query_api(
                f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-speed-128k?access_token={access_token}",
                payload=payload,
                headers={'Content-Type': 'application/json'}
            ).get('result', "无法解析响应")
        elif self.model == "月之暗面":
            from openai import OpenAI
            client = OpenAI(api_key="sk-dx1RuweBS0LU0bCR5HizbWjXLuBL6HrS8BT21NEEGwbeyuo6",
                            base_url="https://api.moonshot.cn/v1")
            completion = client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[{"role": "system", "content": self.system_content}, {"role": "user", "content": msg}],
                temperature=0.9,
            )
            result = completion.choices[0].message.content
        else:
            data = {
                "max_tokens": 64,
                "top_k": 4,
                "temperature": 0.9,
                "messages": [
                    {"role": "system", "content": self.system_content},
                    {"role": "user", "content": msg}
                ],
                "model": "4.0Ultra"
            }
            header = {
                "Authorization": "Bearer xCPWitJxfzhLaZNOAdtl:PgJXiEyvKjUaoGzKwgIi",
                "Content-Type": "application/json"
            }
            response = self.query_api("https://spark-api-open.xf-yun.com/v1/chat/completions", data, header)
            result = response['choices'][0]['message']['content'] if response else "无法解析响应"

        if result:
            self.app_instance.wx.SendMsg(msg=result, who=who)
            log("INFO", f"Ai发送:{result}")


class SplitWorkerThread(QThread):
    pause_changed = pyqtSignal(bool)
    finished = pyqtSignal()

    def __init__(self, app_instance, receiver, sentences):
        super().__init__()
        self.app_instance = app_instance
        self.receiver = receiver
        self.sentences = sentences
        self.stop_event = threading.Event()

    def run(self):
        log("WARNING", f"准备将 {len(self.sentences)} 条信息发给 {self.receiver}")

        for sentence in self.sentences:
            if self.stop_event.is_set():
                break

            try:
                log("INFO", f"发送 '{sentence}' 给 {self.receiver}")
                self.app_instance.wx.SendMsg(msg=sentence, who=self.receiver)
            except Exception as e:
                log("ERROR", f"{str(e)}")
                self.app_instance.is_sending = False
                self.app_instance.is_scheduled_task_active = False
                self.stop_event.set()
                break
        self.app_instance.on_thread_finished()

    def requestInterruption(self):
        self.stop_event.set()


class WorkerThread(QtCore.QThread):
    pause_changed = QtCore.pyqtSignal(bool)
    finished = QtCore.pyqtSignal()

    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.is_paused = False
        self.interrupted = False
        self.prevent_sleep = False
        self.current_time = 'sys'

    def run(self):
        if self.prevent_sleep:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)

        while not self.interrupted:
            if self.interrupted:
                break
            next_task = self.find_next_ready_task()
            if next_task is None:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                self.prevent_sleep = False
                self.app_instance.on_thread_finished()
                break

            task_time = datetime.strptime(next_task['time'], '%Y-%m-%dT%H:%M:%S')
            remaining_time = (task_time - get_current_time(self.current_time)).total_seconds()
            if remaining_time > 0:
                if self.interrupted:
                    break
                self.msleep(int(remaining_time * 1000))

            if self.interrupted:
                break

            max_retries = 1
            retries = 0
            success = False

            while retries <= max_retries and not success:
                try:
                    name = next_task['name']
                    info = next_task['info']

                    if self.interrupted:
                        break

                    if os.path.isdir(os.path.dirname(info)):
                        if os.path.isfile(info):
                            file_name = os.path.basename(info)
                            log("INFO", f"开始把文件 {file_name} 发给 {name}")
                            if self.interrupted:
                                break
                            self.app_instance.wx.SendFiles(filepath=info, who=name)
                        else:
                            raise FileNotFoundError(f"该路径下没有 {os.path.basename(info)} 文件")
                    elif info == 'Video_chat':
                        log("INFO", f"开始与 {name} 视频通话")
                        if self.interrupted:
                            break
                        self.app_instance.wx.VideoCall(who=name)
                    else:
                        log("INFO", f"开始把 {info[:25] + '……' if len(info) > 25 else info} 发给 {name[:8]}")
                        if self.interrupted:
                            break
                        self.app_instance.wx.SendMsg(msg=info, who=name)

                    if self.interrupted:
                        break
                    log("DEBUG", f"成功把 {info[:25] + '……' if len(info) > 25 else info} 发给 {name[:8]} ")
                    success = True
                except Exception as e:
                    if "拒绝访问" in str(e) and retries < max_retries:
                        log("ERROR", f"微信数据发生变化，即将自动适应")
                        retries += 1
                        self.app_instance.parent.update_wx()
                        self.msleep(50)
                    else:
                        log("ERROR", f"{str(e)}")
                        self.app_instance.update_task_status(next_task, '出错')
                        break
                else:
                    self.app_instance.update_task_status(next_task, '成功')

            while not self.interrupted and self.is_paused:
                self.msleep(50)
            if self.interrupted:
                break

        if self.prevent_sleep:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            self.prevent_sleep = False

    def find_next_ready_task(self):
        next_task = None
        min_time = None
        for task in self.app_instance.ready_tasks:
            try:
                task_time = QtCore.QDateTime.fromString(task['time'], "yyyy-MM-ddTHH:mm:ss").toSecsSinceEpoch()
                if min_time is None or task_time < min_time:
                    min_time = task_time
                    next_task = task
            except Exception as e:
                log("ERROR", f"{str(e)}")
        return next_task

    def requestInterruption(self):
        self.interrupted = True


class ErrorSoundThread(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    _is_playing = False

    def __init__(self):
        super().__init__()
        self.sound_file = None
        self.player = None

    def update_sound_file(self, sound_file_path):
        self.sound_file = sound_file_path

    def run(self):
        if not self.sound_file or not os.path.exists(self.sound_file) or self._is_playing:
            return
        self._is_playing = True
        self.player = QtMultimedia.QMediaPlayer()
        # 直接设置媒体源，无需设置音频输出
        self.player.setMedia(QtMultimedia.QMediaContent(QtCore.QUrl.fromLocalFile(self.sound_file)))
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.play()
        loop = QtCore.QEventLoop()
        self.finished.connect(loop.quit)
        loop.exec()

    def _on_media_status_changed(self, status):
        if status == QtMultimedia.QMediaPlayer.EndOfMedia:
            self.finished.emit()
            if self.player:
                self.player.stop()
                self._is_playing = False

    def stop_playback(self):
        if self.player and self._is_playing:
            self.player.stop()
            self._is_playing = False
            self.finished.emit()

    def play_test(self):
        if self._is_playing:
            self.stop_playback()
        else:
            self.start()
