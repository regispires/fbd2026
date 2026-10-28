"""
Seletor de ministrantes: context manager que renderiza um multiselect de
usuários e, para cada selecionado, os campos do vínculo (instituição
obrigatória, mini-bio e Lattes opcionais).

Reutilizado pelo dialog de criação de evento, pelo de criação de atividade
e pelo de adição de ministrantes; ``coletar`` devolve as entradas
validadas (``EntradaMinistrante``).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from nicegui import ui

from app.database.repository.activity import EntradaMinistrante
from app.database.repository.user import Usuario
from app.forms.validacao import campo_com_erro, obrigatorio, vazio_para_none


@dataclass
class CamposMinistrante:
    """Campos do vínculo de um ministrante selecionado no seletor."""

    usuario: Usuario
    instituicao: ui.input
    mini_bio: ui.textarea
    link_lattes: ui.input


@dataclass
class SeletorMinistrantes:
    """
    Componente reutilizável de seleção de ministrantes: um multiselect de
    usuários e, para cada selecionado, os campos do vínculo (instituição
    obrigatória, mini-bio e Lattes opcionais).
    """

    select: ui.select
    campos: dict[int, CamposMinistrante]

    def coletar(self) -> list[EntradaMinistrante] | None:
        """
        Validação de servidor do seletor (a reexecução das regras, exibida
        nos próprios campos): exige ao menos um usuário selecionado e a
        instituição de cada um. Devolve ``None`` quando inválido.
        """
        self.select.validate()
        valido = bool(self.select.value or [])
        for campos in self.campos.values():
            campos.instituicao.validate()
            if campo_com_erro(campos.instituicao):
                valido = False
        if not valido:
            return None
        return [
            EntradaMinistrante(
                usuario=campos.usuario,
                mini_bio=vazio_para_none(campos.mini_bio.value),
                instituicao=(campos.instituicao.value or "").strip(),
                link_lattes=vazio_para_none(campos.link_lattes.value),
            )
            for campos in self.campos.values()
        ]


@contextmanager
def seletor_ministrantes(usuarios: list[Usuario]) -> Iterator[SeletorMinistrantes]:
    """
    Renderiza o seletor de ministrantes no container atual e devolve a
    referência.

    ``usuarios`` são os candidatos (a chamadora já filtra quem não pode,
    ex.: os que ministram a atividade). A seleção de cada usuário revela
    um card com os campos do vínculo; ``coletar`` devolve as
    ``EntradaMinistrante`` validadas.
    """
    por_id = {u.id: u for u in usuarios}
    campos: dict[int, CamposMinistrante] = {}

    with ui.column().classes("w-full gap-2"):
        select = ui.select(
            {u.id: f"{u.nome} — {u.email}" for u in usuarios},
            multiple=True,
            label="Ministrantes *",
            validation={"Selecione pelo menos um ministrante.": lambda v: bool(v)},
        ).classes("w-full")
        cartoes = ui.column().classes("w-full gap-2")

        def reconstruir() -> None:
            campos.clear()
            cartoes.clear()
            with cartoes:
                for usuario_id in select.value or []:
                    usuario = por_id[usuario_id]
                    with (
                        ui.card().classes("w-full"),
                        ui.column().classes("w-full gap-2"),
                    ):
                        _ = ui.label(usuario.nome).classes("text-subtitle2")
                        instituicao = ui.input(
                            "Instituição *",
                            validation={"Informe a instituição.": obrigatorio},
                        ).classes("w-full")
                        mini_bio = ui.textarea("Mini-bio (opcional)").classes("w-full")
                        link_lattes = ui.input("Link do Lattes (opcional)").classes(
                            "w-full"
                        )
                        campos[usuario_id] = CamposMinistrante(
                            usuario=usuario,
                            instituicao=instituicao,
                            mini_bio=mini_bio,
                            link_lattes=link_lattes,
                        )

        select.on_value_change(lambda _: reconstruir())

        seletor = SeletorMinistrantes(select=select, campos=campos)
        yield seletor
