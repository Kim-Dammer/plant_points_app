import os
from pathlib import Path
from kivy.utils import platform


def load_dotenv_manual():
    possible_paths = [
        os.path.join(os.getcwd(), 'config.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.env'),
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        os.environ.setdefault(
                            key.strip(),
                            value.strip().strip('"').strip("'")
                        )
            return


load_dotenv_manual()

DB_HOST     = os.getenv('DB_HOST')
DB_USER     = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME     = os.getenv('DB_NAME')
DB_PORT     = 3306


def resolve_sqlite_path():
    """
    Resolve the SQLite backup path at runtime.
    Must be called after the Kivy App is running so that
    App.get_running_app() is available on Android.
    """
    if platform == 'android':
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            return os.path.join(app.user_data_dir, "local_PlantBackup.db")
        # Fallback: writable cwd on Android
        return os.path.join(os.getcwd(), "local_PlantBackup.db")
    return os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parent, "local_PlantBackup.db")