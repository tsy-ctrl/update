import sys
import subprocess
import os

def install_dependencies():
    """Установка необходимых библиотек"""
    required = {'requests'}
    installed = {pkg.split('==')[0] for pkg in subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']).decode().split()}
    missing = required - installed
    
    if missing:
        print("Установка необходимых библиотек...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + list(missing))
        print("Библиотеки успешно установлены\n")

try:
    install_dependencies()
except Exception as e:
    print(f"Ошибка при установке библиотек: {e}")
    input("\nНажмите Enter для выхода...")
    sys.exit(1)

import requests
from typing import Dict, Optional, List
from datetime import datetime
import json
import hashlib

class OFDownloader:
    def __init__(self):
        """Инициализация загрузчика для репозитория OF_HELPER"""
        self.base_url = "https://api.github.com/repos/ppleaser/OF_HELPER"
        self.raw_base_url = "https://raw.githubusercontent.com/ppleaser/OF_HELPER/main"
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.status_file = "update.json"
        self.last_update: Dict[str, str] = self._load_status()

    def _load_status(self) -> Dict[str, str]:
        """Загружает информацию о последнем обновлении"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_status(self):
        """Сохраняет информацию о последнем обновлении"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.last_update, f, indent=2)

    def _get_file_hash(self, file_path: str) -> Optional[str]:
        """Получает хеш локального файла"""
        full_path = os.path.join(self.root_dir, file_path)
        if not os.path.exists(full_path):
            return None
        
        with open(full_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _is_merge_commit(self, commit_data: dict) -> bool:
        """Проверяет, является ли коммит мерж-коммитом"""
        return len(commit_data.get('parents', [])) > 1

    def _get_changed_files(self) -> tuple[List[str], str, str]:
        """
        Получает список файлов, измененных в последнем коммите
        :return: (список файлов, время коммита, описание коммита)
        """
        try:
            # Получаем список коммитов
            commits_url = f"{self.base_url}/commits"
            response = requests.get(commits_url)
            if response.status_code != 200:
                print(f"Ошибка при получении коммитов: {response.status_code}")
                return [], "", ""

            commits = response.json()
            
            # Находим первый не мерж-коммит
            commit_index = 0
            while commit_index < len(commits) and self._is_merge_commit(commits[commit_index]):
                commit_index += 1

            if commit_index >= len(commits):
                print("Не найдено подходящих коммитов")
                return [], "", ""

            latest_commit = commits[commit_index]
            commit_sha = latest_commit['sha']
            commit_time = datetime.fromisoformat(latest_commit['commit']['author']['date'].replace('Z', '+00:00'))
            commit_message = latest_commit['commit']['message']

            # Получаем детали коммита
            commit_url = f"{self.base_url}/commits/{commit_sha}"
            response = requests.get(commit_url)
            if response.status_code != 200:
                print(f"Ошибка при получении деталей коммита: {response.status_code}")
                return [], "", ""

            # Извлекаем измененные файлы
            files = response.json()['files']
            return [file['filename'] for file in files], commit_time.strftime("%Y-%m-%d %H:%M:%S UTC"), commit_message

        except Exception as e:
            print(f"Ошибка при получении измененных файлов: {e}")
            return [], "", ""

    def _download_file(self, file_path: str) -> bool:
        """
        Скачивает файл с GitHub
        :return: True если файл был обновлён
        """
        try:
            if not file_path:
                print("Пропущен файл с пустым путём")
                return False

            response = requests.get(f"{self.raw_base_url}/{file_path}")
            if response.status_code != 200:
                print(f"Ошибка при скачивании {file_path}: {response.status_code}")
                return False

            full_path = os.path.join(self.root_dir, file_path)
            directory = os.path.dirname(full_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            new_content = response.content
            new_hash = hashlib.sha256(new_content).hexdigest()
            old_hash = self._get_file_hash(file_path)

            if new_hash == old_hash:
                print(f"Файл {file_path} не изменился")
                return False

            with open(full_path, 'wb') as f:
                f.write(new_content)

            self.last_update[file_path] = new_hash
            print(f"Обновлен файл: {file_path}")
            return True

        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {e}")
            return False

    def update_files(self):
        """Обновляет только измененные файлы из последнего коммита"""
        try:
            print("Получаю информацию о последних изменениях...")
            
            changed_files, commit_time, commit_message = self._get_changed_files()
            if not changed_files:
                print("Не найдено измененных файлов или произошла ошибка при получении информации")
                input("\nНажмите Enter для выхода...")
                return

            print(f"\nПоследний коммит от: {commit_time}")
            print(f"Сообщение коммита: {commit_message}")
            print(f"\nНайдено измененных файлов: {len(changed_files)}")
            print("\nСписок измененных файлов:")
            for file in changed_files:
                print(f"- {file}")
            
            print("\nНачинаю обновление...\n")

            updated_count = 0
            for file_path in changed_files:
                if self._download_file(file_path):
                    updated_count += 1

            self._save_status()
            print(f"\nГотово! Обновлено файлов: {updated_count}")
            input("\nНажмите Enter для выхода...")

        except Exception as e:
            print(f"\nПроизошла ошибка: {e}")
            input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    downloader = OFDownloader()
    downloader.update_files()