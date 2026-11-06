"""
Esse módulo define as páginas com o nicegui.

Cada entidade possui uma página para visualização em lista contendo apenas os atributos
mais relevantes de vários registros, e uma visualização detalhada de um único registro
que descreve seus relacionamentos (e.g. detalhes de um usuário mostram atividades
ministradas por ele).

Importar os submódulos aqui é o que registra as rotas das páginas no app do
NiceGUI (os decoradores ``@pagina``/``@ui.page`` rodam no import de cada módulo).
"""

# o dashboard primeiro: /event/dashboard precisa ser registrado antes de
# /event/{evento_id} (registrado ao importar event), senão "dashboard" seria
# lido como o id de um evento
from . import dashboard as dashboard
from . import activity as activity
from . import event as event
from . import event_registration as event_registration
from . import home as home
from . import login as login
from . import user as user
from . import user_profile as user_profile
from . import user_registration as user_registration
