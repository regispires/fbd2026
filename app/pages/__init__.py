"""
Esse módulo define as páginas com o nicegui.

Cada entidade possui uma página para visualização em lista contendo apenas os atributos
mais relevantes de vários registros, e uma visualização detalhada de um único registro
que descreve seus relacionamentos (e.g. detalhes de um usuário mostram atividades
ministradas por ele).

Importar os submódulos aqui é o que registra as rotas das páginas no app do
NiceGUI (os decoradores ``@pagina``/``@ui.page`` rodam no import de cada módulo).
"""

from . import activity as activity
from . import event as event
from . import event_registration as event_registration
from . import home as home
from . import login as login
from . import user as user
