import os
import requests
from typing import Dict, List
import json
from datetime import datetime
import pytz
import sys

class OFDownloader:
    def __init__(self):
        self.base_url = "https://api.github.com/repos/ppleaser/OF_HELPER"
        self.raw_base_url = "https://raw.githubusercontent.com/ppleaser/OF_HELPER/main"
        
        # Изменённое определение корневой директории
        if getattr(sys, 'frozen', False):
            # Если запущено как exe
            self.root_dir = os.path.dirname(sys.executable)
        else:
            # Если запущено как python скрипт
            self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        self.status_file = os.path.join(self.root_dir, "update.json")
        self.status_data = {"last_commit": None}
        self._load_status()
        
        print(f"Рабочая директория: {self.root_dir}")  # Добавим для отладки

    def _load_status(self):
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict) and "last_commit" in loaded_data:
                        self.status_data["last_commit"] = loaded_data["last_commit"]
            except Exception as e:
                print(f"Ошибка загрузки статуса: {e}")

    def _save_status(self):
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status_data, f, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статуса: {e}")

    def _is_merge_commit(self, commit_data: dict) -> bool:
        return len(commit_data.get('parents', [])) > 1

    def _get_commits_since_last_update(self) -> List[Dict]:
        try:
            headers = {'Accept': 'application/vnd.github.v3+json'}
            response = requests.get(f"{self.base_url}/commits", headers=headers)
            
            if response.status_code != 200:
                return []

            all_commits = response.json()
            filtered_commits = [
                commit for commit in all_commits 
                if not self._is_merge_commit(commit)
            ]

            if not self.status_data["last_commit"]:
                return [filtered_commits[0]] if filtered_commits else []

            # Find index of last processed commit
            last_commit_index = next(
                (i for i, commit in enumerate(filtered_commits)
                if commit['sha'] == self.status_data["last_commit"]),
                None
            )

            if last_commit_index is not None and last_commit_index > 0:
                return filtered_commits[:last_commit_index]
            return []

        except Exception as e:
            print(f"Ошибка при получении коммитов: {str(e)}")
            return []
     
    def format_commit_date(self, date_str: str) -> str:
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            local_date = date.astimezone(pytz.timezone('Europe/Kyiv'))
            return local_date.strftime('%d.%m.%Y %H:%M:%S')
        except Exception:
            return date_str

    def _download_file(self, file_path: str) -> bool:
        try:
            if not file_path:
                return False

            response = requests.get(f"{self.raw_base_url}/{file_path}")
            
            if response.status_code != 200:
                print(f"Ошибка скачивания {file_path}: {response.status_code}")  # Добавим для отладки
                return False

            full_path = os.path.join(self.root_dir, file_path)
            directory = os.path.dirname(full_path)
            
            try:
                if directory:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Создана директория: {directory}")  # Добавим для отладки
            except Exception as e:
                print(f"Ошибка создания директории {directory}: {e}")  # Добавим для отладки
                return False

            try:
                with open(full_path, 'wb') as f:
                    f.write(response.content)
                print(f"Файл успешно сохранен: {full_path}")  # Добавим для отладки
                return True
            except Exception as e:
                print(f"Ошибка сохранения файла {full_path}: {e}")  # Добавим для отладки
                return False

        except Exception as e:
            print(f"Общая ошибка скачивания {file_path}: {e}")  # Добавим для отладки
            return False

    def update_files(self):
        try:
            commits = self._get_commits_since_last_update()
            if not commits:
                print("Нет новых обновлений")
                return

            commits.reverse()
            print(f"Получено {len(commits)} новых обновлений:")
            
            for i, commit in enumerate(commits, 1):
                commit_date = self.format_commit_date(commit['commit']['author']['date'])
                print(f"\n{i}. {commit_date} - {commit['commit']['message']}")
                
                print(f"\nНачало обновления {i}")
                
                commit_url = f"{self.base_url}/commits/{commit['sha']}"
                headers = {'Accept': 'application/vnd.github.v3+json'}
                response = requests.get(commit_url, headers=headers)
                
                if response.status_code != 200:
                    continue

                commit_data = response.json()
                changed_files = []
                
                for file_data in commit_data.get('files', []):
                    filename = file_data.get('filename')
                    if filename and self._download_file(filename):
                        changed_files.append(filename)
                
                if changed_files:
                    print("Были изменены файлы:")
                    for file in changed_files:
                        print(f"- {file}")
                
                self.status_data["last_commit"] = commit['sha']
                self._save_status()
            
            print("\nОбновление завершено")

        except Exception as e:
            print(f"Ошибка: {str(e)}")

if __name__ == "__main__":
    downloader = OFDownloader()
    downloader.update_files()
