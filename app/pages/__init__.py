"""
Esse módulo define as páginas com o nicegui.

Cada entidade possui uma página para visualização em lista contendo apenas os atributos
mais relevantes de vários registros, e uma visualização detalhada de um único registro
que descreve seus relacionamentos (e.g. detalhes de um usuário mostram atividades
ministradas por ele).

Importar os submódulos aqui é o que registra as rotas das páginas no app do
NiceGUI (os decoradores ``@ui.page`` rodam no import de cada módulo).
"""

from . import event as event
from . import login as login
from . import registration as registration
from . import user as user
