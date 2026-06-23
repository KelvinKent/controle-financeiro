import sys
import os

sys.path.insert(0, r"C:\Users\kelvin.araujo\AppData\Roaming\Python\Python314\site-packages")

app_path = os.path.join(os.path.dirname(__file__), "app.py")
sys.argv = ["streamlit", "run", app_path, "--server.port", "8501", "--browser.serverAddress", "localhost"]

from streamlit.web import cli
cli.main()
