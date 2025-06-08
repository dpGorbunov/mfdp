#!/usr/bin/env python3
"""
Скрипт для загрузки датасета Instacart с Kaggle
"""
import os
import sys
import subprocess
import zipfile
from pathlib import Path


def check_kaggle_credentials():
    """Проверяет наличие учетных данных Kaggle"""
    kaggle_dir = Path.home() / '.kaggle'
    kaggle_json = kaggle_dir / 'kaggle.json'

    if not kaggle_json.exists():
        print("❌ Файл kaggle.json не найден!")
        print("\nДля загрузки данных необходимо:")
        print("1. Зарегистрироваться на https://www.kaggle.com")
        print("2. Перейти в Account -> API -> Create New API Token")
        print("3. Скачать kaggle.json и поместить его в ~/.kaggle/")
        print("4. Установить права: chmod 600 ~/.kaggle/kaggle.json")
        return False

    # Проверяем права доступа
    if os.name != 'nt':  # Не Windows
        os.chmod(kaggle_json, 0o600)

    return True


def install_kaggle():
    """Устанавливает библиотеку kaggle если её нет"""
    try:
        import kaggle
    except ImportError:
        print("📦 Устанавливаем библиотеку kaggle...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle"])
        print("✅ Kaggle установлен")


def download_dataset():
    """Загружает датасет с Kaggle"""
    data_dir = Path("data")

    # Создаем директорию если её нет
    data_dir.mkdir(exist_ok=True)

    # Проверяем, есть ли уже файлы
    csv_files = list(data_dir.glob("*.csv"))
    if len(csv_files) >= 6:
        print("✅ Данные уже загружены в папку data/")
        response = input("Хотите перезагрузить данные? (y/n): ")
        if response.lower() != 'y':
            return True

    print("📥 Загружаем датасет Instacart с Kaggle...")

    try:
        # Переходим в директорию data
        os.chdir(data_dir)

        # Загружаем датасет
        result = subprocess.run([
            "kaggle", "datasets", "download",
            "-d", "yasserh/instacart-online-grocery-basket-analysis-dataset"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Ошибка загрузки: {result.stderr}")
            return False

        # Распаковываем архив
        zip_file = "instacart-online-grocery-basket-analysis-dataset.zip"
        if Path(zip_file).exists():
            print("📦 Распаковываем архив...")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall('.')

            # Удаляем архив
            os.remove(zip_file)
            print("✅ Данные успешно загружены и распакованы!")

        # Возвращаемся обратно
        os.chdir("..")

        # Проверяем файлы
        csv_files = list(data_dir.glob("*.csv"))
        print(f"\n📊 Загружено файлов: {len(csv_files)}")
        for file in csv_files:
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"  - {file.name}: {size_mb:.1f} MB")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        os.chdir("..")  # Возвращаемся обратно в любом случае
        return False


def main():
    """Основная функция"""
    print("🛒 Smart Shop - Загрузка данных")
    print("=" * 40)

    # Проверяем учетные данные Kaggle
    if not check_kaggle_credentials():
        return 1

    # Устанавливаем kaggle если нужно
    install_kaggle()

    # Загружаем датасет
    if download_dataset():
        print("\n✅ Готово! Данные находятся в папке data/")
        print("Теперь можно запускать docker-compose up -d")
        return 0
    else:
        print("\n❌ Не удалось загрузить данные")
        return 1


if __name__ == "__main__":
    sys.exit(main())