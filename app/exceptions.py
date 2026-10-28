"""
Exceções de domínio da aplicação.

Cada exceção documenta a regra de negócio ou a restrição do banco que a
justifica, de modo que os pontos de ``raise`` nos repositórios não precisem
repetir a explicação.
"""


class UsuarioNaoEncontrado(Exception):
    """Usuário não encontrado pela chave pesquisada"""


class EventoNaoEncontrado(Exception):
    """Evento não encontrado pela chave pesquisada"""


class AtividadeNaoEncontrada(Exception):
    """Atividade não encontrada pela chave pesquisada"""


class UsuarioRepetido(Exception):
    """
    Violação de unicidade ao criar/atualizar usuário: o CPF ou o e-mail já
    pertence a outro usuário.
    """


class EventoRepetido(Exception):
    """
    Violação de unicidade relacionada a evento: o nome do evento já existe,
    ou o usuário já possui inscrição no evento.
    """


class PresencaRepetida(Exception):
    """
    O usuário já possui presença registrada na atividade (violação da PK
    composta da ``presenca_atividade``).
    """


class PresencaNaoEncontrada(Exception):
    """
    Não existe presença registrada do usuário na atividade informada.
    """


class MinistranteRepetido(Exception):
    """
    O usuário já é ministrante da atividade (violação da PK composta da
    ``ministra_atividade``).
    """


class InscricaoNaoPendente(Exception):
    """
    A operação exige que a inscrição ainda esteja ``pendente`` (ex.: editar
    valor/comprovante); inscrições confirmadas ou canceladas não podem ser
    alteradas.
    """


class AprovacaoPropriaProibida(Exception):
    """
    Administradores não podem aprovar ou recusar suas próprias inscrições.
    """


class ComprovanteAusente(Exception):
    """
    A inscrição exige o envio de um comprovante, mas nenhum arquivo foi
    anexado.
    """


class ComprovanteNaoEhPdf(Exception):
    """
    O comprovante anexado não é um arquivo PDF; apenas PDFs são aceitos.
    """


class EventoSemAtividade(Exception):
    """
    A operação criaria um evento sem atividades, o que viola a regra de
    negócio de que todo evento precisa de ao menos uma.
    """


class HorarioAtividadeInvalido(Exception):
    """
    O intervalo horário da atividade não está contido no intervalo do evento
    ao qual ela pertence.
    """


class AtividadeSemMinistrante(Exception):
    """
    A operação deixaria a atividade sem nenhum ministrante, o que viola a
    regra de negócio de que toda atividade precisa de ao menos um.
    """


class SemVagas(Exception):
    """
    O limite de vagas foi atingido (contando as inscrições não canceladas),
    então não é possível registrar mais participantes.
    """


class IdadeAbaixoClassificacao(Exception):
    """
    A idade do usuário é inferior à classificação indicativa do evento;
    a inscrição no evento é negada.
    """


class InscricaoNaoConfirmada(Exception):
    """
    O usuário ainda não tem a inscrição no evento **confirmada**, condição
    obrigatória para se inscrever em uma atividade.
    """


class AtividadeDeOutroEvento(Exception):
    """
    A inscrição em atividade foi solicitada para um evento diferente daquele
    ao qual a atividade pertence.
    """


class EventoComInscricoes(Exception):
    """
    O evento não pode ser excluído porque possui ao menos uma inscrição
    registrada (de qualquer status, inclusive canceladas).
    """


class VagasAbaixoInscricoes(Exception):
    """
    A operação reduziria as vagas do evento para um número menor que o de
    inscrições ativas (não canceladas).
    """


class HorarioEventoInvalido(Exception):
    """
    O horário de início do evento precisa ser anterior ao horário de fim.
    """


class EventoComDependencias(Exception):
    """
    O evento não pode ser excluído porque ainda possui atividades ou
    inscrições vinculadas.
    """


class AtividadeComDependencias(Exception):
    """
    A atividade não pode ser excluída porque já possui presenças
    registradas (regra: atividades não podem ser removidas depois de
    receberem presença). Os vínculos de ministrantes são removidos junto.
    """


class UsuarioComDependencias(Exception):
    """
    O usuário não pode ser excluído porque ainda possui inscrições ou
    registros de ministração vinculados.
    """
