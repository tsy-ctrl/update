import os
import requests
from typing import Dict, List
import json
import hashlib

class OFDownloader:
    def __init__(self):
        """Инициализация загрузчика для репозитория OF_HELPER"""
        self.base_url = "https://api.github.com/repos/ppleaser/OF_HELPER"
        self.raw_base_url = "https://raw.githubusercontent.com/ppleaser/OF_HELPER/main"
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.status_file = "update.json"
        self.status_data = {"last_commit": None, "files": {}}  # Инициализируем структуру
        self._load_status()  # Загружаем существующие данные, если есть

    def _load_status(self):
        """Загружает существующий статус или использует значения по умолчанию"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Обновляем только существующие данные
                    if isinstance(loaded_data, dict):
                        if "last_commit" in loaded_data:
                            self.status_data["last_commit"] = loaded_data["last_commit"]
                        if "files" in loaded_data and isinstance(loaded_data["files"], dict):
                            self.status_data["files"] = loaded_data["files"]
            except Exception as e:
                print(f"Ошибка загрузки статуса: {e}")

    def _save_status(self):
        """Сохраняет текущий статус"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self.status_data, f, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статуса: {e}")

    def _is_merge_commit(self, commit_data: dict) -> bool:
        """Проверяет, является ли коммит мерж-коммитом"""
        return len(commit_data.get('parents', [])) > 1

    def _get_commits_since_last_update(self) -> List[Dict]:
        try:
            print("\nЗапрашиваю список коммитов...")
            headers = {'Accept': 'application/vnd.github.v3+json'}
            response = requests.get(self.base_url + "/commits", headers=headers)
            
            if response.status_code != 200:
                print(f"Тело ответа: {response.text}")
                return []

            commits = response.json()

            # Фильтруем мерж-коммиты и первый коммит
            if len(commits) > 0:
                filtered_commits = [
                    commit for commit in commits[:-1]  # Исключаем последний (самый старый) коммит
                    if not self._is_merge_commit(commit)
                ]
                print(f"Получено: {len(filtered_commits)} коммитов")
                return filtered_commits
            return []

        except Exception as e:
            print(f"Ошибка при получении коммитов: {str(e)}")
            return []

    def _download_file(self, file_path: str) -> bool:
        try:
            print(f"\nПытаюсь скачать файл: {file_path}")
            
            if not file_path:
                print("Пустой путь файла")
                return False

            response = requests.get(f"{self.raw_base_url}/{file_path}")
            
            if response.status_code != 200:
                print(f"Ошибка скачивания: {response.text}")
                return False

            full_path = os.path.join(self.root_dir, file_path)
            directory = os.path.dirname(full_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            content = response.content
            new_hash = hashlib.sha256(content).hexdigest()
            
            # Убеждаемся, что словарь files существует
            if "files" not in self.status_data:
                self.status_data["files"] = {}
                
            # Проверяем изменения
            old_hash = self.status_data["files"].get(file_path)
            if new_hash == old_hash:
                print("Файл не изменился")
                return False

            # Сохраняем файл
            with open(full_path, 'wb') as f:
                f.write(content)

            self.status_data["files"][file_path] = new_hash
            print("Файл успешно обновлен")
            return True

        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {str(e)}")
            return False

    def update_files(self):
        try:
            print("Начинаю процесс обновления...")
            
            commits = self._get_commits_since_last_update()
            if not commits:
                print("Нет коммитов для обработки")
                input("\nНажмите Enter для выхода...")
                return

            print(f"\nОбработка {len(commits)} коммитов...")
            commits.reverse()  # От старых к новым
            
            total_updated = 0
            for commit in commits:
                print(f"\nОбрабатываю коммит: {commit['sha']}")
                print(f"Дата: {commit['commit']['author']['date']}")
                print(f"Сообщение: {commit['commit']['message']}")

                # Получаем детали коммита
                commit_url = f"{self.base_url}/commits/{commit['sha']}"
                headers = {'Accept': 'application/vnd.github.v3+json'}
                response = requests.get(commit_url, headers=headers)
                
                if response.status_code != 200:
                    print(f"Ошибка получения деталей: {response.text}")
                    continue

                commit_data = response.json()
                files = commit_data.get('files', [])
                print(f"Файлов в коммите: {len(files)}")

                # Обрабатываем каждый файл
                commit_updated = 0
                for file_data in files:
                    filename = file_data.get('filename')
                    if filename and self._download_file(filename):
                        commit_updated += 1
                        total_updated += 1

                print(f"Обновлено в этом коммите: {commit_updated}")
                
                # Сохраняем прогресс
                self.status_data["last_commit"] = commit['sha']
                self._save_status()

            print(f"\nВсего обновлено файлов: {total_updated}")
            input("\nНажмите Enter для выхода...")

        except Exception as e:
            print(f"\nОшибка: {str(e)}")
            print("Полная информация об ошибке:")
            import traceback
            traceback.print_exc()
            input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    downloader = OFDownloader()
    downloader.update_files()
