import os
import requests
from typing import Dict, List
import json
from datetime import datetime
import pytz
import sys
from tqdm import tqdm

class OFDownloader:

    GITHUB_TOKEN = "GITHUB_TOKEN_PLACEHOLDER"

    def _check_rate_limit(self):
        response = requests.get(
            "https://api.github.com/rate_limit",
            headers=self.headers
        )
        if response.status_code == 200:
            data = response.json()
            remaining = data['rate']['remaining']
            limit = data['rate']['limit']
            print(f"Доступно запросов: {remaining}/{limit}")
            return remaining
        return None

    def __init__(self):
        self.base_url = "https://api.github.com/repos/ppleaser/OF_HELPER"
        self.raw_base_url = "https://raw.githubusercontent.com/ppleaser/OF_HELPER/main"
        
        token = self.GITHUB_TOKEN

        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'Bearer {token}'
        }
        
        self._check_rate_limit()
        
        if getattr(sys, 'frozen', False):
            if sys.platform == 'darwin':
                self.root_dir = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', '..', '..'))
            else:
                self.root_dir = os.path.dirname(os.path.dirname(sys.executable))
        else:
            self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.update_dir = os.path.join(self.root_dir, "update")
        self.status_file = os.path.join(self.update_dir, "update.json")
        self.status_data = {"last_commit": None}
        self._load_status()
        
        print(f"Рабочая директория: {self.root_dir}")

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
            os.makedirs(self.update_dir, exist_ok=True)
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status_data, f, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статуса: {e}")

    def _is_merge_commit(self, commit_data: dict) -> bool:
        return len(commit_data.get('parents', [])) > 1

    def _get_all_commits(self) -> List[Dict]:
        try:
            response = requests.get(f"{self.base_url}/commits", headers=self.headers)
            
            if response.status_code == 401:
                error_message = response.json().get('message', 'Неизвестная ошибка')
                print(f"Ошибка авторизации (401): {error_message}")
                return []
            elif response.status_code == 403:
                print("Превышен лимит запросов к GitHub API. Попробуйте позже.")
                return []
            elif response.status_code != 200:
                print(f"Ошибка получения коммитов. Код ответа: {response.status_code}")
                return []

            all_commits = response.json()
            filtered_commits = [
                commit for commit in all_commits[:-1]
                if not self._is_merge_commit(commit)
            ]
            
            return filtered_commits

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сетевого подключения: {e}")
            return []
        except Exception as e:
            print(f"Неожиданная ошибка при получении коммитов: {e}")
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

            file_path = file_path.replace('\\', '/')
            response = requests.get(f"{self.raw_base_url}/{file_path}", headers=self.headers)
            
            if response.status_code != 200:
                print(f"Ошибка скачивания {file_path}: {response.status_code}")
                return False

            norm_file_path = file_path.replace('/', os.sep)
            full_path = os.path.join(self.root_dir, norm_file_path)
            
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                with open(full_path, 'wb') as f:
                    f.write(response.content)
                return True
            except Exception as e:
                print(f"Ошибка сохранения файла {full_path}: {e}")
                return False

        except Exception as e:
            print(f"Общая ошибка скачивания {file_path}: {e}")
            return False

    def get_later_updates_for_file(self, file_path: str, commit_sha: str, all_commits: List[Dict]) -> bool:
        current_index = next((i for i, commit in enumerate(all_commits) 
                            if commit['sha'] == commit_sha), -1)
        
        if current_index == -1:
            return False

        for i in range(current_index):
            commit_url = f"{self.base_url}/commits/{all_commits[i]['sha']}"
            response = requests.get(commit_url, headers=self.headers)
            
            if response.status_code == 200:
                commit_files = response.json().get('files', [])
                if any(f.get('filename') == file_path for f in commit_files):
                    return True
        return False

    def show_colored_available_updates(self) -> List[Dict]:
        all_commits = self._get_all_commits()
        if not all_commits:
            print("Не удалось получить список обновлений")
            return []
        
        last_commit_sha = self.status_data.get("last_commit")
        last_commit_index = None
        
        print("\nВсе доступные обновления:")
        print("=" * 60)
        
        RED = '\033[91m'
        YELLOW = '\033[33m'
        GREEN = '\033[92m'
        BLUE = '\033[94m'
        RESET = '\033[0m'
        
        for i, commit in enumerate(all_commits):
            commit_date = self.format_commit_date(commit['commit']['author']['date'])
            
            if commit['sha'] == last_commit_sha:
                status_text = " [Установлено]"
                color = GREEN
                last_commit_index = i
            elif last_commit_index is not None:
                if i < last_commit_index:
                    status_text = " [Будет установлено]"
                    color = YELLOW
                else:
                    status_text = ""
                    color = BLUE
            else:
                status_text = ""
                color = YELLOW
            
            print(f"{RED}{i+1}.{RESET} {color}{commit_date} - {commit['commit']['message']}{status_text}{RESET}")
        
        print("=" * 60)
        return all_commits
    
    def update_files(self, target_commit_index=None):
        all_commits = self._get_all_commits()
        if not all_commits:
            print("Не удалось получить список обновлений")
            return
        
        if target_commit_index is None:
            if self.status_data.get("last_commit"):
                last_installed_index = next(
                    (i for i, commit in enumerate(all_commits) if commit['sha'] == self.status_data["last_commit"]),
                    None
                )
                if last_installed_index is None:
                    commits_to_update = [all_commits[0]]
                elif last_installed_index == 0:
                    print("Нет обновлений")
                    return
                else:
                    target_commit_index = last_installed_index - 1
                    commits_to_update = all_commits[target_commit_index::-1]
            else:
                commits_to_update = [all_commits[0]]
        else:
            if target_commit_index < 0 or target_commit_index >= len(all_commits):
                print(f"Неправильный номер обновления. Доступны обновления с 1 по {len(all_commits)}")
                return
            commits_to_update = all_commits[target_commit_index::-1]

        if not commits_to_update:
            print("Нет обновлений")
            return

        print(f"Получено {len(commits_to_update)} обновлений:")

        for i, commit in enumerate(commits_to_update):
            actual_update_number = len(commits_to_update) - i
            commit_date = self.format_commit_date(commit['commit']['author']['date'])
            print(f"\n{actual_update_number}. {commit_date} - {commit['commit']['message']}")
            print(f"\nНачало обновления {actual_update_number}/{len(commits_to_update)}")

            commit_url = f"{self.base_url}/commits/{commit['sha']}"
            response = requests.get(commit_url, headers=self.headers)

            if response.status_code != 200:
                print("Ошибка получения информации о коммите")
                continue

            commit_data = response.json()
            all_files_updated = True
            changed_files = []
            skipped_files = []

            files_to_process = commit_data.get('files', [])

            with tqdm(total=len(files_to_process), desc="Прогресс обновления", 
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
                for file_data in files_to_process:
                    filename = file_data.get('filename')
                    if filename:
                        if self.get_later_updates_for_file(filename, commit['sha'], all_commits):
                            skipped_files.append(filename)
                            pbar.update(1)
                            continue

                        if self._download_file(filename):
                            changed_files.append(filename)
                        else:
                            all_files_updated = False
                            print(f"Ошибка обновления файла: {filename}")
                            break
                    pbar.update(1)

            if not all_files_updated:
                print("\nОбновление прервано из-за ошибки")
                return

            if changed_files:
                print("\nБыли изменены файлы:")
                for file in changed_files:
                    print(f"- {file}")

            if skipped_files:
                print("\nПропущены файлы (будут обновлены позже):")
                for file in skipped_files:
                    print(f"- {file}")

            self.status_data["last_commit"] = commit['sha']
            self._save_status()

        print("\nОбновление завершено")

if __name__ == "__main__":
    downloader = OFDownloader()
    all_commits = downloader.show_colored_available_updates()
    
    if all_commits:
        choice = input("\nНажмите Enter для автоматического обновления или введите номер обновления: ")
        
        if choice.strip() == "":
            downloader.update_files()
        else:
            try:
                target_index = int(choice) - 1
                downloader.update_files(target_index)
            except ValueError:
                print("Некорректный ввод. Обновление отменено.")
    input()
