"""
Exceções de domínio da aplicação.

Cada exceção documenta a regra de negócio ou a restrição do banco que a
justifica, de modo que os pontos de ``raise`` nos repositórios não precisem
repetir a explicação.
"""


class UserNotFound(Exception):
    """Usuário não encontrado pela chave pesquisada"""


class EventNotFound(Exception):
    """Evento não encontrado pela chave pesquisada"""


class ActivityNotFound(Exception):
    """Atividade não encontrada pela chave pesquisada"""


class DuplicateUserRegistration(Exception):
    """
    Violação de unicidade ao criar/atualizar usuário: o CPF ou o e-mail já
    pertence a outro usuário.
    """


class DuplicateEventRegistration(Exception):
    """
    Violação de unicidade relacionada a evento: o nome do evento já existe,
    ou o usuário já possui inscrição no evento.
    """


class DuplicateAttendance(Exception):
    """
    O usuário já possui presença registrada na atividade (violação da PK
    composta da ``presenca_atividade``).
    """


class AttendanceNotFound(Exception):
    """
    Não existe presença registrada do usuário na atividade informada.
    """


class InscriptionNotPending(Exception):
    """
    A operação exige que a inscrição ainda esteja ``pendente`` (ex.: editar
    valor/comprovante); inscrições confirmadas ou canceladas não podem ser
    alteradas.
    """


class CannotApproveOwnInscription(Exception):
    """
    Administradores não podem aprovar ou recusar suas próprias inscrições.
    """


class MissingInscriptionProof(Exception):
    """
    A inscrição exige o envio de um comprovante, mas nenhum arquivo foi
    anexado.
    """


class InscriptionProofNotPdf(Exception):
    """
    O comprovante anexado não é um arquivo PDF; apenas PDFs são aceitos.
    """


class EventWithoutActivity(Exception):
    """
    A operação criaria um evento sem atividades, o que viola a regra de
    negócio de que todo evento precisa de ao menos uma.
    """


class InvalidActivitySchedule(Exception):
    """
    O intervalo horário da atividade não está contido no intervalo do evento
    ao qual ela pertence.
    """


class ActivityWithoutLecturer(Exception):
    """
    A operação deixaria a atividade sem nenhum ministrante, o que viola a
    regra de negócio de que toda atividade precisa de ao menos um.
    """


class NoMoreVacancy(Exception):
    """
    O limite de vagas foi atingido (contando as inscrições não canceladas),
    então não é possível registrar mais participantes.
    """


class AgeBelowClassification(Exception):
    """
    A idade do usuário é inferior à classificação indicativa do evento;
    a inscrição no evento é negada.
    """


class EventInscriptionNotConfirmed(Exception):
    """
    O usuário ainda não tem a inscrição no evento **confirmada**, condição
    obrigatória para se inscrever em uma atividade.
    """


class WrongEventActivityInscription(Exception):
    """
    A inscrição em atividade foi solicitada para um evento diferente daquele
    ao qual a atividade pertence.
    """


class EventHasDependencies(Exception):
    """
    O evento não pode ser excluído porque ainda possui atividades ou
    inscrições vinculadas.
    """


class ActivityHasDependencies(Exception):
    """
    A atividade não pode ser excluída porque ainda possui presenças ou
    ministrantes vinculados.
    """


class UserHasDependencies(Exception):
    """
    O usuário não pode ser excluído porque ainda possui inscrições ou
    registros de ministração vinculados.
    """
