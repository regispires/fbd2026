"""
Objetos de valor da aplicação: os dados coletados dos formulários, prontos
para as operações de escrita do repositório.

Ficam separados dos dataclasses de linha (``app.database.repository``)
porque representam a *entrada* da aplicação — e possuem conversores para
os kwargs das operações de escrita, evitando cópias campo a campo nos
dialogs das páginas.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.database.repository.event import Evento


@dataclass
class ValoresEvento:
    """
    Valores validados do formulário de evento.

    Serve tanto para preencher o formulário de edição (``de_evento``)
    quanto para criar (``criar_evento``) ou atualizar (``Evento.atualizar``)
    um evento no repositório, via ``parametros``.
    """

    nome: str
    descricao: str | None
    data_hora_inicio: datetime
    data_hora_fim: datetime
    classificacao_indicativa: int | None
    vagas: int
    valor: float
    latitude: float | None
    longitude: float | None
    banner: str | None
    banner_thumbnail: str | None

    @classmethod
    def de_evento(cls, evento: Evento) -> "ValoresEvento":
        """Extrai os valores editáveis de um evento (pré-preenchimento)."""
        return cls(
            nome=evento.nome,
            descricao=evento.descricao,
            data_hora_inicio=evento.data_hora_inicio,
            data_hora_fim=evento.data_hora_fim,
            classificacao_indicativa=evento.classificacao_indicativa,
            vagas=evento.vagas,
            valor=evento.valor,
            latitude=evento.latitude,
            longitude=evento.longitude,
            banner=evento.banner,
            banner_thumbnail=evento.banner_thumbnail,
        )

    def parametros(self) -> dict[str, Any]:
        """
        Kwargs comuns a ``criar_evento`` e ``Evento.atualizar``; as
        atividades (exigidas pela regra de negócio) são acrescentadas pelo
        chamador de ``criar_evento``.
        """
        return dict(
            nome=self.nome,
            descricao=self.descricao,
            data_hora_inicio=self.data_hora_inicio,
            data_hora_fim=self.data_hora_fim,
            classificacao_indicativa=self.classificacao_indicativa,
            vagas=self.vagas,
            valor=self.valor,
            latitude=self.latitude,
            longitude=self.longitude,
            banner=self.banner,
            banner_thumbnail=self.banner_thumbnail,
        )
