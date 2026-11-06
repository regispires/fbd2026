"""
Ponto de entrada da aplicação: cria o app FastAPI que serve a aplicação e
monta o NiceGUI (interfaces e rotas) nele.

O conteúdo da aplicação vive em ``app.pages`` (interfaces e dialogs) e em
``app.database.repository`` (operações de banco). As rotas JSON da API
(login, logout, comprovante) ficam em ``APIRouter``es próprios
(``app.auth`` e ``app.api``) e são incluídas neste app FastAPI.

O servidor é levantado pelo CLI do FastAPI, que importa o objeto ``app``
deste módulo (entrada configurada em ``[tool.fastapi]`` no pyproject.toml)::

    fastapi dev   # desenvolvimento, com recarga automática
    fastapi run   # produção
"""

from fastapi import FastAPI
from nicegui import app, ui

from app import pages  # noqa: F401  (rotas das páginas criadas na importação)
from app.api import router as api_router
from app.auth import router as auth_router
from app.database.settings import settings
from app.imagens import PASTA_UPLOAD, URL_UPLOAD

# imagens enviadas (banners dos eventos) ficam acessíveis publicamente em
# /imagens/...; a pasta precisa existir antes de registrar a rota
PASTA_UPLOAD.mkdir(parents=True, exist_ok=True)
app.add_static_files(URL_UPLOAD, PASTA_UPLOAD)

app = FastAPI(title="FBD 2026")

# Rotas para operações não realizadas diretamente pelo Nicegui
app.include_router(auth_router)
app.include_router(api_router)

# monta o NiceGUI (páginas e assets) em "/" do app FastAPI e habilita o
# armazenamento por usuário (app.storage.user) com o segredo das settings
ui.run_with(app, storage_secret=settings.STORAGE_SECRET.get_secret_value())
