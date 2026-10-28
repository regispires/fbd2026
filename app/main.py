"""
Ponto de entrada da aplicação: importa as rotas de API e as páginas e
sob o ``__main__`` sobe o servidor NiceGUI.

O conteúdo da aplicação vive em ``app.pages`` (interfaces e dialogs) e em
``app.database.repository`` (operações de banco); ``app.api`` registra as
rotas de API (login, logout, comprovante) na importação.
"""

from nicegui import ui

from app import (
    api,  # noqa: F401  (rotas de API criadas na importação)
    pages,  # noqa: F401  (rotas das páginas criadas na importação)
)
from app.database.settings import settings

if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    _ = ui.run(port=8000, storage_secret=settings.STORAGE_SECRET.get_secret_value())
