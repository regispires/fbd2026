"""
Dashboard de estatísticas dos eventos (somente administradores).

- ``/event/dashboard``: visão global, somando todos os eventos, com uma
  tabela comparativa por evento;
- ``/event/dashboard/{evento_id}``: estatísticas de um único evento.

O seletor no topo alterna entre as duas visões. A página tem três seções:
visão geral (inscrições e ocupação), financeiro e demografia. Os números
chegam já agregados pelo banco (``app.database.repository.estatisticas``).

As rotas precisam ser registradas **antes** de ``/event/{evento_id}``
(``app.pages.__init__`` importa este módulo primeiro): caso contrário
``/event/dashboard`` seria tratado como o evento de id "dashboard".
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends
from nicegui import ui

from app.auth import exigir_administrador, obter_usuario
from app.database.repository import FUSO_EVENTOS
from app.database.repository.estatisticas import (
    FAIXAS_ETARIAS,
    STATUS_ATIVAS,
    STATUS_CONFIRMADAS,
    Demografia,
    ResumoEvento,
    listar_opcoes_eventos,
    obter_demografia,
    resumir_eventos,
    situacao_eventos,
    somar_resumos,
)
from app.database.repository.user import ESTADO_CIVIL_ROTULO, SEXO_ROTULO, Usuario
from app.pages.layout import (
    formatar_moeda,
    item_icone,
    nao_encontrado,
    pagina,
    voltar_ao_topo,
)

CAMINHO = "/event/dashboard"
# valor do seletor para a visão global (ids de evento começam em 1)
TODOS = 0

# paleta categórica (ordem fixa): a cor acompanha a categoria, não a posição
COR_SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]
COR_SEXO = dict(zip(SEXO_ROTULO, COR_SERIE, strict=True))  # M, F, O
# eixos e textos em cinza neutro, legível nos temas claro e escuro
COR_TEXTO = "#8a8984"
COR_GRADE = "rgba(138, 137, 132, 0.25)"


def _periodo(resumo: ResumoEvento) -> str:
    """Data do evento (ou intervalo, se durar vários dias), como em ``periodo``."""
    if resumo.data_hora_inicio is None or resumo.data_hora_fim is None:
        return ""
    inicio = resumo.data_hora_inicio.astimezone(FUSO_EVENTOS).date()
    fim = resumo.data_hora_fim.astimezone(FUSO_EVENTOS).date()
    if inicio == fim:
        return f"{inicio:%d/%m/%Y}"
    return f"{inicio:%d/%m/%Y} – {fim:%d/%m/%Y}"


def _percentual(valor: float) -> str:
    return f"{valor:.0%}"


def _decimal(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


# --- componentes ---------------------------------------------------------


def _titulo_secao(icone: str, titulo: str) -> None:
    with ui.row().classes("w-full items-center gap-2 q-mt-lg"):
        _ = ui.icon(icone, size="24px").classes("text-primary")
        _ = ui.label(titulo).classes("text-h6")


def _grade_cartoes() -> ui.grid:
    return ui.grid().classes("w-full gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3")


def _cartao(
    titulo: str,
    valor: str,
    detalhe: str | None = None,
    *,
    icone: str | None = None,
    cor_icone: str = "text-grey-7",
) -> ui.card:
    """Cartão de indicador: rótulo, número em destaque e uma linha de detalhe."""
    with ui.card().classes("w-full gap-1") as cartao:
        with ui.row().classes("items-center gap-1 text-grey-7"):
            if icone:
                _ = ui.icon(icone, size="18px").classes(cor_icone)
            _ = ui.label(titulo).classes("text-body2")
        _ = ui.label(valor).classes("text-h5 text-weight-medium")
        if detalhe:
            _ = ui.label(detalhe).classes("text-caption text-grey-7")
    return cartao


def _grafico(opcoes: dict[str, Any], altura: str = "280px") -> ui.echart:
    """
    Gráfico ECharts com o estilo comum do dashboard: fundo transparente,
    textos e grade neutros e tooltip ao passar o mouse.
    """
    base: dict[str, Any] = {
        "backgroundColor": "transparent",
        "textStyle": {"color": COR_TEXTO},
        "grid": {"left": 8, "right": 24, "top": 36, "bottom": 8, "containLabel": True},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
    }
    for eixo in ("xAxis", "yAxis"):
        if eixo in opcoes:
            opcoes[eixo] = {
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
                "axisTick": {"show": False},
                "axisLabel": {"color": COR_TEXTO},
                "splitLine": {"lineStyle": {"color": COR_GRADE}},
                **opcoes[eixo],
            }
    if "legend" in opcoes:
        opcoes["legend"] = {"top": 0, "textStyle": {"color": COR_TEXTO}, **opcoes["legend"]}
    return ui.echart({**base, **opcoes}).classes("w-full").style(f"height: {altura}")


def _barras_horizontais(
    titulo: str, rotulos: list[str], valores: list[float], formatar: Callable[[float], str]
) -> None:
    """Barras horizontais de uma única série, com o valor rotulado na ponta."""
    total = sum(valores)
    with ui.card().classes("w-full"):
        _ = ui.label(titulo).classes("text-subtitle1")
        _ = _grafico(
            {
                "grid": {"left": 8, "right": 128, "top": 8, "bottom": 8, "containLabel": True},
                "xAxis": {"type": "value", "show": False},
                "yAxis": {"type": "category", "data": rotulos, "inverse": True},
                "series": [
                    {
                        "type": "bar",
                        "name": titulo,
                        "barMaxWidth": 24,
                        "itemStyle": {"color": COR_SERIE[0], "borderRadius": [0, 4, 4, 0]},
                        "label": {"show": True, "position": "right", "color": COR_TEXTO},
                        # o texto do rótulo (valor e participação) vai pronto
                        # em cada item, sem precisar de formatter em JS
                        "data": [
                            {
                                "value": valor,
                                "label": {
                                    "formatter": f"{formatar(valor)} ("
                                    f"{_percentual(valor / total if total else 0)})"
                                },
                            }
                            for valor in valores
                        ],
                    }
                ],
            },
            altura=f"{max(len(rotulos), 2) * 44 + 16}px",
        )


# --- seções --------------------------------------------------------------


def _visao_geral(resumo: ResumoEvento, resumos: list[ResumoEvento]) -> None:
    _titulo_secao("insights", "Visão geral")
    agora = datetime.now(FUSO_EVENTOS)
    situacao = situacao_eventos(resumos, agora)

    with _grade_cartoes():
        _ = _cartao(
            "Inscrições",
            str(resumo.total),
            f"{resumo.ativas} ativas (confirmadas ou pendentes)",
            icone="how_to_reg",
        )
        _ = _cartao(
            "Confirmadas",
            str(resumo.confirmadas),
            _percentual(resumo.confirmadas / resumo.total if resumo.total else 0)
            + " das inscrições",
            icone="check_circle",
            cor_icone="text-positive",
        )
        with _cartao(
            "Pendentes de avaliação",
            str(resumo.pendentes),
            icone="hourglass_top",
            cor_icone="text-warning",
        ):
            if resumo.id is not None and resumo.pendentes:
                _ = ui.link("Avaliar inscrições", f"/event/{resumo.id}/registrations")
        _ = _cartao(
            "Canceladas",
            str(resumo.canceladas),
            f"Taxa de cancelamento: {_percentual(resumo.taxa_cancelamento)}",
            icone="cancel",
            cor_icone="text-negative",
        )
        with _cartao(
            "Ocupação",
            _percentual(resumo.ocupacao),
            f"{resumo.ativas} de {resumo.vagas} vagas",
            icone="event_seat",
        ):
            _ = ui.linear_progress(
                value=min(resumo.ocupacao, 1.0), show_value=False, size="8px"
            ).props("rounded color=primary")

        if resumo.id is None:
            _ = _cartao(
                "Eventos",
                str(resumo.eventos),
                f"{situacao.futuros} futuros · {situacao.em_andamento} em andamento"
                f" · {situacao.encerrados} encerrados",
                icone="event",
            )
        elif situacao.futuros:
            assert resumo.data_hora_inicio is not None
            dias = (resumo.data_hora_inicio.astimezone(FUSO_EVENTOS).date() - agora.date()).days
            _ = _cartao(
                "Situação",
                "Hoje" if dias == 0 else f"Em {dias} dia{'s' if dias != 1 else ''}",
                "até o início do evento",
                icone="schedule",
            )
        else:
            _ = _cartao(
                "Situação",
                "Em andamento" if situacao.em_andamento else "Encerrado",
                icone="schedule",
            )


def _financeiro(resumo: ResumoEvento) -> None:
    _titulo_secao("payments", "Financeiro")
    if resumo.id is not None and resumo.valor == 0:
        _ = ui.label("Evento gratuito: não há movimentação financeira.").classes(
            "text-grey-7"
        )
        return

    if resumo.sem_comprovante:
        with ui.card().classes("w-full bg-warning text-black"), item_icone("warning"):
            _ = ui.label(
                f"{resumo.sem_comprovante} inscrição(ões) ativa(s) em evento pago"
                " sem comprovante anexado."
            )

    atingido = (
        resumo.receita_confirmada / resumo.receita_potencial
        if resumo.receita_potencial
        else 0
    )
    with _grade_cartoes():
        _ = _cartao(
            "Receita confirmada",
            formatar_moeda(resumo.receita_confirmada),
            f"{_percentual(atingido)} da receita potencial",
            icone="paid",
            cor_icone="text-positive",
        )
        _ = _cartao(
            "A confirmar",
            formatar_moeda(resumo.receita_pendente),
            f"{resumo.pendentes} inscrição(ões) pendente(s)",
            icone="pending",
            cor_icone="text-warning",
        )
        _ = _cartao(
            "Receita potencial",
            formatar_moeda(resumo.receita_potencial),
            "todas as vagas vendidas com valor cheio",
            icone="savings",
        )
        _ = _cartao(
            "Perdida com cancelamentos",
            formatar_moeda(resumo.receita_cancelada),
            f"{resumo.canceladas} inscrição(ões) cancelada(s)",
            icone="money_off",
            cor_icone="text-negative",
        )
        _ = _cartao(
            "Ticket médio",
            formatar_moeda(resumo.ticket_medio),
            "por inscrição confirmada",
            icone="receipt_long",
        )
        _ = _cartao(
            "Desconto em meias-entradas",
            formatar_moeda(resumo.desconto_meia),
            f"{resumo.meias_confirmadas} meia(s) confirmada(s)",
            icone="percent",
        )

    # quantidade e receita têm escalas diferentes: dois gráficos, um eixo cada
    with ui.grid().classes("w-full gap-4 grid-cols-1 md:grid-cols-2"):
        _barras_horizontais(
            "Inscrições confirmadas por tipo",
            ["Inteira", "Meia-entrada"],
            [resumo.inteiras_confirmadas, resumo.meias_confirmadas],
            lambda v: str(int(v)),
        )
        _barras_horizontais(
            "Receita confirmada por tipo",
            ["Inteira", "Meia-entrada"],
            [resumo.receita_inteira, resumo.receita_meia],
            formatar_moeda,
        )


def _demografia(evento_id: int | None) -> None:
    _titulo_secao("groups", "Demografia")

    @ui.refreshable
    def conteudo(filtro: str) -> None:
        status = STATUS_CONFIRMADAS if filtro == "confirmadas" else STATUS_ATIVAS
        demografia = obter_demografia(evento_id, status)
        if demografia.total == 0:
            _ = ui.label("Nenhuma inscrição com esse filtro.").classes("text-grey-7")
            return
        _graficos_demografia(demografia, global_=evento_id is None)

    _ = ui.toggle(
        {"confirmadas": "Confirmadas", "ativas": "Confirmadas e pendentes"},
        value="confirmadas",
        on_change=lambda e: conteudo.refresh(e.value),
    ).props("no-caps")
    conteudo("confirmadas")


def _graficos_demografia(demografia: Demografia, *, global_: bool) -> None:
    with _grade_cartoes():
        _ = _cartao(
            "Participantes",
            str(demografia.total),
            # na visão global a mesma pessoa conta uma vez por evento
            "inscrições (uma por evento)" if global_ else None,
            icone="person",
        )
        _ = _cartao(
            "Idade média",
            f"{_decimal(demografia.idade_media or 0)} anos",
            "na data de início do evento",
            icone="cake",
        )
        _ = _cartao(
            "Faixa de idade",
            f"{demografia.idade_minima} a {demografia.idade_maxima} anos",
            "mais novo e mais velho",
            icone="straighten",
        )

    # pirâmide: faixa etária x sexo, empilhada (o total da barra é a faixa)
    with ui.card().classes("w-full"):
        _ = ui.label("Faixa etária por sexo").classes("text-subtitle1")
        series = [
            {
                "type": "bar",
                "name": rotulo,
                "stack": "sexo",
                "barMaxWidth": 48,
                "itemStyle": {"color": COR_SEXO[sexo]},
                "data": [
                    demografia.faixa_sexo.get((faixa, sexo), 0)
                    for faixa in range(len(FAIXAS_ETARIAS))
                ],
            }
            for sexo, rotulo in SEXO_ROTULO.items()
        ]
        # cantos arredondados só na ponta da pilha (última série)
        series[-1]["itemStyle"]["borderRadius"] = [4, 4, 0, 0]
        _ = _grafico(
            {
                "legend": {},
                "xAxis": {"type": "category", "data": FAIXAS_ETARIAS},
                "yAxis": {"type": "value", "minInterval": 1},
                "series": series,
            }
        )

    with ui.grid().classes("w-full gap-4 grid-cols-1 md:grid-cols-2"):
        por_sexo = demografia.por_sexo()
        _barras_horizontais(
            "Sexo",
            list(SEXO_ROTULO.values()),
            [por_sexo.get(codigo, 0) for codigo in SEXO_ROTULO],
            lambda v: str(int(v)),
        )
        _barras_horizontais(
            "Estado civil",
            list(ESTADO_CIVIL_ROTULO.values()),
            [demografia.estado_civil.get(codigo, 0) for codigo in ESTADO_CIVIL_ROTULO],
            lambda v: str(int(v)),
        )

    with ui.card().classes("w-full"):
        _ = ui.label("Meia-entrada por faixa etária").classes("text-subtitle1")
        _ = _grafico(
            {
                "legend": {},
                "xAxis": {"type": "category", "data": FAIXAS_ETARIAS},
                "yAxis": {"type": "value", "minInterval": 1},
                "series": [
                    {
                        "type": "bar",
                        "name": rotulo,
                        "stack": "tipo",
                        "barMaxWidth": 48,
                        "itemStyle": {
                            "color": cor,
                            **({"borderRadius": [4, 4, 0, 0]} if meia else {}),
                        },
                        "data": [
                            demografia.faixa_meia.get((faixa, meia), 0)
                            for faixa in range(len(FAIXAS_ETARIAS))
                        ],
                    }
                    for meia, rotulo, cor in (
                        (False, "Inteira", COR_SERIE[0]),
                        (True, "Meia-entrada", COR_SERIE[1]),
                    )
                ],
            }
        )


def _tabela_eventos(resumos: list[ResumoEvento]) -> None:
    """Comparativo por evento (visão global); a linha abre o dashboard do evento."""
    _titulo_secao("table_chart", "Por evento")
    colunas = [
        {"name": "nome", "label": "Evento", "field": "nome", "align": "left", "sortable": True},
        {"name": "periodo", "label": "Data", "field": "periodo", "align": "left"},
        {"name": "ativas", "label": "Inscrições ativas", "field": "ativas", "sortable": True},
        {"name": "pendentes", "label": "Pendentes", "field": "pendentes", "sortable": True},
        {"name": "ocupacao", "label": "Ocupação", "field": "ocupacao", "sortable": True,
         ":format": "v => Math.round(v * 100) + '%'"},
        {"name": "receita", "label": "Receita confirmada", "field": "receita",
         "sortable": True,
         ":format": "v => v.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})"},
    ]
    linhas = [
        {
            "id": r.id,
            "nome": r.nome,
            "periodo": _periodo(r),
            "ativas": r.ativas,
            "pendentes": r.pendentes,
            "ocupacao": r.ocupacao,
            "receita": r.receita_confirmada,
        }
        for r in resumos
    ]
    tabela = ui.table(columns=colunas, rows=linhas, row_key="id", pagination=10)
    _ = tabela.classes("w-full").props("flat bordered")
    tabela.add_slot(
        "body-cell-nome",
        """
        <q-td :props="props">
            <a :href="'/event/dashboard/' + props.row.id" class="text-primary">
                {{ props.value }}
            </a>
        </q-td>
        """,
    )


# --- página --------------------------------------------------------------


def _seletor(evento_id: int | None) -> None:
    opcoes = {TODOS: "Todos os eventos"} | {
        opcao.id: opcao.nome for opcao in listar_opcoes_eventos()
    }

    def trocar(e: Any) -> None:
        if e.value == TODOS:
            ui.navigate.to(CAMINHO)
        elif e.value is not None:
            ui.navigate.to(f"{CAMINHO}/{e.value}")

    _ = (
        ui.select(
            opcoes,
            value=evento_id if evento_id in opcoes else TODOS,
            label="Evento",
            with_input=True,
            on_change=trocar,
        )
        .props("outlined dense")
        .classes("w-full")
        .style("max-width: 420px")
    )


def _dashboard(evento_id: int | None) -> None:
    resumos = resumir_eventos(evento_id)
    if evento_id is not None and not resumos:
        nao_encontrado("event_busy", "Evento não encontrado", CAMINHO, "Ver todos os eventos")
        return
    resumo = resumos[0] if evento_id is not None else somar_resumos(resumos)

    with ui.column().classes("w-full gap-4").style("max-width: 1100px; margin: 0 auto"):
        with ui.row().classes("w-full items-center gap-4"):
            _ = ui.label("Estatísticas").classes("text-h5")
            _ = ui.space()
            _seletor(evento_id)
        if evento_id is not None:
            with ui.row().classes("w-full items-center gap-x-6 gap-y-1 text-grey-7"):
                with item_icone("calendar_today"):
                    _ = ui.label(_periodo(resumo))
                with item_icone("sell"):
                    _ = ui.label(
                        formatar_moeda(resumo.valor) if resumo.valor else "Gratuito"
                    )
                _ = ui.link("Página do evento", f"/event/{evento_id}")
                _ = ui.link("Inscrições", f"/event/{evento_id}/registrations")

        _visao_geral(resumo, resumos)
        _financeiro(resumo)
        _demografia(evento_id)
        if evento_id is None and resumos:
            _tabela_eventos(resumos)

    voltar_ao_topo()


@pagina(CAMINHO, dependencies=[Depends(exigir_administrador)])
def pagina_dashboard(usuario: Annotated[Usuario, Depends(obter_usuario)]):
    _dashboard(None)


@pagina(f"{CAMINHO}/{{evento_id}}", dependencies=[Depends(exigir_administrador)])
def pagina_dashboard_evento(
    evento_id: int, usuario: Annotated[Usuario, Depends(obter_usuario)]
):
    _dashboard(evento_id)
